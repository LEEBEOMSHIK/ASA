"""Apply the video planner contract to an explicitly selected local planner agent."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

from asa.config import Settings
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import AgentDraft


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("agent_id", type=UUID)
    agent_id = str(parser.parse_args().agent_id)
    settings = Settings()
    if urlsplit(settings.database_url).hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("Local ASA database required")
    root = Path(__file__).resolve().parents[1]
    template = json.loads((root / "docs/agent-templates/video-prompt-planner.json")
                          .read_text(encoding="utf-8"))
    repo = RegistryRepository(settings.database_url, settings.workspace_id)
    agent = repo.get(agent_id)
    draft = AgentDraft.model_validate(agent["draft"])
    fields = draft.input_schema["properties"]
    if not {"script", "scenes", "scene_images"}.issubset(fields):
        raise SystemExit("Expected script, scenes and confirmed scene image inputs")
    fields["video_model"] = template["input_schema"]["properties"]["video_model"]
    required = draft.input_schema.setdefault("required", [])
    if "video_model" not in required:
        required.append("video_model")
    draft.output_schema = template["output_schema"]
    sql = (root / "services/backend/src/asa/registry/migration.sql").read_text(encoding="utf-8")
    start = sql.index("CREATE TABLE IF NOT EXISTS video_clip_jobs")
    end = sql.index("EXECUTE FUNCTION asa_video_usage();", start)
    with repo._connect() as conn:
        conn.execute(sql[start:end + len("EXECUTE FUNCTION asa_video_usage();")])
    if draft.model_dump() != AgentDraft.model_validate(agent["draft"]).model_dump():
        agent = repo.save_settings(draft, agent_id, agent["revision"])
    print("Planner revision", agent["revision"], "video enabled", settings.video_ai_enabled,
          "Runway key configured", bool(settings.runway_api_key.get_secret_value()))


if __name__ == "__main__":
    main()
