# AI Shorts Studio 아키텍처

## 후속 작업 상태 (ASA-105)
- AI 실행 status와 사람 검토를 포함한 work_progress는 별개다. 최근 작업 SSE와 상세가 같은 집계 함수를 사용한다.
- 공통 계약: kind/label/source_version/items/counts/status/resume_anchor. pending/queued/running/review/approved/excluded/failed/unknown 항목을 집계한다. 현재 개별 에이전트 답변 검토와 캐릭터 이미지 adapter를 지원한다. 별도 음성 등 매체별 실행·검토는 adapter를 추가한다.
- 완료 조건은 필요 항목 1개 이상 + 모두 확정. 전부 제외는 완료가 아니라 대상 없음. API 오류·불명확한 결과는 별도 확인 대상으로 유지한다.
- 제외/복원과 마지막 검토 버전은 work_item_preferences에 workspace/request/답변 버전/kind/item으로 저장한다. 이미지나 확정 기록을 삭제하지 않는다. 생성 중 제외/확정을 막고 project 행 잠금으로 생성 접수와 경합을 제어한다.
- 최근 작업은 최신 답변의 상태를 보여준다. 이전 답변 프로젝트는 버전 선택/보관함에서 보존된다. 프로젝트를 아직 열지 않은 캐릭터 답변도 미생성으로 집계한다.
- 확정 후 재생성하면 완료를 해제한다. 사용자가 새 검토본 대신 이전 이미지를 다시 확정할 수도 있다. reviewed_version보다 새로운 생성은 다시 검토가 필요하다.

## 개별 에이전트 실행 큐 (ASA-075/081)
현재 실행 화면의 `답변 생성 실행`은 요청을 저장하고 같은 요청 ID로 `/script/start`에 멱등 접수한다. PostgreSQL script_attempts 큐를 상시 로컬 워커가 처리한다. 별도 Redis/Docker는 필요 없다.

- `.env`의 `ASA_SCRIPT_AI_ENABLED=true`와 모델/API 키가 필요하다. `./scripts/run.ps1 script-worker`로 실행한다. 직접 실행은 `python -m asa.script_queue_worker --allow-paid-call`이다.
- 작업 공간당 한 건씩 순차 실행한다. 세션 advisory lock으로 여러 워커가 같은 작업 공간을 동시에 처리하지 않는다. 큐 한도 기본100건, 일일 실행 한도20건(시작한 요청 기준, DB 일자 경계)이다. 숫자 설정은 ASA_SCRIPT_QUEUE_LIMIT/ASA_SCRIPT_DAILY_AI_CALLS. 응답 출력은 기본 2,048토큰으로 제한하며 ASA_SCRIPT_OUTPUT_TOKENS로 조정한다.
- 새 실행 시 provider/model을 고정하고 호출 직전 허용 정책과 키를 재검증한다. 지침은 요청의 불변 등록 버전에서 읽는다.
- 실행 중 워커가 사라지면 다음 워커가 해당 요청을 unknown으로 마감하고 자동 재시도하지 않는다. 외부 API의 exactly-once를 보장하지 않는다. 모델 응답과 과금 여부가 불명확한 경우 관리자 모니터링/공급자 기록을 확인한다.
- 이전 수동 queued 요청은 automatic=false로 보존하고 소비하지 않는다. 수동 CLI는 자동 큐 요청을 처리하지 못한다.
- 대기 중 취소만 제공한다. AI 호출 중 취소/병렬 워커 슬롯/도구·다른 에이전트 위임은 지원하지 않는다. 고객 실행은 등록 버전의 지침과 output_schema를 사용한다. 고정 대본 역할이나 제목·내레이션 필드를 추가하지 않는다.
- 진행 화면은 입력/지침 기반 접수 정보, 앞선 작업 수, 상태, 경과 시간을 표시한다. 모델의 비공개 추론을 추측하거나 가짜 진행률을 표시하지 않는다. 폴링은 요청을 재접수하지 않는다.
- 실제 토큰은 공급자 응답에서 수집하며 비용은 호출 시 요율에 따른 예상값이다. 사용량 누락은 0이 아닌 미확인이다.

아래 초기 개발 기록 중 ‘고객 요청 저장만 지원/상시 큐 미구현’ 설명은 이 절로 대체한다.


ASA-058: [관리자 모델 카탈로그](model-management.md)는 workspace별 허용 모델·기본 모델·요율을 DB에 저장하고, AI 블록과 에이전트 버전의 모델 선택 및 실행 검증에 공통 적용한다. API 키는 서버 설정에 유지한다.

