"""Local script queue consumer; use --allow-paid-call to explicitly enable consumption."""
import argparse
from uuid import UUID

from langsmith import tracing_context

from asa.config import Settings
from asa.registry.script_queue import ScriptQueue
from asa.worker_control import run_worker


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-paid-call', action='store_true', required=True)
    parser.add_argument('--control-token', type=UUID)
    args = parser.parse_args()
    settings = Settings()
    if not settings.script_ai_enabled:
        parser.error('ASA_SCRIPT_AI_ENABLED must be true')
    repo = ScriptQueue(settings)
    with tracing_context(enabled=False):
        run_worker(settings, 'script', repo.tick, args.control_token)


if __name__ == '__main__':
    main()
