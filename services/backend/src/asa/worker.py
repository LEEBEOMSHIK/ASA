"""Trusted operator CLI; a durable queue consumer is a separate MVP task."""

import argparse
import json
import shutil
import sys
from uuid import UUID, uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command
from langsmith import tracing_context

from asa.config import Settings
from asa.models import DraftRequest, Script
from asa.providers import make_script_generator
from asa.workflow import build_graph


def _run() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="Check configuration presence; makes no paid calls")
    commands.add_parser("init-checkpoints", help="Create/update checkpoint tables explicitly")
    draft = commands.add_parser("draft", help="Generate a script through an external AI API")
    draft.add_argument("--prompt", required=True)
    draft.add_argument("--allow-paid-call", action="store_true", required=True)
    resume = commands.add_parser("resume", help="Resume a pending script review")
    resume.add_argument("run_id", type=UUID)
    resume.add_argument("--decision", choices=["approve", "reject"], required=True)
    args = parser.parse_args()
    settings = Settings()
    if args.command == "check":
        checks = {
            "database_configured": bool(settings.database_url),
            "ai_model_configured": bool(settings.ai_model.strip()),
            "ai_key_configured": bool(settings.ai_api_key.get_secret_value().strip()),
            "ffmpeg_available": shutil.which(settings.ffmpeg_path) is not None,
        }
        print(json.dumps(checks))
        return 0 if all(checks.values()) else 1
    if not settings.database_url:
        parser.error("ASA_DATABASE_URL is required")

    def generate(prompt: str) -> Script:
        return make_script_generator(settings)(prompt)

    with PostgresSaver.from_conn_string(settings.database_url) as saver:
        if args.command == "init-checkpoints":
            saver.setup()
            print("Checkpoint schema initialized.")
            return 0
        graph = build_graph(generate, saver)
        if args.command == "draft":
            request = DraftRequest(prompt=args.prompt)
            run_id = str(uuid4())
            print(json.dumps({"run_id": run_id, "status": "starting"}), flush=True)
            result = graph.invoke(
                {"prompt": request.prompt}, {"configurable": {"thread_id": run_id}}
            )
        else:
            run_id = str(args.run_id)
            config: RunnableConfig = {"configurable": {"thread_id": run_id}}
            snapshot = graph.get_state(config)
            if not any(task.interrupts for task in snapshot.tasks):
                parser.error("Run does not exist or has no pending approval")
            result = graph.invoke(Command(resume={"approved": args.decision == "approve"}), config)
        print(json.dumps({
            "run_id": run_id, "status": result["status"], "script": result.get("script")
        }, ensure_ascii=False))
    return 0


def main() -> int:
    # Inherited tracing settings must not export prompt/script data.
    with tracing_context(enabled=False):
        return _run()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        # Provider/DB exceptions can contain credentials or prompt text.
        print(f"Worker failed ({type(error).__name__}); check configuration and run state.",
              file=sys.stderr)
        raise SystemExit(1) from None
