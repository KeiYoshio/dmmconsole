# Development Guide

## Architecture

```
dmmconsole/
├── backend/
│   ├── version.py                   # Single source of truth for version number
│   ├── main.py                      # FastAPI app, CORS, SPA fallback, /ws mount
│   ├── api/
│   │   ├── routes.py                # REST endpoints (/api/version, /api/instruments, …)
│   │   ├── websocket.py             # WebSocket /ws/stream (measurement streaming)
│   │   └── terminal.py              # REST endpoints (/api/terminal/…)
│   ├── gpib/
│   │   ├── manager.py               # GPIBManager singleton (GPIB / LAN / USB / Serial)
│   │   └── serial_resource.py       # FY6800Serial: pyserial wrapper with pyvisa-compatible API
│   ├── terminal/
│   │   └── manager.py               # TerminalManager singleton – independent from DMM
│   ├── instruments/
│   │   ├── base.py                  # InstrumentBase, Capability, MeasurementResult
│   │   ├── registry.py              # REGISTRY dict — add new instruments here
│   │   ├── dmm/
│   │   │   ├── base_dmm.py          # DMMBase: shared SCPI logic for most DMMs
│   │   │   ├── hp34401a.py
│   │   │   ├── keithley2000.py
│   │   │   ├── keithley2010.py
│   │   │   ├── ad7451a.py           # ADCMT 7451A – GPIB/SCPI
│   │   │   └── ad7451a_usb.py       # ADCMT 7451A – USB/ADC
│   │   └── siggen/
│   │       └── fy6800.py            # FeelElec FY6800 – USB serial
│   └── measurement/
│       └── session.py               # MeasurementSession singleton (streaming loop)
└── frontend/
    └── src/
        ├── App.vue                  # Root component – <RouterView /> only
        ├── main.js                  # app.use(router, pinia, vuetify)
        ├── plugins/vuetify.js       # Theme (dark, primary=#00e5ff, secondary=#00ff88)
        ├── router/
        │   └── index.js             # /, /dmm, /terminal, /siggen
        ├── stores/
        │   ├── instrument.js        # Pinia: connection state, capability, commands
        │   ├── measurement.js       # Pinia: WebSocket client, buffer (max 500 pts)
        │   └── terminal.js          # Pinia: terminal connection, TX/RX history
        ├── views/
        │   ├── HomeView.vue         # Landing page with instrument/tool cards
        │   ├── DmmView.vue          # DMM control panel
        │   ├── TerminalView.vue     # Raw SCPI terminal (TX/RX panes, CR/LF control)
        │   └── SignalGeneratorView.vue  # Signal generator control panel
        └── components/
            ├── ConnectionBar.vue    # Model / interface selector (GPIB/LAN/USB/Serial)
            ├── MeasurementDisplay.vue
            ├── Waveform.vue         # Chart.js realtime scrolling graph
            └── panels/
                ├── GenericDMMPanel.vue       # Dynamically built from Capability descriptor
                └── SignalGeneratorPanel.vue  # CH1/CH2/Counter tabs for FY6800
```

---

## Running in development mode

```bash
# Terminal 1 – backend with hot-reload
source ../agilent82357b/venv-GPIB/bin/activate
sudo uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 – frontend dev server (proxies /api and /ws to backend)
cd frontend && npm run dev
```

Open <http://localhost:5173> (dev) or <http://localhost:8000> (production build).

---

## Adding a new instrument

### SCPI instruments (most DMMs)

1. **Create the driver** – copy `backend/instruments/dmm/hp34401a.py` as a template.
   - Fill in `_FUNC_CONF` (function → SCPI command), `_FUNC_UNITS`, `_RANGE_SCPI`,
     and `_CAPABILITY`.
   - Override `measure()` only if the default SCPI measurement flow differs.

2. **Register it** – add two lines to `backend/instruments/registry.py`:
   ```python
   from .dmm.mynewmodel import MyNewModel
   REGISTRY["mynewmodel"] = MyNewModel
   ```

3. **Done** – the frontend panel is generated automatically from `_CAPABILITY`.
   No frontend changes needed.

### Non-SCPI instruments (vendor command set)

Subclass `InstrumentBase` directly (see `ad7451a_usb.py` for an example) and implement:
- `static_capability()` / `get_capability()`
- `get_idn()`
- `reset()`
- `apply_settings(settings: dict)`
- `measure() → MeasurementResult`

### Signal generators (serial)

See `backend/instruments/siggen/fy6800.py` for an example.  Key differences from DMMs:
- `instrument_type = "siggen"` in the Capability descriptor.
- Communication via `FY6800Serial` (pyserial wrapper) instead of pyvisa.
- `apply_settings()` handles per-channel parameters (waveform, frequency, amplitude, etc.).
- `get_channel_state(ch)` returns current channel state for UI sync.
- The frontend uses `SignalGeneratorPanel.vue` (channel tabs) instead of `GenericDMMPanel.vue`.

---

## Capability descriptor

The `Capability` dataclass (defined in `backend/instruments/base.py`) is the contract
between the backend and the frontend.  The frontend builds the entire control panel from
it dynamically — no frontend code changes are needed when a new instrument is added.

```python
Capability(
    model="HP 34401A",
    manufacturer="HP / Agilent / Keysight",
    instrument_type="dmm",
    functions=[
        {"id": "DCV", "label": "DC V", "icon": "mdi-lightning-bolt", "unit": "V"},
        ...
    ],
    ranges={
        "DCV": ["AUTO", "100mV", "1V", "10V", "100V", "1000V"],
        ...
    },
    settings=[
        {"id": "nplc", "label": "NPLC", "type": "select",
         "options": [0.02, 0.2, 1, 10, 100], "default": 10,
         "applicable_to": ["DCV", "ACV", ...]},
    ],
)
```

---

## Releasing a new version

1. Update `backend/version.py`:
   ```python
   __version__ = "1.1.0"
   ```
2. Update `CHANGELOG.md` — add a new `## [1.1.0] - YYYY-MM-DD` section.
3. Create `release_notes/v1.1.0.md` with user-facing release notes.
4. Rebuild the frontend if needed: `cd frontend && npm run build`.
5. Commit everything:
   ```bash
   git add -A
   git commit -m "Release v1.1.0"
   ```
6. Tag and push:
   ```bash
   git tag -a v1.1.0 -m "Release v1.1.0"
   git push origin main
   git push origin v1.1.0
   ```
7. Create a GitHub Release from the tag, using `release_notes/v1.1.0.md` as the body.

---

## WebSocket protocol

```
Client → Server:
  {"action": "start",  "interval_ms": 200}
  {"action": "stop"}
  {"action": "config", "interval_ms": 500}

Server → Client (measurement):
  {"value": 1.035, "unit": "V", "function": "DCV",
   "range": "AUTO", "timestamp": 1712345678.9, "value_str": "+1.035 V"}

Server → Client (error):
  {"error": "GPIB timeout", "timestamp": 1712345678.9}

Server → Client (status):
  {"status": "started" | "stopped"}
```
