"""Register a manual video reviewer and connect one planner without generating media."""
import argparse
import json
from pathlib import Path

from asa.config import Settings
from asa.registry.repository import RegistryRepository
from asa.registry.review_connection import connection_status
from asa.registry.schemas import AgentDraft

parser = argparse.ArgumentParser()
parser.add_argument('--planner-id', required=True)
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()
s = Settings()
r = RegistryRepository(s.database_url, s.workspace_id)
planner = r.get(args.planner_id)
if planner['draft'].get('after_tasks', {}).get('video_review'):
    print('already_connected; existing settings preserved')
    raise SystemExit(0)
name = '생성 영상 검수 에이전트'
existing = next((a for a in r.list_agents() if a['draft']['name'] == name), None)
if not args.apply:
    print('manual reviewer connection planned; no calls or generation')
    raise SystemExit(0)
backup = Path('.local/diagnostics/video-review-backups')
backup.mkdir(parents=True, exist_ok=True)
(backup / f"{planner['id']}-{planner['revision']}.json").write_text(
    json.dumps(planner, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
if existing is None:
    existing = r.save_settings(AgentDraft(
        name=name, icon='shield',
        description='생성 당시 계획과 영상 표본을 비교합니다. 음성·립싱크는 미검증입니다.',
        instructions='생성된 영상의 샘플 프레임을 생성 당시 제작 지시와 기준 이미지에 대조하세요. '
        '인물·의상·화풍, 구도·카메라, 표정·시선·동작, 시간·연속성 및 왜곡을 검사하세요. '
        '각 항목은 기대 내용과 실제 관찰, 관찰 시각을 구분하세요. 표본으로 알 수 없는 '
        '연속 동작이나 음성·대사·음색·음악·립싱크는 미검증으로 남기세요. '
        '프레임 밖의 사건을 추정해 합격시키지 마세요. 영상 재생성이나 확정을 지시하지 '
        '말고 사용자에게 검토 의견만 제공하세요. 한국어로 답하세요.',
        provider=planner['draft'].get('provider'), model=planner['draft'].get('model'),
        input_schema={'type': 'object', 'properties': {'context': {'type': 'string'}},
                      'required': []}, output_schema={'type': 'string'}, tools=[]))
with r._connect() as c:
    version = c.execute('SELECT max(version) AS v FROM registry_versions WHERE workspace_id=%s '
                        'AND agent_id=%s', (r.workspace_id, existing['id'])).fetchone()['v']
ref = f"agent:{existing['id']}:{version}"
connection_status(r, s, ref)
draft = dict(planner['draft'])
draft['after_tasks'] = {**draft.get('after_tasks', {}),
                        'video_review': {'agent_ref': ref, 'mode': 'manual'}}
saved = r.save_settings(AgentDraft.model_validate(draft), planner['id'], planner['revision'])
print('connected manual reviewer', existing['id'], 'planner revision', saved['revision'])
