"""Serve workspace media from PostgreSQL without reading the full blob for a seek."""

import re
from typing import Any
from uuid import UUID

from fastapi import Response
from psycopg import Connection, sql

from asa.registry.schemas import RegistryError

SINGLE_RANGE = re.compile(r"bytes=([0-9]{0,18})-([0-9]{0,18})", re.IGNORECASE)


def media_response(
    conn: Connection[dict[str, Any]],
    source: str,
    keys: tuple[UUID, UUID],
    range_header: str,
    missing_code: str,
) -> Response | None:
    """Read from a static query selecting media and media_type for a single asset."""
    lookup = sql.SQL(" FROM ({}) AS source").format(sql.SQL(source))
    headers = {
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
        "Accept-Ranges": "bytes",
    }
    requested = SINGLE_RANGE.fullmatch(range_header.strip())
    status = 200
    if requested and any(requested.groups()):
        meta = conn.execute(sql.SQL("SELECT octet_length(media) AS size") + lookup, keys).fetchone()
        if meta is None:
            return None
        if not meta["size"]:
            raise RegistryError(404, missing_code)
        size = meta["size"]
        first, last = requested.groups()
        if first:
            start = int(first)
            end = min(int(last), size - 1) if last else size - 1
        else:
            start, end = max(0, size - int(last)), size - 1
        if start > end:
            headers["Content-Range"] = f"bytes */{size}"
            return Response(status_code=416, headers=headers)
        row = conn.execute(
            sql.SQL("SELECT substring(media FROM %s FOR %s) AS media,media_type") + lookup,
            (start + 1, end - start + 1, *keys),
        ).fetchone()
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        status = 206
    else:
        row = conn.execute(sql.SQL("SELECT media,media_type") + lookup, keys).fetchone()
    if row is None:
        return None
    if not row["media"]:
        raise RegistryError(404, missing_code)
    return Response(
        bytes(row["media"]), media_type=row["media_type"], status_code=status, headers=headers,
    )