ASA-054: [관리자 AI 모니터링](ai-monitoring.md)은 workspace별 호출 이벤트를 PostgreSQL에 기록한다. LangChain callback으로 공급자 반환 사용량·실제 입력·응답·시간을 수집하고 호출 시점 요율로 예상 비용을 계산한다. 자동화/예약/고객 대본/CLI 요청 출처와 요청자·실행 ID를 보존한다. owner/admin API만 상세를 조회하며 외부 tracing 전송은 사용하지 않는다.

기준일: 2026-10-26. 사용자 확정: Next.js + FastAPI, LangGraph + LangChain, 로컬 개발,
운영 Docker, 외부 AI API, 개인 채널 MVP → SaaS. 저장소: C:/projects/ASA.

## 범위와 접근법

한 저장소의 모듈형 모놀리스 + 별도 Python 워커를 채택한다. 업무 코드와 배포 단위를 분리한다.
처음부터 마이크로서비스를 분리하는 안은 분산 트랜잭션·운영 비용 때문에 보류한다.
API 요청 안에서 영상 생성 전체를 실행하는 안은 시간 초과·재시작 복구 문제 때문에 제외한다.
현재 단계는 초기 구성이다. 영상 생성 서비스 전체나 운영 가능한 SaaS를 완성했다고 간주하지 않는다.

## 구조

```text
apps/web/                 Next.js App Router, 토큰과 공통 UI
services/backend/src/asa/ FastAPI, LangChain 모델 어댑터, LangGraph, 명시 실행 CLI 워커
services/backend/tests/   외부 AI 호출 없는 계약·승인 흐름 테스트
scripts/                 Windows 로컬 setup/run/check
deploy/                  운영용 Dockerfile와 Compose
docs/                    설계·실행·UX·작업 기록
WORKBOARD.md             사람과 AI의 개발 협업 보드
```

목표 실행: 브라우저 → Next.js → FastAPI → PostgreSQL 작업 큐 → 워커 → 외부 AI API / FFmpeg.
현재 구현 경계: 초기 안내 화면, health API, 대본 생성→승인 CLI, owner 세션,
workspace별 에이전트 초안·불변 버전·도구 목록과 등록 UI.
작업 큐·SaaS 사용자 인증·영상 렌더링·자산 업로드·외부 게시 API는 후속 구현이다.
LangGraph를 작업 큐나 과금 시스템으로 사용하지 않는다.

## 에이전트·자동화 확장

[에이전트와 자동화 빌더 상세 설계](agent-automation-design.md)를 확장 기능의 정본으로 사용한다.
사용자는 에이전트를 정의·버전 관리하고 워크플로 블록 또는 다른 LLM의 도구로 재사용한다.
ASA 도구와 사용자 에이전트만 허용하며 임의 외부 API·코드 실행은 v1에서 제외한다.
정의 레지스트리, workflow compiler, 공통 ToolDispatcher, run/invocation/event 원장을 추가한다.
사용자에게 입력 해석·호출 트리·결과·시간·비용·승인 상태를 제공하고 비공개 내부 추론은 저장하지 않는다.
입력·결과 원문은 workspace 권한이 적용되는 업무 payload로 관리하고 로그와 개발 보드에는 기록하지 않는다.
공통 실행 상태·하위 호출·중복 방지·비용 규칙은 상세 설계의 확장 계약을 따른다.
레지스트리와 owner 세션, 순차 자동화 초안 빌더는 구현됐다. 자동화 실제 실행·LLM 도구 호출은 후속 단계다.
고객용 첫 화면은 등록된 최신 에이전트 선택과 작업 입력을 제공한다. 요청은 customer_requests에
workspace·에이전트 버전·입력·원본 요청 ID와 함께 저장한다. 신규 요청은 saved(실행 전)이며
실행 큐에 넣거나 답변을 생성하지 않는다. 후속 실행 엔진이 상태·결과를 갱신하도록 연결할 예정이다.
목록은 20개씩 조회하며 상세에서 요청·상태·결과를 확인한다. 다시 작업은 이전 버전/입력을 복원하고
새 ID로 저장한다. 같은 ID의 동일 요청은 중복 저장하지 않고 다른 내용이면 충돌로 처리한다.
클라이언트는 상태·결과를 지정할 수 없다. 로컬 검증은 기존 owner 세션을 사용하고 SaaS 고객 인증은 미구현이다.
고객 화면은 별도 이력 메뉴 없이 왼쪽의 새 작업·최근 작업으로 탐색한다. 최근 작업은 스크롤
하단에서 20개씩 추가 조회하며 기존 목록을 유지한다. 실패 시 같은 위치에서 재시도할 수 있다.
오른쪽에 선택한 작업의 입력/상세를 표시하며 모바일에서는 dialog 메뉴로 전환한다.
등록 절차는 [에이전트 등록 가이드](runbooks/agent-registry.md)를 따른다.

