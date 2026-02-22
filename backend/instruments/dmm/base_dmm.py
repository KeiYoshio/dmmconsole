"""
DMM base class – common SCPI logic shared by HP 34401A, Keithley 2000/2010.

Subclasses override:
  - CAPABILITY      : static Capability descriptor
  - FUNC_CONF       : function-id → SCPI sub-function string
  - FUNC_UNITS      : function-id → unit string
  - RANGE_SCPI      : range label → SCPI value string
  - _set_nplc()     : if NPLC command syntax differs
"""

from __future__ import annotations

import time
from abc import abstractmethod

from ..base import InstrumentBase, Capability, MeasurementResult


class DMMBase(InstrumentBase):
    """Base class for SCPI-speaking digital multimeters."""

    # ------------------------------------------------------------------
    # Subclass must define these
    # ------------------------------------------------------------------
    FUNC_CONF:  dict[str, str] = {}   # "DCV" → "VOLT:DC"
    FUNC_UNITS: dict[str, str] = {}   # "DCV" → "V"
    RANGE_SCPI: dict[str, str] = {}   # "100mV" → "0.1"

    # ------------------------------------------------------------------
    # Class-level capability (used by registry without instantiation)
    # ------------------------------------------------------------------
    _CAPABILITY: Capability | None = None

    @classmethod
    def static_capability(cls) -> Capability:
        """Return the capability descriptor without needing an instance."""
        return cls._CAPABILITY

    # ------------------------------------------------------------------
    # Instance
    # ------------------------------------------------------------------

    def __init__(self, resource) -> None:
        self._res = resource
        self._function: str = list(self.FUNC_CONF)[0]  # first function as default
        self._range:    str = "AUTO"
        self._nplc:     float = 10.0

    # ------------------------------------------------------------------
    # InstrumentBase interface
    # ------------------------------------------------------------------

    def get_capability(self) -> Capability:
        return self._CAPABILITY

    def get_idn(self) -> str:
        return self._res.query("*IDN?").strip()

    def reset(self) -> None:
        self._res.write("*RST")
        self._res.write("*CLS")
        self._function = list(self.FUNC_CONF)[0]
        self._range = "AUTO"
        self._nplc  = 10.0

    def close(self) -> None:
        pass  # VISA resource closed by GPIBManager

    # ------------------------------------------------------------------
    # DMM-specific control
    # ------------------------------------------------------------------

    def set_function(self, func_id: str) -> None:
        if func_id not in self.FUNC_CONF:
            raise ValueError(f"Function {func_id!r} not supported by {self.__class__.__name__}")
        scpi = self.FUNC_CONF[func_id]
        self._res.write(f"CONF:{scpi}")
        self._function = func_id

    def set_range(self, range_str: str) -> None:
        scpi = self.FUNC_CONF.get(self._function, "VOLT:DC")
        val  = self.RANGE_SCPI.get(range_str, "DEF")
        if range_str == "AUTO":
            self._res.write(f"SENS:{scpi}:RANG:AUTO 1")
        else:
            self._res.write(f"SENS:{scpi}:RANG {val}")
        self._range = range_str

    def set_nplc(self, nplc: float) -> None:
        scpi = self.FUNC_CONF.get(self._function, "VOLT:DC")
        self._res.write(f"SENS:{scpi}:NPLC {nplc}")
        self._nplc = nplc

    def apply_settings(self, settings: dict) -> None:
        """Apply a dict of {setting_id: value} atomically."""
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
        raw = self._res.query("READ?").strip()
        value = float(raw)
        return MeasurementResult(
            value=value,
            unit=self.FUNC_UNITS.get(self._function, ""),
            function=self._function,
            range=self._range,
            timestamp=time.time(),
        )
