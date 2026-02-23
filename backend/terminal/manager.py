"""
Terminal connection manager – raw SCPI write/query without instrument model.

Independent singleton from GPIBManager so DMM and Terminal can hold
separate connections simultaneously.
"""

from __future__ import annotations

import os
import sys

# Make agilent82357b importable from the sibling GPIB directory
_HERE   = os.path.dirname(os.path.abspath(__file__))
_GPIB   = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
_A82357 = os.path.join(_GPIB, "agilent82357b")
if _A82357 not in sys.path:
    sys.path.insert(0, _A82357)


class TerminalConfig:
    def __init__(
        self,
        interface:   str,
        gpib_addr:   int = 6,
        ip_address:  str = "",
        visa_string: str = "",
    ) -> None:
        self.interface   = interface
        self.gpib_addr   = gpib_addr
        self.ip_address  = ip_address
        self.visa_string = visa_string


class TerminalManager:
    """Singleton that owns one raw VISA/GPIB resource for terminal use."""

    _instance: "TerminalManager | None" = None

    @classmethod
    def get(cls) -> "TerminalManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._rm       = None
        self._resource = None
        self._config:  TerminalConfig | None = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._resource is not None

    @property
    def config(self) -> TerminalConfig | None:
        return self._config

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self, config: TerminalConfig) -> None:
        if self.is_connected:
            self.disconnect()

        if config.interface == "gpib":
            import agilent82357b
            rm = agilent82357b.ResourceManager()
            resource_str = f"GPIB0::{config.gpib_addr}::INSTR"
            self._rm = rm
            self._resource = rm.open_resource(resource_str)

        elif config.interface == "lan":
            try:
                import pyvisa
            except ImportError:
                raise RuntimeError(
                    "pyvisa is required for LAN connections. "
                    "Install with: pip install pyvisa pyvisa-py"
                )
            rm = pyvisa.ResourceManager()
            resource_str = config.visa_string or f"TCPIP0::{config.ip_address}::inst0::INSTR"
            self._rm = rm
            self._resource = rm.open_resource(resource_str)

        elif config.interface == "usb":
            try:
                import pyvisa
                rm = pyvisa.ResourceManager()
                self._rm = rm
                self._resource = rm.open_resource(config.visa_string)
            except Exception:
                # Fall back to raw pyusb + USBTMC framing
                from ..gpib.usbtmc_raw import USBTMCResource, parse_visa_usb
                if self._rm is not None:
                    try:
                        self._rm.close()
                    except Exception:
                        pass
                    self._rm = None
                vid, pid, serial = parse_visa_usb(config.visa_string)
                self._resource = USBTMCResource(vid, pid, serial)

        else:
            raise ValueError(f"Unknown interface: {config.interface!r}")

        self._config = config

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

    # ------------------------------------------------------------------
    # Raw SCPI operations
    # ------------------------------------------------------------------

    def write(self, command: str) -> None:
        if self._resource is None:
            raise RuntimeError("Not connected")
        self._resource.write(command)

    def query(self, command: str) -> str:
        if self._resource is None:
            raise RuntimeError("Not connected")
        return self._resource.query(command)