## 제작 파이프라인

### 자동화 구성 화면 (ASA-030)

`/automations`는 등록된 에이전트/ASA 도구 버전을 순서대로 배치하는 초안 편집기다.
시작 요청 문자열 → 작업 블록들 → 마지막 출력으로 구성한다. 각 입력은 시작 요청,
앞 블록의 전체 출력/최상위 항목, 직접 값 중에서 선택한다. 임의 코드·표현식은 실행하지 않는다.
workspace별 automation_drafts에 JSON 정의와 revision을 저장하고 충돌 시 덮어쓰지 않는다.
게시 버전·실행 manifest·분기·병렬은 아직 미구현이다. 잘못 연결된 미완성 초안도 저장할 수 있으며
서버 구성 검증/연결 테스트에서 등록 버전·입력 누락·앞선 참조·자료 형식과 실제 전달 값을 검사한다.
연결 테스트는 유료 호출 없이 사용자 샘플 답변을 사용한다. asa.text.inspect만 실제 로컬 계산한다.
샘플 미입력/형식 오류에서 멈추며 실제 AI 응답으로 표시하지 않는다. 테스트 payload는 저장하지 않는다.
고객 실행 화면의 제작 단계는 아직 이 자동화 정의로 생성되지 않는다. 실제 실행 엔진 연결 시 통합한다.

목표: prompt → brief → script → script approval → scenes/voice/captions → render → review → export.
초기 그래프는 script → approval → approved/rejected까지이며 실제 영상 단계는 연결하지 않는다.
LangChain의 structured output을 Pydantic Script(title, narration)로 검증한다.
공급자 초기 구현은 OpenAI 어댑터이며 모델명·키는 환경 설정으로만 제공한다.
다른 공급자는 동일한 ScriptGenerator 계약을 구현한다. 공급자별 지원 기능은 별도 검증한다.
인터넷·비밀키 없는 테스트에서는 테스트 전용 생성기를 주입한다. 프로덕션의 조용한 가짜 응답은 금지한다.

## 실행과 복구

CLI는 PostgreSQL checkpointer를 사용한다. 테스트만 InMemorySaver를 사용한다.
승인 노드와 생성 노드를 분리해 승인 재개 때 대본을 재생성하지 않는다.
thread_id는 실행 UUID, 추후 서버가 workspace 권한을 검사한 뒤만 resume을 허용한다.
현재 CLI는 신뢰된 로컬 운영자 전용이며 SaaS API로 노출하지 않는다.
DB 마이그레이션은 명시적인 init-checkpoints 명령으로 실행하고 서버 시작 때 자동 실행하지 않는다.

후속 큐는 PostgreSQL jobs를 사용한다. 상태는 queued/running/waiting_approval/succeeded/failed/cancelled.
자동화 확장에서는 업무 상태의 정본을 runs/invocations로 통일하고 jobs는 queue/lease만 관리한다.
아래 초기 job 기반 설명은 이 확장 계약으로 대체되며 별도의 job_steps 업무 상태 테이블은 만들지 않는다.
claim은 FOR UPDATE SKIP LOCKED와 lease 만료·heartbeat로 관리한다. attempt별 최대 시간과 횟수를 둔다.
취소 요청과 실제 중단 완료를 구분하며 하위 FFmpeg 프로세스 종료 확인 후 cancelled로 바꾼다.
외부 호출은 (workspace_id, job_id, step, input_version) 고유 작업 원장으로 중복을 제어한다.
공급자 요청 ID와 결과 자산 ID를 저장한다. 제공자가 멱등성을 지원하지 않고 결과가 불명확하면
자동 재시도하지 않고 unknown_external_result로 사용자 확인을 요구한다.
네트워크 API timeout은 설정하며 초기 어댑터는 자동 재시도 0회로 둔다.

## 데이터·파일·비용

목표 엔티티: workspaces, memberships, channels, projects, project_versions, jobs, job_steps,
assets, approvals, usage_events, provider_requests. 모든 업무 레코드는 workspace_id를 포함한다.
승인은 대상 버전·해시와 연결하고 대본 수정 시 이후 자산과 승인을 무효화한다.
영상·음성·이미지는 DB가 아니라 로컬 .local/assets에 저장하고 DB에는 메타데이터·소유권·해시만 둔다.
SaaS에서는 Storage 인터페이스를 통해 S3 호환 저장소로 교체한다.
파일 경로는 사용자 문자열에서 직접 만들지 않고 서버가 발급한 ID를 사용한다.
비용은 공급자 응답의 실제 사용량·가격 버전으로 기록하고 추정 비용과 구분한다.
유료 작업 전 예산 예약, 동시 작업 한도, 최종 정산을 구현한 뒤 UI 생성 기능을 활성화한다.

