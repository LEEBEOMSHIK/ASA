# AI Shorts Studio — WORKBOARD

마지막 갱신: 2026-10-28 Asia/Seoul / 작성자: AI
목표: 개인 채널용 제작 MVP → SaaS. 현재 단계: 초기 기반 완료, 실제 제작 MVP 구현 전.
확정: C:/projects/ASA, Next.js/FastAPI, LangGraph/LangChain, 외부 AI API, 로컬 개발, 운영 Docker.

## 공동 관리 규칙

1. 상태는 BACKLOG → READY → IN_PROGRESS → REVIEW → DONE. BLOCKED에는 재개 조건을 적는다.
2. 작업 ID·책임자·범위·의존성·수용 기준·검증 근거를 기록한다. 시작과 종료 시 보드를 갱신한다.
3. 설계 작성·mock 검증·실제 로컬 실행·운영 검증을 구분한다. 근거 없는 DONE은 금지한다.
4. 다른 작업의 변경은 보존하고, 동일 파일의 동시 수정은 조율한다. 범위 변경은 먼저 기록한다.
5. 키·개인 자료·전체 프롬프트·내부 추론은 기록하지 않는다. 안전한 증거 경로만 연결한다.
6. 최근 완료는 최대 5개, 이전 완료는 docs/worklogs/YYYY-MM.md에 ID와 근거를 보존한다.
7. 사람의 선택은 결정 기록에 남긴다. 무응답·보드 상태를 외부 게시나 유료 요청 승인으로 해석하지 않는다.
8. 회귀는 기존 항목을 다시 열어 사유·재검증 결과를 기록한다.

## 진행

ASA-045 DONE: 입력/출력 연결점·드래그/클릭·빈 공간 추가 연결·선 변경/삭제·접힌 연결 관리. 브라우저 드래그/클릭/Enter/Esc/합류/삭제 검증. 안내로 캔버스 이동하던 결함 수정. 경로19·pytest123·ruff·mypy28·frontend typecheck/build 통과. [기록](docs/worklogs/2026-10-28-port-connections.md)

ASA-044 DONE: OpenAI/Claude 내장 검색 옵션·LangChain 서버 도구·지원 모델 목록·출처 링크 연결. pytest123·ruff·mypy28·frontend typecheck/build 통과. 실제 SDK HTTP 모의 계약 및 DB 승인 재개 검증. 실제 유료 호출0·실계정/예약 검색 미검증. 브라우저 도구 오류로 시각 검증 미완료. [기록](docs/worklogs/2026-10-28-native-search.md) · [설정](docs/native-web-search.md)

ASA-043 DONE: 직접 AI 요청 OpenAI/Claude 공급자·모델 선택 및 키 분리, 실행 스냅샷 고정·허용 목록 검증. 전체 pytest106·ruff·mypy27·frontend typecheck/build 통과. 브라우저 Claude 전환·미설정 안내 확인. 실제 유료 호출/내장 검색 미실행. 모델 ID·키 설정 필요. [기록](docs/worklogs/2026-10-28-provider-selection.md)

ASA-042 REVIEW: Brave 웹 검색·결과 항목 선택·경로 선택·검색 샘플 채우기·워커 연결 구현. 새 테스트14·ruff·mypy27·frontend typecheck/build·연결선18 통과. 전체 pytest는 Windows uuid_utils DLL 차단으로 수집 실패, 브라우저 연결 실패로 시각 검증 보류. 실제 검색/예약·복구 통합 실행 미검증. [기록](docs/worklogs/2026-10-28-search-mapping.md)

ASA-041 DONE: 공통 GNB 접기/열기·브라우저 상태 유지, 블록 설정 버튼·패널 상단 삭제/연결 개수·삭제 취소·좁은 화면 패널 개선. 브라우저 접기/새로고침/열기, 10블록12선 삭제→9/10→취소10/12, 필수 시작 보호 확인. typecheck/build·경로18·pytest81·ruff·mypy26 통과. 외부 검색/결과 매핑은 조사만 완료, 기능 미구현. [기록](docs/worklogs/2026-10-28-builder-controls.md) · [검색 결과 조사](docs/external-search-result-mapping.md)

