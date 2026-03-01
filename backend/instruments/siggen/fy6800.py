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
# Waveform table – based on fygen (github.com/mattwach/fygen) wavedef.py.
#
# FY6800 has different waveform IDs for CH1 vs CH2.
# CH2 IDs diverge from CH1 starting at "Adjustable Pulse" (CH2 = CH1 - 1).
# "Rectangle" and "Trapezoid" are FY6900-only and excluded.
# Arbitrary waveforms (arb1-64) start at CH1=34, CH2=33.
# ---------------------------------------------------------------------------
_WAVEFORM_DEFS: list[dict] = [
    # label (= fygen description)               CH1  CH2  icon
    {"label": "Sin",                     "ch1": 0,  "ch2": 0,  "icon": "mdi-sine-wave"},
    {"label": "Square",                  "ch1": 1,  "ch2": 1,  "icon": "mdi-square-wave"},
    {"label": "CMOS",                    "ch1": 2,  "ch2": 2,  "icon": "mdi-chip"},
    {"label": "Adjustable Pulse",        "ch1": 3,  "ch2": None, "icon": "mdi-pulse"},  # CH1 only
    {"label": "DC",                      "ch1": 4,  "ch2": 3,  "icon": "mdi-minus"},
    {"label": "Triangle",               "ch1": 5,  "ch2": 4,  "icon": "mdi-triangle-wave"},
    {"label": "Ramp",                    "ch1": 6,  "ch2": 5,  "icon": "mdi-chart-line"},
    {"label": "Negative Ramp",           "ch1": 7,  "ch2": 6,  "icon": "mdi-chart-line"},
    {"label": "Stairstep Triangle",      "ch1": 8,  "ch2": 7,  "icon": "mdi-stairs"},
    {"label": "Stairstep",               "ch1": 9,  "ch2": 8,  "icon": "mdi-stairs-up"},
    {"label": "Negative Stairstep",      "ch1": 10, "ch2": 9,  "icon": "mdi-stairs-down"},
    {"label": "Exponential",             "ch1": 11, "ch2": 10, "icon": "mdi-chart-bell-curve"},
    {"label": "Negative Exponential",    "ch1": 12, "ch2": 11, "icon": "mdi-chart-bell-curve"},
    {"label": "Falling Exponential",     "ch1": 13, "ch2": 12, "icon": "mdi-chart-bell-curve"},
    {"label": "Neg Falling Exponential", "ch1": 14, "ch2": 13, "icon": "mdi-chart-bell-curve"},
    {"label": "Logarithm",              "ch1": 15, "ch2": 14, "icon": "mdi-chart-line-variant"},
    {"label": "Negative Logarithm",      "ch1": 16, "ch2": 15, "icon": "mdi-chart-line-variant"},
    {"label": "Falling Logarithm",       "ch1": 17, "ch2": 16, "icon": "mdi-chart-line-variant"},
    {"label": "Neg Falling Logarithm",   "ch1": 18, "ch2": 17, "icon": "mdi-chart-line-variant"},
    {"label": "Full Wave",               "ch1": 19, "ch2": 18, "icon": "mdi-wave"},
    {"label": "Negative Full Wave",      "ch1": 20, "ch2": 19, "icon": "mdi-wave"},
    {"label": "Half Wave",               "ch1": 21, "ch2": 20, "icon": "mdi-wave"},
    {"label": "Negative Half Wave",      "ch1": 22, "ch2": 21, "icon": "mdi-wave"},
    {"label": "Lorentz Pulse",           "ch1": 23, "ch2": 22, "icon": "mdi-chart-bell-curve"},
    {"label": "Multitone",               "ch1": 24, "ch2": 23, "icon": "mdi-music-note-plus"},
    {"label": "Random",                  "ch1": 25, "ch2": 24, "icon": "mdi-blur"},
    {"label": "ECG",                     "ch1": 26, "ch2": 25, "icon": "mdi-heart-pulse"},
    {"label": "Trapezoidal Pulse",       "ch1": 27, "ch2": 26, "icon": "mdi-shape"},
    {"label": "Sinc Pulse",              "ch1": 28, "ch2": 27, "icon": "mdi-chart-bell-curve-cumulative"},
    {"label": "Impulse",                 "ch1": 29, "ch2": 28, "icon": "mdi-arrow-up-bold"},
    {"label": "Gauss White Noise",       "ch1": 30, "ch2": 29, "icon": "mdi-blur"},
    {"label": "AM",                      "ch1": 31, "ch2": 30, "icon": "mdi-signal-variant"},
    {"label": "FM",                      "ch1": 32, "ch2": 31, "icon": "mdi-signal-variant"},
    {"label": "Chirp",                   "ch1": 33, "ch2": 32, "icon": "mdi-signal"},
]

