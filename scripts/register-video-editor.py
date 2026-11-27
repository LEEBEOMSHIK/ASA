"""Register the editing agent or publish a targeted guidance update. No AI calls."""
import argparse
import json
from pathlib import Path

from asa.config import Settings
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import AgentDraft

settings = Settings()
parser = argparse.ArgumentParser()
parser.add_argument("--update-input-guide", action="store_true")
parser.add_argument("--update-motion-guidance", action="store_true")
args = parser.parse_args()
repo = RegistryRepository(settings.database_url, settings.workspace_id)
draft = AgentDraft.model_validate_json(
    (Path(__file__).resolve().parents[1]/"docs/agent-templates/video-editor.json").read_text(encoding="utf-8"))
with repo._connect() as conn:
    existing = conn.execute("SELECT id,revision,draft FROM registry_agents WHERE workspace_id=%s "
                           "AND draft->>'name'=%s", (settings.workspace_id, draft.name)).fetchone()
if existing:
    saved = existing["draft"]
    if args.update_input_guide:
        properties = saved["input_schema"]["properties"]
        properties["editing_mode"] = draft.input_schema["properties"]["editing_mode"]
        properties["brief"]["x-editing-brief"] = True
        properties["brief"]["description"] = "어떤 영상으로 편집할까요?"
        properties["brief"]["default"] = draft.input_schema["properties"]["brief"]["default"]
        properties["editing_sources"]["description"] = "이어 붙일 영상·씬 이미지·음원"
        saved["description"] = draft.description
        paragraph = draft.instructions.split("\n")[-1]
        if paragraph not in saved["instructions"]:
            saved["instructions"] += "\n" + paragraph
        saved = json.loads(json.dumps(saved).replace(
            "(video|image|audio|music)", "(video|reference|image|audio|music)"))
    motion_updated = False
    if args.update_motion_guidance:
        motion_guidance = next(
            line for line in draft.instructions.splitlines()
            if line.startswith("정지 씬 이미지 움직임:")
        )
        if motion_guidance not in saved["instructions"].splitlines():
            saved["instructions"] += "\n" + motion_guidance
            motion_updated = True
    if args.update_input_guide or motion_updated:
        repo.save_settings(AgentDraft.model_validate(saved), str(existing["id"]), existing["revision"])
    print(json.dumps({"id":str(existing["id"]),"existing":True,
                      "guide_updated":args.update_input_guide,
                      "motion_guidance_updated":motion_updated}))
else:
    row = repo.save_settings(draft)
    print(json.dumps({"id":str(row["id"]),"registered":True}))
