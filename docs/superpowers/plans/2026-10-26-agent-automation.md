# Agent Automation Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for task-by-task implementation. Task 1 completed; unchecked tasks remain future work.

**Goal:** 사용자가 만든 에이전트를 도구로 재사용하고 블록으로 연결하며 실행 과정을 조회할 수 있게 한다.
**Architecture:** workspace별 버전 레지스트리, DB 실행·비용 원장, LangGraph 워커, 공통 ToolDispatcher.
Next.js 편집기와 실행 내역은 같은 서버 계약을 사용한다.
**Tech Stack:** 기존 Next.js/TypeScript, FastAPI/Python, PostgreSQL, LangGraph/LangChain.
**Spec:** [상세 설계](../../agent-automation-design.md)

## Global Constraints

- ASA 도구와 사용자 에이전트만 허용. 임의 HTTP API·코드·셸 실행은 v1 제외.
- 개발 서비스는 로컬, AI는 외부 API, Docker는 운영 전용.
- v1 workflow는 DAG·순차 실행·단일 input/output, 최대 50노드.
- root 상한 기본값: 모델20회/도구40회/child 깊이3/활성15분, 승인 만료7일.
- 스키마 깊이4/필드50/배열100/인라인64KiB. 정책 상한과 버전은 서버가 관리.
- API 키·원문 payload는 로그·WORKBOARD에 남기지 않는다. 실행 데이터는 workspace 권한으로 조회.
- 기존 CLI·초기 UI의 완료 상태와 새 기능 구현 상태를 혼동하지 않는다.
- Task 1 등록 기능은 구현·검증 완료. Task 2 이후 실행·빌더 기능은 미구현.

## Review Focus

1. 도구 참조를 통한 다른 workspace 노출 → Task1/2의 교차 workspace FK·권한 통합 검사.
2. 승인·재시작으로 외부 생성 중복 → Task2의 crash recovery·동시 승인 검사.
3. 분기 미실행 출력의 잘못된 참조 → Task3의 경로별 필수 입력 검사.
4. agent-as-tool 순환·병렬 요청으로 예산 우회 → Task4의 ancestor·원자적 root 예산 검사.
5. 재연결·재실행에서 기록/비용 중복 → Task2/4의 sequence·usage key 검사.

## Task 1 — 에이전트·도구 등록 (ASA-009)

Files (new): services/backend/src/asa/registry/{schemas,service,repository,routes}.py,
services/backend/src/asa/tools/catalog.py, services/backend/src/asa/auth/{session,dependencies}.py,
services/backend/migrations/, tests/test_registry.py, tests/integration/test_registry_db.py,
apps/web/app/agents/{page.tsx,[id]/page.tsx}, apps/web/app/tools/page.tsx.

Interfaces:
- Principal(user_id, workspace_id, roles), request 본문과 독립적으로 인증·인가.
- validate_agent(draft, catalog, principal) -> ValidationIssue[] (code, field_path, message).
- publish_agent(agent_id, expected_revision, principal) -> AgentVersion; 버전은 불변.
- ToolDescriptor(id, version, schemas, side_effect, available, unavailable_reason).

- [x] 제한 스키마·역할·목록 밖 도구·다른 workspace·동시 저장·버전 불변성 테스트 먼저 작성/실패 확인.
- [x] owner 세션의 로컬 bootstrap 및 CSRF 방어를 구현. 서버에서 workspace와 사용 도구 권한 결정.
- [x] workspace·registry DB migration, repository, validation/publish API 구현.
- [x] 결정적 asa.text.inspect 도구를 구현. 미디어 계획 도구는 unavailable로 표시.
- [x] 토큰·공통 UI로 편집/목록/버전 화면 구현. 실행 기반 완성 전 실행 버튼은 이유와 함께 비활성.
- [x] pytest tests/test_registry.py tests/integration/test_registry_db.py, ruff/mypy, web typecheck/build 실행.