## SaaS 확장 단계

1. 개인 MVP: 기본 workspace 하나, 생성·수정·검토·내보내기. 자동 게시와 결제는 제외.
2. 비공개 서비스: 인증·서버 권한·workspace 필터·복합 FK·격리 테스트, 백업·복원·감사 기록.
3. SaaS: 팀 RBAC, tenant별 큐 공정성·동시 실행 한도, 과금·보존 기간·삭제, 객체 저장소.
workspace ID를 클라이언트가 보냈다는 이유만으로 권한을 부여하지 않는다.
DB RLS를 추가할 경우 커넥션 풀에서 tenant context 초기화까지 검증한다.
OAuth 채널 연결·게시에는 별도의 승인·중복 게시 방지·정책 검증을 둔다.

## 운영 경계

개발은 Windows 로컬 Node/Python/PostgreSQL/FFmpeg. Docker·Redis·클라우드 DB를 요구하지 않는다.
운영은 web/api/worker/db 컨테이너. 웹/API 포트는 기본 loopback에만 노출하고 TLS reverse proxy는 배포 시 구성한다.
DB·자산 볼륨은 영속 보관, 비밀값은 런타임 주입. 이미지에 .env를 복사하지 않는다.
현재 worker는 수동 실행 프로파일이며 상시 큐 소비자가 아니다. 자동 재시작으로 유료 요청을 반복하지 않는다.
인증·비용 원장·큐·운영 복원 검증 전 인터넷 공개를 금지한다.

## 관측·검증

API liveness와 DB readiness를 구분한다. readiness에서 외부 AI를 호출하지 않는다.
초기 CLI는 실행 전체를 tracing_context(enabled=False)로 감싸 LangSmith 외부 추적을 차단한다.
로그에는 run ID·단계·소요 시간·오류 분류만 기록하며 키·원문 프롬프트·내부 추론은 남기지 않는다.
테스트: 승인 전 중단, 승인/거절 분기, 재개 시 재생성 방지, 잘못된 결정 차단, DB 미설정 readiness.
다음 단계: 실제 PostgreSQL 지속성·프로세스 재시작, 외부 API timeout/비용, FFmpeg 출력, tenant 격리 검증.

## 근거

### 고객 대본 단계 구현 범위 (ASA-029)

customer_requests의 원래 입력·등록 에이전트 버전을 고정한 채 script_stages에 현재 버전과
확정 버전을, script_versions에 불변 대본 버전을, script_attempts에 실행 시도를 저장한다.
모든 테이블은 workspace 경계를 갖는다. 요청 행 잠금·revision 비교로 동시 수정 충돌을 감지하고
operation ID와 대기/실행 중 요청 단일 제약으로 중복 저장·중복 claim을 막는다.
새 대본 버전은 기존 확정을 해제한다. 후속 미디어 단계는 아직 생성하지 않는다.

FastAPI는 인증·CSRF·입력을 검증하고 repository가 업무 규칙을 적용한다.
명시 실행 CLI가 단일 LangGraph 단계를 실행하며 LangChain 공급자 어댑터가 제목·대본 출력을 검증한다.
이 경로는 작업 상태를 DB에 저장하지만 재시작 체크포인트·lease 기반 복구를 제공하지 않는다.
외부 API와 DB 사이 exactly-once를 보장하지 않으며 불확실한 호출은 자동 재시도하지 않는다.
현재 UI는 AI 요청 저장까지만 수행한다. 자동 유료 실행은 예산·비용·복구 체계 연결 후 활성화한다.
도구가 연결된 에이전트는 실행을 거부한다. agent-as-tool 실행 엔진은 별도 후속 범위다.

- https://docs.langchain.com/oss/python/langgraph/interrupts
- https://docs.langchain.com/oss/python/langchain/models
- https://nextjs.org/docs/app/guides/self-hosting
- https://fastapi.tiangolo.com/deployment/docker/


## 자동화 실행 MVP (ASA-033)

