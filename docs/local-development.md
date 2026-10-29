# 로컬 개발

## AI 모니터링 추가 적용 (ASA-054)
`uv run --locked --project services/backend python -m asa.registry.init` 이후 API와 자동화 워커를 재시작한다. 관리자 메뉴 **AI 사용량·비용**(`/monitoring`)에서 확인한다. 기본적으로 비용 요율은 비어 있으므로 `ASA_AI_PRICES`를 설정해야 비용을 계산한다. [설정·집계·권한·미확인 처리](ai-monitoring.md)를 참고한다. 로컬 검증은 모의 HTTP 응답으로 수행하며 실제 유료 호출을 하지 않는다.

## 전제

저장소 루트 C:/projects/ASA에서 PowerShell로 실행한다. 개발에 Docker는 사용하지 않는다.
Node.js 22 이상(검증은 24), uv, Python 3.13 x64, PostgreSQL 17/18을 사용한다.
Windows ARM64 기본 Python에는 psycopg-binary wheel이 없어 x64 Python을 사용한다.
setup은 아키텍처를 명시하여 x64 Python 3.13을 선택한다.
Python 설치 위치는 스크립트에 사용자 절대 경로로 고정하지 않는다.
FFmpeg는 영상 구현 단계에 필요하며 현재 CLI check에서 설치 여부를 알린다.

## 의존성 설치

```powershell
Set-Location C:/projects/ASA
./scripts/setup.ps1
```

uv.lock, package-lock.json으로 의존성을 고정한다. setup은 .env가 없을 때만 예시를 복사한다.
기존 DB·역할·환경 파일을 자동 변경하지 않는다. 검증 중에는 유료 AI API를 호출하지 않는다.

## PostgreSQL 준비

현재 작업 PC에는 ASA 전용 클러스터 `.local/postgres`와 DB가 구성되어 있다.
주소는 127.0.0.1:55439이며 앱은 비관리자 역할을 사용한다. 기존 다른 프로젝트 DB는 변경하지 않는다.
이미 구성된 PC에서는 bootstrap을 다시 실행하지 않고 `./scripts/database.ps1 start`를 사용한다.
`status`와 `stop`도 지원하며 ASA 전용 클러스터만 대상으로 한다.

새 PC에 PostgreSQL 18을 설치한 후 독립 클러스터가 필요한 경우:

```powershell
uv run --locked --project services/backend python scripts/bootstrap-registry.py
```

기본 설치 폴더가 다르면 ASA_POSTGRES_BIN을 지정한다. 설정된 .env나 기존 클러스터는 덮어쓰지 않는다.
setup이 복사한 수정하지 않은 .env.example과 동일한 파일만 자동 설정으로 대체한다.
DB 접속값과 로컬 owner 접근 키는 .env에, 관리용 접속값은 .local/postgres-admin.env에 보관한다.
두 파일은 Git에 포함하지 않는다. bootstrap 실패 후 남은 클러스터는 임의 삭제하지 말고 상태를 확인한다.

기존 PostgreSQL을 직접 설정하는 경우에는 다음 수동 절차를 사용한다.

로컬 PostgreSQL 서비스를 시작하고 관리자 계정으로 psql에 접속한다.
아래는 새 전용 DB가 없는 경우의 수동 준비 예시다. 기존 DB가 있으면 먼저 확인한다.

```sql
CREATE ROLE asa LOGIN;
\password asa
CREATE DATABASE asa OWNER asa;
```

.env의 ASA_DATABASE_URL에 해당 계정과 DB를 설정한다. 비밀번호의 예약 문자는 URL 인코딩한다.
관리자 계정 비밀번호를 코드나 작업 보드에 기록하지 않는다.
ASA_OWNER_ACCESS_KEY는 32자 이상의 무작위 값으로 설정한다. ASA_WORKSPACE_ID도 설정하고
`uv run --locked --project services/backend python -m asa.registry.init`으로 등록 테이블을 초기화한다.
통합 테스트에는 별도 DB의 ASA_TEST_DATABASE_URL을 설정한다. 테스트는 임의 이름의 스키마를 만들고 정리한다.

## 서비스 실행

각각 별도 터미널에서 실행하고 Ctrl+C로 해당 프로세스를 종료한다.

```powershell
./scripts/run.ps1 web
./scripts/run.ps1 api
```