수용: 사용자 초안 저장·검증·게시·재편집이 가능하고 과거 버전/다른 workspace를 바꿀 수 없음.
DB 통합 검사는 ASA-002 전용 DB 연결이 필요. 연결 없는 단위 검사만으로 완료 처리하지 않는다.

## Task 2 — 실행 기반·내역 화면 (ASA-010 + ASA-002/003 연계)

Files (new): src/asa/runs/{schemas,service,repository,events,routes}.py,
src/asa/execution/{queue,worker,budget,approval}.py,
tests/test_runs.py, tests/integration/test_execution.py,
apps/web/app/runs/{page.tsx,[id]/page.tsx}, apps/web/components/runs/.
기존 서비스 경로는 services/backend 기준. 기존 workflow.py는 adapter로 재사용하거나 같은 테스트로 대체.

Interfaces:
- enqueue_run(principal, definition_version, input, limits, idempotency_key) -> Run.
- append_event(run_id, type, metadata) -> RunEvent(sequence).
- decide_approval(principal, approval_id, target_hash, decision, idempotency_key) -> Run.
- reserve_budget(root_run_id, charge_key, maximum_cost) -> Reservation.
- claim_job(worker_id, lease_seconds) -> Job | None; complete_job는 현재 lease 소유자를 검사.

- [ ] 중복 enqueue, 키 재사용 충돌, 예산 동시 예약, stale lease, 이중 승인, 오래된 hash의 실패 테스트 작성.
- [ ] queue·outbox·payload·사용량·승인 migration과 서비스 구현. 글로벌 로그에는 payload 참조만 기록.
- [ ] 고정 agent를 1회 호출하는 실행기와 checkpoint 연결. 자동 도구 선택은 Task4까지 비활성.
- [ ] 실행 snapshot·호출 트리·SSE와 polling 복구 구현. 요청·이벤트마다 workspace 권한 검사.
- [ ] 취소 요청/실제 종료, needs_attention, payload 보존 정리와 감사 메타데이터 유지 구현.
- [ ] 프로세스 재시작·외부 응답 불명확·이벤트 재연결·payload 권한 테스트 통과 확인.
- [ ] intent 저장 직후/호출 직후/응답 원장 저장 후/checkpoint 전 장애를 주입해 invocation ID 유지·완료 결과 재사용·불명확 결과 정지 검증.
- [ ] runs/invocations를 업무 정본, jobs를 queue lease로 구현. 새 job_steps 테이블은 만들지 않음.
- [ ] 실행 내역 UI를 구현하고 로딩/빈 상태/연결 끊김/승인 대기/실패 화면 검증.

수용: 실제 로컬 DB에서 프로세스를 재시작해도 대기 실행을 찾아 승인·재개 가능.
키 없는 가짜 provider 테스트와 실제 provider 계약 검증을 별도 기록한다. 실제 유료 호출은 사용자 설정 후 수행.

## Task 3 — 블록 연결 빌더 (ASA-011)

Files (new): src/asa/workflows/{schemas,validator,compiler,service,routes}.py,
tests/test_workflow_validation.py, tests/integration/test_workflow_execution.py,
apps/web/app/automations/{page.tsx,[id]/page.tsx}, apps/web/components/workflows/.

Interfaces:
- validate_workflow(definition, catalog, principal) -> ValidationIssue[] (node_id, edge_id?, field_path).
- compile_workflow(version, manifest) -> LangGraph graph; 미검증 그래프를 컴파일하지 않는다.
- input/agent/tool/condition/approval/output의 discriminated union과 참조형 field mapping.

- [ ] 순환·누락 참조·도달 불가 노드·두 분기 누락·분기 밖 필수 참조·스키마 불일치 실패 테스트 작성.
- [ ] 순차 실행·조건식 allowlist·선택 안 된 분기 skipped 처리 구현.
- [ ] 진입 edge별 input_mapping 구현 및 true/false 양쪽 병합 테스트. 비활성 경로 참조 미평가 검증.
- [ ] draft 저장/충돌/게시/실행 manifest 고정과 Task2 실행 서비스 연결.
- [ ] 블록 목록·연결·설정·검증 오류·저장 상태 화면 구현. 키보드 폼으로도 동일 연결 편집 지원.
- [ ] Playwright 기반 UI 검사 도입: 키보드 연결·노드 오류 위치·save conflict·버전 유지.
- [ ] 통합 테스트, 타입·빌드, 360/768/1440px 및 light/dark 확인.

