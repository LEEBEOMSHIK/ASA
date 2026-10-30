"""Authenticated, change-driven snapshots. Keepalives never query the database."""
import asyncio
import json
import time
from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import UUID

from fastapi import Request
from starlette.responses import StreamingResponse

from asa.database import changes

STREAM_LIFETIME = 45.0
KEEPALIVE_SECONDS = 15.0


def snapshot_stream(request: Request, load: Callable[[], Any],
                    dsn: str, workspace: UUID) -> StreamingResponse:
    hub = changes(dsn)
    scope = str(workspace)
    version = hub.version(scope, 'state')
    initial = load()  # Subscribe before initial read: no subscribe/snapshot race.

    async def events() -> AsyncIterator[str]:
        deadline = time.monotonic() + STREAM_LIFETIME
        keepalive = time.monotonic() + KEEPALIVE_SECONDS
        previous = json.dumps(initial, ensure_ascii=False, default=str)
        observed = version
        yield 'retry: 1500\n\n'
        yield f'event: snapshot\ndata: {previous}\n\n'
        while not await request.is_disconnected():
            if time.monotonic() >= deadline:
                break  # Reconnect revalidates auth and reconciles a lost notification.
            await asyncio.sleep(0.25)  # Memory-only revision check, not a DB poll.
            current = hub.version(scope, 'state')
            if current != observed:
                observed = current
                try:
                    snapshot = await asyncio.to_thread(load)
                except Exception:
                    yield 'event: unavailable\ndata: {}\n\n'
                    break
                encoded = json.dumps(snapshot, ensure_ascii=False, default=str)
                if encoded != previous:
                    yield f'event: snapshot\ndata: {encoded}\n\n'
                    previous = encoded
                    keepalive = time.monotonic() + KEEPALIVE_SECONDS
            if time.monotonic() >= keepalive:
                yield ': keepalive\n\n'
                keepalive = time.monotonic() + KEEPALIVE_SECONDS

    return StreamingResponse(events(), media_type='text/event-stream', headers={
        'Cache-Control': 'no-cache, no-store, no-transform', 'X-Accel-Buffering': 'no',
        'Content-Encoding': 'identity',
    })
