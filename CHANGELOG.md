# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-02-23

First stable release.

### Added
- **Instruments supported (GPIB)**
  - HP / Agilent 34401A (SCPI)
  - Keithley 2000 (SCPI)
  - Keithley 2010 (SCPI)
  - ADCMT 7451A (SCPI over GPIB)
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