# Add arbitrary waveforms (arb1-64)
for _i in range(1, 65):
    _WAVEFORM_DEFS.append({
        "label": f"Arb {_i}",
        "ch1": 33 + _i,    # 34..97
        "ch2": 32 + _i,    # 33..96
        "icon": "mdi-waveform",
    })

# Per-channel waveform option lists (Adjustable Pulse is CH1-only)
_CH1_WAVEFORM_OPTIONS = [w["label"] for w in _WAVEFORM_DEFS if w["ch1"] is not None]
_CH2_WAVEFORM_OPTIONS = [w["label"] for w in _WAVEFORM_DEFS if w["ch2"] is not None]
_WAVEFORM_OPTIONS = _CH1_WAVEFORM_OPTIONS  # default (superset)

# label -> per-channel ID lookup
_LABEL_TO_CH_ID: dict[str, dict[str, int | None]] = {
    w["label"]: {"CH1": w["ch1"], "CH2": w["ch2"]}
    for w in _WAVEFORM_DEFS
}

# Reverse: per-channel ID -> label
_CH1_ID_TO_LABEL: dict[int, str] = {
    w["ch1"]: w["label"] for w in _WAVEFORM_DEFS if w["ch1"] is not None
}
_CH2_ID_TO_LABEL: dict[int, str] = {
    w["ch2"]: w["label"] for w in _WAVEFORM_DEFS if w["ch2"] is not None
}

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
            "default": "Sin",
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
                "waveform": "Sin", "frequency": 1000.0,
                "amplitude": 1.0, "offset": 0.0,
                "duty": 50.0, "phase": 0.0, "output": False,
            },
            "CH2": {
                "waveform": "Sin", "frequency": 1000.0,
                "amplitude": 1.0, "offset": 0.0,
                "duty": 50.0, "phase": 0.0, "output": False,
            },
        }
        self._gate_time = "1s"
        self._coupling = "AC"  # default; no readback command available
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
                # Waveform (CH1 and CH2 have different ID mappings)
                raw = self._res.query(f"{prefix}W")
                try:
                    idx = int(raw)
                    id_to_label = _CH1_ID_TO_LABEL if ch == "CH1" else _CH2_ID_TO_LABEL
                    wf = id_to_label.get(idx, "Sin")
                except (ValueError, IndexError):
                    wf = "Sin"
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

            # Counter gate time (RCG returns: 0=1s, 1=10s, 2=100s)
            raw_gt = self._res.query("RCG").strip()
            gt_rev = {"0": "1s", "1": "10s", "2": "100s"}
            self._gate_time = gt_rev.get(raw_gt, "1s")

            _log.info("FY6800: synced from device: CH1=%s, CH2=%s, gate=%s",
                      self._ch_state["CH1"], self._ch_state["CH2"],
                      self._gate_time)
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
                ch_ids = _LABEL_TO_CH_ID.get(wf)
                wf_id = ch_ids[ch] if ch_ids else 0
                self._res.write(f"{prefix}W{wf_id:02d}")
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
                self._res.write(f"WCG{gt_map.get(gt, '0')}")
                self._gate_time = gt
            if settings.get("counter_reset"):
                self._res.write("WCZ0")
            if "coupling" in settings:
                cp = settings["coupling"]
                # WCC0=AC(Front Counter), WCC1=DC(Rear Trig) — manual is reversed!
                self._res.write("WCC0" if cp == "AC" else "WCC1")
                self._coupling = cp

    def measure(self) -> MeasurementResult:
        """Return measurement based on current function.

        CH1/CH2: read back current frequency setting.
        COUNTER: read counter frequency.
        """
        ch = self._function

        if ch == "COUNTER":
            raw = self._res.query("RCF")
            count = self._decode_freq(raw)
            # RCF returns raw count within gate window.
            # Frequency [Hz] = count / gate_time [s].
            gt_map = {"1s": 1.0, "10s": 10.0, "100s": 100.0}
            gate_s = gt_map.get(self._gate_time, 1.0)
            freq = count / gate_s

            # Additional counter readings
            try:
                period_ns = float(self._res.query("RCT"))
            except (ValueError, TypeError):
                period_ns = 0.0
            try:
                pos_width_ns = float(self._res.query("RC+"))
            except (ValueError, TypeError):
                pos_width_ns = 0.0
            try:
                neg_width_ns = float(self._res.query("RC-"))
            except (ValueError, TypeError):
                neg_width_ns = 0.0
            try:
                duty_pct = float(self._res.query("RCD")) / 10.0
            except (ValueError, TypeError):
                duty_pct = 0.0

            return MeasurementResult(
                value=freq,
                unit="Hz",
                function="COUNTER",
                range="",
                timestamp=time.time(),
                extra={
                    "period_ns": period_ns,
                    "pos_width_ns": pos_width_ns,
                    "neg_width_ns": neg_width_ns,
                    "duty_pct": duty_pct,
                    "coupling": self._coupling,
                },
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

    # ------------------------------------------------------------------
    # Arbitrary waveform upload
    # ------------------------------------------------------------------

    @staticmethod
    def _encode_arb_data(raw_values: list[int]) -> bytes:
        """Encode 8192 raw 14-bit values to FY6800 binary format.

        Each sample: [value & 0xFF, (value >> 8) & 0x3F]  (little-endian split)
        """
        data = bytearray()
        for v in raw_values:
            v = max(0, min(16383, v))
            data.append(v & 0xFF)
            data.append((v >> 8) & 0x3F)
        return bytes(data)

    def upload_waveform(self, slot: int, samples: list[int]) -> dict:
        """Upload arbitrary waveform to DDS_WAVE slot.

        Args:
            slot: Arb slot number (1..64).
            samples: 8192 values, each 0..16383 (14-bit).

        Returns:
            {"ok": True} on success, {"ok": False, "error": "..."} on failure.
        """
        if not (1 <= slot <= 64):
            return {"ok": False, "error": f"slot must be 1..64, got {slot}"}
        if len(samples) != 8192:
            return {"ok": False, "error": f"need 8192 samples, got {len(samples)}"}

        # Check that target arb is not active on either channel
        try:
            ch1_wf = self._res.query("RMW").strip()
            ch2_wf = self._res.query("RFW").strip()
            arb_ch1_idx = 33 + slot
            arb_ch2_idx = 32 + slot
            if int(ch1_wf) == arb_ch1_idx:
                return {"ok": False, "error": f"Arb {slot} is active on CH1 — select a different waveform first"}
            if int(ch2_wf) == arb_ch2_idx:
                return {"ok": False, "error": f"Arb {slot} is active on CH2 — select a different waveform first"}
        except ValueError:
            pass  # non-numeric response; proceed cautiously

        # Handshake: send DDS_WAVE{slot} command
        cmd = f"DDS_WAVE{slot}"
        _log.info("FY6800: uploading arb slot %d (%s)", slot, cmd)
        self._res._ser.reset_input_buffer()
        self._res._ser.write((cmd + "\n").encode("ascii"))
        time.sleep(0.3)

        avail = self._res._ser.in_waiting
        resp = self._res._ser.read(avail) if avail else b""
        resp_str = resp.decode("ascii", errors="replace").strip()

        if "W" not in resp_str:
            _log.warning("FY6800: DDS_WAVE handshake failed: %r", resp_str)
            return {"ok": False, "error": f"Handshake failed (response: {resp_str!r})"}

        # Send binary data (16384 bytes)
        data = self._encode_arb_data(samples)
        self._res.write_bytes(data)

        # Wait for HN response (up to 15 seconds)
        full_resp = b""
        for _ in range(15):
            time.sleep(1.0)
            avail = self._res._ser.in_waiting
            if avail:
                full_resp += self._res._ser.read(avail)
                decoded = full_resp.decode("ascii", errors="replace")
                if "N" in decoded:
                    break

        final = full_resp.decode("ascii", errors="replace").strip()
        if "H" in final and "N" in final:
            _log.info("FY6800: arb slot %d upload SUCCESS", slot)
            return {"ok": True}

        _log.warning("FY6800: arb slot %d upload FAILED: %r", slot, final)
        return {"ok": False, "error": f"Upload failed (response: {final!r})"}

    def get_channel_state(self, ch: str) -> dict:
        """Return current state for a channel (used by API for UI sync)."""
        if ch in self._ch_state:
            state = dict(self._ch_state[ch])
            # Include per-channel waveform options (Adjustable Pulse is CH1-only)
            state["waveform_options"] = (
                _CH1_WAVEFORM_OPTIONS if ch == "CH1" else _CH2_WAVEFORM_OPTIONS
            )
            return state
        if ch == "COUNTER":
            return {"gate_time": self._gate_time, "coupling": self._coupling}
        return {}
