"""ADVANTEST AD7451A / ADCMT 7451A – USB driver (ADC command set).

.. warning::
    **WORK IN PROGRESS – NOT FUNCTIONAL**

    This driver is excluded from the UI (registry.py) until the underlying
    USB communication issue is resolved.

    Problem summary (as of 2026-02):
    ---------------------------------
    The 7451A exposes a single Vendor-class (0xFF) USB interface with three
    endpoints: EP 0x02 BULK OUT (commands), EP 0x81 BULK IN (responses),
    EP 0x83 INTR IN (status/error notifications).

    The official Windows driver (ausb.dll) was reverse-engineered to determine
    the correct USBTMC-like packet format:
      - Vendor IN control transfer (bmRequestType=0xC1, bRequest=0xF5) during
        device open → returns capability byte 0x01.
      - DEV_DEP_MSG_OUT: 12-byte header + LF-terminated command + 4-byte padding.
        TransferSize = (len(cmd_with_LF) + 3) & ~3   (padded to 4-byte boundary,
        derived from func@0x2c9f0 disassembly).

    Despite the CT init and correct packet format, write commands (F1/F2/*RST etc.)
    are silently ignored by the instrument – reads always return the power-on DCV
    measurement.  Root cause is unknown; candidates include:
      - Additional ausb_open() initialisation beyond the CT (not yet fully analysed)
      - Vendor-specific bulk OUT prologue required before commands
      - macOS/libusb vs. Windows/WinUSB protocol difference

    Investigation artefacts are kept in dmmconsole/ root:
      analyze_ausb_start.py, analyze_ctrl*.py, test_*.py, check_interfaces.py

The 7451A supports three command languages:
  SCPI  → GPIB only
  ADC   → GPIB and USB   ← this driver
  R6552 → GPIB only

This module implements the ADC command set for USB control via raw pyusb +
USBTMC-framed packets (see backend/gpib/usbtmc_raw.py).

References
----------
    ADC Corporation 7451A/61A/61P Operation Manual, Section 6.7.3 (ADC commands)
    VBA sample: docs/extracted/sample/vba/dmm/7451A_61A_USB_sampleprogram_64.xlsm
    DLL:        docs/extracted/bin/x64/ausb.dll  (reverse-engineered)
"""

from __future__ import annotations

import logging
import math
import time

from ..base import Capability, InstrumentBase, MeasurementResult

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# USB inter-command delay required by the instrument (Section 6.7.3 CAUTION)
# ---------------------------------------------------------------------------
_USB_DELAY = 0.02   # 20 ms

# ---------------------------------------------------------------------------
# ADC command function codes (Section 6.7.3, "Measurement → Function")
#
# The ADC command terminator over USB is LF (0x0A), exactly as over GPIB.
# ausb.dll appends LF at RVA 0x2cae8 before every WinUsb_WritePipe call.
# usbtmc_raw.py now mirrors this behaviour, so plain command strings are used.
# ---------------------------------------------------------------------------
_FUNC_ADC: dict[str, str] = {
    "DCV":   "F1",
    "ACV":   "F2",
    "OHM2":  "F3",
    "OHM4":  "F4",
    "DCI":   "F5",
    "ACI":   "F6",
    "ACADV": "F7",
    "ACADI": "F8",
    "DIOD":  "F13",
    "LP2W":  "F20",
    "LP4W":  "F21",
    "CONT":  "F22",
    "FREQ":  "F50",
}

_FUNC_UNITS: dict[str, str] = {
    "DCV": "V",  "ACV": "V",
    "DCI": "A",  "ACI": "A",
    "OHM2": "Ω", "OHM4": "Ω",
    "FREQ": "Hz",
    "CONT": "Ω", "DIOD": "V",
    "ACADV": "V", "ACADI": "A",
    "LP2W": "Ω", "LP4W": "Ω",
}

