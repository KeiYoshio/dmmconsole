"""
Raw USB-TMC communication for vendor-specific USB instruments (class 0xFF)
that implement the USB-TMC bulk protocol without standard class descriptors.

Confirmed working with: ADVANTEST / ADCMT AD7451A over USB.

Key discovery (2026-02-25): USB488 REN_CONTROL must be sent after opening
the device to switch it from local mode to remote mode.  Without this,
the instrument ignores all commands except *RST.

Usage (from routes.py):
    from ..gpib.usbtmc_raw import USBTMCResource, parse_visa_usb
    vid, pid, serial = parse_visa_usb(visa_string)
    resource = USBTMCResource(vid, pid, serial)
    resource.write("F1")
    result = resource.read()      # sends REQUEST_IN then reads BULK IN
    result = resource.query("*IDN?")
"""

from __future__ import annotations

import logging
import struct
import time

import usb.core
import usb.util

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# USB endpoint addresses (AD7451A)
# ---------------------------------------------------------------------------
_EP_OUT  = 0x02   # BULK OUT  (host → device, commands)
_EP_IN   = 0x81   # BULK IN   (device → host, responses)
_IFACE   = 0      # USB interface index

_WRITE_TIMEOUT_MS = 5_000   # 5 s
_READ_TIMEOUT_MS  = 10_000  # 10 s (covers NPLC=100 at 50 Hz ≈ 2 s)
_CT_TIMEOUT_MS    = 2_000   # 2 s for control transfers

# ---------------------------------------------------------------------------
# USB488 control transfer constants
# ---------------------------------------------------------------------------
_USBTMC_CLASS_IN = 0xA1   # bmRequestType: IN, Class, Interface


# ---------------------------------------------------------------------------
# VISA string parser
# ---------------------------------------------------------------------------

def parse_visa_usb(visa_str: str) -> tuple[int, int, str | None]:
    """Parse 'USB0::0x1334::0x0202::662500377::INSTR' → (vid, pid, serial)."""
    parts = visa_str.strip().split("::")
    if len(parts) < 3:
        raise ValueError(f"Cannot parse USB VISA string: {visa_str!r}")
    vid    = int(parts[1], 0)
    pid    = int(parts[2], 0)
    serial = parts[3] if len(parts) >= 5 and parts[3] != "INSTR" else None
    return vid, pid, serial


# ---------------------------------------------------------------------------
# USBTMC packet builders
# ---------------------------------------------------------------------------

def _make_out(payload: bytes, tag: int) -> bytes:
    """USBTMC DEV_DEP_MSG_OUT packet (MsgID=1)."""
    pad = (4 - len(payload) % 4) % 4
    return struct.pack(
        "<BBBBIBBBB",
        0x01, tag, (~tag) & 0xFF, 0x00,   # MsgID, bTag, ~bTag, reserved
        len(payload),                       # TransferSize (LE)
        0x01, 0x00, 0x00, 0x00,            # EOM=1, reserved×3
    ) + payload + bytes(pad)


def _make_req(tag: int, req_size: int = 256) -> bytes:
    """USBTMC REQUEST_DEV_DEP_MSG_IN packet (MsgID=2)."""
    return struct.pack(
        "<BBBBIBBBB",
        0x02, tag, (~tag) & 0xFF, 0x00,
        req_size,
        0x00, 0x00, 0x00, 0x00,
    )


def _make_trigger(tag: int) -> bytes:
    """USB488 TRIGGER message (MsgID=128/0x80) — 12-byte header, no payload.

    This is how ausb_trigger() sends a Group Execute Trigger (GET) to the
    instrument.  It is NOT the same as sending ``*TRG\\n`` as a text command
    via DEV_DEP_MSG_OUT.
    """
    return struct.pack(
        "<BBBBIBBBB",
        0x80, tag, (~tag) & 0xFF, 0x00,   # MsgID=TRIGGER, bTag, ~bTag, reserved
        0,                                  # TransferSize = 0
        0x00, 0x00, 0x00, 0x00,            # reserved
    )


# ---------------------------------------------------------------------------
# Resource class
# ---------------------------------------------------------------------------

