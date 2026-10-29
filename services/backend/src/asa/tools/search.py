"""Fixed-host web search adapter. No crawling, redirects or automatic retry."""

from typing import Any
from urllib.parse import urlsplit

import httpx

from asa.config import Settings

SEARCH_ID = "asa.web.search:1"
RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["results"],
    "properties": {
        "results": {
            "type": "array",
            "maxItems": 10,
            "items": {
                "type": "object",
                "required": ["title", "url", "snippet"],
                "properties": {
                    "title": {"type": "string", "maxLength": 500},
                    "url": {"type": "string", "maxLength": 2000},
                    "snippet": {"type": "string", "maxLength": 4000},
                },
            },
        },
    },
}


def search_tool() -> dict[str, Any]:
    return {
        "id": SEARCH_ID,
        "name": "웹 검색",
        "version": 1,
        "kind": "asa",
        "available": True,
        "execution_available": False,
        "description": "웹에서 제목·URL·요약을 검색합니다. 서버 API 설정이 필요합니다.",
        "usage": "검색어와 개수(1~10)를 연결하세요. 샘플 테스트는 API를 호출하지 않습니다.",
        "input_schema": {
            "type": "object",
            "required": ["query", "count"],
            "properties": {
                "query": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 600,
                    "description": "검색어",
                },
                "count": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "description": "가져올 결과 개수",
                },
            },
        },
        "output_schema": RESULT_SCHEMA,
        "example_input": {"query": "고양이 행동", "count": 3},
        "example_output": {
            "results": [
                {
                    "title": "고양이가 상자를 좋아하는 이유",
                    "url": "https://example.com/cats",
                    "snippet": "검증용 샘플 요약입니다.",
                }
            ]
        },
        "side_effect": "read",
        "cost": "provider",
        "dependencies": ["brave_search"],
    }


def search_ready(settings: Settings) -> bool:
    return bool(settings.search_enabled and settings.search_api_key.get_secret_value().strip())


def web_search(settings: Settings, value: dict[str, Any]) -> dict[str, Any]:
    query, count = value.get("query"), value.get("count")
    if (
        not search_ready(settings)
        or not isinstance(query, str)
        or not query.strip()
        or len(query) > 600
        or len(query.split()) > 75
        or type(count) is not int
        or not 1 <= count <= 10
    ):
        raise ValueError("search_configuration_or_input")
    try:
        with httpx.Client(timeout=20, follow_redirects=False) as client:
            with client.stream(
                "GET",
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": count, "text_decorations": "false"},
                headers={"X-Subscription-Token": settings.search_api_key.get_secret_value()},
            ) as response:
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > 2_000_000:
                        raise ValueError("search_response_too_large")
                import json

                payload = json.loads(data)
        rows = payload.get("web", {}).get("results", [])
        if not isinstance(rows, list):
            raise ValueError("invalid_search_response")
        results = []
        for row in rows[:count]:
            title, url, snippet = row.get("title"), row.get("url"), row.get("description") or ""
            if not all(isinstance(v, str) for v in (title, url, snippet)) or urlsplit(
                url
            ).scheme not in ("http", "https"):
                raise ValueError("invalid_search_result")
            results.append({"title": title[:500], "url": url[:2000], "snippet": snippet[:4000]})
        return {"results": results}
    except Exception:
        # Do not expose provider bodies, request query or credentials in errors.
        raise ValueError("search_request_failed") from None
