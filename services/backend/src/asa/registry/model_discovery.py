"""Read-only provider discovery and conservative official Markdown metadata parsing."""

import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from asa.config import ModelPrice, Settings
from asa.registry.schemas import RegistryError

Provider = Literal["openai", "anthropic"]
SAFE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,199}$")
CLAUDE_SEARCH = "https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool"


class ModelMetadata(BaseModel):
    checked_at: str
    sources: list[str] = Field(default_factory=list, max_length=5)
    web_search_supported: bool | None = None
    compatible: bool | None = None
    price: ModelPrice | None = None
    note: str = ""
    status: str = ""


def read_response(
    client: httpx.Client,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
) -> str:
    # No caller supplied URLs, redirects, response bodies or credentials in errors/logs.
    with client.stream("GET", url, headers=headers, params=params) as response:
        if response.status_code in (401, 403):
            raise RegistryError(422, "provider_auth_failed")
        if response.status_code == 429:
            raise RegistryError(429, "provider_rate_limited")
        if response.status_code != 200:
            raise RegistryError(502, "provider_lookup_failed")
        data = bytearray()
        for chunk in response.iter_bytes():
            data.extend(chunk)
            if len(data) > 1_000_000:
                raise RegistryError(502, "provider_lookup_failed")
        return data.decode("utf-8")


def discover(settings: Settings, provider: Provider) -> dict[str, Any]:
    key = settings.key_for(provider).get_secret_value().strip()
    if not key:
        raise RegistryError(422, "provider_key_missing")
    url = (
        "https://api.openai.com/v1/models"
        if provider == "openai"
        else "https://api.anthropic.com/v1/models"
    )
    headers = (
        {"Authorization": f"Bearer {key}"}
        if provider == "openai"
        else {"x-api-key": key, "anthropic-version": "2023-06-01"}
    )
    rows: dict[str, Any] = {}
    cursor = ""
    try:
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            for _ in range(10):
                params: dict[str, Any] = {} if provider == "openai" else {"limit": 100}
                if cursor:
                    params["after_id"] = cursor
                payload = json.loads(read_response(client, url, headers=headers, params=params))
                if not isinstance(payload.get("data"), list):
                    raise ValueError("invalid_data")
                for row in payload["data"]:
                    model = row.get("id", "")
                    if not isinstance(model, str) or not SAFE_ID.fullmatch(model):
                        continue
                    if row.get("lifecycle") == "retired":
                        continue
                    label = row.get("display_name") or model
                    rows[model] = {"id": model, "label": str(label)[:100], "provider": provider}
                if provider == "openai" or not payload.get("has_more"):
                    break
                next_cursor = payload.get("last_id")
                if not isinstance(next_cursor, str) or not next_cursor or next_cursor == cursor:
                    raise ValueError("invalid_cursor")
                cursor = next_cursor
            else:
                raise ValueError("too_many_pages")
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        raise RegistryError(502, "provider_lookup_failed") from None
    return {
        "models": sorted(rows.values(), key=lambda row: row["id"]),
        "checked_at": datetime.now(UTC).isoformat(),
        "source": url,
    }


def section(document: str, title: str, level: int = 2) -> str | None:
    match = re.search(
        rf"^{'#' * level} {re.escape(title)}\s*\n(.*?)(?=^#{{1,{level}}} |\Z)",
        document,
        re.M | re.S,
    )
    return match[1] if match else None