웹: http://127.0.0.1:3000 (현재 PC 3001), API 문서: http://127.0.0.1:8127/docs.
Next.js가 /api/v1 요청을 8127로 전달한다. API 주소 변경 시 ASA_API_ORIGIN과 웹 재시작이 필요하다.
3000/3001 외의 웹 포트를 쓰면 ASA_ALLOWED_ORIGINS JSON 목록에도 해당 origin을 추가한다.
GET /health/live는 프로세스 상태, /health/ready는 DB 연결 상태다.
ready가 200이어도 인증·큐·외부 AI·FFmpeg·전체 영상 제작 준비를 뜻하지 않는다.
에이전트·도구 등록 화면은 API에 연결되어 있다. 영상 제작과 자동화 실행은 아직 연결되지 않았다.
고객 첫 화면의 왼쪽 ‘최근 작업’은 DB에 저장한 요청과 결과/상태를 조회한다. 스크롤하면 오래된
작업을 추가로 불러온다. 별도 이력 목록이나 페이지 이동 메뉴는 없다. 신규 요청은 ‘실행 전’이며
자동 실행되지 않는다. 업데이트 후 `python -m asa.registry.init`을 기존 uv 실행 방식으로 명시 실행하면
기존 자료를 보존한 채 customer_requests 테이블이 추가된다. 다시 작업은 새 요청으로 저장한다.
로컬 owner 로그인에는 .env의 ASA_OWNER_ACCESS_KEY를 사용한다. AI 공급자 API 키와 다른 값이다.
로그인은 `/login` 관리자 전용 페이지에서 진행한다. 미인증 관리 페이지 접근 시 자동 이동한다.
`./scripts/run.ps1 api`는 해당 프로세스만 development·테스트 로그인 허용으로 실행한다.
로컬 로그인 화면의 ‘테스트 로그인’ 버튼으로 키 입력 없이 현재 작업 공간에 접근할 수 있다.
테스트 로그인도 실제 저장 권한을 갖는다. 별도 데모 데이터가 아니다.
직접 API를 실행할 때는 ASA_ENVIRONMENT=development와 ASA_DEV_LOGIN_ENABLED=true가 모두 필요하다.
기본값·운영 Docker는 비활성이다. API는 loopback에 바인딩하고 forwarded header를 신뢰하지 않는다.

## 수동 워커

```powershell
./scripts/run.ps1 worker-check
uv run --locked --project services/backend python -m asa.worker init-checkpoints
```

check는 설정 존재와 FFmpeg 실행 파일을 확인한다. DB 인증이나 외부 AI 연결 성공 검사가 아니다.
init-checkpoints는 해당 DB에 LangGraph 체크포인트 테이블을 만든다. 새 전용 DB를 사용한다.
상시 큐 워커는 후속 구현이며 이 CLI를 서비스처럼 자동 재시작하지 않는다.

외부 AI 사용 시 .env에 ASA_AI_PROVIDER=openai, ASA_AI_MODEL, ASA_AI_API_KEY를 지정한다.
모델은 structured output 지원 여부를 공급자 문서로 확인한다. 모델을 임의로 고정하지 않는다.
아래 명령은 유료 호출이 발생할 수 있으며 사용자가 직접 실행하는 절차다.

```powershell
uv run --locked --project services/backend python -m asa.worker draft --prompt '고양이의 우주여행' --allow-paid-call
uv run --locked --project services/backend python -m asa.worker resume RUN_UUID --decision approve
# 거절은 --decision reject. RUN_UUID는 draft가 출력한 run_id로 교체.
```

승인 후 결과는 approved이며 영상 생성 완료가 아니다. 재개는 기존 대본을 다시 생성하지 않는다.
CLI는 신뢰된 단일 운영자용이다. SaaS 사용자에게 임의 run ID로 실행 권한을 제공하지 않는다.
API timeout 뒤 공급자 결과가 불확실하면 새 draft를 자동 재시도하지 말고 사용량부터 확인한다.

## 검증

### 자동화 구성 및 연결 테스트

고객 사이드바 ‘자동화 만들기’ 또는 관리자 메뉴 ‘자동화’에서 `/automations`를 연다.
업데이트 시 기존 초기화 명령 `python -m asa.registry.init`으로 automation_drafts 테이블을 추가한다.
1. 목록에서 자동화를 열거나 새로 만든 뒤 이름을 입력한다. 흐름의 ＋를 눌러 에이전트/도구를 선택한다.
2. 가운데 블록을 선택하여 입력 항목마다 ‘시작 요청’, ‘앞 단계 결과’, ‘직접 입력’을 선택한다.
3. ‘구성 검증’으로 누락/잘못된 연결을 확인하고 ‘초안 저장’한다.
4. ‘연결 테스트’에서 요청과 에이전트 샘플 결과를 입력하고 ‘입력 전달 테스트’를 누른다.