자동화 카드 실행/예약은 automation_runs의 definition·manifest에 버전을 고정한다.
API 인증/CSRF → workspace 범위 repository → 로컬 runtime_worker 순서다.
LangGraph는 순차 실행과 확인 대기 종료를 담당하고 LangChain은 외부 모델·출력 계약을 담당한다.
재개 위치와 결과는 PostgreSQL next_step/steps에 저장한다. 이 경로는 LangGraph checkpointer를
사용하지 않으며 기존 승인 그래프 CLI와 별개다. 워커는 workspace 단위 advisory lock을 유지한다.
외부 호출 전 고유 호출 의도를 커밋하며, 중단/불확실 오류는 자동 재시도하지 않는다.
이는 외부 API까지 exactly-once를 보장하지 않는다. DB 연결 단절과 공급자 결과의 불확실성은
확인 필요 상태로 사용자에게 드러낸다. 확인 요청은 expected next_step으로 오래된 승인을 거부한다.

automation_schedules는 현재 예약 하나/자동화, 1회 또는 매일 한국 시간이다.
워크스페이스 잠금 안에서 due occurrence를 고유 실행으로 만들고 다음 시각을 갱신한다.
누락된 여러 시각은 하나로 합치고 활성 실행이 있으면 건너뛴다. 상한100개 대기/진행/확인 작업을 공유한다.
외부 AI 활성화는 명시 서버 설정이며 기본 비활성. 최근24시간 호출수/출력토큰 한도를 적용한다.
금액 예산, 토큰 실측 원장, SaaS 인증, 분기/병렬, agent-as-tool 내장 호출, 미디어 단계는 포함하지 않는다.

## 자유 연결 그래프 자동화 (ASA-035, 2026-10-27)

자동화 정의는 기존 steps 또는 graph(nodes/edges) 중 하나를 사용한다. 기존 순차 정의는 유지하며 사용자가 명시적으로 변환하고 저장한다. 좌표는 화면 배치이고 실행 순서는 edge의 next/yes/no/item/done 포트로 결정한다.

블록은 시작, 등록 도구/에이전트, 직접 AI 요청, 조건, 목록 반복, 최종 결과다. 직접 AI 요청은 서버 기본 모델 설정과 LangChain 출력 계약(글/글 목록)을 사용한다. LangGraph 실행기는 같은 그래프 평가기로 미리보기와 실제 실행을 처리한다. 미리보기의 AI는 사용자 샘플이며 유료 호출하지 않는다.

반복은 최대 20개 목록을 순차 처리한다. 본문은 해당 반복 블록으로 돌아오며 item/index는 본문에서, results는 완료 뒤에 참조한다. 각 반복마다 본문 출력을 초기화하여 이전 항목의 분기 결과가 섞이지 않는다. 모든 경로에서 준비되는 값만 후속 입력에 연결할 수 있다. 중첩 반복, 병렬, 임의 코드/HTTP는 지원하지 않는다.

실행 스냅샷과 graph_state를 DB에 저장한다. 승인 재개는 이미 완료된 호출을 다시 실행하지 않는다. 호출 의도 기록/고유 ID/불확실 결과 중단으로 중복 위험을 관리하며 exactly-once를 보장하지 않는다. 실행당 최대 200전이/AI20회와 기존 최근24시간 호출 한도를 적용한다. 예약은 저장 시 구성과 모델을 고정한다.

## 블록별 모델과 연결 UX (ASA-036)

ASA-038: 화면의 연결선은 전체 블록 사각형을 장애물로 삼아 계산한다. 경로 계산은 실행 그래프를 변경하지 않는다. 드래그 중 경로 스냅샷을 유지하고 이동한 블록의 임시 선만 갱신하며 놓을 때 재계산한다. 안전 경로가 없는 겹침 배치는 경고한다. 복합 실행·재개와 경로 상한 검증 근거는 `worklogs/2026-10-27-complex-graph-tests.md`에 기록한다.

직접 AI 노드는 선택적 model 필드를 갖는다. 비어 있으면 기존 서버 기본값을 사용한다. 선택지는 서버 ASA_AI_MODELS 허용 목록과 ASA_AI_MODEL 기본값에서 제공하며 키/endpoint는 클라이언트에 보내지 않는다. 현재 어댑터는 openai다. 등록 에이전트는 기존 모델 프로필을 유지한다.

명시 선택 모델은 실행/예약 manifest에 고정된다. 이후 기본 모델이 바뀌어도 명시 선택은 유지되며, 허용 목록에서 제거되면 실행하지 않는다. 기본 모델을 쓰는 기존 실행/예약은 기존 설정 불일치 보호를 유지한다. 허용 목록 등록은 공급자의 실제 접근 가능성/요금 검증을 대신하지 않는다.

그래프는 최종 결과를 하나로 수렴한다. 기존 다중 결과 데이터는 자동 수정하지 않는다. 연결 UX는 저장된 edge와 임시 연결을 구분하며 드래그는 좌표만 바꾼다. 작업 팔레트의 ASA 도구와 사용자 에이전트는 기존 kind/입력 계약을 사용한다.

