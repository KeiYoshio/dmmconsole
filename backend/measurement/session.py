"""
Measurement session – manages the streaming measurement loop.

One session exists per server process.  The WebSocket handler calls
start() / stop(), and the stream() async generator yields results.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import AsyncGenerator, TYPE_CHECKING

if TYPE_CHECKING:
    from ..instruments.base import InstrumentBase, MeasurementResult


class MeasurementSession:
    """Singleton measurement session."""

    _instance: "MeasurementSession | None" = None

    @classmethod
    def get(cls) -> "MeasurementSession":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._instrument: "InstrumentBase | None" = None
        self._running:    bool   = False
        self._interval_ms: float = 500.0
        self._buffer:     deque  = deque(maxlen=2000)
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------

    def set_instrument(self, instrument: "InstrumentBase") -> None:
        self._instrument = instrument

    def clear_instrument(self) -> None:
        self._running    = False
        self._instrument = None

    @property
    def is_running(self) -> bool:
        return self._running

    def get_buffer(self) -> list:
        return list(self._buffer)

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    async def stream(
        self,
        interval_ms: float = 500.0,
        max_points: int = 0,
    ) -> AsyncGenerator[dict, None]:
        """
        Async generator that yields measurement result dicts.

        The caller is responsible for calling stop() to end the loop.
        """
        if self._instrument is None:
            raise RuntimeError("No instrument connected.")
        if self._running:
            raise RuntimeError("Stream already running.")

        self._running     = True
        self._interval_ms = interval_ms
        count = 0
        consecutive_errors = 0

        try:
            while self._running:
                t0 = time.monotonic()

                async with self._lock:
                    try:
                        result: "MeasurementResult" = await asyncio.to_thread(
                            self._instrument.measure
                        )
                        data = result.to_dict()
                        self._buffer.append(data)
                        consecutive_errors = 0
                        yield data
                    except Exception as exc:
                        consecutive_errors += 1
                        yield {"error": str(exc), "timestamp": time.time()}
                        if consecutive_errors >= 3:
                            break

                count += 1
                if max_points and count >= max_points:
                    break

                elapsed  = time.monotonic() - t0
                sleep_s  = max(0.0, interval_ms / 1000.0 - elapsed)
                await asyncio.sleep(sleep_s)
        finally:
            self._running = False

    def stop(self) -> None:
        self._running = False

    # ------------------------------------------------------------------
    # Single measurement (for REST endpoint, serialised with lock)
    # ------------------------------------------------------------------

    async def measure_once(self) -> dict:
        if self._instrument is None:
            raise RuntimeError("No instrument connected.")
        async with self._lock:
            result = await asyncio.to_thread(self._instrument.measure)
        return result.to_dict()