class USBTMCResource:
    """
    pyvisa-compatible resource wrapper using raw pyusb + USBTMC framing.

    Implements .write(), .read(), .query() so it can be used as a drop-in
    replacement for a pyvisa resource object in instrument drivers.
    """

    def __init__(self, vid: int, pid: int, serial: str | None = None) -> None:
        self._vid        = vid
        self._pid        = pid
        self._serial     = serial
        self._tag        = 0
        self._dev: usb.core.Device | None = None
        self._reinit_cb  = None
        self._open()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _open(self) -> None:
        dev = self._find()
        if dev is None:
            raise RuntimeError(
                f"USB device {self._vid:#06x}:{self._pid:#06x} not found."
            )
        # Reset clears any stale endpoint STALL state
        dev.reset()
        time.sleep(1.2)

        dev = self._find()
        if dev is None:
            raise RuntimeError("Device disappeared after USB reset.")

        try:
            dev.set_configuration()
        except Exception:
            pass
        try:
            dev.set_auto_detach_kernel_driver(True)
        except Exception:
            pass
        usb.util.claim_interface(dev, _IFACE)

        # Drain any pending data left in BULK IN
        try:
            dev.read(_EP_IN, 256, timeout=500)
        except usb.core.USBTimeoutError:
            pass

        self._dev = dev
        self._usb488_init()

    def _find(self) -> "usb.core.Device | None":
        kwargs: dict = {"idVendor": self._vid, "idProduct": self._pid}
        return usb.core.find(**kwargs)

    def _next_tag(self) -> int:
        self._tag = (self._tag % 127) + 1
        return self._tag

    def _reopen(self) -> None:
        """Full recovery: close old handle, reset device, re-claim interface.

        Called on errno 2 (LIBUSB_ERROR_NOT_FOUND) or errno 19 (NO_DEVICE).
        After this, the instrument driver must re-initialize the device
        (re-send H0, TRS3, INIC0, function, range, NPLC).
        """
        # Close old handle completely so macOS releases the IOKit interface
        try:
            usb.util.release_interface(self._dev, _IFACE)
        except Exception:
            pass
        try:
            usb.util.dispose_resources(self._dev)
        except Exception:
            pass
        self._dev = None

        # Find device and do hardware reset to clear IOKit pipe state
        dev = self._find()
        if dev is None:
            raise RuntimeError(
                f"USB device {self._vid:#06x}:{self._pid:#06x} not found during recovery."
            )
        dev.reset()
        time.sleep(0.8)

        dev = self._find()
        if dev is None:
            raise RuntimeError("Device disappeared after recovery reset.")
        try:
            dev.set_configuration()
        except Exception:
            pass
        try:
            dev.set_auto_detach_kernel_driver(True)
        except Exception:
            pass
        usb.util.claim_interface(dev, _IFACE)

        # Drain any pending data
        try:
            dev.read(_EP_IN, 256, timeout=300)
        except usb.core.USBTimeoutError:
            pass

        self._dev = dev
        self._usb488_init()

        # Notify instrument driver to re-initialize
        if self._reinit_cb is not None:
            try:
                self._reinit_cb()
            except Exception:
                pass

    def _usb488_init(self) -> None:
        """USB488 initialization sequence (equivalent to ausb_open()).

        Sends the control transfers required to put the instrument into
        remote mode.  Without REN_CONTROL, the device ignores all commands
        except *RST.
        """
        dev = self._dev

        # 1. Vendor IN CT 0xC1/0xF5 (ausb_open equivalent)
        try:
            r = bytes(dev.ctrl_transfer(0xC1, 0xF5, 0, 0, 1, timeout=_CT_TIMEOUT_MS))
            _log.debug("USB488 init: Vendor CT 0xF5 → 0x%02X", r[0])
        except Exception as e:
            _log.warning("USB488 init: Vendor CT 0xF5 failed: %s", e)

        # 2. GET_CAPABILITIES
        try:
            r = bytes(dev.ctrl_transfer(
                _USBTMC_CLASS_IN, 0x07, 0, _IFACE, 24, timeout=_CT_TIMEOUT_MS))
            _log.debug("USB488 init: GET_CAPABILITIES status=0x%02X", r[0])
        except Exception as e:
            _log.warning("USB488 init: GET_CAPABILITIES failed: %s", e)

        # 3. REN_CONTROL — assert Remote Enable (the key step!)
        try:
            r = bytes(dev.ctrl_transfer(
                _USBTMC_CLASS_IN, 0xA0, 1, _IFACE, 1, timeout=_CT_TIMEOUT_MS))
            status = {0x01: "SUCCESS", 0x81: "FAILED"}.get(r[0], f"0x{r[0]:02X}")
            _log.info("USB488 init: REN_CONTROL → %s", status)
            if r[0] != 0x01:
                _log.error("USB488 REN_CONTROL failed — device may stay in local mode")
        except Exception as e:
            _log.error("USB488 init: REN_CONTROL failed: %s", e)

        # 4. INITIATE_CLEAR + CHECK_CLEAR_STATUS
        try:
            r = bytes(dev.ctrl_transfer(
                _USBTMC_CLASS_IN, 0x05, 0, _IFACE, 1, timeout=_CT_TIMEOUT_MS))
            _log.debug("USB488 init: INITIATE_CLEAR → 0x%02X", r[0])
        except Exception as e:
            _log.warning("USB488 init: INITIATE_CLEAR failed: %s", e)
        time.sleep(0.2)

        try:
            r = bytes(dev.ctrl_transfer(
                _USBTMC_CLASS_IN, 0x06, 0, _IFACE, 2, timeout=_CT_TIMEOUT_MS))
            _log.debug("USB488 init: CHECK_CLEAR_STATUS → 0x%02X", r[0])
        except Exception as e:
            _log.warning("USB488 init: CHECK_CLEAR_STATUS failed: %s", e)
        time.sleep(0.3)

        # Drain any residual data after init
        for _ in range(4):
            try:
                dev.read(_EP_IN, 512, timeout=200)
            except Exception:
                break

    def read_status_byte(self) -> int:
        """USB488 READ_STATUS_BYTE — returns STB (0–255) or 0 on error.

        IMPORTANT: Must never return a value with bit 4 set on error,
        because the caller uses ``stb & 0x10`` to detect MAV.
        """
        try:
            tag = self._next_tag()
            resp = bytes(self._dev.ctrl_transfer(
                _USBTMC_CLASS_IN, 0x80, tag, _IFACE, 3, timeout=_CT_TIMEOUT_MS))
            return resp[2] if len(resp) >= 3 else 0
        except Exception:
            return 0

    def go_to_local(self) -> None:
        """USB488 GO_TO_LOCAL — return instrument to front-panel control."""
        try:
            r = bytes(self._dev.ctrl_transfer(
                _USBTMC_CLASS_IN, 0xA1, 0, _IFACE, 1, timeout=_CT_TIMEOUT_MS))
            status = {0x01: "SUCCESS", 0x81: "FAILED"}.get(r[0], f"0x{r[0]:02X}")
            _log.info("USB488 GO_TO_LOCAL → %s", status)
        except Exception as e:
            _log.warning("USB488 GO_TO_LOCAL failed: %s", e)

    def trigger(self) -> None:
        """Send USB488 TRIGGER (MsgID=0x80) via BULK OUT.

        This is the USB equivalent of IEEE 488.1 Group Execute Trigger (GET).
        ausb_trigger() uses this method — NOT a text ``*TRG`` command.
        """
        tag = self._next_tag()
        pkt = _make_trigger(tag)
        try:
            self._dev.write(_EP_OUT, pkt, timeout=_WRITE_TIMEOUT_MS)
        except usb.core.USBError as e:
            if e.errno in (2, 19):
                self._reopen()
                self._dev.write(_EP_OUT, pkt, timeout=_WRITE_TIMEOUT_MS)
            else:
                raise

    def set_reinit_callback(self, cb) -> None:
        """Register a callback invoked after USB recovery (e.g. re-send H0/TRS3)."""
        self._reinit_cb = cb

    # ------------------------------------------------------------------
    # Public interface (matches pyvisa resource API)
    # ------------------------------------------------------------------

    def write(self, cmd: str) -> None:
        """Send command as USBTMC DEV_DEP_MSG_OUT packet.

        The AD7451A firmware uses LF (0x0A) as the ADC command terminator
        (mirroring GPIB behaviour). Without a trailing LF the instrument
        buffers the bytes but never executes the command.  ausb.dll appends
        0x0A at RVA 0x2cae8 before calling WinUsb_WritePipe.

        Retries once with full device recovery on errno 2 or 19.
        """
        if isinstance(cmd, str):
            payload = (cmd + "\n").encode()
        else:
            payload = cmd if cmd.endswith(b"\n") else cmd + b"\n"
        tag = self._next_tag()
        pkt = _make_out(payload, tag)
        try:
            self._dev.write(_EP_OUT, pkt, timeout=_WRITE_TIMEOUT_MS)
        except usb.core.USBError as e:
            if e.errno in (2, 19):   # NOT_FOUND or NO_DEVICE
                self._reopen()
                self._dev.write(_EP_OUT, pkt, timeout=_WRITE_TIMEOUT_MS)
            else:
                raise

    def read(self) -> str:
        """Request a response (REQUEST_DEV_DEP_MSG_IN) then read BULK IN."""
        tag = self._next_tag()
        req = _make_req(tag)
        try:
            self._dev.write(_EP_OUT, req, timeout=_WRITE_TIMEOUT_MS)
        except usb.core.USBError as e:
            if e.errno in (2, 19):
                self._reopen()
                self._dev.write(_EP_OUT, req, timeout=_WRITE_TIMEOUT_MS)
            else:
                raise
        raw = bytes(self._dev.read(_EP_IN, 256, timeout=_READ_TIMEOUT_MS))
        # Strip 12-byte USBTMC response header, decode payload
        return raw[12:].decode(errors="replace").strip()

    def query(self, cmd: str) -> str:
        """Send command and read response in one call."""
        self.write(cmd)
        return self.read()

    def close(self) -> None:
        if self._dev is not None:
            self.go_to_local()
            try:
                usb.util.release_interface(self._dev, _IFACE)
            except Exception:
                pass
            self._dev = None
