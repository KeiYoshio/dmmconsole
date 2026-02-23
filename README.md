# dmmconsole  [![version](https://img.shields.io/badge/version-1.0.0-blue)](release_notes/v1.0.0.md)

Web-based Digital Multimeter console panel.

Supports **HP 34401A**, **Keithley 2000**, **Keithley 2010** (and any SCPI DMM via subclassing),
and **ADCMT 7451A** via GPIB.

- Real-time measurement display with SI prefix formatting
- Oscilloscope-like waveform graph (Chart.js)
- Full control panel reproduced from capability descriptors
- GPIB via [agilent82357b](../agilent82357b), LAN/USB via PyVISA
- Vue.js 3 + Vuetify 3 frontend (dark theme, easy to restyle)

## Installation

```bash
# 1. Backend dependencies
pip install fastapi "uvicorn[standard]" websockets
pip install -e ../agilent82357b   # GPIB driver

# 2. Frontend (build once)
cd frontend
npm install
npm run build
cd ..
```

## Run

```bash
# From the dmmconsole/ directory
sudo uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 in a browser.

During development (with hot-reload):
```bash
# Terminal 1: backend
sudo uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: frontend dev server (proxies /api and /ws to backend)
cd frontend && npm run dev
```
Then open http://localhost:5173.

## Adding a new instrument

1. Create `backend/instruments/dmm/mynewmodel.py` – subclass `DMMBase`, fill in
   `FUNC_CONF`, `FUNC_UNITS`, `RANGE_SCPI`, and `_CAPABILITY`.
2. Register it in `backend/instruments/registry.py`:
   ```python
   from .dmm.mynewmodel import MyNewModel
   REGISTRY["mynewmodel"] = MyNewModel
   ```
3. Done – the frontend panel is generated automatically from the capability descriptor.

## Instrument status

| Model | Interface | Status |
|-------|-----------|--------|
| HP 34401A | GPIB | Tested |
| Keithley 2000 | GPIB | Implemented, untested |
| Keithley 2010 | GPIB | Implemented, untested |
| ADCMT 7451A | GPIB | Tested |
| ADCMT 7451A | USB direct | **Work in progress – not functional** |


## License

GPL-2.0
