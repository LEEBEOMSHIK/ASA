"""Process-local bounded pools and shared PostgreSQL change listeners."""
import atexit
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row, tuple_row
from psycopg_pool import ConnectionPool

_lock = threading.Lock()
_pools: dict[str, ConnectionPool[psycopg.Connection[Any]]] = {}
_hubs: dict[str, 'ChangeHub'] = {}


@contextmanager
def connection(dsn: str, *, dictionary: bool = False) -> Iterator[psycopg.Connection[Any]]:
    with _lock:
        pool = _pools.get(dsn)
        if pool is None:
            pool = ConnectionPool(dsn, min_size=0, max_size=8, timeout=5, max_idle=60,
                                  kwargs={'connect_timeout': 3, 'application_name': 'asa-pool'},
                                  open=True)
            _pools[dsn] = pool
    with pool.connection() as conn:
        conn.row_factory = dict_row if dictionary else tuple_row
        yield conn


class ChangeHub:
    """One LISTEN socket per process/DSN, no query on idle waits.

    Epoch changes force reconciliation after listener reconnects. Subscribers capture
    versions before reading DB, so commits during a snapshot aren't lost.
    """
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.condition = threading.Condition()
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.epoch = 0
        self.counter = 0
        self.backend_pid: int | None = None
        self.versions: dict[tuple[str, str], int] = {}
        self.thread = threading.Thread(target=self._listen, daemon=True, name='asa-db-listen')
        self.thread.start()

    def version(self, workspace: str, topic: str) -> int:
        with self.condition:
            return max(self.epoch, self.versions.get((workspace, topic), 0))

    def wait(self, workspace: str, topic: str, version: int, timeout: float) -> int:
        with self.condition:
            self.condition.wait_for(
                lambda: self.stop.is_set() or self.version(workspace, topic) != version,
                timeout=max(0, timeout))
            return self.version(workspace, topic)

    def _invalidate(self) -> None:
        with self.condition:
            self.counter += 1
            self.epoch = self.counter
            self.versions.clear()
            self.condition.notify_all()

    def _listen(self) -> None:
        while not self.stop.is_set():
            try:
                with psycopg.connect(self.dsn, autocommit=True, connect_timeout=3,
                                     application_name='asa-listener') as conn:
                    conn.execute('LISTEN asa_changes')
                    self.backend_pid = conn.info.backend_pid
                    self._invalidate()
                    self.ready.set()
                    while not self.stop.is_set():
                        for event in conn.notifies(timeout=1, stop_after=100):
                            parts = event.payload.split(':')
                            if len(parts) != 2 or parts[1] not in {
                                'state', 'script', 'image', 'automation'
                            }:
                                continue
                            try:
                                UUID(parts[0])
                            except ValueError:
                                continue
                            with self.condition:
                                self.counter += 1
                                self.versions[(parts[0], parts[1])] = self.counter
                                if len(self.versions) > 4096:
                                    self._invalidate()
                                self.condition.notify_all()
            except psycopg.Error:
                self.backend_pid = None
                self.ready.clear()
                self._invalidate()
                self.stop.wait(5)

    def close(self) -> None:
        self.stop.set()
        with self.condition:
            self.condition.notify_all()
        self.thread.join(timeout=5)


def changes(dsn: str) -> ChangeHub:
    with _lock:
        if dsn not in _hubs:
            _hubs[dsn] = ChangeHub(dsn)
        return _hubs[dsn]


def release_lock(conn: psycopg.Connection[Any], key: str) -> None:
    """Never return a session with an uncertain advisory lock to the pool."""
    try:
        conn.execute('SELECT pg_advisory_unlock(hashtextextended(%s,0))', (key,))
    except BaseException:
        conn.close()
        raise


def close_database(dsn: str | None = None) -> None:
    with _lock:
        names = {dsn} if dsn is not None else set(_pools) | set(_hubs)
        hubs = [_hubs.pop(name) for name in names if name in _hubs]
        pools = [_pools.pop(name) for name in names if name in _pools]
    for hub in hubs:
        hub.close()
    for pool in pools:
        pool.close()


atexit.register(close_database)
