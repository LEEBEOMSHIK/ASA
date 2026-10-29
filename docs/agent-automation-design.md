# 에이전트와 자동화 빌더 상세 설계 v1

상태: 구현 기준 설계. 기능 구현 완료를 의미하지 않는다. 기준일: 2026-10-26.
기존 [아키텍처](architecture.md)를 확장하며 로컬 개발·외부 AI API·운영 Docker 제약을 유지한다.

## 1. 목적과 범위

사용자는 프롬프트가 어떻게 해석되고 처리되는지 확인하고, 직접 만든 에이전트를
블록 또는 도구로 재사용하며, 개인 제작 절차를 자동화로 저장한다.

사용자 확정 범위:
- 작업 블록을 연결하는 자동화 빌더. 범용 앱 화면·DB 빌더는 제외.
- ASA가 제공하는 도구와 사용자 정의 에이전트만 도구 목록에 포함.
- 사용자가 임의 URL의 API, 스크립트, 패키지, 셸 명령을 실행하는 기능은 제외.
- 쇼츠 제작이 기본 템플릿이며 개인 workspace부터 SaaS 확장 경계를 유지.

설계자 결정: v1 워크플로는 순환 없는 그래프(DAG), 순차 실행, 단일 입력·출력 블록을 사용한다.
반복·병렬·스케줄·웹훅 시작·템플릿 공개 마켓은 후속 단계다.
에이전트 내부의 도구 선택은 제한된 반복을 허용하지만 워크플로 캔버스의 순환은 허용하지 않는다.

비교한 접근: 고정 제작 파이프라인만 제공하면 사용자별 자동화를 표현할 수 없다.
범용 코드/API 실행 빌더는 사용자 확정 범위를 넘는다. 따라서 등록된 기능만 연결하는 빌더를 채택한다.

## 2. 개념과 책임

| 개념 | 책임 | 실행 결과 |
|---|---|---|
| ToolDefinition | ASA가 검증한 기능의 계약·실행 어댑터 | 스키마가 있는 데이터 또는 자산 참조 |
| AgentVersion | 역할·모델 프로필·출력 형식·허용 도구·한도의 불변 버전 | 자유 텍스트 또는 항목별 결과와 도구 호출 기록 |
| WorkflowVersion | 블록·연결·입출력 매핑·승인 규칙의 불변 버전 | 최종 출력과 단계별 결과 |
| Run | 특정 버전과 입력을 사용하는 실행 인스턴스 | 상태·이벤트·비용·결과물 |
| Invocation | 에이전트 또는 도구 호출 한 번 | 입력·출력·상태·상하위 관계 |

FastAPI는 입력·인증·권한, application service는 버전·실행·승인 규칙을 담당한다.
워커가 queue에서 작업을 가져와 LangGraph를 실행한다. LangChain은 모델 메시지·도구 스키마·출력을 연결한다.
LLM은 도구 호출을 제안할 뿐, 실제 실행 권한은 서버의 ToolDispatcher가 결정한다.
기존 수동 CLI는 개발용으로 유지하고, 새 실행 서비스와 별도의 작업 시스템을 중복 구축하지 않는다.

## 3. 에이전트 생성과 도구 등록

에이전트 편집 필드:
- 이름·설명·역할 지침, 모델 프로필 ID(비밀키가 아닌 서버 설정 참조).
- 입력·출력 필드 편집기: string, number, integer, boolean, object, array와 required/enum/길이·개수 제한.
- 출력 기본값은 최상위 string(자유 답변), 선택적으로 object(항목별 답변). 입력 최상위는 object다. 실행기에서 string은 자유 텍스트 응답, object는 구조화 출력 계약을 적용한다. 자유 답변을 자동화로 연결할 때는 전체 문자열을 전달하며 필드별 참조는 제공하지 않는다.
- 허용된 ASA 도구 버전과 다른 에이전트의 게시된 버전.
- 최대 모델 호출·도구 호출·시간·비용. 상위 정책보다 느슨하게 설정할 수 없다.

