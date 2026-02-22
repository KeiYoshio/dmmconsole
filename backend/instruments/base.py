"""
Abstract base classes for all instruments.

Adding a new instrument type:
  1. Subclass InstrumentBase (or a domain-specific subclass like DMMBase)
  2. Implement all abstract methods
  3. Register in instruments/registry.py
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class MeasurementResult:
    value: float
    unit: str
    function: str
    range: str
    timestamp: float = field(default_factory=time.time)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        # Format value for display
        d["value_str"] = _format_value(self.value, self.unit)
        return d


def _format_value(value: float, unit: str) -> str:
    """Return a human-readable string with SI prefix."""
    if value != value:          # NaN
        return "----"
    abs_v = abs(value)
    if abs_v == 0:
        return f"0.000000 {unit}"
    for threshold, prefix in [
        (1e-9,  "n"), (1e-6,  "μ"), (1e-3, "m"),
        (1.0,    ""), (1e3,   "k"), (1e6,  "M"),
    ]:
        if abs_v < threshold * 1000:
            scaled = value / threshold
            return f"{scaled:+.6g} {prefix}{unit}"
    return f"{value:+.6g} {unit}"


@dataclass
class Capability:
    """Describes what an instrument can do.

    The frontend uses this descriptor to dynamically build the control panel,
    so adding a new instrument does not require any frontend changes for the
    basic panel.
    """
    model: str
    manufacturer: str
    instrument_type: str          # "dmm", "scope", "source", …
    functions: list[dict]         # [{id, label, icon, unit}, …]
    ranges: dict[str, list[str]]  # function_id → [range_str, …]
    settings: list[dict]          # [{id, label, type, options, default, applicable_to}, …]

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class InstrumentBase(ABC):
    """Common interface for every instrument, regardless of type."""

    @abstractmethod
    def get_capability(self) -> Capability:
        """Return the static capability descriptor for this instrument model."""

    @abstractmethod
    def measure(self) -> MeasurementResult:
        """Perform a single measurement and return the result."""

    @abstractmethod
    def reset(self) -> None:
        """Reset the instrument to a known default state."""

    @abstractmethod
    def close(self) -> None:
        """Release any instrument-specific resources (not the VISA resource)."""

    def get_idn(self) -> str:
        """Return *IDN? response (optional – override if supported)."""
        return ""
