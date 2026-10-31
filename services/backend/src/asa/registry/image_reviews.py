"""Optional image review queue; no implicit regeneration or human approval."""

import base64
import json
from contextlib import nullcontext
from typing import Any
from uuid import UUID, uuid4

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from psycopg.types.json import Jsonb

from asa.config import Settings
from asa.registry.history import valid_input
from asa.registry.model_catalog import effective_settings, validate_selection
from asa.registry.schemas import RegistryError
from asa.telemetry import call_config, trace_call


def review_config(conn: Any, workspace: UUID, project: UUID) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT v.definition->'after_tasks'->'image_review' AS link "
        "FROM character_projects p JOIN customer_requests r ON r.workspace_id=p.workspace_id "
        "AND r.id=p.request_id JOIN registry_versions v ON v.workspace_id=r.workspace_id "
        "AND v.agent_id=r.agent_id AND v.version=r.version "
        "WHERE p.workspace_id=%s AND p.id=%s",
        (workspace, project),
    ).fetchone()
    return row["link"] if row else None


def enqueue_review(
    repo: Any,
    image_id: UUID,
    review_id: UUID,
    character: dict[str, Any] | None,
    settings: Settings,
    automatic: bool = False,
    connection: Any = None,
) -> dict[str, Any]:
    with nullcontext(connection) if connection is not None else repo._connect() as conn:
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"asset-review:{repo.workspace_id}",),
        )
        job = conn.execute(
            "SELECT * FROM character_image_jobs WHERE workspace_id=%s AND id=%s "
            "AND status='succeeded' AND image IS NOT NULL",
            (repo.workspace_id, image_id),
        ).fetchone()
        if not job:
            raise RegistryError(404, "image_not_found")
        character = character or job["character"]
        if character["id"] != job["character_id"]:
            raise RegistryError(422, "image_reference_invalid")
        existing = conn.execute(
            "SELECT id::text,image_id,character,status FROM asset_reviews "
            "WHERE workspace_id=%s AND id=%s",
            (repo.workspace_id, review_id),
        ).fetchone()
        if existing:
            if existing["image_id"] != image_id or existing["character"] != character:
                raise RegistryError(409, "image_id_conflict")
            return {"id": existing["id"], "status": existing["status"]}
        link = review_config(conn, repo.workspace_id, job["project_id"])
        if not link or (automatic and link["mode"] != "automatic"):
            if automatic:
                return {}
            raise RegistryError(409, "review_not_configured")
        if (
            automatic
            and conn.execute(
                "SELECT 1 FROM asset_reviews WHERE workspace_id=%s AND image_id=%s AND automatic",
                (repo.workspace_id, image_id),
            ).fetchone()
        ):
            return {}
        if conn.execute(
            "SELECT 1 FROM asset_reviews WHERE workspace_id=%s AND image_id=%s "
            "AND status IN ('queued','running')",
            (repo.workspace_id, image_id),
        ).fetchone():
            raise RegistryError(409, "review_already_running")
        count = conn.execute(
            "SELECT count(*) AS n FROM asset_reviews WHERE workspace_id=%s "
            "AND created_at>now()-interval '24 hours'",
            (repo.workspace_id,),
        ).fetchone()
        if count["n"] >= settings.image_daily_calls:
            raise RegistryError(429, "image_daily_limit")
        _, agent, version = link["agent_ref"].split(":")
        row = conn.execute(
            "SELECT definition FROM registry_versions WHERE workspace_id=%s "
            "AND agent_id=%s AND version=%s",
            (repo.workspace_id, agent, int(version)),
        ).fetchone()
        if not row or row["definition"].get("purpose") != "image_review":
            raise RegistryError(409, "review_not_configured")
        definition = dict(row["definition"])
        config = effective_settings(
            settings.model_copy(update={"workspace_id": repo.workspace_id}), conn
        )
        provider = definition.get("provider") or config.ai_provider
        model = definition.get("model") or config.ai_model
        validate_selection(config, provider, model)
        if not config.image_ai_enabled or not config.key_for(provider).get_secret_value():
            raise RegistryError(409, "image_not_configured")
        definition.update(provider=provider, model=model)
        conn.execute(
            "INSERT INTO asset_reviews(workspace_id,id,project_id,image_id,agent_ref,"
            "definition,character,change,automatic) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                repo.workspace_id,
                review_id,
                job["project_id"],
                image_id,
                link["agent_ref"],
                Jsonb(definition),
                Jsonb(character),
                job["change"],
                automatic,
            ),
        )
        return {"id": str(review_id), "status": "queued"}


