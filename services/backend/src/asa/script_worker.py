"""Run exactly one explicitly selected script attempt. No automatic paid retries."""
import argparse
import json
import sys
from uuid import UUID

from langsmith import tracing_context

from asa.config import Settings
from asa.providers import make_script_generator
from asa.registry.script_stage import ScriptRepository, execute_attempt


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
        processed = execute_attempt(repo, str(args.request_id), str(args.attempt_id), generate,
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
