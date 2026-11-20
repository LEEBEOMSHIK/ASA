"""Explicit classification-only maintenance. No plan rewrite or video job creation."""
import argparse
from uuid import UUID, uuid4

from langchain.chat_models import init_chat_model

from asa.config import Settings
from asa.registry.audio_service import load
from asa.registry.repository import RegistryRepository
from asa.telemetry import trace_call
from asa.video_review import classify, save, sources


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', type=UUID, required=True)
    parser.add_argument('--version', type=int, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--refresh', action='store_true',
                        help='Explicitly replace review metadata only; never rewrite the plan')
    args = parser.parse_args()
    settings = Settings()
    repo = RegistryRepository(settings.database_url, settings.workspace_id)
    with repo._connect() as conn:
        original = load(conn, repo.workspace_id, args.request, args.version)
        texts = sources(original['answer'], original['settings'])
        row = conn.execute(
            'WITH RECURSIVE lineage AS ('
            'SELECT version,base_version,operation_id FROM script_versions WHERE workspace_id=%s '
            'AND request_id=%s AND version=%s UNION ALL '
            'SELECT v.version,v.base_version,v.operation_id FROM script_versions v JOIN lineage l '
            'ON v.version=l.base_version AND v.version<l.version '
            'WHERE v.workspace_id=%s AND v.request_id=%s) '
            'SELECT a.provider,a.model FROM lineage l JOIN script_attempts a '
            'ON a.id=l.operation_id AND a.workspace_id=%s AND a.request_id=%s '
            'ORDER BY l.version DESC LIMIT 1',
            (repo.workspace_id, args.request, args.version, repo.workspace_id, args.request,
             repo.workspace_id, args.request)).fetchone()
        exists = conn.execute('SELECT 1 FROM video_review_annotations WHERE workspace_id=%s '
                              'AND request_id=%s AND answer_version=%s',
                              (repo.workspace_id, args.request, args.version)).fetchone()
    if exists and not args.refresh:
        print('already_classified')
        return
    if not row:
        raise ValueError('original_planning_model_missing')
    print(f"review_sources={len(texts)} provider={row['provider']} model={row['model']}")
    if not args.apply:
        return
    model = init_chat_model(row['model'], model_provider=row['provider'],
                           api_key=settings.key_for(row['provider']).get_secret_value(),
                           timeout=settings.ai_timeout_seconds, max_retries=0,
                           max_tokens=settings.scene_plan_output_tokens)
    context = dict(run_id=str(uuid4()), request_id=str(args.request), source='agent',
                   name='영상 계획 검토 구절 분류', step_id='review_annotations',
                   step_name='원문 보존 분류', provider=row['provider'], model=row['model'],
                   original_request={'version': args.version})
    with trace_call(settings, context):
        raw = classify(model, texts)
    with repo._connect() as conn:
        current = load(conn, repo.workspace_id, args.request, args.version)
        if sources(current['answer'], current['settings']) != texts:
            raise ValueError('review_source_changed')
        save(conn, repo.workspace_id, args.request, args.version, raw, texts)
    print('review_metadata_saved; plan_and_video_jobs_unchanged')


if __name__ == '__main__':
    main()
