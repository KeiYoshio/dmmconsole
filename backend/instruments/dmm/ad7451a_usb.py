"""ADVANTEST AD7451A / ADCMT 7451A – USB driver (ADC command set).

The 7451A supports three command languages:
  SCPI  → GPIB only
  ADC   → GPIB and USB   ← this driver
  R6552 → GPIB only

This module implements the ADC command set for USB control via raw pyusb +
USBTMC-framed packets (see backend/gpib/usbtmc_raw.py).

Key requirement: The instrument must be switched to remote mode via USB488
REN_CONTROL before it will accept ADC commands.  This is handled by
USBTMCResource._usb488_init().  In remote mode, auto-trigger (TRS0) does
not work; BUS trigger (TRS3 + INI + *TRG) must be used.

References
----------
    ADC Corporation 7451A/61A/61P Operation Manual, Section 6.7.3 (ADC commands)
    docs/7451A_USB_investigation_summary.md (full investigation log)
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
# MAV polling: exponential backoff parameters
# ---------------------------------------------------------------------------
_MAV_BACKOFF_INIT_MS = 20     # first wait step (ms)
_MAV_BACKOFF_MAX_MS  = 2_000  # longest single wait step → timeout if exceeded

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
        # _log.debug("USB write: %r", cmd)  # too noisy during streaming
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

    def _prime_after_change(self) -> None:
        """Send INI+TRIGGER cycles until the device responds, discarding results.

        After a function change (F-code) the 7451A ignores the very first
        INI+TRIGGER — STB stays 0x00 for ~4.5 s.  The *next* cycle works
        instantly (~300 ms).  This method absorbs the dead cycle so the
        streaming loop never sees the timeout.

        Uses a short fixed poll (50 ms × 10 = 500 ms max) per attempt
        instead of the full exponential backoff, to keep latency low.
        """
        for attempt in range(3):
            self._write("TRS3")
            self._write("INI")
            self._res.trigger()
            time.sleep(_USB_DELAY)
            # Short poll: 10 × 50 ms = 500 ms max per attempt
            got_mav = False
            for _ in range(10):
                time.sleep(0.05)
                stb = self._res.read_status_byte()
                if stb & 0x10:
                    got_mav = True
                    break
            if got_mav:
                # Drain the measurement data (read() sends REQUEST then reads BULK IN)
                try:
                    self._res.read()
                except Exception:
                    pass
                _log.info("_prime_after_change: OK on attempt %d", attempt + 1)
                return
            # No MAV — do NOT call read() here (it would block for 10 s).
            # Just retry; the device will eventually be ready.
            _log.info("_prime_after_change: attempt %d no MAV (500 ms), retrying", attempt + 1)
        _log.warning("_prime_after_change: all attempts failed")

    # ------------------------------------------------------------------
    # InstrumentBase interface
    # ------------------------------------------------------------------

    def get_capability(self) -> Capability:
        return _CAPABILITY

    def get_idn(self) -> str:
        return self._res.query("*IDN?")

    def reset(self) -> None:
        self._write("*RST")
        self._write("*CLS")
        self._function = "DCV"
        self._range    = "AUTO"
        self._nplc     = 10.0
        self._setup()   # *RST restores header ON and default trigger settings

    def close(self) -> None:
        # GO_TO_LOCAL is called by USBTMCResource.close()
        pass

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
        # F-code resets trigger source to TRS0 (auto-trigger), which does not
        # work in remote mode.  Re-assert BUS trigger mode explicitly.
        self._write("TRS3")
        # After a function change the device ignores the first INI+TRIGGER
        # cycle (STB stays 0x00 for ~4.5 s).  Perform one "priming"
        # measurement here and discard the result so that measure() always
        # sees a responsive device.
        self._prime_after_change()

    def set_range(self, range_str: str) -> None:
        code = _RANGE_ADC.get(self._function, {}).get(range_str)
        if code is None:
            _log.info("set_range(%r) → no ADC code for function %r, skipped", range_str, self._function)
            return   # CONT / DIOD have no range, or unknown label
        _log.info("set_range(%r) → %s", range_str, code)
        self._write(code)
        self._range = range_str
        self._prime_after_change()

    def set_nplc(self, nplc: float) -> None:
        cmd = f"ITP{nplc:g}"
        _log.info("set_nplc(%g) → %s", nplc, cmd)
        self._write(cmd)
        self._nplc = nplc
        self._prime_after_change()

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

    def _wait_mav(self) -> bool:
        """Poll READ_STATUS_BYTE until MAV (bit 4) is set.

        Uses exponential backoff: 20 ms → 40 ms → 80 ms → … → _MAV_BACKOFF_MAX_MS.
        Returns True when MAV is set, False if timed out.
        """
        if not hasattr(self._res, "read_status_byte"):
            time.sleep(1.0)   # fallback: fixed wait
            return True
        wait_ms = _MAV_BACKOFF_INIT_MS
        t0 = time.monotonic()
        polls = 0
        while True:
            stb = self._res.read_status_byte()
            polls += 1
            if stb & 0x10:    # MAV bit
                return True
            if wait_ms >= _MAV_BACKOFF_MAX_MS:
                # One final check after the maximum wait step
                time.sleep(wait_ms / 1000.0)
                stb = self._res.read_status_byte()
                elapsed_ms = (time.monotonic() - t0) * 1000
                _log.warning("_wait_mav: TIMEOUT after %d polls (%.0fms), final STB=0x%02X",
                             polls + 1, elapsed_ms, stb)
                return bool(stb & 0x10)
            time.sleep(wait_ms / 1000.0)
            wait_ms = min(wait_ms * 2, _MAV_BACKOFF_MAX_MS)

    def measure(self) -> MeasurementResult:
        """Arm trigger, fire USB488 TRIGGER, wait for MAV, read."""
        self._write("TRS3")      # defensive: re-assert BUS trigger every measurement
        self._write("INI")       # arm: IDLE → INITIATE state
        # Use USB488 TRIGGER (MsgID=0x80) — the same method as ausb_trigger().
        # Text "*TRG\n" via DEV_DEP_MSG_OUT does NOT reliably fire TRS3 BUS trigger.
        self._res.trigger()
        time.sleep(_USB_DELAY)
        if not self._wait_mav():
            raise RuntimeError("AD7451A_USB: MAV not set after 10 s — measurement timeout")
        raw   = self._res.read().strip()
        try:
            value = float(raw)
        except ValueError:
            _log.error("AD7451A_USB: cannot parse %r", raw)
            value = math.nan
        if abs(value) > 9.0e36:  # 9.99999E+37 = overload
            value = math.nan
        return MeasurementResult(
            value     = value,
            unit      = _FUNC_UNITS.get(self._function, ""),
            function  = self._function,
            range     = self._range,
            timestamp = time.time(),
        )