ASA-040 DONE: 전체 연결 일괄 계산·12px 평행 통로 분리·합류 진입점 분산·꺾임 비용·공간 부족 안내. 경로18개(50블록98선 공유 구간0)·pytest81·ruff·mypy26·웹 typecheck/build 통과. 실제 브라우저12선48직선구간 겹침0 확인. 수직 교차/과밀 배치 한계 명시. [기록](docs/worklogs/2026-10-28-separated-lanes.md)

ASA-039 DONE: 교차선 외곽선 분리·선 클릭/키보드 선택·연결 검색·선택선 단독 보기·출발/도착 강조. 브라우저12선 선택→단독1선/양끝2블록→Escape12선 복귀 검증. 경로15·pytest81·ruff·mypy26·웹 typecheck/build 통과. 기하학적 공유 구간은 유지하며 목록으로 구분. [기록](docs/worklogs/2026-10-28-connection-tracing.md)

ASA-038 DONE: 복잡한 그래프 장애물 회피·겹침 안내·드래그 경로 캐시 적용. 경로15개(50블록100선 비정렬 포함)·pytest81·ruff·mypy26·웹 typecheck/build 통과. 브라우저10블록12선 충돌 샘플3913점0건·6항목32전이·확대/축소·겹침/복원·실제 드래그 확인. 중첩 반복/병렬 미지원, 선끼리 교차·겹침은 남을 수 있음. 유료 AI0회. [기록](docs/worklogs/2026-10-27-complex-graph-tests.md)

ASA-037 DONE(재검증): 가까운 정방향 연결의 60px 오분류 제거·모든 우회 모서리 둥근 곡선 적용. 신규2개 실패→통과 포함 경로5개·pytest73(100.73s)·ruff·mypy26·웹 typecheck/build 통과. 두 번째 사용자 상대배치 브라우저 확인. 이전 검증: 수직으로 떨어진 블록은 블록 사이 빈 공간으로 연결해 최종 결과 아래를 도는 현상 수정. 경로 회귀3개·pytest73·ruff·mypy26·웹 typecheck/build 통과. 브라우저 사용자와 동일한 상대배치 확인(검증 좌표 미저장), 실제 AI0회. [기록](docs/worklogs/2026-10-27-graph-routing.md)

로컬 서비스 재시작 DONE (2026-10-27): 웹3001 HTTP200·API8127 ready/database connected·DB55439 확인, 자동화 워커 백그라운드 실행. 유료 AI 비활성 유지. 코드 변경 없음, 서비스 응답 검증만 수행.

ASA-036 DONE: 명확한 연결모드/대상/취소·드래그 정리, 직접 AI/ASA 도구/내 에이전트별 입력, 단일 결과와 기존 초안 복구, 허용 모델 선택→실행/예약 연결. pytest73·ruff·mypy26·웹 typecheck/build 통과. 브라우저 연결/이동/입력분류/샘플/저장·360/768px·light/dark 확인. 실모델 호출은 모의검증, 유료0회. 중간 호출한도 테스트1회 실패 후 단독/최종전체 통과(원인 미확정). [기록](docs/worklogs/2026-10-27-graph-builder-ux.md)

ASA-035 DONE(MVP): 자유 배치/연결·직접 AI·조건·목록 반복 그래프와 실행/승인/예약/이력 통합. 기존 순차 보존. pytest66·ruff·mypy26소스·웹 typecheck/build 통과. 브라우저 목록 편집/저장·드래그·로컬12전이/3결과/양쪽 분기·이력, AI 샘플 테스트, 360/768px 검증. 유료 AI0회, 중첩 반복/병렬/미디어 제외. [기록](docs/worklogs/2026-10-27-graph-builder.md)