필드 편집기는 제한된 JSON Schema를 생성한다. 임의 $ref, 원격 스키마, 실행 코드, 사용자 정규식은 v1 제외.
스키마 깊이 4, 필드 50개, 배열 항목 100개, 인라인 입출력 64 KiB를 기본 상한으로 한다.
미디어는 인라인 base64 대신 권한 검증된 asset_id로 전달한다. 이 수치는 설계 기본값이며 정책 설정으로 관리한다.

수명주기: draft → validate → publish(version N) → archive.
publish는 workspace 안에서 실행 가능한 버전을 고정한다는 뜻이며 외부 공개가 아니다.
draft 저장에는 revision과 If-Match를 사용한다. 동시 편집 충돌은 409로 알리고 덮어쓰지 않는다.
게시된 버전은 수정하지 않는다. 편집은 새 초안이며 기존 실행·워크플로는 이전 버전을 유지한다.

도구 등록은 AgentVersion을 가리키는 AgentToolBinding을 만든다. LLM에는 이름·설명·입력 스키마만 제공한다.
서버가 생성한 provider-safe 별칭과 내부 tool_version_id를 매핑하며 표시 이름을 실행 ID로 쓰지 않는다.
도구를 호출하면 child Invocation을 생성하고 검증된 출력만 상위 에이전트에 반환한다.
LLM이 지침으로 도구 목록을 늘리거나 다른 workspace ID를 지정해도 권한은 늘지 않는다.
자기 호출·상호 순환은 게시 시 의존 그래프로 거부하며 런타임에서도 ancestor 버전 ID를 확인한다.

보관은 새 실행·새 참조만 금지하고 이미 고정된 실행의 재개는 허용한다.
긴급 revoke는 모든 후속 호출을 차단한다. 실행 중 외부 호출의 철회 성공까지 보장하지 않는다.

## 4. ASA 도구 카탈로그

| 도구 ID 예시 | 계약 | 제공 시점 |
|---|---|---|
| asa.text.inspect | text → 글자 수·길이 기준 초과 여부 | 첫 등록/실행 단계, 네트워크 없음 |
| asa.channel.read_style | channel_id → 채널 스타일 | 채널 저장소·권한 구현 후 |
| asa.media.image | 장면 명세 → 이미지 asset_id | 이미지 공급자 구현·비용 검증 후 |
| asa.media.voice | 대본·음성 프로필 → 음성 asset_id | 음성 공급자 구현 후 |
| asa.video.render | 자산·자막·규격 → 영상 asset_id | FFmpeg 어댑터 구현 후 |

카탈로그의 계획 항목은 available=false와 사유를 표시하고 실행·게시 검증에서 거부한다.
설계 표에 존재한다는 이유로 실행 가능한 가짜 도구를 등록하지 않는다.
도구 버전은 입력·출력 스키마, side_effect(read/generate/write), 취소 지원, timeout,
멱등성 지원, 사용량·최대 비용 계산 방식을 가진다. 비밀키는 카탈로그 응답에서 제외한다.
외부 AI API는 ASA가 구현한 제공자 어댑터를 통해서만 호출한다.

## 5. 실행 기록과 프롬프트 분석

기본 쇼츠 템플릿은 기획 에이전트의 결과를 다음 필드로 저장한다:
topic, audience, tone, duration_seconds, constraints, assumptions, missing_information, proposed_steps.
사용자는 원래 입력과 이 결과를 나란히 검토하고 수정한다. 빠진 정보를 AI가 확정 사실처럼 채우지 않도록
assumptions를 분리한다. v1 input 블록은 최초 입력 전용이다. 필수 정보 누락은 기획 결과의
missing_information으로 표시하고 이어지는 approval에서 검토한다. 사용자는 보완 입력으로 fork한다.
중간 입력 대기 상태·입력 재개 API는 v1에 추가하지 않는다.
수정한 기획서는 새 결과 버전이 되고 이후 단계는 그 버전을 참조한다.
모든 사용자 워크플로에 기획 에이전트를 강제 삽입하지는 않는다.

