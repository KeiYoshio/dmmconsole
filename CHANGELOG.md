# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.0] - 2026-02-26

### Added
- **ADCMT 7451A USB direct driver** (`ad7451a_usb`) – now functional and registered.
  Uses the ADC proprietary command set over USB-TMC.
  The instrument must be set to LANG=ADC (MENU → 8 I/F → LANG) to use this mode.
  Key requirements: USB488 REN_CONTROL to enter remote mode; BUS trigger
  (TRS3 + INI + USB488 TRIGGER); automatic priming cycle after function/range changes.

### Changed
- **`/api/command` stops the stream before applying settings** – the measurement
  stream is stopped, the setting is applied, then streaming is automatically restarted
  if it was running.  The response now includes `was_streaming`.
- **Function change sends function and default range in a single request** – reduces
  the number of stop/restart cycles when switching measurement functions.

---

## [1.1.0] - 2026-02-24

### Added
- **Instrument Console home page** (`/`) – landing page with cards for each
  instrument / tool; replaces the single-page DMM layout.
- **Vue Router** – client-side routing introduced (`vue-router@4`).
  DMM panel moved to `/dmm`; new `/terminal` route added.
- **SCPI Terminal** (`/terminal`) – raw command console for any connected instrument:
  - TX pane (sent commands) and RX pane (received responses) with independent scrolling
    and per-entry timestamps.
  - CR / LF toggle buttons; selected characters are appended to every sent command.
  - Auto-focus on the command input field after each send for continuous entry.
  - Connection bar (GPIB / LAN / USB) independent from the DMM connection.
  - `TerminalManager` singleton – separate from `GPIBManager` so DMM and Terminal
    can hold independent connections simultaneously.
- **USB instrument discovery** – VISA Resource field in both the Terminal and DMM
  connection bars is now a combobox:
  - Clicking / focusing the field scans connected USB devices via pyusb.
  - Dropdown shows manufacturer, product name, and the full VISA resource string.
  - Non-instrument USB devices (HID, Mass Storage, Hub, Audio, Video) are excluded.
- **`GET /api/terminal/usb_resources`** – enumerate connected USB instruments.
- **`POST /api/terminal/connect|disconnect|send`** – terminal connection and
  raw SCPI command API (write or query auto-detected by `?` in command string).

### Changed
- App title renamed from **DMM Console** to **Instrument Console**
  (toolbar, FastAPI title, home page).
- `backend/main.py` now reads `version` from `backend/version.py`
  (was hardcoded `"0.1.0"`).

---

## [1.0.0] - 2026-02-23

First stable release.

### Added
- **Instruments supported via GPIB**
  - HP / Agilent 34401A (SCPI) – tested
  - Keithley 2000 (SCPI) – implemented, untested
  - Keithley 2010 (SCPI) – implemented, untested
  - ADCMT 7451A (SCPI) – tested
- **ADCMT 7451A USB driver** (`ad7451a_usb`) – work in progress, excluded from UI
- Real-time measurement display with SI prefix auto-scaling (μ / m / k / M …)
- Oscilloscope-like waveform graph (Chart.js) with selectable time window
- WebSocket streaming for continuous measurement updates
- Capability-based dynamic control panel generated from instrument descriptors
- GPIB interface via [agilent82357b](https://github.com/KeiYoshio/agilent82357b) driver
- LAN (VXI-11) and USB-TMC interfaces via PyVISA
- CSV download of measurement buffer
- Version display in toolbar (`/api/version` endpoint)

### Fixed
- **`abstractmethod` import error in `base_dmm.py`** – `classmethod` was incorrectly
  imported from `abc`; only `abstractmethod` belongs there.
- **GPIB lock contention causing USB timeout `[Errno 60]`** – `/api/command` and
  `/api/reset` endpoints now acquire `sess._lock` before calling GPIB functions,
  preventing concurrent access during streaming.
- **Waveform graph freezing at buffer limit** – changed watcher from
  `buffer.length` to `latest` so the graph keeps updating when the 500-point
  buffer is full and length stops changing.
- **Stream hanging on repeated errors** – `session.py` now auto-stops the stream
  after 3 consecutive measurement errors.
- **Reconnect failure after SCPI errors** – `/api/connect` sends `*CLS` on connect
  to clear any `-410`/`-420` error state left by the previous session; also calls
  `sess.stop()` to terminate any still-running stream before reconnecting.
