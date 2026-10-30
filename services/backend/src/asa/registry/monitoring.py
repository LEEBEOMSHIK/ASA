"""Admin-only AI ledger queries; all totals use the same workspace and filters."""
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.registry.account_usage import OpenAIUsage
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import RegistryError

SUMMARY = """
 count(*) AS calls, count(DISTINCT run_id) AS runs,
 count(*) FILTER (WHERE status='failed') AS failed,
 count(*) FILTER (WHERE status='incomplete') AS incomplete,
 sum((usage->>'input_tokens')::bigint) AS input_tokens,
 sum((usage->>'output_tokens')::bigint) AS output_tokens,
 count(*) FILTER (WHERE usage->>'input_tokens' IS NULL) AS usage_unknown,
 sum(estimated_usd) AS estimated_usd,
 count(*) FILTER (WHERE estimated_usd IS NULL) AS cost_unknown,
 count(*) FILTER (WHERE cost_state='tokens_only') AS partial_cost,
 avg(duration_ms) AS average_ms
"""
LIST = """id::text,run_id,request_id,source,requested_by,automation_id,name,revision,
 step_id,step_name,provider,model,status,created_at::text,finished_at::text,duration_ms,
 usage,estimated_usd,cost_state,error_code"""


class MonitoringRepository(RegistryRepository):
    def overview(self, start: datetime, end: datetime, provider: str, status: str,
                 source: str, query: str, offset: int) -> dict[str, Any]:
        where = "workspace_id=%s AND created_at>=%s AND created_at<%s"
        params: list[Any] = [self.workspace_id, start, end]
        for column, value in [('provider', provider), ('status', status), ('source', source)]:
            if value:
                where += f" AND {column}=%s"
                params.append(value)
        if query:
            where += (" AND (name ILIKE %s OR model ILIKE %s OR run_id ILIKE %s "
                      "OR request_id ILIKE %s OR step_name ILIKE %s "
                      "OR original_request::text ILIKE %s)")
            params.extend([f"%{query}%"] * 6)
        with self._connect() as conn:
            summary = conn.execute(f"SELECT {SUMMARY} FROM ai_usage_events WHERE {where}",
                                   params).fetchone()
            models = conn.execute(f"SELECT provider,model,{SUMMARY} FROM ai_usage_events "
                                  f"WHERE {where} GROUP BY provider,model ORDER BY calls DESC "
                                  "LIMIT 50", params).fetchall()
            automations = conn.execute(
                                       "SELECT max(automation_id) AS automation_id,"
                                       "CASE WHEN max(automation_id) IS NOT NULL THEN "
                                       "(array_agg(name ORDER BY created_at DESC,id DESC))[1] "
                                       "WHEN max(source)='customer' THEN '고객 대본 요청' "
                                       "WHEN max(source)='character' THEN '캐릭터 이미지' "
                                       "ELSE '운영자 CLI' END AS name,"
                                       f"{SUMMARY} FROM ai_usage_events WHERE {where} "
                                       "GROUP BY COALESCE(automation_id,source) "
                                       "ORDER BY calls DESC LIMIT 50", params).fetchall()
            items = conn.execute(f"SELECT {LIST} FROM ai_usage_events WHERE {where} "
                                 "ORDER BY created_at DESC,id DESC LIMIT 26 OFFSET %s",
                                 [*params, offset]).fetchall()
        return dict(summary=summary, models=models, automations=automations,
                    items=items[:25], has_more=len(items) > 25)

    def detail(self, event_id: UUID) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(f"SELECT {LIST},workspace_id::text,original_request,messages,"
                               "response,pricing,requested_at::text FROM ai_usage_events "
                               "WHERE workspace_id=%s "
                               "AND id=%s", (self.workspace_id, event_id)).fetchone()
            if not row:
                raise RegistryError(404, "usage_not_found")
            row['related'] = conn.execute(f"SELECT {LIST} FROM ai_usage_events "
                                          "WHERE workspace_id=%s AND run_id=%s "
                                          "ORDER BY created_at,id LIMIT 200",
                                          (self.workspace_id, row['run_id'])).fetchall()
            row['run'] = None
            if row['source'] in ('automation', 'schedule'):
                row['run'] = conn.execute(
                    "SELECT status,created_at::text,updated_at::text,"
                    "EXTRACT(EPOCH FROM (updated_at-created_at))*1000 AS elapsed_ms,"
                    "EXTRACT(EPOCH FROM (started_at-created_at))*1000 AS queue_ms "
                    "FROM automation_runs WHERE workspace_id=%s AND id::text=%s",
                    (self.workspace_id, row['run_id']),
                ).fetchone()
        return row


def monitoring_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix="/api/v1/admin/ai-usage")
    account_usage = OpenAIUsage(settings)

    @router.get("/openai-account")
    def official_usage(refresh: bool = False,
                       principal: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        if 'owner' not in principal.roles or principal.workspace_id != settings.workspace_id:
            raise HTTPException(403, 'owner_required')
        return account_usage.read(force=refresh)

    def repo(principal: Principal = Depends(sessions.principal)) -> MonitoringRepository:
        if not set(principal.roles).intersection({'owner', 'admin'}):
            raise HTTPException(403, "admin_required")
        return MonitoringRepository(settings.database_url, principal.workspace_id)

    @router.get("")
    def overview(
        start: datetime | None = None, end: datetime | None = None,
        provider: Literal['', 'openai', 'anthropic'] = '',
        status: Literal['', 'succeeded', 'failed', 'incomplete'] = '',
        source: Literal['', 'automation', 'schedule', 'customer', 'cli', 'character'] = '',
        q: str = Query('', max_length=200), offset: int = Query(0, ge=0, le=100000),
        repository: MonitoringRepository = Depends(repo),
    ) -> dict[str, Any]:
        end = end or datetime.now(UTC)
        start = start or end - timedelta(days=7)
        if not start.tzinfo or not end.tzinfo or start >= end or end-start > timedelta(days=366):
            raise HTTPException(422, "invalid_usage_period")
        return repository.overview(start, end, provider, status, source, q, offset)

    @router.get("/{event_id}")
    def detail(event_id: UUID, repository: MonitoringRepository = Depends(repo)) -> dict[str, Any]:
        return repository.detail(event_id)

    return router