## 전체 연결 라우팅 (ASA-040)
웹 routeConnections가 전체 edge를 안정적으로 정렬하고 합류 진입점을 분산한다. routeConnection은 이미 사용한 직교 구간의 평행 간격을 검사하며 후보 통로/경계 좌표 A*로 우회한다. 직교 교차는 허용하며 꺾임 비용으로 불필요한 우회를 줄인다. 실패 시 crowded 상태와 기존 장애물 회피 경로를 반환해 연결을 보존한다. 화면 경로만 바뀌고 실행 정의는 바뀌지 않는다.

## 외부 검색과 결과 선택 (2026-10-28)
고정 호스트 Brave 어댑터 → 표준 results[{title,url,snippet}] → map 제어 노드 → 후속 입력 경로로 연결한다. map은 외부 호출 없이 값 선택/이름 변경/타입 검증을 수행한다. 검색 호출은 기존 자동화 실행 manifest에 공급자를 고정하고 워커의 호출 기록·한도·불확실 실패 처리를 공유한다. 샘플 preview는 외부 API를 호출하지 않는다. 상세 범위는 [검색 연결 안내](external-search-result-mapping.md)를 참조한다.

## 직접 AI 공급자 선택 (ASA-043)
GraphNode.provider는 openai/anthropic 또는 생략이다. 생략은 기존 OpenAI 동작을 유지한다. 공급자별 서버 허용 모델 목록과 비밀 키를 사용한다. 실행/예약 manifest는 provider/model을 고정하며 재개 시 허용 모델과 공급자 키를 재검증한다. LangChain의 langchain-anthropic 어댑터를 추가했다. 기존 대본 생성 및 등록 에이전트 기본 프로필은 OpenAI를 유지한다. 내장 웹 검색은 이번 모델 선택 변경의 실행 범위에 포함되지 않는다.

## 모델 내장 검색 (ASA-044)
GraphNode.web_search는 기본 false이며 직접 AI의 글 출력에만 허용한다. ai_tool manifest에 고정하고 LangChain의 공급자별 서버 도구를 호출한다. 답변 인용은 HTTP(S) Markdown 링크로 보존하며 React가 링크만 안전하게 렌더링한다. 지원 모델 허용 목록 재검증, 검색 호출 상한, 중단 오류 및 비용 경계는 [내장 검색 안내](native-web-search.md)에 정의한다. 기존 OpenAI/Claude 선택 기능의 검색 미연결 상태를 대체한다.

## 연결점 UI (ASA-045)
기존 edge 스키마를 유지하면서 일반 카드90px·분기/반복166px와 우측 출력점/좌측 입력점으로 표현한다. 라우터 사각형과 포트 좌표를 동일하게 계산한다. 합류는 기존 분산 진입점을 유지한다. 임시 연결/블록 선택 메뉴는 로컬 UI 상태이며 확정 전 저장 그래프를 바꾸지 않는다.

## AI 카드 요약 (ASA-048)
직접 AI 카드는 280×216px 고정 크기이며 같은 nodeWidth/nodeHeight를 카드와 장애물 라우팅에 사용한다. 지시문 공백을 정리해 2줄 요약으로 표시하고 모델명·검색 사용 여부·필수 설정 안내를 렌더링한다. 모델 기본값은 기존 공급자 규칙을 유지하며 카탈로그 조회 중에 모델 미설정 오류를 단정하지 않는다. 저장 그래프 구조는 변경하지 않는다.

## 전체 카드 시각 규격 (ASA-049)
ASA-048의 치수를 대체한다. graph-card-layout.ts가 AI 360×248, 일반 280×120, 분기/반복 280×216을 정의하고 카드와 경로가 공유한다. 단일 입출력은 중앙, 다중 입력은 기존 분산 규칙, 두 출력은 140/188px이다. 간격 정리는 사용자 실행 시 위치만 조정하며 연결을 보존한다. 저장 정의 자동 마이그레이션은 하지 않는다.

ASA-076: 개별 에이전트 고객 화면은 요청/답변만 표시한다. 제작 단계는 자동화의 사용자 구성에 한정한다. 기존 대본 큐/출력 계약(제목·내레이션)은 유지하며, 범용 에이전트 출력 계약 확장은 별도 backend 작업이다.

