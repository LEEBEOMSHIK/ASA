"""Durable script queue. One active consumer per workspace; uncertain calls never retry."""
import time
from collections.abc import Callable
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from asa.config import Settings
from asa.database import release_lock
from asa.models import AgentAnswer, Script
from asa.providers import make_agent_generator
from asa.registry.model_catalog import effective_settings
from asa.registry.schemas import RegistryError
from asa.registry.script_stage import GenerateScript, ScriptRepository, execute_attempt
from asa.telemetry import trace_call


class ScriptQueue(ScriptRepository):
    def __init__(self, settings: Settings):
        super().__init__(settings.database_url, settings.workspace_id)
        self.settings = settings

    def submit(self, request_id: str, body: GenerateScript | None = None) -> dict[str, Any]:
        if not self.settings.script_ai_enabled:
            raise RegistryError(409, "script_execution_disabled")
        config = effective_settings(self.settings)
        with self._connect() as conn:
            agent = self._request(conn, request_id)['definition']
        provider = agent.get('provider') or config.ai_provider
        model = agent.get('model') or config.ai_model
        if (model not in config.models_for(provider)
                or not config.key_for(provider).get_secret_value()):
            raise RegistryError(422, "invalid_model_selection")
        body = body or GenerateScript(
            id=UUID(request_id), expected_revision=0, base_version=0,
            instruction='등록된 지침과 답변 형식에 따라 입력 요청에 답하세요.')
        return self.queue(request_id, body, provider=provider, model=model, automatic=True,
                          queue_limit=config.script_queue_limit)

    def progress(self, request_id: str) -> dict[str, Any]:
        result = self.get(request_id)
        with self._connect() as conn:
            request = self._request(conn, request_id)
            worker = conn.execute(
                "SELECT seen_at > now() - %s * interval '1 second' AS online "
                "FROM script_worker_status WHERE workspace_id=%s",
                (max(90, self.settings.ai_timeout_seconds + 30), self.workspace_id)).fetchone()
            active = conn.execute(
                "SELECT created_at FROM script_attempts WHERE workspace_id=%s AND request_id=%s "
                "AND automatic AND status IN ('queued','running')",
                (self.workspace_id, request_id)).fetchone()
            ahead = conn.execute(
                "SELECT count(*) n FROM script_attempts WHERE workspace_id=%s AND automatic "
                "AND status IN ('queued','running') AND created_at < %s",
                (self.workspace_id, active['created_at'])).fetchone() if active else None
        result.update(execution_enabled=self.settings.script_ai_enabled,
                      worker_online=bool(worker and worker['online']),
                      queue_ahead=ahead['n'] if ahead else 0,
                      request_input=request['input'],
                      agent_instructions=request['definition']['instructions'])
        return result

    def tick(self, generator: Callable[[str], Script | AgentAnswer] | None = None) -> bool:
        if not self.settings.script_ai_enabled:
            return False
        # Session lock spans the paid call. A second process cannot recover an active job.
        with self._connect() as lock:
            key = f"script-worker:{self.workspace_id}"
            acquired = lock.execute("SELECT pg_try_advisory_lock(hashtextextended(%s,0)) ok",
                                    (key,)).fetchone()
            lock.commit()
            if not acquired or not acquired['ok']:
                return False
            try:
                return self._process(generator)
            finally:
                release_lock(lock, key)

    def _process(self, generator: Callable[[str], Script | AgentAnswer] | None) -> bool:
        with self._connect() as conn:
            conn.execute("INSERT INTO script_worker_status(workspace_id) VALUES (%s) "
                         "ON CONFLICT(workspace_id) DO UPDATE SET seen_at=now()",
                         (self.workspace_id,))
            abandoned = conn.execute(
                "SELECT * FROM script_attempts WHERE workspace_id=%s AND automatic "
                "AND status='running'", (self.workspace_id,)).fetchall()
        for attempt in abandoned:
            self.finish(str(attempt['request_id']), attempt, None)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM script_attempts WHERE workspace_id=%s AND automatic "
                "AND status='queued' ORDER BY created_at,id LIMIT 1",
                (self.workspace_id,)).fetchone()
            used = conn.execute(
                "SELECT count(*) n FROM script_attempts WHERE workspace_id=%s AND automatic "
                "AND started_at >= date_trunc('day',now())", (self.workspace_id,)).fetchone()
        if not row:
            return False
        config = effective_settings(self.settings)
        rid, aid = str(row['request_id']), str(row['id'])
        provider, model = row['provider'], row['model']
        # Keep the queued model snapshot, but honor a later administrative disable.
        allowed = (model in config.models_for(provider)
                   and bool(config.key_for(provider).get_secret_value())
                   and bool(used and used['n'] < config.script_daily_ai_calls))
        if not allowed:
            reason = ('일일 AI 호출 한도에 도달했습니다. AI를 호출하지 않았습니다.'
                      if used and used['n'] >= config.script_daily_ai_calls
                      else '선택한 모델을 사용할 수 없습니다. AI를 호출하지 않았습니다.')
            with self._connect() as conn:
                self._request(conn, rid, True)
                changed = conn.execute(
                    "UPDATE script_attempts SET status='failed',finished_at=now(),error_code=%s "
                    "WHERE workspace_id=%s AND request_id=%s AND id=%s AND status='queued' "
                    "RETURNING id", (reason, self.workspace_id, rid, aid)).fetchone()
                if changed:
                    conn.execute("UPDATE customer_requests SET status='failed',error=%s,"
                                 "updated_at=now() WHERE workspace_id=%s AND id=%s",
                                 (reason, self.workspace_id, rid))
                    conn.execute("UPDATE script_stages SET revision=revision+1 "
                                 "WHERE workspace_id=%s AND request_id=%s",
                                 (self.workspace_id, rid))
            return True
        config = config.model_copy(update={'ai_provider': provider, 'ai_model': model})

        last_write = 0.0
        pending: dict[str, Any] = {}

        def publish(partial: dict[str, Any], force: bool = False) -> None:
            nonlocal last_write, pending
            pending = {key: value for key, value in partial.items()
                       if key in ("understanding", "direction", "value")}
            if not force and time.monotonic() - last_write < 0.25:
                return
            with self._connect() as conn:
                conn.execute("UPDATE script_attempts SET live_output=%s WHERE workspace_id=%s "
                             "AND request_id=%s AND id=%s AND status='running'",
                             (Jsonb(pending), self.workspace_id, rid, aid))
            last_write = time.monotonic()

        def monitored(prompt: str) -> Script | AgentAnswer:
            with self._connect() as conn:
                request = conn.execute(
                    "SELECT r.input,r.requested_by,r.created_at::text,r.version,"
                    "v.definition->>'name' AS name FROM customer_requests r "
                    "JOIN registry_versions v USING(workspace_id,agent_id,version) "
                    "WHERE r.workspace_id=%s AND r.id=%s", (self.workspace_id, rid)).fetchone()
            assert request
            with trace_call(config, dict(
                run_id=aid, request_id=rid, source='customer',
                requested_by=request['requested_by'], name=request['name'],
                requested_at=request['created_at'], revision=request['version'],
                step_id='script', step_name='에이전트 답변', original_request=request['input'],
                provider=provider, model=model,
            )):
                # Model construction errors also leave a trace and cannot strand the job.
                try:
                    return (generator or make_agent_generator(config, publish))(prompt)
                finally:
                    if pending:
                        publish(pending, force=True)

        return execute_attempt(self, rid, aid, monitored, provider, model)