수용: 등록된 agent와 도구를 연결한 workflow를 저장·게시·실행하고 승인 후 결과 조회.
선택되지 않은 분기의 출력에 접근하지 않고 도구 미구현이면 게시/실행을 거부한다.

## Task 4 — LLM 도구 선택과 agent-as-tool (ASA-012)

Files (new): src/asa/agents/{runner,tool_binding}.py, src/asa/tools/dispatcher.py,
tests/test_agent_runner.py, tests/integration/test_nested_execution.py.

Interfaces:
- dispatch_tool(context, tool_version_id, arguments, call_sequence) -> ToolResult.
- run_agent(context, agent_version, input) -> AgentResult.
- ExecutionContext(root_run_id, invocation_id, principal, manifest, limits, ancestor_versions).

- [ ] 미허용 도구·위조된 별칭·자기/상호 호출·한도 초과·잘못된 출력 테스트 먼저 작성.
- [ ] 모델에 허용 도구 스키마만 제공. 모든 호출은 Dispatcher에서 다시 권한·입력·버전 검사.
- [ ] 요청·결과를 child Invocation으로 기록하고 동일 root 예산·시간·호출 한도 적용.
- [ ] 복수 tool call 순차 실행, child 승인 대기·취소를 root까지 전파.
- [ ] 불명확한 외부 결과는 needs_attention으로 정지, 실패해도 예약금 임의 해제 금지.
- [ ] 중첩 비용 중복 합산·depth 우회·권한 회수·checkpoint/원장 커밋 틈 재시작 테스트 실행.

수용: 사용자 agent를 단독 블록 또는 다른 agent의 도구로 실행하고 호출 트리·결과·비용 조회.
한도·권한·승인 경계를 모델 출력으로 우회할 수 없음.

## Task 5 — 쇼츠 템플릿·종합 수용 (ASA-013)

Files (new): src/asa/templates/shorts.py, tests/integration/test_shorts_template.py,
docs/runbooks/agent-automation.md. Existing: WORKBOARD.md, docs/verification.md.

- [ ] 기본 기획 스키마와 대본 검토 workflow fixture로 실패 테스트 작성.
- [ ] 요청 분석→기획 검토→대본 생성→승인 템플릿을 게시 버전으로 제공.
- [ ] 미디어 도구는 ASA-005 구현/검증 후만 템플릿에 활성 연결. 없는 기능은 완료처럼 표시하지 않음.
- [ ] 사용자 수정 fork·산출물 재사용·새 승인·과거 버전 조회를 종합 검증.
- [ ] 필수 기획 정보 누락→approval 검토→보완 입력 fork 검사. artifact revision 생성 및 하위 승인 무효화, manifest 불일치 재사용 거부 검사.
- [ ] scripts/check.ps1과 새 단위/DB/UI 테스트, 정적 보안·비밀값 검사 수행.
- [ ] 실제 모델/미디어 검증 여부, 비용, 운영 미검증 항목을 WORKBOARD와 검증 기록에 명시.

## 계획 검토

공통 Principal·Version·Run·ToolDescriptor 계약을 선행 정의하고 후속 작업이 재사용한다.
Task2가 ASA-003 실행 기반을 구현하므로 별도 큐·비용 엔진을 중복 만들지 않는다.
Task1의 저장·검증은 독립적이나 단독 실행 UI는 Task2, 도구 선택은 Task4 이후 활성화한다.
전체 기능 구현 승인을 위한 구체적 기준이며 현재 턴에서는 구현을 수행하지 않는다.