ASA-033 DONE(MVP): 자동화 카드 실행/기록·단계별 결과·확인 후 이어가기·1회/매일 예약·로컬 워커 연결. 버전 스냅샷/중복 방지/중단 복구/오래된 승인 차단. pytest50개·ruff/mypy24소스·웹 typecheck/build 통과. 브라우저 로컬 도구12자 실행→확인→완료/기록·매일 예약 저장/끄기·360/768px 넘침 없음·카드 밝게/어둡게 확인. 실제 유료 AI0회, 1회 예약 UI 제출 미검증(날짜 입력 자동화 제한). 중첩 도구·미디어·결과 수정 재실행 후속. [기록](docs/worklogs/2026-10-26-automation-runtime.md)

ASA-032 DONE: 자동화 목록/편집 분리, 중앙 순차 흐름·사이 ＋ 삽입·검색 가능한 선택 dialog·선택 시 설정/요청 시 테스트 패널·닫기 제공. 기본 자료형 노출 제거. pytest43개·ruff/mypy·웹 타입/최종빌드 통과. 브라우저 삽입/제거/원래 연결 보존·검증/샘플9자 실제 도구계산·저장/재열기·360/768px 넘침 없음·Escape 초점복귀·light/dark 확인. [기록](docs/worklogs/2026-10-26-builder-focus.md)

ASA-031 DONE: ui.tsx StudioNavigation 공통 메뉴·아이콘·현재 위치 강조, 고객/관리/빌더 동일 사이드바 탐색, 새 작업 행동 분리, 빌더 패널 제목/밀도 개선. 디자인 시스템 계약 갱신. pytest43개·ruff/mypy·웹 typecheck/build 통과. 브라우저 고객→빌더→고객 이동, 모바일360px 메뉴/넘침/Enter/Escape·밝게/어둡게 확인. [기록](docs/worklogs/2026-10-26-studio-navigation.md)

ASA-030 DONE(구성 화면): /automations 순차 블록 편집·입력 연결·DB 초안 저장·구성 검증·샘플 연결 테스트 구현. pytest43개·ruff/mypy·웹 typecheck/build 통과. 브라우저 에이전트→길이 검사 연결·샘플23자 전달/계산·새로고침 재조회/재저장·360px 넘침 없음·밝게/어둡게 확인. 실제 AI 실행·게시·조건/병렬·고객 제작 단계 연동은 후속. [검증 기록](docs/worklogs/2026-10-26-automation-builder.md)

ASA-029 DONE(대본 단계): 직접 작성/수정·불변 버전·비교·현재 버전 확정·대본만 재작성 요청·대기 취소·명시 실행 로컬 워커 구현. pytest37개·ruff/mypy·웹 typecheck/build 통과. 브라우저 v1→v2 보존/확정 해제/비교/요청 취소/재확정·360px 넘침 없음 확인. 실제 AI 설정/유료 호출·상시 실행/복구·미디어 단계는 미완료. [검증 기록](docs/worklogs/2026-10-26-script-stage.md)

ASA-028 DONE: 공통 토큰 기반 밝게/어둡게/시스템 모드와 브라우저 저장, 초기 렌더 전 테마 적용·OS 변경 구독·탭 동기화 구현. 고객 사이드바/모바일 메뉴/관리자·로그인 선택 UI. 브라우저 모드 전환·현재 OS 설정 반영·새로고침 유지·관리자 입력 색상·360px 전환/넘침 없음 확인. pytest35개·ruff/mypy·웹 typecheck/build 통과. OS 설정 자체 변경·복수 탭 동기화는 소스 검토만 수행.

ASA-027 DONE: 별도 작업 이력 메뉴/목록/이전·다음 제거, 최근 작업 20개씩 스크롤 추가 로딩 통합. 기존 목록 유지·중복 방지·실패 재시도·키보드 추가 로딩 제공. DB 45건 순차 조회 포함 pytest35개·ruff/mypy·웹 typecheck/build 통과. 브라우저 데스크톱/360px에서 20→27건 자동 로딩·오래된 작업 상세 확인. 임시25건은 생성 ID+표식으로 제거, 기존2건 보존. 실제 AI 실행 미연결.

