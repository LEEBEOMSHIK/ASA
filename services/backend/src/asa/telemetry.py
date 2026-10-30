"""Local, workspace-scoped AI accounting. Never exports prompts to a tracing service."""
import json
import re
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal
from typing import Any, cast
from uuid import uuid4

from langchain_core.callbacks import BaseCallbackHandler
from psycopg.types.json import Jsonb

from asa.config import ModelPrice, Settings
from asa.registry.repository import RegistryRepository

_active: ContextVar[Any] = ContextVar("asa_usage_capture", default=None)


def call_config() -> dict[str, Any]:
    capture = _active.get()
    return {"config": {"callbacks": [capture]}} if capture is not None else {}


def normalize_usage(raw: Any) -> dict[str, int] | None:
    if not isinstance(raw, dict):
        return None
    values = [raw.get("input_tokens"), raw.get("output_tokens")]
    details = raw.get("input_token_details") or {}
    if not isinstance(details, dict):
        return None
    values += [details.get(k) or 0 for k in (
        'cache_read', 'cache_creation', 'ephemeral_5m_input_tokens', 'ephemeral_1h_input_tokens')]
    if any(type(n) is not int or n < 0 for n in values):
        return None
    incoming, outgoing, read, write, write5, write1 = cast(list[int], values)
    if write5 + write1:
        write = write5 + write1
    if read + write > incoming:
        return None
    return dict(input_tokens=incoming, output_tokens=outgoing,
                cache_read=read, cache_creation=write,
                cache_creation_5m=write5, cache_creation_1h=write1)


def estimate(usage: dict[str, int] | None, price: ModelPrice | None,
             web_search: bool = False) -> tuple[Decimal | None, str]:
    if usage is None:
        return None, "usage_unknown"
    if price is None:
        return None, "rate_missing"
    rates = (price.long_context if price.long_context is not None
             and usage["input_tokens"] > price.long_context.input_tokens_gt else price)
    read, write = usage["cache_read"], usage["cache_creation"]
    write5, write1 = usage.get('cache_creation_5m', 0), usage.get('cache_creation_1h', 0)
    generic = write - write5 - write1
    if ((read and rates.cache_read is None) or (generic and rates.cache_creation is None)
            or (write5 and rates.cache_creation_5m is None)
            or (write1 and rates.cache_creation_1h is None)):
        return None, "cache_rate_missing"
    amount = ((usage["input_tokens"] - read - write) * rates.input
              + usage["output_tokens"] * rates.output
              + read * (rates.cache_read or Decimal(0))
              + generic * (rates.cache_creation or Decimal(0))
              + write5 * (rates.cache_creation_5m or Decimal(0))
              + write1 * (rates.cache_creation_1h or Decimal(0))) / Decimal(1_000_000)
    return amount, "tokens_only" if web_search else "estimated"


