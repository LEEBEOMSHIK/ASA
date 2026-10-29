# AI Shorts Studio 아키텍처

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
