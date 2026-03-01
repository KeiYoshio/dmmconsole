"""
Serial communication resource for FY6800 DDS Signal Generator / Counter.

Provides a pyvisa-compatible API (write / read / query / close) over
pyserial, so it can be used as a drop-in resource for InstrumentBase
subclasses.

Protocol: 115200 bps, 8N1, LF-terminated ASCII text commands.
"""

from __future__ import annotations

import logging
import time

import serial
from serial.tools import list_ports

_log = logging.getLogger(__name__)

# Post-write delay – FY6800 needs a short gap between commands
_CMD_DELAY = 0.05  # 50 ms


class FY6800Serial:
    """Serial resource wrapper with pyvisa-compatible API."""

    def __init__(self, port: str, baudrate: int = 115200) -> None:
        self._port = port
        self._baudrate = baudrate
        self._ser: serial.Serial | None = None
        self._open()

    def _open(self) -> None:
        _log.info("FY6800Serial: opening %s @ %d", self._port, self._baudrate)
        self._ser = serial.Serial(
            port=self._port,
            baudrate=self._baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=2.0,
        )
        time.sleep(0.1)
        self._ser.reset_input_buffer()

    def write(self, cmd: str) -> None:
        """Send a command (no response expected)."""
        if self._ser is None or not self._ser.is_open:
            raise RuntimeError("Serial port not open")
        self._ser.reset_input_buffer()
        self._ser.write((cmd + "\n").encode("ascii"))
        time.sleep(_CMD_DELAY)

    def write_bytes(self, data: bytes) -> None:
        """Send raw bytes without LF termination or delay."""
        if self._ser is None or not self._ser.is_open:
            raise RuntimeError("Serial port not open")
        self._ser.write(data)
        self._ser.flush()

    def read(self) -> str:
        """Read a response line."""
        if self._ser is None or not self._ser.is_open:
            raise RuntimeError("Serial port not open")
        return self._ser.readline().decode("ascii", errors="replace").strip()

    def query(self, cmd: str) -> str:
        """Send a command and return the response."""
        self.write(cmd)
        return self.read()

    def close(self) -> None:
        """Close the serial port."""
        if self._ser is not None and self._ser.is_open:
            _log.info("FY6800Serial: closing %s", self._port)
            self._ser.close()
        self._ser = None

    @property
    def port(self) -> str:
        return self._port


def list_serial_ports() -> list[dict]:
    """Return list of available serial ports with metadata."""
    result = []
    for p in list_ports.comports():
        result.append({
            "port": p.device,
            "description": p.description,
            "hwid": p.hwid,
            "manufacturer": p.manufacturer or "",
            "product": p.product or "",
            "vid": f"0x{p.vid:04X}" if p.vid else "",
            "pid": f"0x{p.pid:04X}" if p.pid else "",
        })
    return result