def redact(value: Any, settings: Settings) -> Any:
    """Bound stored payloads; redact configured credentials and common secret fields."""
    secrets = [settings.ai_api_key.get_secret_value(),
               settings.anthropic_api_key.get_secret_value(),
               settings.search_api_key.get_secret_value(),
               settings.owner_access_key.get_secret_value(),
               settings.database_url]

    def clean(item: Any, depth: int = 0) -> Any:
        if depth > 30:
            return "[DEPTH LIMIT]"
        if isinstance(item, dict):
            return {str(k): "[REDACTED]" if re.search(
                r"api.?key|authorization|password|secret|access.?token", str(k), re.I)
                else clean(v, depth + 1) for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [clean(v, depth + 1) for v in item]
        if not isinstance(item, str):
            return item
        if item.lstrip().startswith(('{', '[')):
            try:
                decoded = json.loads(item)
            except (ValueError, RecursionError):
                pass
            else:
                return json.dumps(clean(decoded, depth + 1), ensure_ascii=False)
        for secret in secrets:
            if secret:
                item = item.replace(secret, "[REDACTED]")
        item = re.sub(r"\b(?:sk-[\w-]{12,}|gh[pousr]_[\w]{20,})", "[REDACTED]", item)
        item = re.sub(r"(?i)(bearer\s+)\S+", r"\1[REDACTED]", item)
        item = re.sub(r'(?i)((?:api[_ -]?key|password|secret|access[_ -]?token)["\x27]?'
                      r'\s*[=:]\s*)[^\s,;]+',
                      r'\1[REDACTED]', item)
        return item

    result = clean(value)
    text = json.dumps(result, ensure_ascii=False, default=str)
    return result if len(text) <= 64000 else {"truncated": True, "preview": text[:64000]}


class Capture(BaseCallbackHandler):
    raise_error = True
    def __init__(self, settings: Settings, context: dict[str, Any]):
        self.settings = settings
        self.context = context
        self.repo = RegistryRepository(settings.database_url, settings.workspace_id)
        self.id = uuid4()
        self.usage: dict[str, int] | None = None
        self.messages: Any = None
        self.response: Any = None
        self.price = settings.ai_prices.get(f"{context['provider']}:{context['model']}")
        self.model_started: float | None = None
        self.model_duration: int | None = None

    def start(self) -> None:
        c = self.context
        with self.repo._connect() as conn:
            conn.execute(
                "INSERT INTO ai_usage_events(workspace_id,id,run_id,request_id,source,requested_by,"
                "automation_id,name,revision,step_id,step_name,provider,model,"
                "original_request,pricing,requested_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (self.settings.workspace_id, self.id, str(c['run_id']), str(c['request_id']),
                 c['source'], c.get('requested_by'), c.get('automation_id'), c['name'],
                 c.get('revision'), c['step_id'], c['step_name'], c['provider'], c['model'],
                 Jsonb(redact(c.get('original_request'), self.settings)),
                 Jsonb(self.price.model_dump(mode='json')) if self.price else None,
                 c.get('requested_at')),
            )

    def on_chat_model_start(self, serialized: dict[str, Any], messages: Any, **kwargs: Any) -> None:
        self.messages = redact([[{"role": m.type, "content": m.content} for m in batch]
                                for batch in messages], self.settings)
        self.save("incomplete", finished=False)
        self.model_started = time.perf_counter()

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        self.record_duration()
        # One external invocation per capture; structured-output parsing may fail afterwards.
        generations = response.generations
        if generations and generations[0]:
            message = getattr(generations[0][0], "message", None)
            if message is not None:
                self.usage = normalize_usage(getattr(message, "usage_metadata", None))
                self.response = redact({"content": message.content,
                                        "tool_calls": getattr(message, "tool_calls", [])},
                                       self.settings)
        self.save("incomplete", finished=False)

    def record_duration(self) -> None:
        if self.model_started is not None:
            self.model_duration = round((time.perf_counter() - self.model_started) * 1000)

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        self.record_duration()  # Never store provider exception text.

    def save(self, status: str, finished: bool = True) -> None:
        cost, cost_state = estimate(self.usage, self.price, self.context.get('web_search', False))
        with self.repo._connect() as conn:
            conn.execute(
                "UPDATE ai_usage_events SET status=%s,messages=%s,response=%s,usage=%s,"
                "estimated_usd=%s,cost_state=%s,duration_ms=%s,"
                "finished_at=CASE WHEN %s THEN now() ELSE NULL END,error_code=%s "
                "WHERE workspace_id=%s AND id=%s",
                (status, Jsonb(self.messages), Jsonb(self.response), Jsonb(self.usage), cost,
                 cost_state,
                 self.model_duration,
                 finished, "call_or_output_failed" if status == "failed" else None,
                 self.settings.workspace_id, self.id),
            )


@contextmanager
def trace_call(settings: Settings, context: dict[str, Any]) -> Iterator[Capture]:
    capture = Capture(settings, context)
    capture.start()  # Fail closed before paid work if recording cannot start.
    token = _active.set(capture)
    try:
        yield capture
    except Exception:
        capture.save("failed")
        raise
    else:
        capture.save("succeeded")
    finally:
        _active.reset(token)


def observed_generate(repo: Any, run: dict[str, Any], tool: dict[str, Any], step_id: str,
                      value: Any, generate: Callable[..., Any]) -> Any:
    graph = run['definition'].get('graph')
    steps = graph['nodes'] if graph else run['definition']['steps']
    label = next((s['label'] for s in steps if s['id'] == tool.get('node_id', step_id)),
                 tool.get('name', step_id))
    context = dict(run_id=str(run['id']), request_id=str(run['id']),
                   source="schedule" if run.get('schedule_id') else "automation",
                   requested_by=run.get('requested_by'), automation_id=str(run['automation_id']),
                   name=run['definition']['name'], revision=run['revision'], step_id=step_id,
                   step_name=label, provider=tool['provider'], model=tool['model'],
                   original_request=run['prompt'], web_search=tool.get('web_search', False))
    context['requested_at'] = run.get('created_at')
    with trace_call(repo.settings, context):
        return generate(repo, tool, value)