에이전트 샘플은 사용자가 제공하는 테스트 값이며 실제 모델 응답이 아니다.
대본 길이 검사는 실제 로컬 계산하고 전달 입력과 결과를 함께 표시한다.
테스트 입력/샘플/결과는 브라우저 메모리에만 유지된다. 연결 테스트는 샘플 전용이다. 실제 실행/예약은 목록 카드에서 별도로 연다.
순서 변경/블록 제거 후 입력 참조는 자동으로 다른 결과에 바꾸지 않는다. 검증 오류에서 재연결한다.

### 고객 대본 단계 실행

고객 화면에서 요청을 저장하거나 최근 작업을 선택한 뒤 ‘대본 단계 시작하기’를 누른다.
제목·대본 직접 작성, 새 버전 저장, 이전 버전 비교, 현재 버전 확정은 즉시 DB에 저장된다.
AI 첫 작성/재작성 버튼은 요청만 저장한다. 자동 실행 서비스는 아직 연결하지 않았다.
등록 에이전트에 도구가 연결되어 있으면 현재 대본 워커는 해당 에이전트 실행을 차단한다.

모델 설정 후 운영자가 화면의 ‘운영자용 실행 정보’에 있는 작업 ID와 요청 ID를 사용한다.
다음 명령은 실제 외부 API 비용이 발생할 수 있다. 대본 요청 한 건만 처리한다.

```powershell
uv run --locked --project services/backend python -m asa.script_worker REQUEST_UUID ATTEMPT_UUID --allow-paid-call
```

실행 후 ‘대본 상태 새로고침’으로 결과를 조회한다. AI 결과도 새 버전으로 보존하며 이전 버전을 덮어쓰지 않는다.
대기 중인 요청만 고객 화면에서 취소할 수 있다. 실행 중 호출 취소는 지원하지 않는다.
응답 오류는 결과 확인 필요(unknown)로 남기며 공급자 사용량·결과 확인 후에만 새 요청을 만든다.
워커 강제 종료 또는 결과 DB 저장 실패로 running에 남는 경우 자동 재실행하지 않는다.
공급자 결과와 DB를 운영자가 대조해야 하며, 이 상태의 자동 복구 UI·lease·비용 원장은 후속 구현이다.
기존 `asa.worker draft` 승인 그래프 CLI와 고객 대본 요청은 별도 경로다.

```powershell
./scripts/check.ps1
```

백엔드 테스트·린트·타입, 웹 타입·빌드를 실행한다. 테스트는 외부 AI를 호출하지 않는다.
실제 DB 지속성·FFmpeg·유료 모델·브라우저 검증 결과는 docs/verification.md를 확인한다.

기본 3000 포트가 사용 중이면 Next.js가 다른 포트를 선택하므로 터미널에 표시된 URL을 따른다.
워커 실행은 상속된 설정과 무관하게 LangSmith 추적 전송을 비활성화한다.
실행 시작 시 run_id를 즉시 출력한다. 실패 뒤에도 해당 ID를 보관하고 새 유료 실행 전에 DB·공급자 상태를 확인한다.


### 자동화 실행과 시간 예약 (ASA-033)

`python -m asa.registry.init`으로 실행/예약 테이블을 추가한 뒤 별도 터미널에서
`./scripts/run.ps1 automation-worker`를 실행한다. API와 웹도 기존 로컬 프로세스로 실행한다.
목록 카드의 실행 → 작업 내용 → 자동화 실행에서 단계별 실제 결과를 확인한다.
편집 화면의 ‘이 단계 결과를 확인한 뒤 계속하기’를 켜면 해당 결과 뒤에서 멈춘다.
확인 완료는 그 단계에만 적용되며, 이미 완료된 단계는 다시 호출하지 않는다.

시간 예약은 한 번/매일, 한국 시간으로 설정한다. 예약 저장 당시 구성/에이전트 버전을 고정한다.
편집을 예약에 반영하려면 예약을 다시 저장한다. PC/워커가 꺼져 있던 동안 누락된 예약은
재시작 시 한 번으로 합친다. 이전 작업이 진행/확인 대기 중이면 다음 예약을 건너뛴다.
대기열이 가득 차면 예약 시각을 유지하고 공간이 생겼을 때 처리한다. 예약 끄기는 이미 생성된 실행을 취소하지 않는다.