ASA-026 DONE: 고객 새 작업·작업 이력·최근20개 작업을 왼쪽 사이드바에 배치하고 오른쪽에 입력/상세 표시. 현재 선택 동기화, 저장 후 최근 목록 갱신, 모바일 dialog 메뉴. 브라우저 최근 작업→상세→원래 작업 이동·선택 표시, 360px 넘침 없음·Esc 닫기/포커스 복귀·메뉴 선택 후 닫기 검증. pytest34개·ruff/mypy·웹 typecheck/build 통과. 기존 작업 데이터 변경 없음.

ASA-025 DONE(이력): 고객 요청 DB 저장·20개 단위 목록/상세·요청/결과/상태 조회·이전 버전/입력으로 재작업 구현. workspace 격리·입력 검증·서버 상태 통제·동일 ID 중복 저장 방지. pytest34개·ruff/mypy·웹 typecheck/build 통과. 브라우저 샘플2건 저장·재작업·새로고침 후 유지·360px 넘침 없음 확인. 결과/완료 상태는 격리 테스트 DB에서 검증했으며 실제 AI 실행은 미연결, 신규 요청은 실행 전(saved). 샘플 이력은 표시를 붙여 로컬 DB에 보존.

ASA-024 DONE(화면): 고객 첫 화면에 등록 최신 에이전트 선택→작업 입력→입력 확인→빈 결과 영역 제공. 관리자 편집과 분리, 기존 owner 세션/개발용 로그인 경로 유지. 브라우저에서 선택·필수 입력·입력 확인·목록 복귀·360px 가로 넘침 없음 확인. pytest32개·ruff/mypy·웹 typecheck/build 통과. 로그인/빈 목록/오류 신규 분기는 소스 확인만 수행. 실제 AI 생성·고객 계정·실행 내역은 미구현이며 후속 연결.

ASA-023 DONE: 중복된 도구 생성 버튼 제거. 에이전트 생성은 에이전트 탭에 유지. pytest32개·ruff/mypy·웹 typecheck/build 통과, 소스 확인(별도 브라우저 확인 없음). 다음 작업은 ASA-010 실행 기반·내역이며 이번 변경에서는 시작하지 않음.

ASA-022 DONE: 도구 상세 화면(등록 버전·사용법·입출력·설명 예시), 도구 만들기 안내 및 기존 에이전트 생성/편집 연결. 등록 버전 유지·로그인·workspace 격리 포함 pytest32개, ruff/mypy, 웹 typecheck/build 통과. 브라우저에서 기본 도구 상세와 예시 확인, 주소의 콜론 중복 인코딩 수정 후 웹 검사 재실행. 실제 AI 실행·임의 API/코드 도구 생성은 범위 제외.

ASA-021 DONE: 누락된 결과 입력란 label을 ‘AI가 채울 답변 항목 1’로 수정하고 바로 아래 제목·대본·해시태그 예시 표시. 실제 상세 화면에서 확인. pytest31개·ruff/mypy·웹 타입/빌드 통과.

ASA-020 DONE: ‘AI가 채워줄 답변 항목을 정하세요. 예: 제목 · 대본 · 해시태그’로 설명 변경, 선택 후 작성 안내 추가. pytest31개·ruff/mypy·웹 타입/빌드 통과. 문구 소스 확인, 별도 브라우저 재검증 없음.

ASA-019 DONE: 새 에이전트/예시 기본 자유 답변, 선택적 항목별 설정과 편집 중 전환 복원, 기존 형식 보존. 결과 영역은 실행 전 빈 자리만 표시. pytest31개·ruff/mypy·웹 타입/빌드, 브라우저 기본값·방식 전환·빈 결과 검증. [기록](docs/worklogs/2026-10-26-free-response.md)

ASA-018 DONE: 사용자 정정 반영 — 3번 ASA/내 에이전트 그룹별 독립 접기, 2번에서 별도 실행 화면 미리보기로 전환·입력 확인·편집 복귀. 실제 AI 실행 없음. pytest29개·ruff/mypy·웹 타입/빌드 및 브라우저 동작 확인. [기록](docs/worklogs/2026-10-26-run-preview.md)

