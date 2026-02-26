"""
Instrument registry.

To add a new instrument:
  1. Implement its class (subclass InstrumentBase)
  2. Add one entry to REGISTRY below
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import InstrumentBase

from .dmm.hp34401a    import HP34401A
from .dmm.keithley2000 import Keithley2000
from .dmm.keithley2010 import Keithley2010
from .dmm.ad7451a     import AD7451A
from .dmm.ad7451a_usb import AD7451A_USB

# model_id → class
REGISTRY: dict[str, type[InstrumentBase]] = {
    "hp34401a":     HP34401A,
    "keithley2000": Keithley2000,
    "keithley2010": Keithley2010,
    "ad7451a":      AD7451A,
    "ad7451a_usb":  AD7451A_USB,
}


def list_models() -> list[dict]:
    """Return summary info for all registered models."""
    result = []
    for model_id, cls in REGISTRY.items():
        cap = cls.static_capability()
        result.append({
            "id":           model_id,
            "model":        cap.model,
            "manufacturer": cap.manufacturer,
            "type":         cap.instrument_type,
        })
    return result


def create(model_id: str, resource) -> "InstrumentBase":
    """Instantiate an instrument by model id, wrapping the given VISA resource."""
    if model_id not in REGISTRY:
        raise ValueError(f"Unknown instrument model: {model_id!r}. "
                         f"Known: {list(REGISTRY)}")
    return REGISTRY[model_id](resource)
