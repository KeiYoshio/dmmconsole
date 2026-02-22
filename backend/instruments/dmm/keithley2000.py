"""Keithley 2000 Digital Multimeter driver."""

from ..base import Capability
from .base_dmm import DMMBase


class Keithley2000(DMMBase):

    FUNC_CONF = {
        "DCV":  "VOLT:DC",
        "ACV":  "VOLT:AC",
        "DCI":  "CURR:DC",
        "ACI":  "CURR:AC",
        "OHM2": "RES",
        "OHM4": "FRES",
        "FREQ": "FREQ",
        "PER":  "PER",
        "CONT": "CONT",
        "DIOD": "DIOD",
        "TEMP": "TEMP",
    }

    FUNC_UNITS = {
        "DCV": "V",  "ACV": "V",
        "DCI": "A",  "ACI": "A",
        "OHM2": "Ω", "OHM4": "Ω",
        "FREQ": "Hz", "PER": "s",
        "CONT": "Ω", "DIOD": "V",
        "TEMP": "°C",
    }

    RANGE_SCPI = {
        "100mV": "0.1",  "1V": "1",    "10V": "10",
        "100V":  "100",  "1000V": "1E3",
        "10mA":  "0.01", "100mA": "0.1","1A": "1",   "3A": "3",
        "100Ω":  "100",  "1kΩ": "1E3", "10kΩ": "1E4",
        "100kΩ": "1E5",  "1MΩ": "1E6", "10MΩ": "1E7","100MΩ": "1E8",
        "1GΩ":   "1E9",
    }

    _CAPABILITY = Capability(
        model="Keithley 2000",
        manufacturer="Keithley",
        instrument_type="dmm",
        functions=[
            {"id": "DCV",  "label": "DC V",   "icon": "mdi-lightning-bolt",          "unit": "V"},
            {"id": "ACV",  "label": "AC V",   "icon": "mdi-sine-wave",               "unit": "V"},
            {"id": "DCI",  "label": "DC I",   "icon": "mdi-current-dc",              "unit": "A"},
            {"id": "ACI",  "label": "AC I",   "icon": "mdi-current-ac",              "unit": "A"},
            {"id": "OHM2", "label": "Ω 2W",  "icon": "mdi-omega",                   "unit": "Ω"},
            {"id": "OHM4", "label": "Ω 4W",  "icon": "mdi-omega",                   "unit": "Ω"},
            {"id": "FREQ", "label": "Freq",   "icon": "mdi-chart-bell-curve",        "unit": "Hz"},
            {"id": "PER",  "label": "Period", "icon": "mdi-clock-outline",           "unit": "s"},
            {"id": "CONT", "label": "Cont",   "icon": "mdi-electric-switch",         "unit": "Ω"},
            {"id": "DIOD", "label": "Diode",  "icon": "mdi-arrow-right-bold-outline","unit": "V"},
            {"id": "TEMP", "label": "Temp",   "icon": "mdi-thermometer",             "unit": "°C"},
        ],
        ranges={
            "DCV":  ["AUTO", "100mV", "1V", "10V", "100V", "1000V"],
            "ACV":  ["AUTO", "100mV", "1V", "10V", "100V"],
            "DCI":  ["AUTO", "10mA", "100mA", "1A", "3A"],
            "ACI":  ["AUTO", "1A", "3A"],
            "OHM2": ["AUTO", "100Ω", "1kΩ", "10kΩ", "100kΩ", "1MΩ", "10MΩ", "100MΩ", "1GΩ"],
            "OHM4": ["AUTO", "100Ω", "1kΩ", "10kΩ", "100kΩ", "1MΩ", "10MΩ", "100MΩ", "1GΩ"],
            "FREQ": ["AUTO"], "PER": ["AUTO"],
            "CONT": [],       "DIOD": [],
            "TEMP": [],
        },
        settings=[
            {
                "id": "nplc", "label": "NPLC", "type": "select",
                "options": [0.01, 0.1, 1, 10], "default": 10,
                "applicable_to": ["DCV", "ACV", "DCI", "ACI", "OHM2", "OHM4"],
            },
        ],
    )
