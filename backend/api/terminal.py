"""REST API routes for raw SCPI terminal."""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..terminal.manager import TerminalManager, TerminalConfig

router = APIRouter()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ConnectRequest(BaseModel):
    interface:   str = "gpib"
    gpib_addr:   int = 6
    ip_address:  str = ""
    visa_string: str = ""


class SendRequest(BaseModel):
    command:     str
    line_ending: str = ""   # "", "\r", "\n", "\r\n"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/connect")
async def connect(req: ConnectRequest):
    mgr = TerminalManager.get()
    try:
        config = TerminalConfig(
            interface   = req.interface,
            gpib_addr   = req.gpib_addr,
            ip_address  = req.ip_address,
            visa_string = req.visa_string,
        )
        await asyncio.to_thread(mgr.connect, config)
        idn = ""
        try:
            idn = await asyncio.to_thread(mgr.query, "*IDN?")
            idn = idn.strip()
        except Exception:
            pass
        return {"ok": True, "idn": idn}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/disconnect")
async def disconnect():
    await asyncio.to_thread(TerminalManager.get().disconnect)
    return {"ok": True}


# Interface classes that are definitively NOT measurement instruments.
# Devices whose every interface belongs to this set are excluded.
_NON_INSTRUMENT_IFACE_CLASSES = frozenset({
    0x01,  # Audio
    0x03,  # HID  (keyboard, mouse, gamepad)
    0x08,  # Mass Storage (SSD, USB drive, card reader)
    0x0B,  # Smart Card
    0x0E,  # Video
})

# Device-level classes to exclude unconditionally (before reading interfaces).
_EXCLUDED_DEVICE_CLASSES = frozenset({
    0x03,  # HID declared at device level (old-style)
    0x09,  # Hub
})


def _is_instrument_candidate(dev) -> bool:
    """Return False only for devices that are obviously not instruments.

    Strategy:
      1. Exclude hubs and device-level HID by bDeviceClass.
      2. Exclude devices whose every interface is HID / Mass Storage /
         Audio / Video / Smart Card.
      3. Keep everything else – including USBTMC (0xFE/0x03),
         vendor-specific (0xFF), CDC/serial (0x02), and unknown classes.
    """
    try:
        if dev.bDeviceClass in _EXCLUDED_DEVICE_CLASSES:
            return False
    except Exception:
        pass

    try:
        has_iface = False
        for cfg in dev:
            for intf in cfg:
                has_iface = True
                if intf.bInterfaceClass not in _NON_INSTRUMENT_IFACE_CLASSES:
                    return True   # at least one non-excluded interface → keep
        if has_iface:
            return False          # every interface was in the excluded set
    except Exception:
        pass

    return True   # could not inspect interfaces → include to be safe


@router.get("/usb_resources")
def list_usb_resources():
    """Enumerate USB devices that could be measurement instruments.

    Hubs, keyboards/mice (HID), storage, audio, and video devices are
    excluded.  Everything else – including USBTMC, vendor-specific class,
    and CDC-based instruments – is returned.
    """
    try:
        import usb.core
    except ImportError:
        return {"devices": [], "error": "pyusb not installed"}

    devices = []
    try:
        found = usb.core.find(find_all=True) or []
    except Exception as exc:
        return {"devices": [], "error": str(exc)}

    for dev in found:
        try:
            if not _is_instrument_candidate(dev):
                continue
            ser  = ""
            prod = ""
            mfr  = ""
            try:
                ser  = dev.serial_number  if dev.iSerialNumber  else ""
            except Exception:
                pass
            try:
                prod = dev.product        if dev.iProduct       else ""
            except Exception:
                pass
            try:
                mfr  = dev.manufacturer   if dev.iManufacturer  else ""
            except Exception:
                pass
            visa = f"USB0::0x{dev.idVendor:04x}::0x{dev.idProduct:04x}::{ser}::INSTR"
            devices.append({
                "visa_string":  visa,
                "manufacturer": mfr,
                "product":      prod,
                "vid":          f"0x{dev.idVendor:04x}",
                "pid":          f"0x{dev.idProduct:04x}",
                "serial":       ser,
            })
        except Exception:
            pass

    return {"devices": devices}


@router.get("/status")
def status():
    mgr = TerminalManager.get()
    if not mgr.is_connected:
        return {"connected": False}
    cfg = mgr.config
    return {"connected": True, "interface": cfg.interface}


@router.post("/send")
async def send(req: SendRequest):
    mgr = TerminalManager.get()
    if not mgr.is_connected:
        raise HTTPException(status_code=400, detail="Not connected.")

    command = req.command.strip()
    if not command:
        raise HTTPException(status_code=400, detail="Empty command.")

    # Append user-selected line ending; VISA layer may also add its own terminator
    full_command = command + req.line_ending
    is_query     = "?" in command
    timestamp    = time.time()

    try:
        if is_query:
            response = await asyncio.to_thread(mgr.query, full_command)
            return {
                "ok":        True,
                "command":   command,
                "response":  response.strip(),
                "timestamp": timestamp,
            }
        else:
            await asyncio.to_thread(mgr.write, full_command)
            return {
                "ok":        True,
                "command":   command,
                "response":  None,
                "timestamp": timestamp,
            }
    except Exception as exc:
        # Return error as application-level response (not HTTP error)
        # so the frontend can display it in the RX pane
        return {
            "ok":        False,
            "command":   command,
            "response":  None,
            "error":     str(exc),
            "timestamp": timestamp,
        }