ASA-017 DONE: 3번 기본 접힘·선택 개수 유지·클릭/키보드 펼치기, 2번 지금 설정→나중 실행→결과 연결 안내와 현재 설정 기반 양식 미리보기. pytest29개·ruff/mypy·웹 타입/빌드 및 브라우저 접기/펼치기 확인. [기록](docs/worklogs/2026-10-26-agent-usage.md)

ASA-016 DONE: 2번 역할별 입력/결과 고정 예시, 3번 ASA 도구/내 에이전트 그룹·선택 개수·선택 불가 안내 구현. 예시 전환·양쪽 동시 선택 저장/재조회·360px 넘침 확인. pytest29개·ruff/mypy·웹 타입/빌드 통과. [기록](docs/worklogs/2026-10-26-agent-examples.md)

ASA-015 DONE: 밝은 시각 체계와 안내형 에이전트 편집. 예시 시작·쉬운 입력/결과 안내·고급 설정 분리·요약·등록 안내 구현. 실제 저장/등록·360/768px·키보드 이동, pytest29개·ruff/mypy·웹 타입/빌드 검증. [기록](docs/worklogs/2026-10-26-agent-editor-ux.md)

ASA-014 DONE: 관리자 전용 /login 분리, 로컬 개발 전용 테스트 로그인 구현. 실제 DB 포함 테스트29개·ruff/mypy·웹 타입/빌드 통과. 브라우저 미인증 이동→테스트 로그인→원래 화면 복귀→로그아웃 확인. [기록](docs/worklogs/2026-10-26-admin-login.md)

| ID | 작업 | 상태 | 책임자 | 의존성 | 수용 기준 / 근거 |
|---|---|---|---|---|---|
| ASA-001 | 초기 기반·문서·공통 UI | DONE | AI | 확정 설계 | 테스트 11개·타입·린트·웹 빌드·HTTP·브라우저 확인. [검증 범위](docs/verification.md) |
| ASA-002 | 전용 DB·체크포인트 통합 검증 | READY | AI | ASA 전용 DB 구성 완료 | 체크포인트의 실제 DB 재시작 후 승인 재개·중복 생성 검증은 남음 |
| ASA-003 | 프로젝트·작업 큐·비용 원장 | BACKLOG | AI | ASA-001 | workspace 경계, 멱등성·lease·예산·취소 통합 검증 |
| ASA-004 | 제작 UI와 API 연결 | BACKLOG | AI | ASA-003 | 생성·저장·승인·오류·복구 실제 동작 |
| ASA-005 | 이미지·음성·영상 생성 | BACKLOG | AI | ASA-003, 공급자 선택 | 실제 API·FFmpeg 결과·비용 확인 |
| ASA-006 | 운영 Docker 검증 | BLOCKED | AI | Docker 실행 환경 | 이미지 빌드·health·백업 복원 검증 |
| ASA-007 | SaaS 인증·격리·한도 | BACKLOG | AI | 개인 MVP | 권한·tenant 누출·동시 비용 한도 테스트 |
| ASA-008 | 에이전트·자동화 빌더 상세 설계 | DONE | AI | 사용자 범위 확정 | [설계](docs/agent-automation-design.md)·[구현 계획](docs/superpowers/plans/2026-10-26-agent-automation.md), 독립 검토 5건 반영. 기능 구현은 아래 별도 작업 |
| ASA-009 | 에이전트·도구 등록 | DONE | AI | ASA-008 | 실제 DB 포함 테스트26개·ruff/mypy·웹 타입/빌드 통과. 브라우저 로그인·저장·검증·버전 확정·도구 목록 확인. [기록](docs/worklogs/2026-10-26-agent-registry.md) |
| ASA-010 | 실행 기반·내역 | BACKLOG | AI | ASA-009, ASA-002/003 | 호출 트리·payload·예산·승인·복구·SSE. ASA-003과 같은 실행 엔진. 계획 Task2 |
| ASA-011 | 블록 연결 빌더 | BACKLOG | AI | ASA-009/010 | DAG 검증·edge별 매핑·키보드 연결·버전 고정. 계획 Task3 |
| ASA-012 | LLM 도구 선택·agent-as-tool | BACKLOG | AI | ASA-010/011 | 하위 호출·권한·순환·root 예산·취소·승인 전파. 계획 Task4 |
| ASA-013 | 쇼츠 템플릿·종합 수용 | BACKLOG | AI | ASA-011/012, 미디어는 ASA-005 | 기획→대본→검토, fork·재사용, 실제 검증 구분. 계획 Task5 |