실행 상세 화면:
- 개요: 작업·정의 버전, 상태, 현재 단계, 생성자, 시간, 예상/확정/미확정 비용.
- 호출 트리: workflow step → agent → tool/child agent, 부모 상태와 대기 이유.
- 선택한 항목: 입력, 적용 지침·모델 버전, 도구 인자, 결과·자산, 오류·재시도 이력.
- 검토: 대본·이미지·음성·영상 미리보기, 승인 대상 버전, 변경 후 재실행 영향.

요구 해석과 선택 이유의 짧은 요약·관측 가능한 호출 기록을 제공하며 비공개 내부 추론은 저장하지 않는다.
프롬프트·도구 인자·결과는 민감할 수 있는 업무 데이터다. 서버 로그·WORKBOARD에 넣지 않고
workspace 권한이 적용되는 payload 저장소에서 필요 시 조회한다. API 키·인증 헤더는 저장 전 제거한다.
이벤트에는 payload_ref·오류 코드·사용량 등 메타데이터만 두고 원문 payload를 브로드캐스트하지 않는다.
실행 payload와 체크포인트는 같은 보존 정책으로 정리한다. 초기 기본 보존 30일, 원본 프로젝트 자산은
별도 보존 정책을 따른다. 삭제 후에도 실행 ID·상태·합산 사용량처럼 내용 없는 감사 정보는 유지할 수 있다.

## 6. 실행 상태와 사용자 조작

공통 상태: queued, running, waiting_approval, cancel_requested, succeeded, failed, cancelled,
needs_attention. 분기에서 선택되지 않은 step은 skipped.
needs_attention은 외부 결과·비용이 불명확하거나 사람의 복구 판단이 필요한 상태다.
대본 거절은 실행 failed(reason=approval_rejected), 실행 취소는 cancelled로 구분한다.
현재 CLI의 approved/rejected는 향후 이 공통 실행 상태로 매핑하되 대본 승인 결과는 별도 유지한다.

승인 레코드는 run/step/입력 버전·해시/승인 정책을 고정한다. 승인 요청은 version과
Idempotency-Key로 중복·오래된 승인·권한 없는 승인을 거부한다. 승인 대상 변경 후 이전 승인은 재사용하지 않는다.
중첩 에이전트에서 승인이 필요하면 root까지 waiting_approval을 전파하고 실행 트리에 위치를 표시한다.
v1 builder의 approval 블록은 사용자가 명시적으로 배치하며 다른 노드의 결과를 수정하는 편집기는 아니다.
결과를 수정하려면 fork 실행을 만들고 수정 결과를 새 artifact revision으로 저장한다.

동일 입력의 기술적 재시도는 같은 논리 invocation의 attempt로 기록한다.
입력 수정·선택 단계부터 다시 실행은 parent_run_id를 갖는 새 Run을 만든다.
동일 workspace·동일 upstream 버전/입력 해시일 때만 기존 산출물을 명시적으로 재사용한다.
fork 요청은 동일 WorkflowVersion의 start_node_id와 replacements를 받는다. replacements는
새 input 또는 선택한 upstream 산출물의 새 revision이며 해당 스키마를 다시 검증한다.
새 revision에는 원본 revision, 생산 invocation, 스키마 버전, content_hash, 편집자를 기록한다.
재사용은 관련 manifest의 agent/tool/model/policy 버전과 입력 해시가 모두 같을 때만 허용한다.
변경된 결과의 후속 단계와 모든 후속 승인은 무효화하며 과거 Run은 수정하지 않는다.
다른 WorkflowVersion으로의 변경은 fork가 아니라 새 실행이다. 취소·진행 중인 외부 호출의
불명확한 결과를 fork에서 재사용하거나 새 호출로 덮지 않는다.
외부 효과가 있는 작업은 이미 실행된 결과를 조회하거나 승인받고, 단순 replay로 재실행하지 않는다.
취소는 root와 자식에 전파하고 자식 실행 lease가 정리된 뒤 완료한다. 원격 공급자가 취소를
지원하지 않으면 이를 표시하고 요청 비용을 정산하며 결과를 자동 다음 단계에 연결하지 않는다.

## 7. 워크플로 빌더

