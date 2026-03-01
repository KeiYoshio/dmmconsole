"""REST API routes."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..gpib.manager        import GPIBManager, ConnectionConfig
from ..instruments.registry import REGISTRY, list_models, create
from ..measurement.session  import MeasurementSession
from ..version             import __version__

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ConnectRequest(BaseModel):
    model_id:    str
    interface:   str = "gpib"   # "gpib" | "lan" | "usb" | "serial"
    gpib_addr:   int = 6
    ip_address:  str = ""
    visa_string: str = ""
    serial_port: str = ""

class CommandRequest(BaseModel):
    function:  str | None = None
    range:     str | None = None
    nplc:      float | None = None
    # Signal generator settings
    waveform:  str | None = None
    frequency: float | None = None
    amplitude: float | None = None
    offset:    float | None = None
    duty:      float | None = None
    phase:     float | None = None
    output:    bool | None = None
    gate_time: str | None = None

class StatusResponse(BaseModel):
    connected:   bool
    model_id:    str | None = None
    model_name:  str | None = None
    interface:   str | None = None
    streaming:   bool = False


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

@router.get("/version")
def get_version():
    return {"version": __version__}


# ---------------------------------------------------------------------------
# Instrument discovery
# ---------------------------------------------------------------------------

@router.get("/instruments")
def get_instruments():
    """Return list of all registered instrument models with their capabilities."""
    result = []
    for m in list_models():
        cap = REGISTRY[m["id"]].static_capability()
        result.append({**m, "capability": cap.to_dict()})
    return result


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

@router.post("/connect")
def connect(req: ConnectRequest):
    sess = MeasurementSession.get()
    mgr  = GPIBManager.get()
    sess.stop()  # stop any running stream before reconnecting
    try:
        config = ConnectionConfig(
            interface   = req.interface,
            model_id    = req.model_id,
            gpib_addr   = req.gpib_addr,
            ip_address  = req.ip_address,
            visa_string = req.visa_string,
            serial_port = req.serial_port,
        )
        try:
            resource = mgr.connect(config)
        except Exception:
            if config.interface == "usb":
                # pyvisa cannot open vendor-specific USB (class 0xFF) devices.
                # Fall back to raw pyusb + USBTMC framing.
                from ..gpib.usbtmc_raw import USBTMCResource, parse_visa_usb
                # Clean up partial pyvisa state left by the failed connect()
                if mgr._rm is not None:
                    try:
                        mgr._rm.close()
                    except Exception:
                        pass
                    mgr._rm = None
                vid, pid, serial = parse_visa_usb(config.visa_string)
                resource = USBTMCResource(vid, pid, serial)
                # Register resource with GPIBManager so disconnect() works
                mgr._resource = resource
                mgr._config   = config
            else:
                raise

        instrument = create(req.model_id, resource)
        # Clear SCPI error state (-410/-420) left from any previous session
        # (skip for serial instruments which don't speak SCPI)
        if req.interface != "serial":
            try:
                resource.write("*CLS")
            except Exception:
                pass
        sess.set_instrument(instrument)
        idn = ""
        try:
            idn = instrument.get_idn()
        except Exception:
            pass
        return {"ok": True, "idn": idn}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/disconnect")
def disconnect():
    MeasurementSession.get().stop()
    MeasurementSession.get().clear_instrument()
    GPIBManager.get().disconnect()
    return {"ok": True}


@router.get("/status")
def status() -> StatusResponse:
    mgr  = GPIBManager.get()
    sess = MeasurementSession.get()
    if not mgr.is_connected:
        return StatusResponse(connected=False)
    cfg = mgr.config
    cap = REGISTRY[cfg.model_id].static_capability()
    return StatusResponse(
        connected  = True,
        model_id   = cfg.model_id,
        model_name = cap.model,
        interface  = cfg.interface,
        streaming  = sess.is_running,
    )


# ---------------------------------------------------------------------------
# Instrument control
# ---------------------------------------------------------------------------

@router.post("/command")
async def command(req: CommandRequest):
    sess = MeasurementSession.get()
    mgr  = GPIBManager.get()
    if not mgr.is_connected:
        raise HTTPException(status_code=400, detail="Not connected.")

    instrument = sess._instrument
    if instrument is None:
        raise HTTPException(status_code=400, detail="No instrument.")

    try:
        settings = req.model_dump(exclude_none=True)
        was_streaming = sess.is_running
        sess.stop()   # stop stream before changing settings so the device can settle
        async with sess._lock:
            await asyncio.to_thread(instrument.apply_settings, settings)
        return {"ok": True, "was_streaming": was_streaming}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/reset")
async def reset_instrument():
    sess = MeasurementSession.get()
    if sess._instrument is None:
        raise HTTPException(status_code=400, detail="Not connected.")
    try:
        async with sess._lock:
            await asyncio.to_thread(sess._instrument.reset)
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/measure")
async def measure_once():
    sess = MeasurementSession.get()
    if sess._instrument is None:
        raise HTTPException(status_code=400, detail="Not connected.")
    try:
        return await sess.measure_once()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/buffer")
def get_buffer():
    """Return the current measurement buffer (for reconnected clients)."""
    return MeasurementSession.get().get_buffer()


# ---------------------------------------------------------------------------
# Serial port discovery
# ---------------------------------------------------------------------------

@router.get("/serial_ports")
def get_serial_ports():
    """Return list of available serial ports."""
    from ..gpib.serial_resource import list_serial_ports
    return {"ports": list_serial_ports()}


# ---------------------------------------------------------------------------
# Signal generator channel state
# ---------------------------------------------------------------------------

@router.get("/channel_state/{channel}")
def get_channel_state(channel: str):
    """Return current state for a signal generator channel (CH1/CH2/COUNTER)."""
    sess = MeasurementSession.get()
    instrument = sess._instrument
    if instrument is None:
        raise HTTPException(status_code=400, detail="Not connected.")
    if not hasattr(instrument, "get_channel_state"):
        raise HTTPException(status_code=400, detail="Instrument does not support channel state.")
    return instrument.get_channel_state(channel.upper())
