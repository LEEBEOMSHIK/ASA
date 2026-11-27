"""Build production speech from the saved scene timing contract."""

from typing import Any
from uuid import UUID

from pydantic import ValidationError

from asa.audio_contracts import AudioSettings, Voice
from asa.registry.schemas import RegistryError
from asa.registry.work_titles import describe_work

FORMAT = "asa_speech_production_v1"


def is_production_output(schema: dict[str, Any]) -> bool:
    return schema.get("properties", {}).get("format", {}).get("enum") == [FORMAT]


def is_production_answer(answer: Any) -> bool:
    return isinstance(answer, dict) and answer.get("format") == FORMAT


def production_settings(
    scene: AudioSettings, model_key: str, voices: list[str],
) -> AudioSettings:
    if scene.purpose != "timing" or not scene.cues:
        raise RegistryError(422, "speech_source_unavailable")
    speakers = [
        speaker.model_copy(update={
            "voice": Voice(model_key=model_key, voice=voices[index % len(voices)]),
            "sample_job_id": None,
        })
        for index, speaker in enumerate(scene.speakers)
        if any(cue.speaker_id == speaker.id for cue in scene.cues)
    ]
    return AudioSettings(
        enabled=True, speakers=speakers,
        cues=[cue.model_copy(deep=True) for cue in sorted(scene.cues, key=lambda cue: cue.start)],
    )


def require_original_dialogue(current: AudioSettings, edited: AudioSettings) -> None:
    def dialogue(data: AudioSettings) -> dict[str, tuple[str, str]]:
        return {cue.id: (cue.speaker_id, cue.text) for cue in data.cues}

    def speakers(data: AudioSettings) -> dict[str, tuple[str, str]]:
        return {speaker.id: (speaker.name, speaker.role) for speaker in data.speakers}

    if (dialogue(current) != dialogue(edited) or speakers(current) != speakers(edited)
            or not edited.enabled or edited.purpose != "production"
            or edited.delivery_mode != "separate" or edited.music != current.music
            or edited.timing_auto_align or edited.timing_duration_seconds is not None
            or edited.timing_preview_seconds is not None):
        raise RegistryError(422, "speech_source_dialogue_changed")


SOURCE_FIELDS = (
    "s.title,s.answer,r.input,n.name AS custom_name,v.definition->>'name' AS agent_name,"
    "v.definition->'input_schema' AS input_schema,v.definition->'output_schema' AS output_schema"
)
SOURCE_ROWS = (
    " FROM audio_settings a JOIN script_versions s ON s.workspace_id=a.workspace_id "
    "AND s.request_id=a.request_id AND s.version=a.answer_version "
    "JOIN customer_requests r ON r.workspace_id=s.workspace_id AND r.id=s.request_id "
    "JOIN registry_versions v ON v.workspace_id=r.workspace_id AND v.agent_id=r.agent_id "
    "AND v.version=coalesce(s.agent_version,r.version) "
    "LEFT JOIN user_work_names n ON n.workspace_id=r.workspace_id AND n.request_id=r.id "
    "AND n.user_id=%s WHERE a.workspace_id=%s AND a.settings->>'purpose'='timing' "
    "AND v.definition#>>'{after_tasks,scene_timing}'='true' "
    "AND a.settings->'cues' <> '[]'::jsonb"
)


def source_title(row: dict[str, Any]) -> str:
    return describe_work(
        row["answer"], row["title"], row["input"], row["input_schema"], row["agent_name"],
        row["custom_name"], output_schema=row["output_schema"],
    )["display_title"]


def source_list(conn: Any, workspace: UUID, user: str, query: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT s.request_id::text AS request_id,s.version,s.created_at::text,"
        "jsonb_array_length(a.settings->'cues') AS cue_count," + SOURCE_FIELDS
        + SOURCE_ROWS
        + " AND strpos(lower(concat_ws(' ',n.name,s.title,s.answer::text,r.input::text,"
          "v.definition->>'name')),lower(%s))>0"
        + " ORDER BY s.created_at DESC,s.request_id,s.version DESC LIMIT 50",
        (user, workspace, query),
    ).fetchall()
    return [
        {"request_id": row["request_id"], "version": row["version"],
         "title": source_title(row), "cue_count": row["cue_count"], "created_at": row["created_at"]}
        for row in rows
    ]


def load_source(conn: Any, workspace: UUID, user: str | None,
                reference: str) -> tuple[AudioSettings, str]:
    try:
        raw_id, raw_version = reference.split(":")
        request_id, version = UUID(raw_id), int(raw_version)
        if reference != f"{request_id}:{version}" or not 0 < version <= 2**31 - 1:
            raise ValueError
    except ValueError as exc:
        raise RegistryError(422, "speech_source_unavailable") from exc
    row = conn.execute(
        "SELECT a.settings," + SOURCE_FIELDS + SOURCE_ROWS
        + " AND s.request_id=%s AND s.version=%s",
        (user, workspace, request_id, version),
    ).fetchone()
    if not row:
        raise RegistryError(422, "speech_source_unavailable")
    try:
        return AudioSettings.model_validate(row["settings"]), source_title(row)
    except ValidationError as exc:
        raise RegistryError(422, "speech_source_unavailable") from exc