블록 유형: input, agent, tool, condition, approval, output.
condition은 필드 경로와 eq/ne/gt/gte/lt/lte/exists만 제공한다. eval·JS·Python 표현식을 실행하지 않는다.
입출력 연결은 자유 템플릿 코드가 아니라 {node_id, output_path} 구조의 참조와 literal 값이다.
전체 문자열 보간·반복·병렬 fan-out은 v1에서 제외한다.

검증 기준:
1. input/output 각 1개, 최대 50개 노드, 모든 ID·참조 존재, 순환·도달 불가 노드 없음.
2. condition의 true/false 연결이 각각 1개이고 양쪽 모두 output에 도달해야 한다.
3. 일반 노드의 활성 후속 연결은 1개. 조건 분기 후 병합은 실제 활성 경로의 입력만 소비한다.
4. 분기에서만 존재하는 값을 병합 후 필수 입력에 무조건 참조하면 거부한다. 기본값 또는
   양쪽 경로에서 공통 출력 계약을 만족하는 매핑을 명시해야 한다.
5. 필수 입력 누락·호환되지 않는 스키마·동일 workspace가 아닌 참조·철회/미구현 도구는 거부.
6. 실행 모델의 구조화 출력·tool calling 지원, 도구 권한·예산 설정을 실행 전 검사한다.

각 edge는 id/from/to와 input_mapping을 갖는다. 병합 목적 노드는 실제 진입한 edge 하나의
mapping만 평가한다. 예를 들어 true 경로 A→C는 narration을 A.output.narration에서,
false 경로 B→C는 narration을 B.output.narration에서 가져온다. 두 mapping을 각각 C의
입력 스키마로 검증하며 실행되지 않은 다른 edge의 참조를 조회하지 않는다.
각 mapping은 해당 edge에서 반드시 실행된 ancestor의 출력만 참조한다.

UI 흐름: 템플릿 선택 → 블록 추가/연결 → 노드 설정 → 검증 오류 해결 → 저장 → 버전 확정 → 실행.
저장과 실행은 분리하고, 실행 때 비용 한도·사용 모델·승인 지점을 요약한다.
시험 실행은 유료 실제 실행과 동일한 보호 규칙을 적용한다. offline fixture 검증은
개발 테스트 전용이며 실제 에이전트 결과처럼 사용자에게 표시하지 않는다.
활성 경로가 결정되지 않은 비용은 범위 또는 미산정으로 표시한다.

## 8. 런타임과 실행 한도

WorkflowVersion → 서버 검증 → 불변 execution manifest → LangGraph 컴파일 → queue/worker 실행.
manifest는 모든 agent/tool/model profile 버전과 정책을 고정한다. 그래프 checkpoint는
복구 상태이고 DB run/invocation/event가 사용자 관측·감사의 정본이다.

AgentRunner는 bounded model → proposed tool calls → ToolDispatcher → validated results 루프를 실행한다.
복수 도구 요청은 v1에서 순차 실행한다. agent-as-tool도 같은 Dispatcher와 사용량 원장을 거친다.
사용 권한은 실행자 현재 권한 ∩ 게시 버전의 허용 목록 ∩ 상위 호출 제한 ∩ workspace 정책이다.
같은 정의 버전이어도 도구 철회·멤버 권한 회수는 다음 호출에서 즉시 검사한다.

설계 기본 상한: root당 모델 호출 20회, 도구 호출 40회, child 깊이 3(root=0),
활성 처리 시간 15분, 승인 만료 7일. 하위 호출은 공통 root 한도를 소비한다.
승인 대기 시간은 활성 처리 시간에서 제외한다. 상한 증가는 정책 변경이며 LLM이 변경할 수 없다.
금액 예산은 사용자가 실행 전 지정하며 통화·가격표 버전을 고정한다. 초기에는 USD만 지원한다.
실제 호출 전 보수적 최대 비용을 원자적으로 예약하고 중첩/동시 호출도 root 예산을 공유한다.
가격 또는 최대 청구량을 산정할 수 없는 유료 도구는 v1에서 활성화하지 않는다.
외부 결과가 불명확하면 예약금을 유지하고 needs_attention으로 전환한다. 부모 비용은
leaf usage 합계로 계산해 부모·자식 중복 과금을 막는다. 실제 공급자 청구와의 정산 차이를 표시한다.

