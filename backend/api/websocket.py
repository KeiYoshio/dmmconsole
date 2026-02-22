"""WebSocket endpoint for real-time measurement streaming."""

from __future__ import annotations

import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..measurement.session import MeasurementSession

websocket_router = APIRouter()


@websocket_router.websocket("/ws/stream")
async def stream(ws: WebSocket) -> None:
    """
    Protocol (JSON messages):

    Client → Server:
      {"action": "start",  "interval_ms": 200}
      {"action": "stop"}
      {"action": "config", "interval_ms": 500}   ← change interval while running

    Server → Client:
      {"value": -5.97e-6, "unit": "V", "function": "DCV",
       "range": "AUTO", "timestamp": 1712345678.9,
       "value_str": "-5.97 μV"}

      {"error": "description", "timestamp": ...}   ← on instrument error
      {"status": "started" | "stopped"}
    """
    await ws.accept()
    sess = MeasurementSession.get()
    stream_task: asyncio.Task | None = None

    async def _do_stream(interval_ms: float) -> None:
        try:
            await ws.send_json({"status": "started"})
            async for data in sess.stream(interval_ms=interval_ms):
                await ws.send_json(data)
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            try:
                await ws.send_json({"error": str(exc)})
            except Exception:
                pass
        finally:
            await ws.send_json({"status": "stopped"})

    try:
        while True:
            msg = await ws.receive_json()
            action = msg.get("action", "")

            if action == "start":
                if stream_task and not stream_task.done():
                    sess.stop()
                    await asyncio.sleep(0.05)
                interval_ms = float(msg.get("interval_ms", 500))
                stream_task = asyncio.create_task(_do_stream(interval_ms))

            elif action == "stop":
                sess.stop()
                if stream_task:
                    await stream_task
                    stream_task = None

            elif action == "config":
                # Hot-change interval: stop current stream, restart with new interval
                if sess.is_running:
                    sess.stop()
                    if stream_task:
                        await stream_task
                    interval_ms = float(msg.get("interval_ms", 500))
                    stream_task = asyncio.create_task(_do_stream(interval_ms))

    except WebSocketDisconnect:
        pass
    finally:
        sess.stop()
        if stream_task and not stream_task.done():
            stream_task.cancel()
