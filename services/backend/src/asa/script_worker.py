"""Run exactly one explicitly selected script attempt. No automatic paid retries."""
import argparse
import json
import sys
from uuid import UUID

from langsmith import tracing_context

from asa.config import Settings
from asa.models import Script
from asa.providers import make_script_generator
from asa.registry.script_stage import ScriptRepository, execute_attempt
from asa.telemetry import trace_call


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request_id", type=UUID)
    parser.add_argument("attempt_id", type=UUID)
    parser.add_argument("--allow-paid-call", action="store_true", required=True)
    args = parser.parse_args()
    settings = Settings()
    if not settings.database_url:
        parser.error("ASA_DATABASE_URL is required")
    with tracing_context(enabled=False):
        generate = make_script_generator(settings)
        repo = ScriptRepository(settings.database_url, settings.workspace_id)

        def monitored(prompt: str) -> Script:
            with repo._connect() as conn:
                request = conn.execute("SELECT r.input,r.requested_by,r.created_at::text,r.version,"
                                       "v.definition->>'name' AS name FROM customer_requests r "
                                       "JOIN registry_versions v "
                                       "USING(workspace_id,agent_id,version) "
                                       "WHERE r.workspace_id=%s AND r.id=%s",
                                       (settings.workspace_id, args.request_id)).fetchone()
            assert request
            with trace_call(settings, dict(
                run_id=str(args.attempt_id), request_id=str(args.request_id), source='customer',
                requested_by=request['requested_by'], name=request['name'], step_id='script',
                requested_at=request['created_at'], revision=request['version'],
                step_name='대본 작성', original_request=request['input'],
                provider=settings.ai_provider, model=settings.ai_model,
            )):
                return generate(prompt)

        processed = execute_attempt(repo, str(args.request_id), str(args.attempt_id), monitored,
                                    settings.ai_provider, settings.ai_model)
        print(json.dumps({"processed": processed, "request_id": str(args.request_id),
                          "attempt_id": str(args.attempt_id)}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Script worker stopped ({type(error).__name__}); inspect attempt status.",
              file=sys.stderr)
        raise SystemExit(1) from None