def parse_document(
    provider: Provider, model: str, document: str, search_doc: str = ""
) -> ModelMetadata:
    result = ModelMetadata(checked_at=datetime.now(UTC).isoformat())
    # A date-stripped URL is only accepted when the exact snapshot is documented there.
    if not re.search(rf"`{re.escape(model)}`", document):
        result.note = "공식 문서에서 이 모델 ID를 확인하지 못했습니다."
        return result
    tier: dict[str, Any] | None = None
    if provider == "openai":
        tools = section(document, "Supported tools")
        features = section(document, "Supported features")
        endpoints = section(document, "Endpoints") or ""
        if tools is not None:
            result.web_search_supported = bool(re.search(r"^- web_search\s*$", tools, re.M))
        if features is not None:
            result.compatible = "- structured_outputs" in features and bool(
                re.search(r"\| Chat Completions\s*\|[^\n]*\| Supported\s*\|", endpoints)
            )
        status = re.search(r"^Status: (.+)$", document, re.M)
        result.status = status[1] if status else ""
        pricing = section(document, "Text tokens", 3) or ""
        names = {
            "Input": "input",
            "Output": "output",
            "Cached input": "cache_read",
            "Cache writes": "cache_creation",
        }
        values = {}
        for metric, key in names.items():
            found = re.findall(
                rf"^\| {metric}\s*\| \$([0-9]+(?:\.[0-9]+)?) "
                r"\| 1M tokens\s*\|",
                pricing,
                re.M,
            )
            if len(found) == 1:
                values[key] = found[0]
        # Conditional tariffs cannot be represented as a single unconditional token rate.
        conditional = bool(
            re.search(
                r"(?:prompts with|prompts over|for prompts|more than|tiered|\b>\s*\d)",
                pricing,
                re.I,
            )
        )
        if "Cache writes are billed at 1.25x the uncached input token rate." in pricing:
            if "input" in values:
                values["cache_creation"] = str(Decimal(values["input"]) * Decimal("1.25"))
        rule = re.search(
            r"(?:API )?Prompts with (?:>|more than )([0-9,]+)(K)? input tokens are priced at "
            r"([0-9.]+)x input( and cache rates)? and ([0-9.]+)x output for the full request\.",
            pricing,
            re.I,
        )
        if rule and {"input", "output"} <= values.keys():
            remaining = pricing[: rule.start()] + pricing[rule.end() :]
            if not re.search(
                r"(?:prompts with|prompts over|for prompts|more than|tiered)", remaining, re.I
            ):
                tier = {
                    "input_tokens_gt": int(rule[1].replace(",", "")) * (1000 if rule[2] else 1),
                    "input": str(Decimal(values["input"]) * Decimal(rule[3])),
                    "output": str(Decimal(values["output"]) * Decimal(rule[5])),
                }
                # Only propagate cache multipliers when the source explicitly states them.
                if rule[4]:
                    for key in ("cache_read", "cache_creation"):
                        if key in values:
                            tier[key] = str(Decimal(values[key]) * Decimal(rule[3]))
                conditional = False
    else:
        support = re.search(r"  supportedModels:\n(.*?)(?=^  \w|^---)", search_doc, re.M | re.S)
        if support:
            # Absence is unknown: aliases or older supported versions may not be listed.
            if re.search(rf"^    - {re.escape(model)}\s*$", support[1], re.M):
                result.web_search_supported = True
        pricing = section(document, "Pricing", 3) or ""
        names = {
            "Input": "input",
            "Output": "output",
            "Cache read": "cache_read",
            "5m cache write": "cache_creation_5m",
            "1h cache write": "cache_creation_1h",
        }
        values = {}
        for metric, key in names.items():
            found = re.findall(
                rf"^\| (?:{re.escape(metric)}|\[{re.escape(metric)}\]\([^\n]+?\))"
                r"\s*\| \$([0-9]+(?:\.[0-9]+)?) / MTok\s*\|",
                pricing,
                re.M,
            )
            if len(found) == 1:
                values[key] = found[0]
        conditional = bool(re.search(r"(?:for prompts|up to|over \d|\bfrom\b)", pricing, re.I))
        tier_values: dict[str, str] = {}
        thresholds: set[int] = set()
        for metric, key in names.items():
            found = re.findall(
                rf"^\| (?:{re.escape(metric)}|\[{re.escape(metric)}\]\([^\n]+?\))\s*\| "
                r"\$([0-9.]+) / MTok for prompts up to ([0-9,]+) tokens; "
                r"\$([0-9.]+) / MTok for prompts over ([0-9,]+) tokens\s*\|",
                pricing,
                re.M,
            )
            if len(found) == 1:
                low, limit, high, limit2 = found[0]
                thresholds.update((int(limit.replace(",", "")), int(limit2.replace(",", ""))))
                values[key], tier_values[key] = low, high
        if len(thresholds) == 1 and {"input", "output"} <= tier_values.keys():
            tier = {"input_tokens_gt": thresholds.pop(), **tier_values}
            conditional = False
        # Claude Messages structured output is checked by the server runtime when invoked.
    if {"input", "output"} <= values.keys() and not conditional:
        result.price = ModelPrice.model_validate(
            {"label": "공식 문서 표준 요율", **values, "long_context": tier}
        )
    result.note = (
        "공식 문서의 요금 조건을 자동 해석하지 못했습니다. 비용은 미확인으로 기록됩니다."
        if conditional
        else (
            "입력 토큰 수에 따라 구간 요율을 자동 적용합니다. "
            "표준 처리 기준이며 검색 도구·지역 추가 요금은 별도입니다."
        )
        if tier and result.price
        else "표준 텍스트 요율입니다. 검색 도구 요금·계약 할인은 별도입니다."
        if result.price
        else "공식 요율을 확인하지 못했습니다. 비용은 미확인으로 기록됩니다."
    )
    return result


def metadata(provider: Provider, model: str) -> ModelMetadata:
    if not SAFE_ID.fullmatch(model) or ":" in model:
        raise RegistryError(422, "invalid_model_selection")
    # Only fixed official origins. No key is attached to documentation requests.
    base = (
        re.sub(r"-\d{4}-\d{2}-\d{2}$", "", model)
        if provider == "openai"
        else re.sub(r"-\d{8}$", "", model)
    )
    url = (
        f"https://developers.openai.com/api/docs/models/{base}"
        if provider == "openai"
        else f"https://platform.claude.com/docs/en/models/{base.removeprefix('claude-')}/overview"
    )
    try:
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            document = read_response(client, url + ".md")
            search_doc = ""
            if provider == "anthropic":
                try:
                    search_doc = read_response(client, CLAUDE_SEARCH + ".md")
                except (httpx.HTTPError, RegistryError):
                    pass
            result = parse_document(provider, model, document, search_doc)
            result.sources = [url] + ([CLAUDE_SEARCH] if search_doc else [])
            return result
    except (httpx.HTTPError, RegistryError, ValueError):
        return ModelMetadata(
            checked_at=datetime.now(UTC).isoformat(),
            sources=[url],
            note="공식 정보를 불러오지 못했습니다. 공식 정보 갱신으로 다시 확인하세요.",
        )
