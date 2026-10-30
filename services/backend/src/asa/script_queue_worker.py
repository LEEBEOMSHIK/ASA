"""Local script queue consumer; use --allow-paid-call to explicitly enable consumption."""
import argparse
import time

from langsmith import tracing_context

from asa.config import Settings
from asa.database import changes
from asa.registry.script_queue import ScriptQueue


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-paid-call', action='store_true', required=True)
    parser.parse_args()
    settings = Settings()
    if not settings.script_ai_enabled:
        parser.error('ASA_SCRIPT_AI_ENABLED must be true')
    repo = ScriptQueue(settings)
    hub = changes(settings.database_url)
    scope = str(settings.workspace_id)
    with tracing_context(enabled=False):
        while True:
            version = hub.version(scope, "script")
            try:
                worked = repo.tick()
            except Exception:
                # No secrets/provider messages in logs. Recovery marks abandoned calls unknown.
                print('Script queue temporarily unavailable; retrying queue polling.', flush=True)
                time.sleep(5)
            else:
                if not worked:
                    hub.wait(scope, "script", version, 30)


if __name__ == '__main__':
    main()
