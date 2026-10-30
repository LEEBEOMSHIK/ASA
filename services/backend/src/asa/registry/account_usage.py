"""Read-only official billing aggregates; never infer prepaid balances."""
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from threading import Lock
from time import monotonic
from typing import Any

import httpx

from asa.config import Settings


class OpenAIUsage:
    def __init__(self, settings: Settings, *, transport: httpx.BaseTransport | None = None,
                 clock: Callable[[], float] = monotonic,
                 now: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self.settings, self.transport, self.clock, self.now = settings, transport, clock, now
        self.lock = Lock()
        self.data: dict[str, Any] | None = None
        self.synced: str | None = None
        self.attempted: str | None = None
        self.error: str | None = None
        self.next_read = 0.0
        self.last_read = float('-inf')

    def read(self, force: bool = False) -> dict[str, Any]:
        with self.lock:
            if not self.settings.openai_admin_api_key.get_secret_value():
                self.error = 'not_configured'
            elif self.clock() >= self.next_read or (
                force and self.clock() - self.last_read >= 30
            ):
                self.last_read = self.clock()
                self.attempted = self.now().isoformat()
                try:
                    self.data = self.fetch()
                    self.synced = self.attempted
                    self.error = None
                except httpx.HTTPStatusError as exc:
                    self.error = {401: 'invalid_key', 403: 'permission_denied',
                                  429: 'rate_limited'}.get(exc.response.status_code,
                                                         'provider_unavailable')
                except httpx.RequestError:
                    self.error = 'connection_failed'
                except (ValueError, KeyError, TypeError, AttributeError, OverflowError,
                        InvalidOperation):
                    self.error = 'invalid_response'
                self.next_read = self.clock() + (60 if self.error else 900)
            return dict(data=self.data, error_code=self.error, last_synced_at=self.synced,
                        last_attempt_at=self.attempted, stale=bool(self.data and self.error),
                        project_id=self.settings.openai_usage_project_id or None,
                        configured=bool(self.settings.openai_admin_api_key.get_secret_value()))

    def fetch(self) -> dict[str, Any]:
        now = self.now().astimezone(UTC)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month = today.replace(day=1)
        start = min(month, today - timedelta(days=29))
        deadline = self.clock() + 45
        headers = {'Authorization': 'Bearer ' +
                   self.settings.openai_admin_api_key.get_secret_value()}
        with httpx.Client(headers=headers, timeout=15, transport=self.transport) as client:
            def buckets(path: str, grouped: bool = False) -> list[dict[str, Any]]:
                params: dict[str, Any] = dict(start_time=int(start.timestamp()),
                    end_time=int(now.timestamp()), bucket_width='1d', limit=31)
                if self.settings.openai_usage_project_id:
                    params['project_ids'] = self.settings.openai_usage_project_id
                if grouped:
                    params['group_by'] = 'model'
                rows = []
                cursors: set[str] = set()
                for _ in range(20):
                    if self.clock() > deadline:
                        raise ValueError('deadline')
                    response = client.get('https://api.openai.com/v1/organization/' + path,
                                          params=params)
                    response.raise_for_status()
                    payload = response.json()
                    page = payload['data']
                    if not isinstance(page, list):
                        raise ValueError('data')
                    rows.extend(page)
                    if payload.get('has_more') is False:
                        return rows
                    cursor = payload.get('next_page')
                    if not isinstance(cursor, str) or not cursor or cursor in cursors:
                        raise ValueError('pagination')
                    cursors.add(cursor)
                    params['page'] = cursor
                raise ValueError('page_limit')

            costs = buckets('costs')
            usage = buckets('usage/completions', True)
        daily: dict[str, Decimal] = {}
        for bucket in costs:
            date = datetime.fromtimestamp(bucket['start_time'], UTC).date().isoformat()
            daily.setdefault(date, Decimal(0))
            for row in bucket['results']:
                if row['amount']['currency'].lower() != 'usd':
                    raise ValueError('currency')
                amount = Decimal(str(row['amount']['value']))
                if not amount.is_finite():
                    raise ValueError('amount')
                daily[date] += amount
        fields = ('input_tokens', 'output_tokens', 'input_cached_tokens', 'num_model_requests')
        totals = dict.fromkeys(fields, 0)
        models: dict[str, dict[str, int]] = {}
        for bucket in usage:
            for row in bucket['results']:
                model = row.get('model') or '미분류'
                target = models.setdefault(model, dict.fromkeys(fields, 0))
                for field in fields:
                    value = row[field]
                    if type(value) is not int or value < 0:
                        raise ValueError('usage')
                    totals[field] += value
                    target[field] += value
        boundaries = dict(today=today, month=month, days7=today-timedelta(days=6),
                          days30=today-timedelta(days=29))
        return dict(start=start.isoformat(), end=now.isoformat(), timezone='UTC',
                    costs={key: str(sum((v for d, v in daily.items()
                                        if d >= boundary.date().isoformat()), Decimal(0)))
                           for key, boundary in boundaries.items()},
                    daily=[dict(date=d, usd=str(v)) for d, v in sorted(daily.items())],
                    tokens=totals, models=[dict(model=m, **v) for m, v in sorted(models.items())])
