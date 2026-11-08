"""Bounded plain-text excerpts for library cards; stored source is never changed."""

import re
from typing import Any


def excerpt(content: Any) -> str:
    parts: list[str] = []
    remaining = 320

    def visit(value: Any, depth: int = 0) -> None:
        nonlocal remaining
        if remaining <= 0 or depth > 8:
            return
        if isinstance(value, str):
            text = re.sub(r"(?m)^\s{0,3}(?:#{1,6}\s+|[-*]\s+|---+\s*$)", "", value[:2000])
            text = " ".join(text.replace("**", "").replace("__", "").split())
            if text and not text.startswith(("http://", "https://", "data:")):
                part = text[:remaining]
                parts.append(part)
                remaining -= len(part) + 3
        elif isinstance(value, list):
            for item in value[:12]:
                visit(item, depth + 1)
        elif isinstance(value, dict):
            for key, item in value.items():
                if key not in {"id", "url", "media_url", "model", "provider"} and not key.endswith(
                    ("_id", "_url")
                ):
                    visit(item, depth + 1)

    visit(content)
    return " · ".join(parts)[:320]