queue lease, outbox 이벤트, invocation 원장은 DB 트랜잭션으로 연결한다.
checkpoint와 원장이 별도 커밋될 수 있으므로 invocation 고유 키와 결과 조회로 재시작을 조정한다.
고유 키는 (workspace_id, root_run_id, node_instance_id, call_sequence)를 사용하고 attempt는 별도다.
node_instance_id는 Run 생성 시 workflow 노드마다 고정한다. agent 반복은 저장된 turn_index를 사용하며,
call_sequence는 DB에서 할당하고 checkpoint 재실행 시 새로 증가시키지 않는다.
모델 호출도 intent·입력 해시·예산 예약을 먼저 저장하고, 응답과 제안 tool call 목록을 원자적으로
확정한 후에만 dispatch한다. child ID는 저장된 부모 invocation과 제안 목록의 ordinal로 결정한다.
재개 시 완료 원장이 있으면 결과를 재사용한다. 호출 의도만 있고 전송 여부나 응답이 불명확하면
needs_attention으로 정지한다. 공급자 조회/멱등성으로 결과가 확정될 때만 복구하며 모델을 임의 재호출하지 않는다.
최소 한 번 실행 환경에서 공급자의 비멱등 호출까지 exactly-once라고 주장하지 않는다.

상태 정본은 runs/invocations다. jobs는 실행할 run을 가리키는 내부 queue/lease 레코드이며
업무 상태를 중복 저장하지 않는다. 기존 설계의 job_steps는 새로 만들지 않고 invocations로 통합한다.
job 재배정은 invocation ID를 바꾸지 않는다. 기존 CLI는 레거시 개발 경로로 유지하다가
새 실행 서비스가 준비되면 그 서비스의 클라이언트로 전환한다.

## 9. 데이터 모델과 API 계약

모든 업무 테이블은 workspace_id를 포함하고 복합 FK로 교차 workspace 참조를 막는다.
글로벌 ASA tool 정의는 서버 관리 카탈로그이며 workspace enablement가 사용 가능 범위를 결정한다.

| 엔티티 | 핵심 필드 |
|---|---|
| agents / agent_drafts | id, workspace_id, name, revision, draft_config |
| agent_versions | agent_id, version, schemas, instructions_ref, model_profile_version, limits, digest |
| agent_tool_bindings | agent_version_id, workspace_id, alias, description, input_schema |
| workflows / workflow_versions | draft_revision, nodes, edges, mappings, version, digest |
| runs | definition_version, root/parent_run_id, principal_id, manifest, input_ref, status, limits |
| invocations / attempts | run_id, parent_invocation_id, step_id, call_sequence, versions, payload_refs, status |
| run_events | run_id, sequence, event_type, invocation_id, metadata, timestamp |
| artifact_revisions | workspace_id, artifact_id, revision, origin_revision, invocation_id, schema_version, content_hash, payload_ref, editor_id |
| jobs | run_id, queue_state, lease_owner, lease_expires_at, heartbeat, attempt |
| approvals | invocation_id, target_hash, policy, decision, actor, expires_at |
| budget_reservations / usage_events | root_run_id, invocation_id, unique charge key, reserved/actual, currency |

API 전제: 인증된 principal로 workspace를 결정한다. 초기 개인 모드도 서버 측 owner 세션을
사용하고 요청 본문의 workspace_id를 권한 근거로 삼지 않는다.