# ---------------------------------------------------------------------------
# Range code table: function → { range_label → ADC R-code }
#
# 7451A uses ×3 range series (300 mV / 3 V / 30 V …).
# The same R-code means different physical ranges depending on function,
# so we define per-function dicts instead of one flat dict.
# (Section 6.7.3, "Measurement condition → Measurement range", 7451A column)
# ---------------------------------------------------------------------------
_RANGE_ADC: dict[str, dict[str, str]] = {
    "DCV": {
        "AUTO": "R0", "300mV": "R3", "3V": "R4",
        "30V":  "R5", "300V":  "R6", "1000V": "R7",
    },
    "ACV": {
        "AUTO": "R0", "300mV": "R3", "3V": "R4",
        "30V":  "R5", "300V":  "R6", "700V":  "R7",
    },
    "ACADV": {
        "AUTO": "R0", "300mV": "R3", "3V": "R4",
        "30V":  "R5", "300V":  "R6", "700V":  "R7",
    },
    "DCI": {
        "AUTO": "R0", "3mA": "R4", "30mA": "R5",
        "300mA": "R6", "3A": "R7",
    },
    "ACI": {
        "AUTO": "R0", "3mA": "R4", "30mA": "R5",
        "300mA": "R6", "3A": "R7",
    },
    "ACADI": {
        "AUTO": "R0", "3mA": "R4", "30mA": "R5",
        "300mA": "R6", "3A": "R7",
    },
    "OHM2": {
        "AUTO": "R0", "30Ω": "R2",  "300Ω": "R3",  "3kΩ": "R4",
        "30kΩ": "R5", "300kΩ": "R6", "3MΩ": "R7",
        "30MΩ": "R8", "300MΩ": "R9",
    },
    "OHM4": {
        "AUTO": "R0", "30Ω": "R2",  "300Ω": "R3",  "3kΩ": "R4",
        "30kΩ": "R5", "300kΩ": "R6", "3MΩ": "R7",
        "30MΩ": "R8", "300MΩ": "R9",
    },
    "LP2W": {
        "AUTO": "R0", "300Ω": "R3", "3kΩ": "R4",
        "30kΩ": "R5", "300kΩ": "R6", "3MΩ": "R7", "30MΩ": "R8",
    },
    "LP4W": {
        "AUTO": "R0", "300Ω": "R3", "3kΩ": "R4",
        "30kΩ": "R5", "300kΩ": "R6", "3MΩ": "R7", "30MΩ": "R8",
    },
    "FREQ": {"AUTO": "R0"},
    "CONT": {},   # no range selection
    "DIOD": {},   # no range selection
}

# ---------------------------------------------------------------------------
# Capability descriptor (identical functions/ranges to the GPIB driver)
# ---------------------------------------------------------------------------
_CAPABILITY = Capability(
    model="AD7451A (USB)",
    manufacturer="ADVANTEST / ADCMT",
    instrument_type="dmm",
    functions=[
        {"id": "DCV",   "label": "DC V",    "icon": "mdi-lightning-bolt",           "unit": "V"},
        {"id": "ACV",   "label": "AC V",    "icon": "mdi-sine-wave",                "unit": "V"},
        {"id": "DCI",   "label": "DC I",    "icon": "mdi-current-dc",               "unit": "A"},
        {"id": "ACI",   "label": "AC I",    "icon": "mdi-current-ac",               "unit": "A"},
        {"id": "OHM2",  "label": "Ω 2W",   "icon": "mdi-omega",                    "unit": "Ω"},
        {"id": "OHM4",  "label": "Ω 4W",   "icon": "mdi-omega",                    "unit": "Ω"},
        {"id": "FREQ",  "label": "Freq",    "icon": "mdi-chart-bell-curve",         "unit": "Hz"},
        {"id": "CONT",  "label": "Cont",    "icon": "mdi-electric-switch",          "unit": "Ω"},
        {"id": "DIOD",  "label": "Diode",   "icon": "mdi-arrow-right-bold-outline", "unit": "V"},
        {"id": "ACADV", "label": "ACV+DC",  "icon": "mdi-sine-wave",                "unit": "V"},
        {"id": "ACADI", "label": "ACI+DC",  "icon": "mdi-current-ac",               "unit": "A"},
        {"id": "LP2W",  "label": "LP Ω 2W", "icon": "mdi-omega",                   "unit": "Ω"},
        {"id": "LP4W",  "label": "LP Ω 4W", "icon": "mdi-omega",                   "unit": "Ω"},
    ],
    ranges={
        "DCV":   ["AUTO", "300mV", "3V", "30V", "300V", "1000V"],
        "ACV":   ["AUTO", "300mV", "3V", "30V", "300V", "700V"],
        "DCI":   ["AUTO", "3mA", "30mA", "300mA", "3A"],
        "ACI":   ["AUTO", "3mA", "30mA", "300mA", "3A"],
        "OHM2":  ["AUTO", "30Ω", "300Ω", "3kΩ", "30kΩ", "300kΩ", "3MΩ", "30MΩ", "300MΩ"],
        "OHM4":  ["AUTO", "30Ω", "300Ω", "3kΩ", "30kΩ", "300kΩ", "3MΩ", "30MΩ", "300MΩ"],
        "FREQ":  ["AUTO"],
        "CONT":  [],
        "DIOD":  [],
        "ACADV": ["AUTO", "300mV", "3V", "30V", "300V", "700V"],
        "ACADI": ["AUTO", "3mA", "30mA", "300mA", "3A"],
        "LP2W":  ["AUTO", "300Ω", "3kΩ", "30kΩ", "300kΩ", "3MΩ", "30MΩ"],
        "LP4W":  ["AUTO", "300Ω", "3kΩ", "30kΩ", "300kΩ", "3MΩ", "30MΩ"],
    },
    settings=[
        {
            "id": "nplc", "label": "NPLC", "type": "select",
            "options": [0.02, 0.2, 1, 10, 100], "default": 10,
            "applicable_to": ["DCV", "ACV", "DCI", "ACI", "OHM2", "OHM4",
                               "ACADV", "ACADI", "LP2W", "LP4W"],
        },
    ],
)


