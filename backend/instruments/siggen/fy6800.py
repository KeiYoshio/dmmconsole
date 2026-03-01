"""FY6800 DDS Signal Generator / Counter driver.

Communicates over serial (115200 8N1) using FY6800's proprietary
text-based protocol.  Each command is LF-terminated ASCII.

Channel addressing:
  CH1: WM* / RM* commands  (M = Main)
  CH2: WF* / RF* commands  (F = sub-Frequency)
  Counter: RC* / WC* commands

Frequency encoding (asymmetric):
  Write: 14-digit integer in micro-hertz (uHz).
    1 kHz = "00001000000000"
  Read: floating-point Hz string.
    1 kHz = "00001000.000000"

Amplitude encoding (asymmetric):
  Write (WMA/WFA): floating-point Vpp string.
    1.0 Vpp = "1.0"  (integer values clip to 20 Vpp max!)
  Read (RMA/RFA): integer × 10000.
    1.0 Vpp = "10000"
"""

from __future__ import annotations

import logging
import time

from ..base import Capability, InstrumentBase, MeasurementResult

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Waveform table: index -> (label, icon)
# ---------------------------------------------------------------------------
_WAVEFORMS: list[dict] = [
    {"id": "0",  "label": "Sine",        "icon": "mdi-sine-wave"},
    {"id": "1",  "label": "Square",      "icon": "mdi-square-wave"},
    {"id": "2",  "label": "Rectangle",   "icon": "mdi-square-wave"},
    {"id": "3",  "label": "Trapezoid",   "icon": "mdi-shape"},
    {"id": "4",  "label": "CMOS",        "icon": "mdi-chip"},
    {"id": "5",  "label": "Adj Pulse",   "icon": "mdi-pulse"},
    {"id": "6",  "label": "DC",          "icon": "mdi-minus"},
    {"id": "7",  "label": "Triangle",    "icon": "mdi-triangle-wave"},
    {"id": "8",  "label": "Ramp",        "icon": "mdi-chart-line"},
    {"id": "9",  "label": "Staircase+",  "icon": "mdi-stairs-up"},
    {"id": "10", "label": "Staircase-",  "icon": "mdi-stairs-down"},
    {"id": "11", "label": "Half Wave",   "icon": "mdi-wave"},
    {"id": "12", "label": "Full Wave",   "icon": "mdi-wave"},
    {"id": "13", "label": "Pos Stair",   "icon": "mdi-stairs-up"},
    {"id": "14", "label": "Neg Stair",   "icon": "mdi-stairs-down"},
    {"id": "15", "label": "Noise",       "icon": "mdi-blur"},
    {"id": "16", "label": "Exp Rise",    "icon": "mdi-chart-bell-curve"},
    {"id": "17", "label": "Exp Decay",   "icon": "mdi-chart-bell-curve"},
    {"id": "18", "label": "Multi Tone",  "icon": "mdi-music-note-plus"},
    {"id": "19", "label": "Sinc",        "icon": "mdi-chart-bell-curve-cumulative"},
    {"id": "20", "label": "Lorenz",      "icon": "mdi-chart-bell-curve"},
    {"id": "21", "label": "Impulse",     "icon": "mdi-arrow-up-bold"},
    {"id": "22", "label": "PRBS",        "icon": "mdi-code-brackets"},
    {"id": "23", "label": "AM",          "icon": "mdi-signal-variant"},
    {"id": "24", "label": "FM",          "icon": "mdi-signal-variant"},
    {"id": "25", "label": "Chirp",       "icon": "mdi-signal"},
    {"id": "26", "label": "ECG",         "icon": "mdi-heart-pulse"},
    {"id": "27", "label": "Gauss",       "icon": "mdi-chart-bell-curve"},
    {"id": "28", "label": "LFPulse",     "icon": "mdi-pulse"},
    {"id": "29", "label": "RSPulse",     "icon": "mdi-pulse"},
    {"id": "30", "label": "CPulse",      "icon": "mdi-pulse"},
    {"id": "31", "label": "PWM",         "icon": "mdi-square-wave"},
    {"id": "32", "label": "NPulse",      "icon": "mdi-pulse"},
    {"id": "33", "label": "Trapezia",    "icon": "mdi-shape"},
]