def review_image(
    settings: Settings,
    definition: dict[str, Any],
    character: dict[str, Any],
    change: str,
    image: bytes,
    reference: bytes | None,
) -> Any:
    model = init_chat_model(
        definition["model"],
        model_provider=definition["provider"],
        api_key=settings.key_for(definition["provider"]).get_secret_value(),
        timeout=min(settings.ai_timeout_seconds, definition["limits"]["seconds"]),
        max_retries=0,
        max_tokens=settings.script_output_tokens,
    )
    content: list[Any] = [
        {
            "type": "text",
            "text": json.dumps(
                {
                    "character": character,
                    "requested_change": change,
                    "image_order": "1: 검수 대상 이미지, 2가 있으면 수정 전 기준 이미지",
                },
                ensure_ascii=False,
            ),
        }
    ]
    for data in [image, reference]:
        if data:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/png;base64," + base64.b64encode(data).decode()
                    },
                }
            )
    envelope = {
        "title": "ImageReview",
        "type": "object",
        "properties": {"value": definition["output_schema"]},
        "required": ["value"],
        "additionalProperties": False,
    }
    result = model.with_structured_output(envelope).invoke(
        [SystemMessage(content=definition["instructions"]), HumanMessage(content=content)],
        **call_config(),
    )
    if not isinstance(result, dict) or not valid_input(
        result.get("value"), definition["output_schema"]
    ):
        raise ValueError("review_output_invalid")
    return result["value"]


def process_review(repo: Any, settings: Settings) -> bool:
    with repo._connect() as conn:
        conn.execute(
            "UPDATE asset_reviews SET status='unknown',error_code='worker_interrupted',"
            "finished_at=now() WHERE workspace_id=%s AND status='running'",
            (repo.workspace_id,),
        )
        review = conn.execute(
            "SELECT * FROM asset_reviews WHERE workspace_id=%s AND status='queued' "
            "ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED",
            (repo.workspace_id,),
        ).fetchone()
        if not review:
            return False
        conn.execute(
            "UPDATE asset_reviews SET status='running',started_at=now() "
            "WHERE workspace_id=%s AND id=%s",
            (repo.workspace_id, review["id"]),
        )
        job = conn.execute(
            "SELECT j.image,j.base_id,p.request_id FROM character_image_jobs j "
            "JOIN character_projects p ON p.workspace_id=j.workspace_id AND p.id=j.project_id "
            "WHERE j.workspace_id=%s AND j.id=%s",
            (repo.workspace_id, review["image_id"]),
        ).fetchone()
        reference = None
        if job["base_id"]:
            base = conn.execute(
                "SELECT image FROM character_image_jobs WHERE workspace_id=%s AND id=%s",
                (repo.workspace_id, job["base_id"]),
            ).fetchone()
            if base and base["image"]:
                reference = bytes(base["image"])
    result = None
    status, error = "succeeded", None
    try:
        config = effective_settings(settings.model_copy(update={"workspace_id": repo.workspace_id}))
        definition = review["definition"]
        validate_selection(config, definition["provider"], definition["model"])
        with trace_call(
            config,
            dict(
                run_id=str(review["project_id"]),
                request_id=str(job["request_id"]),
                source="character",
                name=definition["name"],
                step_id=str(review["id"]),
                step_name="이미지 검수",
                provider=definition["provider"],
                model=definition["model"],
                original_request={
                    "image_id": str(review["image_id"]),
                    "character": review["character"],
                    "change": review["change"],
                    "agent_ref": review["agent_ref"],
                },
            ),
        ):
            result = review_image(
                config,
                definition,
                review["character"],
                review["change"],
                bytes(job["image"]),
                reference,
            )
    except Exception:
        status, error = "failed", "review_call_failed"
    with repo._connect() as conn:
        conn.execute(
            "UPDATE asset_reviews SET status=%s,result=%s,error_code=%s,finished_at=now() "
            "WHERE workspace_id=%s AND id=%s",
            (status, Jsonb(result), error, repo.workspace_id, review["id"]),
        )
    return True


def enqueue_automatic(
    repo: Any, image_id: UUID, settings: Settings, connection: Any = None
) -> None:
    enqueue_review(repo, image_id, uuid4(), None, settings, automatic=True, connection=connection)