# ---------------------------------------------------------------------------
# Driver class
# ---------------------------------------------------------------------------

class AD7451A_USB(InstrumentBase):
    """AD7451A controlled over USB using ADC proprietary commands."""

    @classmethod
    def static_capability(cls) -> Capability:
        return _CAPABILITY

    def __init__(self, resource) -> None:
        self._res      = resource
        self._function = "DCV"
        self._range    = "AUTO"
        self._nplc     = 10.0
        self._setup()
        # Register USB reconnect callback if resource supports it
        if hasattr(resource, "set_reinit_callback"):
            resource.set_reinit_callback(self._reinit_after_usb_reconnect)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write(self, cmd: str) -> None:
        """Send a write-only ADC command with the mandatory USB delay."""
        _log.debug("USB write: %r", cmd)
        self._res.write(cmd)
        time.sleep(_USB_DELAY)

    def _setup(self) -> None:
        """Configure instrument for USB remote operation."""
        _log.info("AD7451A_USB: _setup() → H0 TRS3 INIC0")
        self._write("H0")     # response header OFF → plain numeric output
        self._write("TRS3")   # trigger source: BUS (*TRG command)
        self._write("INIC0")  # continuous measurement: OFF (single-shot)

    def _reinit_after_usb_reconnect(self) -> None:
        """Called by USBTMCResource after a USB recovery reset.

        Re-sends the full setup sequence and restores function/range/NPLC
        so the instrument returns to the same state it was in before the
        disconnect.
        """
        _log.warning("AD7451A_USB: USB reconnected – re-initialising device")
        self._setup()
        self.set_function(self._function)
        self.set_range(self._range)
        self.set_nplc(self._nplc)

    # ------------------------------------------------------------------
    # InstrumentBase interface
    # ------------------------------------------------------------------

    def get_capability(self) -> Capability:
        return _CAPABILITY

    def get_idn(self) -> str:
        # *IDN? is not supported in ADC command mode; return static string.
        return "ADVANTEST AD7451A (USB/ADC mode)"

    def reset(self) -> None:
        self._write("*RST")
        self._write("*CLS")
        self._function = "DCV"
        self._range    = "AUTO"
        self._nplc     = 10.0
        self._setup()   # *RST restores header ON and default trigger settings

    def close(self) -> None:
        pass   # resource lifetime managed by GPIBManager

    # ------------------------------------------------------------------
    # DMM control
    # ------------------------------------------------------------------

    def set_function(self, func_id: str) -> None:
        if func_id not in _FUNC_ADC:
            raise ValueError(f"Function {func_id!r} not supported by AD7451A_USB.")
        adc_cmd = _FUNC_ADC[func_id]
        _log.info("set_function(%r) → %s", func_id, adc_cmd)
        self._write(adc_cmd)
        self._function = func_id

    def set_range(self, range_str: str) -> None:
        code = _RANGE_ADC.get(self._function, {}).get(range_str)
        if code is None:
            _log.info("set_range(%r) → no ADC code for function %r, skipped", range_str, self._function)
            return   # CONT / DIOD have no range, or unknown label
        _log.info("set_range(%r) → %s", range_str, code)
        self._write(code)
        self._range = range_str

    def set_nplc(self, nplc: float) -> None:
        cmd = f"ITP{nplc:g}"
        _log.info("set_nplc(%g) → %s", nplc, cmd)
        self._write(cmd)
        self._nplc = nplc

    def apply_settings(self, settings: dict) -> None:
        if "function" in settings:
            self.set_function(settings["function"])
        if "range" in settings:
            self.set_range(settings["range"])
        if "nplc" in settings:
            self.set_nplc(float(settings["nplc"]))

    # ------------------------------------------------------------------
    # Measurement
    # ------------------------------------------------------------------

    def measure(self) -> MeasurementResult:
        """Arm trigger, fire *TRG, and read one measurement result."""
        self._write("INI")       # arm: IDLE → INITIATE state
        self._write("*TRG")      # trigger one measurement (TRS3 = BUS mode)
        raw   = self._res.read().strip()   # blocks until instrument responds
        value = float(raw)
        if abs(value) > 9.0e36:  # 9.99999E+37 = overload
            value = math.nan
        return MeasurementResult(
            value     = value,
            unit      = _FUNC_UNITS.get(self._function, ""),
            function  = self._function,
            range     = self._range,
            timestamp = time.time(),
        )
