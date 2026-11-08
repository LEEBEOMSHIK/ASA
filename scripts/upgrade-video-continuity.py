"""Upgrade existing video planner settings using revision-checked registry saves."""
import argparse
import json
from pathlib import Path

from asa.config import Settings
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import AgentDraft
from asa.video_continuity_instructions import upgrade_definition

parser = argparse.ArgumentParser()
parser.add_argument("--apply", action="store_true")
args = parser.parse_args()
settings = Settings()
repo = RegistryRepository(settings.database_url, settings.workspace_id)
with repo._connect() as conn:
    rows = conn.execute(
        "SELECT id,revision,draft FROM registry_agents WHERE workspace_id=%s",
        (repo.workspace_id,),
    ).fetchall()
for row in rows:
    draft = row["draft"]
    props = draft.get("input_schema", {}).get("properties", {})
    if not any(isinstance(p, dict) and p.get("x-video-model") for p in props.values()):
        continue
    upgraded = upgrade_definition(draft)
    validated = AgentDraft.model_validate(upgraded)
    if upgraded == draft:
        print("unchanged", row["id"])
        continue
    print("upgrade", row["id"], "revision", row["revision"])
    if args.apply:
        backup = Path(".local/diagnostics/video-continuity-backups")
        backup.mkdir(parents=True, exist_ok=True)
        (backup / f"{row['id']}-{row['revision']}.json").write_text(
            json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
        saved = repo.save_settings(validated, str(row["id"]), row["revision"])
        print("saved", saved.get("revision"))