_WAVEFORM_OPTIONS = [w["label"] for w in _WAVEFORMS]
_WAVEFORM_LABEL_TO_ID = {w["label"]: w["id"] for w in _WAVEFORMS}

# Gate time options
_GATE_TIMES = [
    {"value": "0", "label": "1s"},
    {"value": "1", "label": "10s"},
    {"value": "2", "label": "100s"},
]

# ---------------------------------------------------------------------------
# Capability descriptor
# ---------------------------------------------------------------------------
_CAPABILITY = Capability(
    model="FY6800",
    manufacturer="FeelElec",
    instrument_type="siggen",
    functions=[
        {"id": "CH1",     "label": "CH1",     "icon": "mdi-numeric-1-circle",  "unit": ""},
        {"id": "CH2",     "label": "CH2",     "icon": "mdi-numeric-2-circle",  "unit": ""},
        {"id": "COUNTER", "label": "Counter", "icon": "mdi-counter",           "unit": "Hz"},
    ],
    ranges={
        "CH1": [], "CH2": [], "COUNTER": [],
    },
    settings=[
        {
            "id": "waveform", "label": "Waveform", "type": "select",
            "options": _WAVEFORM_OPTIONS,
            "default": "Sine",
            "applicable_to": ["CH1", "CH2"],
        },
        {
            "id": "frequency", "label": "Frequency (Hz)", "type": "number",
            "default": 1000.0,
            "applicable_to": ["CH1", "CH2"],
        },
        {
            "id": "amplitude", "label": "Amplitude (Vpp)", "type": "number",
            "default": 1.0,
            "applicable_to": ["CH1", "CH2"],
        },
        {
            "id": "offset", "label": "Offset (V)", "type": "number",
            "default": 0.0,
            "applicable_to": ["CH1", "CH2"],
        },
        {
            "id": "duty", "label": "Duty (%)", "type": "number",
            "default": 50.0,
            "applicable_to": ["CH1", "CH2"],
        },
        {
            "id": "phase", "label": "Phase (deg)", "type": "number",
            "default": 0.0,
            "applicable_to": ["CH1", "CH2"],
        },
        {
            "id": "output", "label": "Output", "type": "toggle",
            "default": False,
            "applicable_to": ["CH1", "CH2"],
        },
        {
            "id": "gate_time", "label": "Gate Time", "type": "select",
            "options": ["1s", "10s", "100s"],
            "default": "1s",
            "applicable_to": ["COUNTER"],
        },
    ],
)

# Channel command prefixes
_CH_PREFIX = {
    "CH1": {"write": "WM", "read": "RM"},
    "CH2": {"write": "WF", "read": "RF"},
}