기본 `ASA_AUTOMATION_AI_ENABLED=false`에서는 실제 ASA 길이 검사만 실행할 수 있다.
외부 AI는 서버 .env의 ASA_AI_PROVIDER/MODEL/API_KEY와 위 활성화 설정이 모두 필요하다.
기본 최근 24시간 호출 한도20회, 응답 최대2048토큰. 실패/결과 불확실 호출도 한도에 포함한다.
금액 예산·실제 요금 원장·사용량 집계 UI는 아직 없다. 공급자 측 지출 제한도 설정해야 한다.
워커 시작 후 설정을 바꾸면 재시작한다. 모델이 예약 스냅샷과 다르면 실행을 멈춘다.
현재 다른 도구를 내장 호출하는 에이전트는 차단한다. 각각 별도 작업 블록으로 연결한다.
실행 중 취소/자동 재시도/결과 수정 후 분기 재실행/미디어 생성은 후속 범위다.
재시작 시 running은 확인 필요로 남기고 연결된 예약을 끈다. 공급자 결과를 확인한 뒤 새 실행을 준비한다.
고객 대본 버전 관리와 자동화 실행 기록은 아직 별도 기능이다.

### 자유 연결 빌더 (ASA-035)

마이그레이션 `python -m asa.registry.init`은 실행 테이블에 graph_state를 추가한다. 기존 API/웹/automation-worker 로컬 프로세스를 사용한다.

/automations → 새 자동화에서 블록을 추가하고 제목을 드래그해 배치한다. 출구를 누른 뒤 대상 블록을 누르거나, 설정의 다음 블록 선택으로 연결한다. 조건은 맞으면/아니면 두 경로를 연결한다. 목록 반복은 각 항목 경로 끝을 반복 블록으로 돌려보내고 반복 완료 경로를 최종 결과로 연결한다. 직접 입력 목록은 한 줄에 한 항목이다.

직접 AI 요청은 별도 에이전트 등록 없이 지시문/입력 출처/글 또는 글 목록을 설정한다. 샘플 테스트는 API 비용 없이 경로와 도구 계산을 확인한다. 실제 AI에는 기존 서버 모델/키/활성화 설정이 필요하다. 설정 변경 뒤 워커를 재시작한다.

체험용 · 조건과 반복은 로컬 도구만 사용한다. 검증용 · 직접 AI 요청은 샘플 테스트 예제다. 제작 화면의 고정 6단계와 그래프 자동화는 아직 별개이며 이미지/영상 생성 도구는 후속이다.

### 직접 AI 모델 선택과 연결 편집 (ASA-036)

복합 연결 회귀는 `node --experimental-strip-types --test apps/web/lib/graph-routing.test.mjs`로 검사한다. 로컬 자동화 목록의 ‘검증용 · 복합 분기와 반복’은 샘플 연결 테스트용 초안이다. 실제 AI 실행에는 별도 공급자 설정이 필요하다. 블록이 겹쳐 연결 경고가 나타나면 블록 사이를 띄운다. 이동 중 선은 임시 표시이며 놓으면 장애물을 피하도록 다시 계산한다.

직접 AI 블록의 ‘사용할 AI 모델’은 서버 설정에 등록한 모델 목록에서 선택한다. 루트 .env의 ASA_AI_MODELS는 JSON 문자열 배열이며, 각 값에는 사용 권한이 있는 실제 모델 ID를 넣는다. ASA_AI_MODEL 기본값도 목록에 포함된다. 현재 공급자는 openai 하나다. 설정 뒤 API와 automation-worker를 재시작한다. API 키는 서버의 ASA_AI_API_KEY에만 저장한다. 키가 없으면 목록은 확인할 수 있지만 실제 AI 호출은 할 수 없다. 등록은 공급자 접근 가능성/요금 검증이 아니다.

모델 미선택은 서버 기본 모델이다. 명시 선택은 실행/예약에 고정되며, 허용 목록에서 제거하면 새 실행/예약 진행이 차단된다. 기존 기본 모델 예약의 기본값 변경 보호는 유지된다. 운영 compose에는 API/worker 모델 목록 전달을 추가했으나 운영 자동화 워커 배포/실제 운영 실행 검증은 별도다.

‘다음 블록 연결’ → 대상의 ‘여기로 연결’로 연결한다. 기존 연결 교체 안내를 확인하고, 취소/Esc/빈 캔버스로 연결을 취소할 수 있다. 드래그는 8px 격자로 정렬하고 설정 선택과 분리된다. 최종 결과는 하나를 유지한다. 오래된 초안에 결과 블록이 없으면 경고의 ‘최종 결과 복원’을 사용하고, 여러 개이면 여분을 수동 제거한다.

