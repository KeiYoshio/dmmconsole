"""
GPIB / VISA connection manager (singleton).

Supports:
  - GPIB via agilent82357b (interface="gpib")
  - LAN/VXI-11 via pyvisa (interface="lan")   ← requires: pip install pyvisa pyvisa-py
  - USB-TMC via pyvisa    (interface="usb")   ← requires: pip install pyvisa pyvisa-py
"""

from __future__ import annotations

import os
import sys

# ---------------------------------------------------------------------------
# Make agilent82357b importable from the sibling directory
# ---------------------------------------------------------------------------
_HERE   = os.path.dirname(os.path.abspath(__file__))
_GPIB   = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))   # …/GPIB/
_A82357 = os.path.join(_GPIB, "agilent82357b")
if _A82357 not in sys.path:
    sys.path.insert(0, _A82357)


class ConnectionConfig:
    def __init__(
        self,
        interface: str,         # "gpib" | "lan" | "usb" | "serial"
        model_id:  str,
        gpib_addr: int  = 0,
        ip_address: str = "",
        visa_string: str = "",  # full VISA resource string for usb/lan
        serial_port: str = "",  # serial port path for serial interface
    ) -> None:
        self.interface   = interface
        self.model_id    = model_id
        self.gpib_addr   = gpib_addr
        self.ip_address  = ip_address
        self.visa_string = visa_string
        self.serial_port = serial_port


class GPIBManager:
    """Singleton that owns the ResourceManager and the open resource."""

    _instance: "GPIBManager | None" = None

    @classmethod
    def get(cls) -> "GPIBManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._rm       = None
        self._resource = None
        self._config:  ConnectionConfig | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._resource is not None

    @property
    def config(self) -> ConnectionConfig | None:
        return self._config

    def connect(self, config: ConnectionConfig):
        """Open a VISA resource and return it."""
        if self.is_connected:
            self.disconnect()

        if config.interface == "serial":
            from .serial_resource import FY6800Serial
            if not config.serial_port:
                raise ValueError("For serial connections provide a serial port path.")
            resource = FY6800Serial(config.serial_port)
            self._resource = resource
            self._config   = config
            return resource

        if config.interface == "gpib":
            import agilent82357b
            self._rm = agilent82357b.ResourceManager()
            resource_str = f"GPIB0::{config.gpib_addr}::INSTR"

        elif config.interface in ("lan", "usb"):
            try:
                import pyvisa
            except ImportError:
                raise RuntimeError(
                    "pyvisa is required for LAN/USB connections. "
                    "Install it with: pip install pyvisa pyvisa-py"
                )
            self._rm = pyvisa.ResourceManager()
            if config.visa_string:
                resource_str = config.visa_string
            elif config.interface == "lan":
                resource_str = f"TCPIP0::{config.ip_address}::inst0::INSTR"
            else:
                raise ValueError("For USB connections provide a full VISA resource string.")

        else:
            raise ValueError(f"Unknown interface: {config.interface!r}")

        self._resource = self._rm.open_resource(resource_str)
        self._config   = config
        return self._resource

    def disconnect(self) -> None:
        if self._resource is not None:
            try:
                self._resource.close()
            except Exception:
                pass
            self._resource = None
        if self._rm is not None:
            try:
                self._rm.close()
            except Exception:
                pass
            self._rm = None
        self._config = None
