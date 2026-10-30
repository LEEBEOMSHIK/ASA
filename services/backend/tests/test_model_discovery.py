from decimal import Decimal

import httpx
import pytest

from asa.config import Settings
from asa.registry import model_discovery as discovery
from asa.registry.schemas import RegistryError

DOCUMENT = """# Test
Model ID: `test-model`
## Pricing
### Text tokens
| Input | $1 | 1M tokens |
| Output | $4 | 1M tokens |
| Cached input | $0.25 | 1M tokens |
## Endpoints
| Chat Completions | `v1/chat/completions` | Supported |
## Supported features
- structured_outputs
## Supported tools
- web_search
"""


def test_exact_model_and_tariff() -> None:
    result = discovery.parse_document("openai", "test-model", DOCUMENT)
    assert result.web_search_supported is True
    assert result.compatible is True
    assert result.price and result.price.cache_read == Decimal(".25")
    assert discovery.parse_document("openai", "other-model", DOCUMENT).price is None


def test_conditional_tariff_is_not_misrepresented() -> None:
    doc = DOCUMENT.replace("## Endpoints", "Prompts with >272K tokens cost more.\n## Endpoints")
    assert discovery.parse_document("openai", "test-model", doc).price is None


def test_claude_cache_rates() -> None:
    doc = """Model ID: `claude-example`
### Pricing
| Input | $3 / MTok |
| Output | $15 / MTok |
| [Cache read](url) | $0.30 / MTok |
| [5m cache write](url) | $3.75 / MTok |
| [1h cache write](url) | $6 / MTok |
"""
    result = discovery.parse_document(
        "anthropic",
        "claude-example",
        doc,
        "  supportedModels:\n    - claude-example\n  supportedPlatforms:",
    )
    assert result.web_search_supported
    assert result.price and result.price.cache_creation_1h == 6


def test_missing_key() -> None:
    with pytest.raises(RegistryError):
        discovery.discover(Settings(_env_file=None, ai_api_key=""), "openai")


def test_discovery_does_not_generate(monkeypatch: pytest.MonkeyPatch) -> None:
    real_client = httpx.Client

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == "https://api.openai.com/v1/models"
        assert request.headers["authorization"] == "Bearer fake"
        return httpx.Response(200, json={"data": [{"id": "test-model"}, {"id": "../evil"}]})

    monkeypatch.setattr(
        discovery.httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handle)),
    )
    result = discovery.discover(Settings(_env_file=None, ai_api_key="fake"), "openai")
    assert [m["id"] for m in result["models"]] == ["test-model"]


def test_invalid_metadata_path() -> None:
    with pytest.raises(RegistryError):
        discovery.metadata("openai", "../private")


def test_claude_pagination_and_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    real_client = httpx.Client
    seen = []

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "fake"
        assert request.method == "GET"
        seen.append(request.url.params.get("after_id"))
        if len(seen) == 1:
            return httpx.Response(
                200,
                json={
                    "data": [{"id": "claude-a", "display_name": "A"}],
                    "has_more": True,
                    "last_id": "claude-a",
                },
            )
        return httpx.Response(200, json={"data": [{"id": "claude-b"}], "has_more": False})

    monkeypatch.setattr(
        discovery.httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handle)),
    )
    result = discovery.discover(Settings(_env_file=None, anthropic_api_key="fake"), "anthropic")
    assert seen == [None, "claude-a"]
    assert len(result["models"]) == 2


def test_document_failure_preserves_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    real_client = httpx.Client

    def handle(request: httpx.Request) -> httpx.Response:
        assert "authorization" not in request.headers and "x-api-key" not in request.headers
        assert request.url.host == "developers.openai.com"
        return httpx.Response(404, text="private upstream details")

    monkeypatch.setattr(
        discovery.httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handle)),
    )
    result = discovery.metadata("openai", "missing")
    assert result.price is None and result.web_search_supported is None
    assert "private" not in result.note


def test_openai_long_context_document_and_estimate() -> None:
    from asa.telemetry import estimate

    doc = DOCUMENT.replace(
        "## Endpoints",
        "API prompts with more than 272K input tokens are priced at 2x input and cache rates "
        "and 1.5x output for the full request.\n## Endpoints",
    )
    price = discovery.parse_document("openai", "test-model", doc).price
    assert price is not None and price.long_context is not None
    assert price.long_context.input_tokens_gt == 272000

    def usage(n: int) -> dict[str, int]:
        return dict(input_tokens=n, output_tokens=100, cache_read=100, cache_creation=0)

    assert estimate(usage(272000), price)[0] == Decimal("0.272325")
    assert estimate(usage(272001), price)[0] == Decimal("0.544452")


def test_claude_tiered_rates() -> None:
    from asa.telemetry import estimate

    doc = """Model ID: `claude-example`
### Pricing
| Input | $0.10 / MTok for prompts up to 100,000 tokens; $0.50 / MTok for prompts over 100,000 tokens |
| Output | $0.50 / MTok for prompts up to 100,000 tokens; $2.50 / MTok for prompts over 100,000 tokens |
| Cache read | $0.01 / MTok for prompts up to 100,000 tokens; $0.05 / MTok for prompts over 100,000 tokens |
"""
    price = discovery.parse_document("anthropic", "claude-example", doc).price
    assert price is not None and price.long_context is not None
    amount, state = estimate(
        dict(input_tokens=100001, output_tokens=10, cache_read=1, cache_creation=0), price
    )
    assert state == "estimated" and amount == Decimal("0.05002505")


def test_unspecified_high_cache_rate_and_roundtrip() -> None:
    from asa.config import ModelPrice
    from asa.telemetry import estimate

    doc = DOCUMENT.replace(
        "## Endpoints",
        "Prompts with >272K input tokens are priced at 2x input and 1.5x output "
        "for the full request.\n## Endpoints",
    )
    price = discovery.parse_document("openai", "test-model", doc).price
    assert price is not None
    restored = ModelPrice.model_validate_json(price.model_dump_json())
    assert restored.long_context and restored.long_context.output == 6
    assert estimate(
        dict(input_tokens=272001, output_tokens=1, cache_read=1, cache_creation=0), restored
    ) == (None, "cache_rate_missing")
    assert (
        estimate(
            dict(input_tokens=272000, output_tokens=1, cache_read=1, cache_creation=0), restored
        )[0]
        is not None
    )