## 결정

| ID | 결정 | 근거 |
|---|---|---|
| D-001 | 저장소 C:/projects/ASA, origin LEEBEOMSHIK/ASA | 사용자 지정 |
| D-002 | AI는 외부 API, 앱 서비스는 로컬 | 사용자 확정 |
| D-003 | 모듈형 모놀리스 + 별도 워커 | 제안 후 진행 승인 |
| D-004 | Python 3.13 x64로 개발 | ARM64 psycopg-binary 미지원 확인, 기존 x64 설치 활용 |
| D-005 | 초기 공급자 어댑터 OpenAI, 모델·키 미설정 | 구현자 선택. 제공자 추가는 계약으로 확장. 실제 호출 없음 |
| D-006 | 초기 worker는 수동 CLI | 큐·비용 제어 미구현 상태에서 자동 유료 호출 방지 |
| D-007 | 작업 블록 연결형 자동화 빌더 | 사용자 확정. 범용 화면·앱 제작기는 제외 |
| D-008 | ASA 제공 도구와 사용자 에이전트를 도구로 사용 | 사용자 확정. 임의 외부 API 연결·사용자 코드 실행은 v1 제외 |
| D-009 | v1은 순차 DAG·input/output 각1개, 반복·병렬·스케줄 제외 | 구현자 설계 선택. 세부 상한은 상세 설계 참조 |
| D-010 | runs/invocations 업무 정본, jobs는 queue/lease만 담당 | 중복 실행 상태 시스템 방지 |

## 최근 완료

ASA-009: 로컬 owner 세션·CSRF·workspace 경계·에이전트 초안/버전·도구 목록과 편집 UI 구현.
전용 로컬 PostgreSQL(55439), API(8127), 웹(현재3001) 연결 검증. AI 호출·빌더·실행 엔진은 미구현.

ASA-008: 사용자 에이전트·도구 등록·실행 관측·블록 빌더 상세 설계와 5단계 구현 계획 작성.
독립 설계 검토의 복구 ID, 중간 입력, fork, 상태 정본, 분기 병합 5건 반영. 새 기능 코드는 미구현.
[검증 기록](docs/worklogs/2026-10-26-agent-automation-design.md): 기존 테스트11개·타입·린트·웹 빌드 통과.

ASA-001: 설계·보드·디자인 토큰·공통 UI·API health·승인 그래프·수동 워커·실행 설정 반영.
유료 API/실제 DB 지속성/영상 생성/Docker 실행은 완료 범위에서 제외한다.

## 다음 행동

고객 대본 단계(ASA-029)와 자동화 구성 화면(ASA-030) 구현. 사용자가 구성한 자동화로 실제 실행 테스트를 진행할 수 있도록 ASA-010 실행 기반·비용 제어·복구 및 모델 설정을 연결한다. ASA-002 체크포인트 재시작 검증도 남아 있다.
ASA-010은 ASA-003의 큐·비용 제어를 포함한다. 미디어 공급자·FFmpeg는 ASA-005 단계에 연결한다.
커밋·push·외부 배포는 아직 수행하지 않았다.

ASA-034 DONE (2026-10-27): 로컬 웹3001/API8127 재시작. 웹 / HTTP200, API /health/ready HTTP200 및 database=connected 확인. Windows 실행 래퍼 차단으로 기존 venv Python -m uvicorn 사용. 기능 코드 변경 없음; 전체 테스트 재실행 없음. 자동화 워커 재시작은 이번 범위 제외.


