import asyncio
from uuid import uuid4

from asa.registry import sse


class Hub:
    value = 0

    def version(self, *args):
        return self.value


class Request:
    async def is_disconnected(self):
        return False


def test_sse_idle_keeps_connection_without_database_reload(monkeypatch):
    hub = Hub()
    monkeypatch.setattr(sse, 'changes', lambda dsn: hub)
    monkeypatch.setattr(sse, 'STREAM_LIFETIME', 0.6)
    monkeypatch.setattr(sse, 'KEEPALIVE_SECONDS', 0.1)
    calls = []

    def load():
        calls.append(1)
        return {'value': 'initial'}

    response = sse.snapshot_stream(Request(), load, 'test', uuid4())

    async def collect():
        return [part async for part in response.body_iterator]

    parts = asyncio.run(collect())
    assert len(calls) == 1
    assert sum('event: snapshot' in p for p in parts) == 1
    assert any('keepalive' in p for p in parts)


def test_sse_commit_during_initial_read_is_not_missed(monkeypatch):
    hub = Hub()
    monkeypatch.setattr(sse, 'changes', lambda dsn: hub)
    monkeypatch.setattr(sse, 'STREAM_LIFETIME', 0.6)
    calls = []

    def load():
        calls.append(1)
        if len(calls) == 1:
            hub.value += 1
            return {'value': 'before'}
        return {'value': 'after'}

    response = sse.snapshot_stream(Request(), load, 'test', uuid4())

    async def collect():
        return [part async for part in response.body_iterator]

    parts = asyncio.run(collect())
    assert len(calls) == 2
    assert any('before' in p for p in parts)
    assert any('after' in p for p in parts)