### ASA-081 답변 계약
요청에 고정된 에이전트 지침을 system 메시지로 전달하고 원래 입력·선택한 이전 답변·수정 요청을 함께 전달한다. LangChain 구조화 응답은 등록된 output_schema를 감싼 value를 반환하며 서버가 스키마를 검사한 뒤 실제 답변만 저장한다. script_versions.answer JSONB가 신규 답변을 보존한다. 기존 title/narration 버전과 수정 기능은 호환성을 위해 유지한다. 내부 큐·API의 script 명칭은 호환용이며 개별 에이전트에 제작 단계를 부여하지 않는다. 초기 명시적 대본 CLI(asa.worker)는 별도 시제품이며 고객 에이전트 실행 경로에서 사용하지 않는다.

### ASA-084 사용자 입력 계약
input_schema.description은 항목 이름, enum은 선택지, default는 새 입력 폼 기본값, x-widget은 화면 방식이다. 슬라이더는 integer/minimum/maximum(step1)을 사용한다. 서버가 방식/타입/선택지/범위/기본값을 등록 시 검증하고 실행 시 실제 값의 enum/범위/필수를 검증한다. 기본값은 요청 누락을 서버에서 임의로 보충하지 않는다. 고객과 자동화 AI 호출에 입력 스키마를 함께 전달하여 내부 연결 키의 의미를 해석할 수 있게 한다. 기존 키와 등록 버전은 유지한다.


## 캐릭터 설정과 이미지 버전 (ASA-099)
- 사용자 선택 에이전트의 불변 등록 버전 → 기존 고객 요청/LangChain 워커 → 검증된 characters 답변 → 캐릭터 프로젝트 가져오기 → 이미지 큐로 연결한다. 개별 에이전트에 이미지 호출을 숨겨서 강제하지 않는다.
- `character_projects`는 원본 설정/요청ID/확정 버전 포인터를 보관하고 `character_image_jobs`는 인물별 설정 스냅샷·모델·수정문·기준 이미지ID·생성 이미지·사용량을 보관한다. API는 인증/CSRF/workspace, 서비스는 검증·멱등성, image_worker는 외부 호출을 담당한다.
- 동일 인물의 활성 작업은1개, 동일 요청UUID는1건. workspace 단위 advisory lock으로 동시 워커를 막는다. 외부 호출 exactly-once는 보장하지 않으며 불확실 호출은 자동 재시도하지 않는다.
- 승인 API는 예상 이전 버전을 비교한다. 새 이미지 생성이나 수정 완료로 기준 포인터를 바꾸지 않는다. 수정 시 해당 workspace/프로젝트/인물의 완료된 이미지 bytes를 실제 edit API에 첨부한다.
- 이미지는 MVP에서 DB bytea로 보관하고 인증된 image/png endpoint로만 제공한다. 운영 대용량 자산은 private object storage 전환 필요. 외부 URL 다운로드/사용자 파일 업로드는 현재 미지원.
- 도구 라이브러리 이미지 항목은 캐릭터 보관함으로 안내하며, 실제 생성·수정·확정은 캐릭터 설정 에이전트 답변에서 수행한다. 자동화 빌더의 범용 이미지 블록 실행과 장면별 이미지 생성은 별도 구현 대상이다.
- 이미지 호출은 관리자 ledger의 character 출처로 기록한다. 텍스트 입력/이미지 입력/이미지 출력 토큰의 서로 다른 요율을 적용하며 원시usage와 검증일/요율을 함께 보관한다. 사용량 누락은 미확인으로 표시한다.

- 캐릭터 구성은 workspace/request/source_version으로 유일하다. 저장된 script_versions.answer를 검증해 가져오며, 새 답변 버전은 별도 이미지 구성을 갖는다. 기존 이미지와 확정 포인터는 이전 답변에 보존된다.
# 개별 에이전트 답변 확정

AgentDraft.requires_approval은 기본 false이며 등록 버전의 definition에 보존된다. 개별 실행은 해당 버전의 설정을 사용한다. true인 작업은 최신 답변의 script_stages.approved_version을 기준으로 답변 검토 work_progress를 만든다. 답변 수정·재생성은 확정을 해제한다. 캐릭터 이미지 후속 작업이 함께 있으면 두 그룹을 통합하며 필요한 항목 모두 확정된 경우만 완료한다. 자동화 진행 중 승인은 기존 검토 노드에서 별도로 설정한다.