class FY6800(InstrumentBase):
    """FY6800 DDS Signal Generator / Counter."""

    @classmethod
    def static_capability(cls) -> Capability:
        return _CAPABILITY

    def __init__(self, resource) -> None:
        self._res = resource
        self._function = "CH1"
        # Per-channel state
        self._ch_state = {
            "CH1": {
                "waveform": "Sine", "frequency": 1000.0,
                "amplitude": 1.0, "offset": 0.0,
                "duty": 50.0, "phase": 0.0, "output": False,
            },
            "CH2": {
                "waveform": "Sine", "frequency": 1000.0,
                "amplitude": 1.0, "offset": 0.0,
                "duty": 50.0, "phase": 0.0, "output": False,
            },
        }
        self._gate_time = "1s"
        # Read current state from device
        self._sync_from_device()

    # ------------------------------------------------------------------
    # Frequency encoding / decoding
    # ------------------------------------------------------------------

    @staticmethod
    def _encode_freq(hz: float) -> str:
        """Encode Hz to 14-digit uHz string."""
        uhz = int(hz * 1_000_000)
        return f"{uhz:014d}"

    @staticmethod
    def _decode_freq(raw: str) -> float:
        """Decode frequency response to Hz.

        FY6800 returns frequency as a floating-point Hz value:
          '00001000.000000' = 1000.0 Hz
        """
        try:
            return float(raw)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _encode_amplitude(vpp: float) -> str:
        """Encode Vpp for WMA command.

        WMA takes a floating-point Vpp string directly (e.g. '1.0' = 1 Vpp).
        Integer values get clipped to max (20 Vpp) — must use float format.
        """
        return f"{vpp:.4f}"

    @staticmethod
    def _decode_amplitude(raw: str) -> float:
        """Decode amplitude response to Vpp."""
        try:
            return int(raw) / 10000.0
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _encode_offset(volts: float) -> str:
        """Encode offset voltage. FY6800: value = (offset + range) * 1000.
        For simplicity, encode as integer (device-specific encoding).
        Offset range is typically -12V to +12V, encoded as 0-2400 (0=min, 1200=zero, 2400=max).
        """
        # FY6800 offset: 0 = -Vpp/2, 100 = 0V, 200 = +Vpp/2 (percentage-based)
        # Actually the encoding is: value = (offset_percent + 100) * 100
        # where offset_percent = -100 to +100
        # Simplified: we pass raw value for now
        val = int((volts + 12.0) * 100)  # rough mapping
        return str(max(0, min(2400, val)))

    @staticmethod
    def _encode_duty(percent: float) -> str:
        """Encode duty cycle percentage. FY6800: value * 1000."""
        return str(int(percent * 1000))

    @staticmethod
    def _decode_duty(raw: str) -> float:
        """Decode duty cycle response to percentage."""
        try:
            return int(raw) / 1000.0
        except (ValueError, TypeError):
            return 50.0

    @staticmethod
    def _encode_phase(degrees: float) -> str:
        """Encode phase in degrees. FY6800: value * 1000."""
        return str(int(degrees * 1000))

    @staticmethod
    def _decode_phase(raw: str) -> float:
        """Decode phase response to degrees."""
        try:
            return int(raw) / 1000.0
        except (ValueError, TypeError):
            return 0.0

    # ------------------------------------------------------------------
    # Device sync
    # ------------------------------------------------------------------

    def _sync_from_device(self) -> None:
        """Read current settings from device to sync internal state."""
        try:
            for ch, prefix in [("CH1", "RM"), ("CH2", "RF")]:
                # Waveform
                raw = self._res.query(f"{prefix}W")
                try:
                    idx = int(raw)
                    wf = _WAVEFORMS[idx]["label"] if idx < len(_WAVEFORMS) else "Sine"
                except (ValueError, IndexError):
                    wf = "Sine"
                self._ch_state[ch]["waveform"] = wf

                # Frequency
                raw = self._res.query(f"{prefix}F")
                self._ch_state[ch]["frequency"] = self._decode_freq(raw)

                # Amplitude
                raw = self._res.query(f"{prefix}A")
                self._ch_state[ch]["amplitude"] = self._decode_amplitude(raw)

                # Duty
                raw = self._res.query(f"{prefix}D")
                self._ch_state[ch]["duty"] = self._decode_duty(raw)

                # Phase
                raw = self._res.query(f"{prefix}P")
                self._ch_state[ch]["phase"] = self._decode_phase(raw)

            _log.info("FY6800: synced from device: CH1=%s, CH2=%s",
                      self._ch_state["CH1"], self._ch_state["CH2"])
        except Exception as e:
            _log.warning("FY6800: sync_from_device failed: %s", e)

    # ------------------------------------------------------------------
    # InstrumentBase interface
    # ------------------------------------------------------------------

    def get_capability(self) -> Capability:
        return _CAPABILITY

    def get_idn(self) -> str:
        try:
            return self._res.query("UMO")
        except Exception:
            return "FY6800"

    def reset(self) -> None:
        # FY6800 has no reset command; turn off both outputs
        self._res.write("WMN0")
        self._res.write("WFN0")
        self._ch_state["CH1"]["output"] = False
        self._ch_state["CH2"]["output"] = False

    def close(self) -> None:
        pass

    def apply_settings(self, settings: dict) -> None:
        """Apply settings to the current channel.

        Settings dict may contain:
          function, waveform, frequency, amplitude, offset, duty, phase,
          output, gate_time
        """
        if "function" in settings:
            self._function = settings["function"]

        ch = self._function
        if ch in ("CH1", "CH2"):
            prefix = _CH_PREFIX[ch]["write"]
            state = self._ch_state[ch]

            if "waveform" in settings:
                wf = settings["waveform"]
                wf_id = _WAVEFORM_LABEL_TO_ID.get(wf, "0")
                self._res.write(f"{prefix}W{int(wf_id):02d}")
                state["waveform"] = wf

            if "frequency" in settings:
                freq = float(settings["frequency"])
                self._res.write(f"{prefix}F{self._encode_freq(freq)}")
                state["frequency"] = freq

            if "amplitude" in settings:
                amp = float(settings["amplitude"])
                self._res.write(f"{prefix}A{self._encode_amplitude(amp)}")
                state["amplitude"] = amp

            if "offset" in settings:
                offset = float(settings["offset"])
                self._res.write(f"{prefix}O{self._encode_offset(offset)}")
                state["offset"] = offset

            if "duty" in settings:
                duty = float(settings["duty"])
                self._res.write(f"{prefix}D{self._encode_duty(duty)}")
                state["duty"] = duty

            if "phase" in settings:
                phase = float(settings["phase"])
                self._res.write(f"{prefix}P{self._encode_phase(phase)}")
                state["phase"] = phase

            if "output" in settings:
                on = settings["output"]
                if isinstance(on, str):
                    on = on.lower() in ("true", "1", "on")
                self._res.write(f"{prefix}N{'1' if on else '0'}")
                state["output"] = bool(on)

        elif ch == "COUNTER":
            if "gate_time" in settings:
                gt = settings["gate_time"]
                gt_map = {"1s": "0", "10s": "1", "100s": "2"}
                self._res.write(f"WCT{gt_map.get(gt, '0')}")
                self._gate_time = gt

    def measure(self) -> MeasurementResult:
        """Return measurement based on current function.

        CH1/CH2: read back current frequency setting.
        COUNTER: read counter frequency.
        """
        ch = self._function

        if ch == "COUNTER":
            raw = self._res.query("RCF")
            freq = self._decode_freq(raw)
            return MeasurementResult(
                value=freq,
                unit="Hz",
                function="COUNTER",
                range="",
                timestamp=time.time(),
            )

        # CH1 or CH2: read back the frequency as the "measurement"
        prefix = _CH_PREFIX[ch]["read"]
        raw = self._res.query(f"{prefix}F")
        freq = self._decode_freq(raw)
        state = self._ch_state[ch]
        return MeasurementResult(
            value=freq,
            unit="Hz",
            function=ch,
            range="",
            timestamp=time.time(),
            extra={
                "waveform":  state["waveform"],
                "amplitude": state["amplitude"],
                "offset":    state["offset"],
                "duty":      state["duty"],
                "phase":     state["phase"],
                "output":    state["output"],
            },
        )

    def get_channel_state(self, ch: str) -> dict:
        """Return current state for a channel (used by API for UI sync)."""
        if ch in self._ch_state:
            return dict(self._ch_state[ch])
        if ch == "COUNTER":
            return {"gate_time": self._gate_time}
        return {}
