"""ADVANTEST AD7451A / ADCMT 7451A Digital Multimeter driver.

Notes:
- SCPI mode must be selected on the instrument:
    MENU → 8 I/F → LANG → SCPI
- Ranges follow ×3 series (300mV / 3V / 30V …) unlike HP 34401A (×10 series).
- Response header must be disabled (H0) to get plain numeric output from READ?.
- Overload response: 9.99999E+37 → converted to NaN.
"""

from __future__ import annotations

import time
import math

from ..base import Capability, MeasurementResult
from .base_dmm import DMMBase


class AD7451A(DMMBase):

    FUNC_CONF = {
        "DCV":   "VOLT:DC",
        "ACV":   "VOLT:AC",
        "DCI":   "CURR:DC",
        "ACI":   "CURR:AC",
        "OHM2":  "RES",
        "OHM4":  "FRES",
        "FREQ":  "FREQ",
        "CONT":  "CONT",
        "DIOD":  "DIOD",
        "ACADV": "VOLT:ACDC",
        "ACADI": "CURR:ACDC",
        "LP2W":  "RES:LPOW",
        "LP4W":  "FRES:LPOW",
    }

    FUNC_UNITS = {
        "DCV":   "V",  "ACV":   "V",
        "DCI":   "A",  "ACI":   "A",
        "OHM2":  "Ω",  "OHM4":  "Ω",
        "FREQ":  "Hz",
        "CONT":  "Ω",  "DIOD":  "V",
        "ACADV": "V",  "ACADI": "A",
        "LP2W":  "Ω",  "LP4W":  "Ω",
    }

    # Range label → SCPI value (SI units)
    RANGE_SCPI = {
        # Voltage
        "300mV": "0.3",  "3V":    "3",    "30V":  "30",
        "300V":  "300",  "700V":  "700",  "1000V":"1000",
        # Resistance
        "30Ω":   "30",   "300Ω":  "300",  "3kΩ":  "3E3",
        "30kΩ":  "3E4",  "300kΩ": "3E5",  "3MΩ":  "3E6",
        "30MΩ":  "3E7",  "300MΩ": "3E8",
        # Current
        "3mA":   "0.003","30mA":  "0.03", "300mA":"0.3",
        "3A":    "3",
    }

    _CAPABILITY = Capability(
        model="AD7451A",
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
            {"id": "LP2W",  "label": "LP Ω 2W","icon": "mdi-omega",                    "unit": "Ω"},
            {"id": "LP4W",  "label": "LP Ω 4W","icon": "mdi-omega",                    "unit": "Ω"},
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

    def __init__(self, resource) -> None:
        super().__init__(resource)
        self._res.write("H0")   # disable response header → plain numeric output

    def reset(self) -> None:
        super().reset()
        self._res.write("H0")   # *RST restores H1 (header ON), so disable again

    def measure(self) -> MeasurementResult:
        raw = self._res.query("READ?").strip()
        value = float(raw)
        # 9.99999E+37 = overload indicator
        if abs(value) > 9.0e36:
            value = math.nan
        return MeasurementResult(
            value=value,
            unit=self.FUNC_UNITS.get(self._function, ""),
            function=self._function,
            range=self._range,
            timestamp=time.time(),
        )