## DB 연결과 변경 알림 (ASA-111)
- API와 워커의 일반 DB 접근은 프로세스/DSN별 psycopg_pool을 공유한다(최소0, 최대8, 대기5초). 반환 시 트랜잭션 commit/rollback 후 재사용한다. 마이그레이션과 LISTEN은 전용 연결이다.
- LISTEN 연결은 프로세스/DSN별 1개이며 autocommit으로 대기한다. NOTIFY에는 workspace UUID와 state/script/image/automation 토픽만 넣는다. 요청 본문·이미지·키를 보내지 않는다.
- 변경 트리거는 commit 후 알림을 전달한다. SSE는 구독 revision을 먼저 잡고 최초 DB snapshot을 읽는다. 이후 변경 revision이 있을 때만 읽고, 값이 달라졌을 때만 snapshot을 전송한다. 15초 keepalive는 DB 조회가 없다.
- SSE는 45초마다 재연결하여 권한과 최신 상태를 재검증한다. LISTEN 복구 시 revision epoch를 바꿔 누락된 상태를 다시 읽는다. 기존 0.5초 DB 반복 조회는 제거했다.
- 에이전트·이미지·자동화 워커는 큐 알림을 기다린다. 작업이 없으면 최대30초에 한 번 복구·생존 확인을 한다. 자동화는 다음 예약 시각까지 기다리며, 다른 워커가 잠금을 보유하면30초 대기한다. DB 장애 시5초 후 재시도한다.
- 이미지 워커 heartbeat30초, 온라인 판정90초. 에이전트 판정도 최소90초로 조정했다. 주기 heartbeat 자체는 NOTIFY하지 않는다.
- 큐 소유권의 기존 advisory lock은 유지한다. unlock 실패 시 연결을 폐기하여 잠금이 남은 연결을 풀에 반환하지 않는다. 외부 호출 결과 불명확 시 자동 재호출하지 않는 정책은 유지한다.
- 캐릭터 이미지 화면의3초 조회와 자동화 실행 화면의2초 조회도 SSE로 전환했다.
- 알림은 영구 큐가 아니다. 업무 행이 진실의 원천이며, 재연결/저빈도 복구 조회가 알림 유실을 보완한다. 완전 무조회 또는 exactly-once를 의미하지 않는다.

### 캐릭터 이미지 설정 우선순위
- 이미지 요청은 현재 facts/proposed를 reference_context로, appearance/image_prompt를 primary_settings로 구분한다. 명시한 수정 요청은 해당 속성에 한해 우선, 그 다음 primary_settings, 마지막으로 충돌하지 않는 참고 정보 순서다. 모델에 전달하는 지침이며 시각적 준수를 보장하지는 않는다.
- 네 항목 모두 편집 가능하며 다음 생성·수정 요청 시 이미지 작업의 불변 character 스냅샷에 저장한다. 참고 편집은 외형/제작 지침을 자동 변경하지 않는다. 이전 버전은 변경하지 않는다.

## 선택적 이미지 검수 (ASA-123)
- 에이전트 편집의 ‘답변 이후 작업’에서 등록된 이미지 검수 에이전트 버전과 수동/자동 실행을 선택한다. 연결은 불변 등록 버전에 저장되므로 기존 요청에는 소급 적용하지 않는다.
- 검수 전용 에이전트는 이미지 결과 화면에서만 실행한다. 일반 텍스트 실행·자동화 블록에서 이미지 없이 실행하지 않는다. 자동화에서 이미지 검수 블록을 직접 연결하는 것은 아직 미지원이다.
- 이미지와 수정 전 기준 이미지를 서버의 같은 workspace 자산에서 읽고, 사용자가 편집한 설정과 함께 비전 입력으로 전달한다. 모델의 이미지 입력 지원 여부는 실제 공급자 호출에서 확인된다. 검수자의 지침·모델·출력 계약을 사용하며 자유 형식/구조화 답변을 지원한다.
- asset_reviews는 이미지 버전, 검수자 버전, 설정, 결과·상태·시간을 보존한다. 이미지 워커의 동일 workspace advisory lock 아래 처리하며, UUID 멱등 접수와 이미지별 활성 검수 유니크 제약을 둔다. 자동 검수 접수는 이미지 저장 트랜잭션의 savepoint에서 수행하며 실패는 이미지 job.review_error_code로 표시한다.
- 자동 검수는 이미지당 한 번 접수한다. 중단된 running은 unknown이며 자동 재시도·재생성·확정을 하지 않는다. 검수 오류는 이미지/사람 확정을 막지 않는다. 검수 기준 변경 시 UI가 재검수 필요를 안내한다.
- ai_usage_events의 source=character, step_name=이미지 검수, request_id=원래 고객 요청, step_id=검수 ID. 토큰은 공급자 응답에서 수집하고 예상 비용은 모델 카탈로그 요율로 계산한다. 이미지 base64는 로그에 저장하지 않는다.
- DB 변경 알림/SSE로 검수 상태를 갱신한다. 경과 시간은 브라우저 타이머이며 추가 DB 조회를 하지 않는다.