| API안 (/api/v1) | 결과 |
|---|---|
| GET /tools | 허용된 도구·계약·사용 가능 여부 |
| POST /agents, PATCH /agents/{id}/draft | 생성·revision을 검사하는 편집 |
| POST /agents/{id}/validate, /publish | 검증 오류 또는 고정 버전 |
| POST /workflows, PATCH /workflows/{id}/draft | 블록·연결 저장 |
| POST /workflows/{id}/validate, /publish | 스키마·경로 검증, 버전 확정 |
| POST /runs | 정의 kind/id/version·입력·예산으로 202 + run_id |
| GET /runs/{id}, /invocations, /artifacts | 권한을 검사한 상태·호출 계층·결과 조회 |
| GET /runs/{id}/events?after=sequence | SSE 재연결, 영속 이벤트 재전송 |
| POST /runs/{id}/approvals/{approval_id} | 대상 hash·decision 검사 후 승인·재개 큐 등록 |
| POST /runs/{id}/cancel | 취소 요청202, 완료 전까지 cancel_requested |
| POST /runs/{id}/fork | 변경 입력·재사용 범위를 가진 새 Run |

API 설명은 구현 시 OpenAPI와 동기화한다. POST /runs는 Idempotency-Key 필수이며
같은 키+같은 입력은 같은 run, 다른 입력은409. 버전 충돌409, 입력 오류422, 미인증401,
권한 밖 리소스404. 예산 부족409(code=budget_exceeded). SSE는 run별 순번으로 중복 제거하며,
보존 범위 밖 cursor에는410과 snapshot 재조회 안내를 반환한다. 연결 끊김을 실행 실패로 처리하지 않는다.

## 10. 화면과 수용 기준

왼쪽 탐색: 프로젝트 / 에이전트 / 도구 / 자동화 / 실행 내역.
에이전트 편집: 설정, 입출력, 사용 도구, 시험 실행, 버전.
빌더: 왼쪽 블록 목록, 중앙 연결, 오른쪽 설정, 하단 검증 오류와 실행 결과.
실행 상세: 상단 요약, 왼쪽 호출 트리, 오른쪽 입력/결과/사용량/이력.
기존 tokens.css와 공통 UI를 사용한다. 드래그뿐 아니라 버튼과 선택 폼으로도 연결을 편집할 수 있다.
자동 저장 실패·충돌을 명시하고 실행 중인 정의가 편집으로 바뀌지 않는다는 점을 표시한다.

최소 수용 시나리오:
1. 사용자 에이전트를 단독 실행하고 구조화된 결과·설정 버전 조회.
2. 상위 에이전트가 허용된 하위 에이전트를 호출하고 계층·비용 확인.
3. 미허용 도구·다른 workspace·자기 호출을 실행 전 또는 dispatch에서 거부.
4. 블록 연결→조건 분기→승인 대기→재개. 잘못된 입력의 위치를 편집기에서 안내.
5. 중단 후 재개해도 기존 결과를 중복 생성하지 않음. 불명확한 외부 결과는 자동 재시도하지 않음.
6. 동시 중복 승인, 오래된 승인, 예산 초과, 취소 경합 검증.
7. 이벤트 재연결 시 중복 없음, 미실행 분기는 skipped, 비밀값은 이력에서 제외.
8. 키 없는 테스트와 실제 API 검증을 구분하고 실제 모델 없이는 품질·비용 검증 완료로 보지 않음.

## 11. 구현 순서와 남은 운영 설정

[구현 계획](superpowers/plans/2026-10-26-agent-automation.md)을 따른다.
정의·등록 → 실행 기반과 내역 → 블록 편집기 → LLM 도구 선택·agent-as-tool → 쇼츠 템플릿.
앞 단계의 단독 agent는 구조화된 응답을 반환하는 모델 호출 1회만 수행한다. 허용 도구 설정은
저장할 수 있어도 dispatch 구현 전에는 사용 가능하다고 표시하지 않는다. UI 시험 실행도 실행 기반 완성 후 활성화한다.
선행 ASA-002/003의 DB·queue·비용 원장은 이 계획의 실행 기반 작업과 함께 진행한다.
인증·workspace 권한의 최소 구현을 먼저 진행하고 SaaS 팀·과금 전체는 ASA-007에 남긴다.
DB 접속, 실제 AI 모델/키, 미디어 공급자, FFmpeg는 운영 설정으로 남아 있다.
설정이 없어도 스키마·검증기·화면 개발은 가능하지만 실제 실행 연동 완료로 처리하지 않는다.