ASA-046 DONE: 이동 중 입력점의 스냅샷/현재 좌표 혼용 수정. 입력점과 임시 선 끝점의 상대 좌표 계산 공유. 경로20개·pytest123개·ruff/mypy·웹 typecheck/build 통과. 브라우저 도구 연결 오류로 실제 드래그 재검증 미수행. [기록](docs/worklogs/2026-10-29-input-socket-drag.md)

ASA-047 DONE: AI 카드 전체에 accent-soft 배경 적용, 내부 제목 배경 제거로 하단 흰 띠 수정. pytest123개·ruff/mypy·웹 typecheck/build 통과. 브라우저 시각 재검증 미수행. 추가 요약 정보는 제안만 수행.

ASA-048 DONE: AI 카드 시안 반영 — 2줄 지시문 요약/모델/웹 검색/필수 설정 안내, 280×216 카드와 경로 좌표 통일. 카드·경로24개/pytest123개/ruff/mypy/웹 typecheck·build 통과. 실제 브라우저 요약 갱신·안내 전환·내용 넘침 확인, 테스트 입력 복원. 유료 AI 호출 없음. 화면 .local/verification/ai-card-summary.png. 기존 이동 회귀 테스트의 누락된 target fixture도 수정.

ASA-049 DONE: 전체 카드 SVG 아이콘/24px 여백/제목 위계/아이콘 설정/중앙 연결점 통일. 사용자 실행 카드 간격 정리 추가(연결 보존). 회귀27개·pytest123개·ruff/mypy·최종 웹 타입/빌드 통과. 실제 브라우저 데스크톱 배치·설정 접근·간격 정리 검증, viewport 복원. 검증용 직접 AI 요청의 배치 수정은 미저장 초안. .local/verification/workflow-cards-refined.png. 유료 호출 없음.

ASA-050 DONE: 공통 Pretendard Variable v1.3.9 로컬 폰트와 OFL 라이선스 동봉, 폼 글꼴 상속 통일. 빌더 제목28/설명16/메타13 및 아이콘28/배경52 토큰, 설정·검색 SVG 개선. 브라우저 폰트 로딩/실제 크기/카드 넘침 확인, viewport 복원. pytest123개·ruff/mypy·웹 typecheck/build 통과. 다른 화면 개별 시각 재검증은 미수행. .local/verification/workflow-typography.png.

ASA-051 DONE: GNB 내부 아이콘 토글/64px 축소 레일, 로컬 OpenAI·Claude 로고, 도구 플러그/에이전트 로봇 구분. 추가·드롭 시 가까운 빈자리 배치, 선택 카드 앞으로, 전체 블록 목록 추가. 브라우저 토글/실제 겹침 드롭/목록 선택/공급자 로고 전환 확인. 회귀28개·pytest123개·ruff/mypy·웹 타입/빌드 통과. 검증용 별도 탭은 저장 없이 닫고 원래 편집 화면 보존. 고객 화면 GNB 개별 UI 재검증 미수행. .local/verification/navigation-and-blocks.png.

ASA-052 DONE: 자동화 목록 카드 아이콘/버전·제목/설명·블록 정보·하단 동작 위계 정리. 설명 3줄 제한, 동일 높이와 실행/예약/기록 한 줄 정렬, 조용한 편집 버튼 적용. 브라우저 데스크톱/390px 모바일 배치 및 실행 진입 확인(실제 실행 없음), 가로 넘침 없음. pytest123개·ruff/mypy·웹 typecheck/build 통과. 예약/기록 개별 진입 재검증은 미수행. 검증 탭 닫음, viewport 복원. .local/verification/automation-library-cards.png.


ASA-053 READY: 사용자 요청으로 전체 구현 초기 커밋 및 origin/main 푸시. 원격 빈 저장소 확인. 소스/테스트/문서/배포 구성/라이선스 자산 포함, .env/.local/캐시 제외. ASA-052의 pytest123개·ruff/mypy·typecheck/build 검증 재사용(이후 실행 코드 변경 없음).