## 웹 검색 (ASA-042)
Brave API 기반 `asa.web.search:1`과 그래프 `map`(결과 항목 선택)을 제공한다. 환경 설정과 샘플 테스트 방법은 [검색 연결 안내](external-search-result-mapping.md)를 따른다. 검색과 AI는 기존 일일 외부 호출 한도를 공유한다. 실제 API 키는 서버 환경에서만 설정한다. 운영 Compose는 검색 환경값을 전달하지만 자동화 워커 운영 배포 검증은 별도다.

## OpenAI와 Claude 선택 (ASA-043)
자동화 빌더의 직접 AI 요청에서 AI 서비스(OpenAI/Claude)와 모델을 선택한다. 기존 공급자 미지정 블록은 OpenAI 기본값을 유지한다. 등록 에이전트는 기존 서버 기본 모델을 사용한다.

OpenAI: 기존 `ASA_AI_MODEL`, `ASA_AI_MODELS`와 `ASA_AI_API_KEY`.
Claude: `ASA_ANTHROPIC_MODELS`(사용 권한이 있는 실제 모델 ID의 JSON 문자열 배열), `ASA_ANTHROPIC_API_KEY`.
공통 실제 실행 활성화: `ASA_AUTOMATION_AI_ENABLED=true`. `.env` 변경 후 API와 자동화 워커를 다시 시작한다. 모델 ID는 계정의 공식 모델 목록에서 확인하여 등록하며 임의로 최신 모델을 고정하지 않는다.

키는 공급자별로 분리하며 화면에는 설정 유무만 전달한다. 키/모델이 미설정이어도 샘플은 사용할 수 있다. 실제 호출 비용은 각 공급자에게 청구된다. 내장 웹 검색은 아직 연결하지 않았으며 모델 선택만으로 검색하지 않는다. 기존 Brave 검색은 독립 블록이다.

## 내장 웹 검색 연결 (ASA-044)
직접 AI 요청의 **웹 검색 사용** 옵션을 연결했다. OpenAI/Claude별 검색 지원 모델 목록을 설정해야 한다. 답변·출처 링크, 비용 및 중단 처리, 설정 방법은 [내장 검색 안내](native-web-search.md)를 따른다. 앞선 ASA-043의 검색 미연결 상태는 이 변경으로 대체된다. 실제 유료 API 호출 검증은 별도다.

## 연결점 편집 (ASA-045)
출력점을 입력점으로 끌거나 차례로 눌러 연결한다. 빈 캔버스로 드래그하면 블록 선택 메뉴가 열리며 선택 후 추가와 연결이 함께 반영된다. Esc/취소는 기존 연결을 보존한다. 선 선택 후 연결 변경/삭제가 가능하다. 상세 패널의 연결 관리는 기본 접힌 상태다. Enter로 점을 선택할 수 있으며 입력점/출력점에 접근성 이름과 포커스를 제공한다. 연결 중 안내 영역 높이를 고정해 대상이 움직이지 않는다.

## AI 카드 검증 (ASA-048)
직접 AI 카드에서 지시문 요약·모델·웹 검색 사용 여부를 확인한다. 지시문이 없거나 Claude 모델 미선택이면 안내가 표시된다. 전체 실행 가능성은 연결 테스트 및 서버 검증으로 확인한다. node --experimental-strip-types --test apps/web/lib/ai-card.test.mjs apps/web/lib/graph-routing.test.mjs 로 카드와 경로 회귀를 검사한다.

ASA-049: 기존 배치가 넓어진 카드와 겹치면 카드 간격 정리를 누른다. 같은 세로 영역의 카드 사이를 띄우며 연결은 유지한다. 위치 변경은 저장 전 초안이며 저장 버튼으로 확정한다. graph-card-layout.test.mjs는 중앙 포트/간격 정리 회귀를 검사한다.

ASA-050: 폰트는 public/fonts에서 로컬 제공한다(CDN 런타임 의존 없음). 개발 브라우저에서 Pretendard Variable 로딩을 확인한다. 폰트 파일 배포 시 라이선스 파일도 함께 유지한다.

ASA-051: 새 블록과 드래그 드롭 시 자동으로 빈자리에 놓인다. 드래그 중 일시 겹침은 허용한다. 기존 배치/좌표 직접 입력의 겹침은 전체 블록 목록과 카드 간격 정리로 처리한다. GNB를 접어도 좌측 레일의 열기 아이콘이 남는다.
