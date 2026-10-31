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


ASA-053 DONE: 사용자 요청으로 전체 구현 초기 커밋 83a7a5d 및 origin/main 푸시 완료. 원격 빈 저장소 확인. 소스/테스트/문서/배포 구성/라이선스 자산 포함, .env/.local/캐시 제외. ASA-052의 pytest123개·ruff/mypy·typecheck/build 검증 재사용(이후 실행 코드 변경 없음).

ASA-054 DONE: /monitoring 관리자 사용량·비용 및 요청→실행→블록 추적 구현. 직접/예약/고객 대본/CLI 호출 수집, 공급자 반환 토큰·캐시·응답 시간, 요율 스냅샷, 미확인/검색 비용 분리. 원래 요청·요청자·실제 메시지·응답을 owner/admin 및 workspace 범위에서 조회. pytest140개·ruff/mypy·웹 typecheck/build 통과. OpenAI/Claude SDK 모의 HTTP 사용량 검증, DB 마이그레이션과 API 재시작 완료. 브라우저 상세/실패 필터/모바일 넘침/밝음·어두움 확인, 검증용 3개 이벤트 제거. 리뷰의 JSON 문자열 비밀값·자동화 이름 변경 집계 문제 수정 및 재확인. 실제 유료 호출 미수행. .local/verification/ai-monitoring.png, ai-monitoring-mock-trace.png(모의 기록). 요율 설정은 docs/ai-monitoring.md 참고. 커밋/푸시 미수행.

ASA-055 DONE: 모니터링 기본 조회를 기간·검색 한 줄로 축소. 서비스/출처/상태 상세 조건은 기본 접힘, 값 유지·적용 태그·변경 미적용 안내·초기화 제공. 브라우저 펼치기/접기·Enter·접힌 상태 조회·조건 초기화·모바일 가로 넘침 검증. pytest140개·ruff/mypy·웹 typecheck/build 통과. .local/verification/monitoring-compact-filters.png.

ASA-056 DONE: 사용자 요청에 따라 ASA-054/055 커밋 대상 선별·검증 완료. 구현/테스트/설정 예시/문서 포함, .env/.local/캐시 제외. 직전 pytest140개·ruff/mypy·typecheck/build 검증 재사용(이후 실행 코드 변경 없음). 원격 main 기준 0bb58cc 확인. 커밋·푸시 결과는 Git 이력 참조.

ASA-057 WAITING_CONFIG: 실제 AI 연결 상태 점검 완료. OpenAI/Claude 키·모델 미설정, 실행 비활성화, 요율 미등록, 워커 오프라인 확인. 로컬 DB에 '실제 AI 테스트 · 쇼츠 대본 생성'(b157bc67-e1d8-43f2-9dc1-21b34ed43c90, v1)을 추가하고 구조 검증 오류 0개·저장 후 조회 확인. 시작 요청→직접 AI 대본 생성→최종 결과 구성, 모델은 서버 설정 대기. 비밀값 출력·실제 유료 호출 없음. 실제 결과/토큰/비용 기록 검증은 API 키·모델·요율 설정 후 진행 필요. 실행 코드 변경 없음, 전체 테스트 재실행 안 함.

ASA-058 DONE: 관리자 /models 모델 등록·활성화·기본 모델·웹 검색·선택 요율 관리 구현. workspace별 DB/revision/owner·admin 권한, 활성 모델 선택 목록과 AI 블록·에이전트 기본 영역 선택 연결. 에이전트 버전·자동화 manifest 모델 보존, 워커 설정 갱신·비활성 모델 차단·고객 대본 모델 반영. pytest142개·ruff/mypy·웹 typecheck/build·AI 카드 회귀3개(Claude 기본 모델 추가 assertion 포함) 통과. 브라우저 등록 폼·기본 모델 선택·상세 접기·변경 취소·모바일 넘침 없음·에이전트 모델 노출 확인. DB 마이그레이션/API 재시작 완료, OpenAI 키 설정 여부 확인(인증/실제 호출 미검증), Claude 키 미설정. 검증 입력 미저장·탭 닫음·viewport/GNB 복원. 실제 모델 등록/유료 호출 없음. docs/model-management.md, .local/verification/model-management.png.

ASA-059 DONE: 테스트 로그인은 local-owner/owner 권한임을 확인. 고객 작업 공간이 /session 권한을 조회·전달하도록 수정해 관리자 메뉴 누락 해소. 작업 공간/관리 화면에 현재 권한 표시, 테스트 로그인 안내에 소유자 권한 명시. 테스트 로그인 owner 및 관리자 API 접근 회귀 추가. pytest142개·ruff/mypy·웹 typecheck/build 통과. 브라우저 고객/자동화 메뉴·owner 표시·모델 화면 진입 확인. 이전 SSR 코드 혼용으로 인한 hydration 오류 확인 후 ASA 웹 서버만 재시작. .local/verification/owner-admin-navigation.png. 다중 사용자 계정·멤버십·역할 변경 화면은 미구현이며 이번 메뉴 수정과 별도 범위.

ASA-060 DONE: 공통 SettingsSection/설정 토큰·배치 규칙 추가, 모델 관리의 키 설정 상태/기본 모델/허용 모델/저장 영역 분리. 카드 간격24·필드16·입력 높이44·제목/우측 동작 중앙 정렬·체크박스/펼침/저장 동작 정리. 브라우저 입력 상단/높이 일치 및 비용 필드 정렬, 390px 모바일 넘침 없음·저장 버튼 동일 너비 확인. 검증 입력 미저장 취소·viewport 복원. pytest142개·ruff/mypy·웹 typecheck/build 통과, ASA 웹 서버 재시작. .local/verification/model-settings-layout.png(미저장 등록 폼 예시).

ASA-061 DONE: 관리자 모델 목록 조회·검색·선택 및 공식 문서 기반 검색 지원/입출력·캐시 요율 자동 반영, 출처·확인 시각 저장, 재확인·수동 수정 구현. owner/admin 및 고정 공식 URL·응답 제한·비밀값 없는 오류 적용. 실제 OpenAI 목록130개/공식 요율 반영, 모바일 넘침 없음 확인. Claude 키 미설정으로 페이지네이션 모의 응답 및 공식 문서 파싱 검증. 전체 pytest149개+추가 단위2개(단위8개)·ruff/mypy/typecheck 통과. 웹 최종 build 파일 접근 충돌 후 서버 중지 재검증 통과·웹 재시작. 검증 입력 미저장 취소, 유료 AI 생성 없음. .local/verification/model-discovery.png, docs/model-management.md.

ASA-062 DONE: 공급자 선택 시 모델 목록 자동 조회·화면 내 공급자별 캐시, 별도 조회/검색 UI 제거·검색 가능한 콤보박스 통합. ID 세대 번호·일반 모델·별칭 우선 정렬(성능 순위 아님), 특수 모델도 검색 유지. Enter 선택/Escape 닫기/재열기·공급자 변경 시 선택 초기화·Claude 키 누락·OpenAI 캐시 복귀·390px 넘침 없음 확인. pytest151개·ruff/mypy·웹 typecheck/build·정렬 회귀2개 통과. ASA 웹 서버 재시작, 검증 탭 종료·viewport 복원, 유료 생성·카탈로그 저장 없음. .local/verification/model-picker-unified.png.

ASA-063 DONE: 공급자·모델 선택을 ui.tsx 공통 SelectCombobox로 통일. 동일44px 높이/테두리/반경10px/글꼴/패딩/SVG 화살표/목록/포커스 적용. 공급자는 선택 전용, 모델은 검색 유지. 브라우저 실제 computed style 일치·방향키/Enter 공급자 변경·모델 검색·모바일309x44 동일 크기/넘침 없음 검증. pytest151개·ruff/mypy·typecheck/build 통과, 웹 재시작. docs/design-system.md 규칙 추가, .local/verification/model-select-uniform.png. 카탈로그 저장/유료 생성 없음.

ASA-064 DONE: 검색 가능한 요약 행 목록(최대360px 내부 스크롤)과 단일 상세 패널 구현. 자동 확인됨/직접 수정됨/확인 필요 상태, 빈 요율 미등록 처리. 수동 입력·캐시 별도 접기, USD/100만 토큰/입출력 용도/예상 비용/미확인 안내. 전체 초안 검증으로 다른 모델에 숨은 빈 요율 저장 차단·해당 상세 열기. 실제 OpenAI 두 모델 미저장 초안으로 추가·검색·상세 전환·입력 유지·누락 요율 차단·390px 가로 넘침 없음 확인 후 취소. pytest151개·ruff/mypy·typecheck/build·요율 회귀2개 통과, 웹 재시작. .local/verification/model-compact-catalog.png(검증용 미저장 초안), 관련 문서 갱신. 유료 생성/카탈로그 변경 없음.

ASA-065 DONE: 공식 요율 읽기 전용 표/비용 사용 체크박스 제거, 별도 계약만 고급 수동 편집·공식 요율 복원. 상태 배지 내용 너비/갱신 버튼 우측 정렬·안내/출처12px 간격. OpenAI 명시된 입력·출력·캐시 배수와 Claude up-to/over 표 파싱, ModelPrice.long_context/호출 스냅샷·전체 입력 기준 구간 계산 추가. 경계값/초과·캐시 미확인·JSON 왕복 검증. 공식 문서 실제 조회(gpt-6.1-sol/claude-haiku-5-5)와 브라우저 자동 표·계약 복원·390px 넘침 없음 검증, 초안 취소. pytest154개·ruff/mypy·typecheck/build·요율 UI 회귀2개 통과. API/웹 재시작, .local/verification/model-automatic-tier-pricing.png. 지원 문서 형식 외 조건은 미확인, 표준 처리 기준(검색/지역/Fast/Batch 등 별도), 유료 생성·카탈로그 저장 없음.

ASA-066 DONE: 선택한 모델 등록 시 POST /admin/models로 즉시 DB 저장, 성공 후 목록 반영. 기존 편집/기본 모델 초안은 등록 요청에서 제외·클라이언트에서 유지하고 새 revision 적용. owner/admin·workspace 잠금·revision·중복·100개 제한. + 새 모델/등록창 닫기/선택한 모델 등록으로 구분, 편집 내용 저장/편집 취소는 dirty일 때만 표시. 등록 후 조회 지속·기존 기본/모델 보존·중복/충돌·권한을 격리 테스트 DB에서 검증. pytest155개·ruff/mypy·typecheck/build 통과, API/웹 재시작. 실제 UI 자동 목록/동작명/즉시 저장 안내 확인, .local/verification/model-register-action.png. 사용자 작업 공간에 검증 모델 등록/삭제 없음, 유료 생성 없음.

ASA-067 DONE: 고급 설정 접힘 제거·제목 옆 요율 직접 설정/공식 요율로 복원 버튼으로 단일 단계 편집. 표준 금액 초깃값·직접 설정 시 입력/출력 즉시 노출, 선택 캐시만 접기. 수동 요율 안내와 공식 메타데이터 안내 충돌 정리. 기존 gpt-6.1-terra에서 입력 수정 후 조건부 공식 요율 복원·모바일 넘침 없음 확인, 편집 취소로 원래 저장 상태 유지. pytest155개·ruff/mypy·typecheck/build 통과, 웹 재시작. .local/verification/model-direct-rate-edit.png(미저장 검증 입력), 관련 문서 갱신.

ASA-068 DONE: 에이전트 편집의 맡길 일을 에이전트 지침으로 변경. 역할·말투·규칙의 반복 적용과 실행마다 바뀌는 입력을 설명. pytest155개·backend src ruff/mypy·frontend typecheck/build 통과. 전체 backend ruff는 기존 테스트 파일 E501 6건 확인(변경하지 않음). 최초 sandbox DB 검사 중단 후 권한 재검증 통과, 빌드 EPERM 재검증 통과. 브라우저 시각 검증 및 유료 AI 호출 없음.

ASA-069 DONE: 승인된 상세 제목·입력 항목·도구/에이전트·위임 한도 설명·버전 이력/JSON 제목 정리. 최초 에이전트 등록/이후 새 버전 등록 구분, 초안 저장됨, 기본 모델 상속 설명, 실제 호출과 미리보기/연결 설정 지원 범위 안내 통일. 관련 가이드/미리보기 및 디자인 시스템 문서 반영. pytest155개·src ruff/mypy·frontend typecheck/build 통과. 브라우저 시각 검증·실제 AI 호출 없음.

ASA-070 DONE: 공통 HelpText/Field.help와 토큰 기반 스타일 추가. 지침·모델·입력·답변·도구/에이전트·실행 한도·저장/등록 7개 도움말에 사용자 예시/선택 기준 작성. 클릭/Enter/Space 토글, Escape 닫기, aria-expanded/controls, 모바일44px 터치 영역·문서 흐름 내 설명 구현. 필수 지원 제한 안내 유지. pytest155개·src ruff/mypy·frontend typecheck/build·diff check 통과. 브라우저 시각/인터랙션 실검증 미실시, 유료 AI 호출 없음.

ASA-071 DONE: Field.annotation으로 AI 전달/관리용/호출 설정, 실행 입력값 및 자동화 응답 형식 표시. 전달 범위 안내에 등록 버전/수정 요청/고객 대본 고정 출력 계약 명시. 대본 작가 기본 템플릿을 역할·입력 해석·구성·사실/불확실성·출력·수정 점검 1414자 지침으로 보강. 샘플 · 쉬운 대본 작가 초안 revision3에 지침만 저장(등록 버전 변경 없음). pytest155개·src ruff/mypy·frontend typecheck/build·diff check 통과. 실제 AI 품질/브라우저 시각 검증 미실시.

ASA-072 DONE: AI 전달 텍스트 배지를 보라색 18px 선형 SVG 아이콘으로 대체. 지침/실행 입력/자동화 출력 형식에 공통 적용, 기존 ? 도움말을 하나로 통합. 접근 가능한 전달 의미/title·클릭/키보드/터치 설명 유지. frontend typecheck/build·src ruff/mypy·diff check 통과. 전체 pytest는 DB 연결 시간초과로 3통과/1실패 중단, 해당 SDK 모니터링 테스트 단독2개 재검증 통과(전체 재통과 미확인). 브라우저 검증 탭 로컬 서버 탐색 시간초과로 시각 확인 미완료.

ASA-073 DONE: AI18→14px, 데스크톱 버튼32→24px, 기본 배경 제거. 관리용 문서/호출 설정 슬라이더14px 아이콘으로 통일하고 도움말 통합. 모바일44px 터치 영역 유지. frontend typecheck/build·src ruff/mypy·diff check 통과. pytest37통과 후 모델 관리 테스트 KeyError로 중단, 해당 테스트 단독 재검증1개 통과(전체 통과 미확인). 브라우저 시각 검증 미실시.

ASA-074 DONE: 고객 실행/실행 미리보기 입력란의 AI 전달 annotation 제거, 에이전트 설정 아이콘 유지. 디자인 시스템 적용 범위 명시. pytest155개·src ruff/mypy·frontend typecheck/build·diff check 통과. 브라우저 시각 검증 미실시.

ASA-075 DONE: 고객 대본 실행 큐·상시 로컬 워커·멱등 접수·workspace별 순차 실행·중단 복구·접수 정보/상태 폴링·대기 취소·모니터링 통합. 쉬운 대본 작가 v3(도구 해제/보강 지침) 실제 AI 1회 성공: 6.243초, 입력1015/출력288토큰, 예상USD0.002455. 브라우저 결과/요청 추적/대기 취소 확인, 워커 재가동. pytest161·소스ruff/mypy34·웹typecheck/build 통과. 실제 공급자 동시 부하 미검증, 외부 호출 exactly-once 미보장. [기록](docs/worklogs/2026-10-30-script-queue.md)

ASA-076 DONE: 개별 에이전트 요청·답변 화면, 고정 제작 단계/중복 JSON 제거, 읽기·복사·직접 수정·취소·접힌 재요청/이력. 브라우저 기존 성공 요청과 미저장 보호/취소 복원 확인. pytest161·src ruff/mypy34·web typecheck/build 통과. 추가 AI 호출0. 현재 대본 backend 계약 유지. [기록](docs/worklogs/2026-10-30-agent-answer.md)

ASA-077 DONE: 내가 보낸 요청 원문 인용·DB 테스트 메타데이터/목록·상세 배지·확인된 테스트3건 구분. 대기/이력의 입력과 시스템 지시, 에이전트 버전/시각 문구 정리. 브라우저 표시 확인·pytest162·src ruff/mypy34·web typecheck/build 통과. 원문 보존·추가 AI0회. [기록](docs/worklogs/2026-10-30-request-labels.md)

ASA-078 DONE: 내가 보낸 요청 라벨과 입력 원문을 동일 박스 안에 바로 이어 배치. 중간 안내 제거·항목 설명 외부 이동·테스트 배지 유지. 브라우저 확인, pytest162·ruff/mypy34·typecheck/build 통과. [기록](docs/worklogs/2026-10-30-request-grouping.md)

ASA-079 DONE: 사용자 지정 성공 테스트 요청(b05622eb)의 입력에서 실행 연결 검증 접두사 제거. DB 저장 및 실제 브라우저에서 고양이가…로 시작하는 문장 확인. 과거 호출 감사 기록/AI 결과 보존. 코드 변경 없어 테스트/빌드 재실행 없음, AI 호출0. 증거 .local/verification/request-prefix-removed.png.

ASA-080 DONE: 실제 수정 AI1회 성공. 실제 전달 메시지 v1 포함·v1 원문 보존·base_version1→v2·고객 결과 일치 확인. 기존 제목/첫 문장 유지, 3문장 축약/지정 끝문장 반영. 입력1221/출력107/캐시생성1219토큰·3.946초·예상USD0.00206075 기록, 실행별 이벤트1건. 브라우저 v1/v2 비교 및 관리자 요청 추적 확인. [기록](docs/worklogs/2026-10-30-revision-live.md)

ASA-081 DONE: 등록 지침/출력 스키마 기반 단독 에이전트 실행, 범용 답변 저장·표시·수정·재요청. 쉬운 대본 작가 v4 등록 및 동일30초 입력 실제 API1회 성공(251자/3문단, 입력1004·출력204토큰,6.771초,예상USD0.002024). 브라우저 읽기/수정 취소 확인. pytest166·src ruff/mypy34·frontend typecheck/build 통과. 기존 버전 보존, 음성 낭독 시간 미측정. [기록](docs/worklogs/2026-10-30-agent-contract.md)

ASA-082 DONE: 실제1분 대본 v1 437자·수정v2 443자/각4문단. 이전 답변 전체 전송·첫/끝문장 보존·지정 내용 교체·v1 보존·최신 결과 일치 검증. 성공 사용량2건/예상합계USD0.00653775. 브라우저v2·버전/이력 확인. pytest166·ruff/mypy34·web typecheck/build 통과. 낭독60초 실측은 미실시. [기록](docs/worklogs/2026-10-30-minute-script-live.md)

ASA-083 DONE: 테스트 · 1분 대본 생성과 길이 검사 저장, 자동화AI 활성화·로컬워커 실행. 실제 AI1회/4노드 성공. 생성444자→검사입력 일치·600자 이하 확인, 경계600/601 무과금 검사. 자동화/실행/단계별 사용량997/358토큰·8.978초·예상USD0.002787 및 브라우저 결과/모니터링 확인. pytest166·ruff/mypy34·web typecheck/build 통과. [기록](docs/worklogs/2026-10-30-automation-writer-inspect.md)

ASA-084 DONE: 입력 폼 편집(이름/짧은글/긴글/숫자/라디오/선택목록/슬라이더/필수/기본값), 공통 실행·미리보기, 등록/실행 검증 및 AI 입력 이름 전달. 브라우저 기본값/변경값 확인. pytest173+최종 관련8·공급자5, ruff/mypy34, typecheck/build 통과. API·워커 재시작, 유료호출0. [기록](docs/worklogs/2026-10-30-agent-input-form.md)

ASA-085 DONE: 무서운 쇼츠 대본 작가(0ccdd20c) 초안revision2에 아이나이/공포강도/길이/소재/분위기/주인공/목적/제외소재 8항목 저장. 참고 이미지 선택지·기본값 반영. 지침/출력/모델·등록버전 보존 비교 및 서버 정의검증·브라우저 미리보기 확인. 아직 미등록 초안이며 유료호출0. 코드 변경 없어 빌드/전체회귀 재실행 없음. 증거 .local/verification/horror-input-form.png.

### ASA-086 · 선택지 편집 UX 개선 (DONE)
- 줄바꿈 입력을 개별 선택지 행으로 교체하고 추가·삭제, 빈 값·중복 안내 및 기본값 동기화를 검증합니다.

- 완료: 개별 행 추가/삭제, 기본값 이름 동기화·삭제 안내, 공백/중복 안내와 저장 차단. 실제 화면에서 동작 확인. 기존 사용자 초안은 변경하지 않음.
- 검증: frontend typecheck/build, backend ruff src/mypy src 통과. 전체 pytest 169 통과/기존 input_schema fixture 누락 5 실패, tests ruff 기존 26건. 상세: docs/worklogs/2026-10-30-choice-options-editor.md.

ASA-087 DONE: 에이전트 입력 방식 선택에 사용자용 도움말과 방식별 입력 예시를 표시.

- ‘사용자가 답하는 방식’ 라벨, 공통 ? 도움말, 6가지 방식별 설명/예시를 선택칸 바로 아래 표시. 입력 정의와 사용자 초안 데이터 변경 없음.
- 검증: frontend typecheck/build, backend ruff src/mypy src 통과. 로컬3001 연결 거절로 브라우저 확인 미실시. 전체 pytest는 로컬 서비스 미응답 상태에서 진행되지 않아 중단(통과 주장 없음).

ASA-088 DONE: 로컬 DB/API/web 재시작 및 입력 방식 설명의 실제 화면 검증.

- DB/API/web 정상 포트 확인. 실제 에이전트 편집에서 6가지 설명 전환, ? 도움말 열기/닫기 확인. 도움말 펼침 시 옆 입력칸 늘어남을 CSS 정렬로 수정.
- typecheck/build, backend ruff src/mypy src 통과. 전체 pytest 재실행은 결과 없이 대기하여 중단; 전체 회귀 통과로 간주하지 않음. 사용자 초안/지침 저장 변경 없음. docs/worklogs/2026-10-30-input-mode-help.md.

ASA-089 DONE: 에이전트 상단 AI 전달 안내와 설정 카드 간격 수정·접힘/펼침 실화면 검증.

- 상단 disclosure 하단을 settings-section-gap(24px)으로 분리. 실제 브라우저에서 접힘/펼침 모두24px, 기본설정→입력양식→도구→고급설정 각24px 확인. .local/verification/agent-section-spacing.png.
- frontend typecheck/build 통과. backend pytest -x 2통과 후 기존 input_schema 누락1실패로 중단, ruff src/mypy src 통과. 사용자 데이터 변경 없음.

ASA-090 DONE: 무서운 쇼츠 대본 작가 등록 및 고객 실행 입력 항목 검증(AI 호출 없음).

- UI로 무서운 쇼츠 대본 작가(0ccdd20c) v1 등록 성공 확인. 새 작업 목록 v1 노출 및 실제 고객 실행 폼 확인.
- 8항목(나이/무서운정도/길이/소재/분위기/주인공/목적/피할소재), 필수2/선택6, 라디오/슬라이더/목록/텍스트 및 기본값 확인. 나이·슬라이더·소재·주인공 조작 후 새 선택으로 기본값 복원 확인.
- AI 호출/요청 저장 없음. 코드 변경 없는 등록·UI 검증이므로 전체 pytest/빌드 재실행 없음. 증거 .local/verification/horror-registered-run.png.

ASA-091 DONE: 에이전트 실행 전 빈 결과 카드 제거 및 단일 열 입력 배치.

- 고객 실행/설정 미리보기의 빈 작업 결과 카드 제거. 입력 전용 단일 열(최대960px) 배치. 설정 미리보기의 지침 펼침은 아래에 유지. 실행 접수·기존 답변 화면 코드는 변경하지 않음.
- 실제 고객 화면에서 결과 카드0개, 단일 열941px 확인. 사용자 데이터/유료 호출 없음. .local/verification/run-input-single-column.png.
- typecheck/build, backend ruff src/mypy src 통과. pytest -x 기존 input_schema 누락으로2통과/1실패(전체통과 아님).

ASA-092 DONE: 실행 입력 폼의 공통 세로 간격과 선택 해제 버튼 간격 정리·실측 검증.

- 실행 폼 공통 flex gap24px, 개별 field/p 중복 margin 제거, 라디오 해제 버튼 상단12px, 슬라이더/선택지 내부 토큰 정리.
- 브라우저 전체8항목 경계+실행/안내 간격24px, 해제 버튼3개 모두12px 실측. 선택 해제 후 버튼이 없어져도 다음 그룹24px 확인. 기본5분 복원. AI실행/저장 없음. .local/verification/input-form-spacing.png.
- 검증: frontend typecheck/build 및 backend ruff src/mypy src 통과. pytest -x 기존 input_schema 누락1실패/2통과에서 중단.

ASA-093 PARTIAL: 실행 워커 복구 및 요청 요약 UI 개선 완료. 실제 답변 생성 실패는 미해결.

- 누락된 script worker를 복구해 기존 대기 요청(4c6524de)을 중복 접수 없이 처리. 약35초 후 call_or_output_failed, 출력 버전 없음. 토큰/비용 미확인(usage_unknown)이므로 유료 자동 재시도 없음. 기존 로그에는 상세 오류가 없어 원인 확정 불가.
- 내가 보낸 요청 제목1개 + 항목명/값 요약으로 통합. 진행 영역의 입력 원문 중복 제거. 워커 오프라인 시 AI 호출 미시작과 자동 재개 안내 표시.
- 실화면 제목1개/중복 영역0개 및 7개 입력값 확인. 증거 .local/verification/compact-request-receipt.png.
- frontend typecheck/build, backend ruff src/mypy src 통과. pytest -x 기존 integration fixture input_schema 누락으로2통과/1실패. 실제 AI 성공·전체 회귀 통과를 주장하지 않음.

ASA-094 DONE: 최근 작업의 완료 후 수정 요청 상태 갱신, 작성 중 표시, 실제 시간 초과와 조회 장애 구분.

- 완료된 항목도 포함해 로드된 최근 작업 페이지를3초 간격 조회. 대기/AI작성중 텍스트+점 표시, 조회 오류는 마지막 상태임을 안내. 요청 상세 상단에 진행 안내 추가.
- 최신 시도가 실패하면 이전 답변 유무와 별도로 실패/결과확인 표시. 실제 timeout 예외만 ai_timeout 기록 및 목록에 시간초과 표시. 원문 오류/비밀값 저장 없음, 자동 재시도 없음.
- timeout 분류/중복호출 방지3테스트, 큐/DB통합5테스트 통과. frontend typecheck/build 및 backend ruff/mypy 통과. 전체 pytest는 기존 input_schema fixture 오류로2통과/1실패.
- 진행중 작업0건 확인 후 API·에이전트 워커 재시작. 사용자17:23요청은17:24:01성공 기록 확인. 실제 실패 화면은 Chrome에서 확인(.local/verification/request-status.png). 유료호출 없이 모의 timeout을 DB까지 검증했으며 브라우저에서 실제 AI 실행/timeout 전환 재현은 하지 않음.

ASA-095 DONE: SSE 공개 요청 이해·작성 방향·부분 답변 및 최근 작업 동기화.
- 단일 모델 스트리밍→부분출력DB→인증된 SSE 스냅샷. 재연결 무중복, 최종스키마검증, 실패시미완성 보존. gzip 프록시 지연 발견/identity 헤더로 해결. 카드간격16px/height:auto 검증.
- 단위10·큐/SSE통합5경우, typecheck/build, ruff/mypy 통과. 전체pytest 기존input_schema fixture오류1실패/2통과.
- 실제2호출(프록시 수정 전후), 최종부분118→180→305→438자 후완료 및 재연결attempt1건 확인. 최근작업 작성중→완료 실화면 확인. 총예상USD0.00558730. docs/worklogs/2026-10-30-agent-sse.md 참고.

ASA-096 DONE: 누락된 테스트 입력 정의 수정 및 전체 회귀 검증.
- 첫 전체 실행176통과/5실패. 5건 모두 테스트용 자동화 도구의 input_schema 누락: SDK 사용량 OpenAI/Claude2건, 모델스냅샷1건, 공급자키선택2건.
- tests/integration/test_registry_db.py, test_graph_automation.py, test_multi_provider.py의 입력이 문자열인 fixture에 string 입력정의 추가. 실행 코드/검증 조건/사용자 데이터 변경 없음.
- 수정 후 전체 backend pytest181통과(230.78초), frontend node --test lib/*.test.mjs 32통과, typecheck/build 통과. backend ruff src/mypy src(35개) 통과. 유료AI호출0.
- Node 테스트의 MODULE_TYPELESS_PACKAGE_JSON 경고는 비실패 안내이며 남아 있음. 테스트 범위 밖 모든 동작이 무결하다는 의미는 아님.

ASA-097 DONE: 기존 DB 에이전트·자동화 input_schema 읽기 전용 전수 감사.
- 2026-10-30 22:51 KST, 전체 업무 workspace 1개를 repeatable-read/read-only 트랜잭션으로 조회. 에이전트 초안3개·등록버전6개, 자동화8개(도구/에이전트 참조11개·직접AI4개), 실행 스냅샷3개·예약1개 확인. 현재 정의 누락/빈값/스키마 검증 오류/참조 오류0건, 실행·예약 manifest와 정의의 실행블록 일치.
- 고객 요청12개 버전 참조 정상. 에이전트 실행 시도11건 중 최근4건의 prompt input_schema 정상. 과거7건(완료5·취소2)은 이전 형식으로 prompt에 input_schema 없음. 해당 에이전트 버전 정의는 정상이며, 누락된 과거 시도 중 대기/실행 중0건. 과거 실제 전송 기록을 사후 변경하지 않음.
- 시작/결과/분기/반복 제어블록17개는 별도 input_schema 저장 대상 아님. 직접AI는 런타임의 string 입력 계약으로 검증, 에이전트 설정은 object 입력 계약으로 검증. 총34개 스키마 확인.
- DB 수정/유료AI호출/실행 코드 변경 없음. 이번 검증은 데이터 감사이며 전체 테스트 재실행은 하지 않음(직전 ASA-096 전체 검증 결과 유지). 로컬 감사 결과: .local/verification/input-schema-audit.json.

ASA-098 DONE: 장면 구성 에이전트 등록 및 대본→장면 구성 실제 연결 검증.
- 장면 구성 에이전트 v1 등록. 대본 필수/화풍·인물 설정 선택, 원문 보존·연출 제안 구분·장면별 대본 구간/시간/화면/인물/카메라 지침. 재사용 정의 docs/agent-templates/scene-planner.json.
- 기존 무서운 대본 단독 실행: 첫 호출 unknown/사용량 미확인, 7번째 장면에서 부분출력 중단. 출력 상한2048→8192 로컬 설정 후 별도 실행 성공(12장면·300초·3874자). 실패 원인을 상한으로 확정하지 않음.
- 자동화 '어린이 공포 동화 · 대본에서 장면 구성까지' 구성 v1 등록/실제 완료. 대본2581자가 다음 에이전트 script 입력과 완전히 일치. 장면 구성14개·300초·4206자. 웹 실행 기록에서 각 단계 완료/출력 표시 확인.
- 성공3호출 예상비용USD0.04857405(자동화2호출 USD0.0336075). 첫 실패는 비용 미확인 별도 기록. 토큰/시간/요청ID/단계ID DB 기록 확인. 기존 사용자 에이전트/요청 변경 없음. 워커 실행 유지, 활성 예약 없음.
- backend pytest181통과(196.62초), ruff/mypy35파일 통과. frontend node32통과/typecheck/build 통과. 제품 실행 코드 수정 없음; DB 등록·로컬 환경설정·문서 추가. 원문/생성물/비밀은 Git 제외.
- 웹 프록시 단독 조회 간헐500은 API 직접 조회로 최종 결과 확인; 원인 해결을 주장하지 않음. 상세: docs/worklogs/2026-10-30-scene-planner.md.

ASA-099 DONE: 캐릭터 설정 에이전트와 기준 이미지 생성·수정·확정 연결.
- 기존 OpenAI 키로 캐릭터 설정/이미지 생성/이미지 편집 실제3호출 성공. 이하나 v1/v2 보존, 장화만 파란색으로 수정 확인. 사용자 확정 대기.
- 기존 대본·장면 결과를 입력으로 사용하고 캐릭터별 이미지 작업을 큐에 저장. 이전 이미지 기반 수정, 명시적 확정, 버전·사용량 보존.
- backend185테스트/ruff/mypy38파일 및 frontend32테스트/typecheck/build 통과. 실제 이미지 인증/CSRF/모니터링·버전 전환 확인. 전체3호출 예상USD0.065109.
- 캐릭터 전용 화면 연결 완료. 파일 업로드/장면 이미지/범용 자동화 이미지 블록은 미구현. 상세 docs/worklogs/2026-10-30-character-images.md.

ASA-100 IN PROGRESS: 에이전트 답변 내 등장인물 선택·이미지 생성/수정/확정 통합. 보관함은 원본 실행 결과로 연결. 답변 버전별 이미지 구성 분리 및 기존 이미지 보존 검증 예정.

ASA-100 DONE: 에이전트 답변에서 등장인물 목록·선택 생성·이미지 버전 수정/확정을 통합. `/characters`는 원본 요청/답변 버전으로 연결하는 보관함으로 변경.
- 기존 7인과 이하나 이미지 v1/v2 보존 확인. 선택 2명 표시/이미지 버전 전환/보관함 왕복을 실제 브라우저에서 검증.
- source_version별 구성 격리, import 중복/ID 충돌/다른 workspace/없는 버전 회귀 검증. SSE 이전 버전 선택 유지, 수정한 캐릭터 설정을 일괄 생성에도 반영.
- backend pytest 186 passed, ruff/mypy 통과. frontend 32 tests/typecheck/build 통과.
- 이번 작업에서는 새 유료 생성과 사용자 이미지 확정을 실행하지 않음. 상세 docs/worklogs/2026-10-31-character-results.md.

ASA-101 IN PROGRESS: 구름 할머니 실제 이미지 생성→수정→확정 UI 검증, 이하나와 화풍 비교 및 다른 인물 생성 위치 확인. 사용자 승인 범위에서 실제 이미지 API 호출 예정.

ASA-101 DONE: 구름 할머니 실제 UI 생성→수정→확정 및 새로고침 보존 확인.
- 구름 할머니 v1 생성 22.358초, v2 꽃 자수 수정 22.715초. 실제 API2호출 예상 총 USD0.040122. 관리자 사용량 API의 토큰/비용/시간 기록 확인.
- v2를 기준 이미지로 확정하고 v1 보존. 이하나 및 다른5인 작업은 변경하지 않음.
- 두 인물의 따뜻한 3D 화풍은 육안으로 유사. 타 인물 이미지 직접 참조 없이 공통 텍스트 스타일이므로 완전 일관성 보장으로 주장하지 않음.
- 같은 에이전트 답변에서 나머지 인물 선택 또는 개별 생성 가능. 캡처 .local/verification/grandma-confirmed-ui.png.
- backend186테스트(290.80초)/ruff/mypy, frontend32테스트/typecheck/build 통과. 제품 코드 변경 없음. 상세 docs/worklogs/2026-10-31-grandma-image-live.md.

ASA-102 IN PROGRESS: 메뉴 증가/짧은 화면에서 최근 작업이 0 높이로 축소되는 문제 수정. 접기 버튼과 콘텐츠 높이 분리, 메뉴 독립 스크롤 및 최근 작업 최소180px 확보, 극단적으로 짧은 화면은 사이드바 전체 스크롤.

ASA-102 DONE: 최근 작업이 메뉴에 밀려 사라지는 높이 문제 수정.
- 사이드바 콘텐츠가 접기 버튼을 제외한 남은 높이 사용. 메뉴 최대32dvh 독립 스크롤, 최근 작업 최소180px 및 제목 고정. 매우 짧은 화면은 전체 콘텐츠 스크롤.
- 실제 브라우저에서 최근 작업 표시/클릭 진입, 메뉴 독립 스크롤, 오래된 작업 스크롤 확인. 사용자 확대 설정 변경 없음.
- backend186테스트(197.05초)/ruff/mypy, frontend typecheck/build 통과. docs/design-system.md에 규칙 반영. 검증 캡처 .local/verification/sidebar-recent-fixed.png.

ASA-103 IN PROGRESS: 이미지 모델 선택에 Sunburst/Flare 용도 설명과 공식 단가 비교를 공통 컴포넌트로 적용. 일괄·개별 선택 모두 반영, 검증 진행 중.

ASA-103 DONE: 일괄/개별 이미지 모델 선택에 용도 설명·접이식 비교·동일 표준 단가·공식 출처 적용. 실제 브라우저 모델 전환/설명 변경/펼치기 확인. backend186 tests(211.01초), ruff/mypy, frontend32 tests/typecheck/build 통과. 유료 생성 및 실측 모델 비교 없음. docs/worklogs/2026-10-31-image-model-guide.md.

ASA-104 IN PROGRESS: 모델 안내 출처 링크의 밑줄 제거, 공통 외부 링크 스타일과 디자인 규칙 반영.

ASA-104 DONE: 공통 ExternalLink에 작은 외부 이동 아이콘/hover 배경/키보드 포커스 적용. 기본 anchor 밑줄 제거, 모델 출처 링크 간격 및 줄바꿈 정리. docs/design-system.md 규칙 반영. 실제 화면/키보드 포커스 확인(.local/verification/image-model-links.png). backend186 tests(330.94초)/ruff/mypy, frontend typecheck/build 통과.

ASA-105 IN PROGRESS: 공통 후속 작업 상태 계약 및 캐릭터 이미지 생성/검토/확정/제외 상태를 최근 작업에 반영. 최신 답변별 격리, 제외 복원, SSE 재개 동선과 테스트 구현.

ASA-105 DONE: 공통 work_progress 계약과 캐릭터 이미지 adapter 적용. 최근 작업 SSE에 미생성/생성 대기·진행/검토/확정/제외·실패 집계, 상세/인물별 재개 동선 제공. 필요 항목 모두 확정 시만 완료(전체 제외는 대상 없음). 제외/복원·버전 격리·활성 작업 보호·오래된 탭 확정 경합 검증. 실제 UI에서 뭉실이 제외/복원 후 원상태(미생성5/검토1/확정1) 확인. 유료 생성/이미지 확정 추가 없음. 최종 backend190 tests(238.79초)/ruff/mypy, frontend33 tests/typecheck/build 통과. docs/worklogs/2026-10-31-followup-progress.md.

ASA-106 IN PROGRESS: 사용자 확정 필요 설정/개별 실행 확정/후속 상태 통합, 입력 폼 정렬과 에이전트 고정 A 아이콘 개선.

ASA-106 DONE: 등록 버전별 requires_approval과 일반 답변 검토/확정/재검토, 답변+이미지 통합 진행 상태 구현. 입력 라벨44px 정렬/chevron/AgentIcon/카드 하단 정렬. 실제 화면 및 옵션 선택 확인, 기존 사용자 설정 변경 없음. backend192 tests/ruff(src)/mypy, frontend33 tests/typecheck/build 통과. 전체 tests ruff의 기존 스타일 오류는 범위 밖으로 유지. docs/worklogs/2026-10-31-agent-approval.md.

ASA-107 IN PROGRESS: checkbox 공통 클래스의 field-row 종속 제거. 체크박스-문구 gap8/중앙 정렬/기본 margin 초기화 및 실제 화면 검증.

ASA-107 DONE: checkbox 규칙의 부모 종속 제거, gap8px/중앙 정렬/margin0/20px 고정 적용. 승인·필수·기본값 체크박스 실제 화면 확인. backend192 tests(204.44초)/ruff(src)/mypy, frontend typecheck/build 통과. docs/worklogs/2026-10-31-checkbox-spacing.md. 사용자 설정 변경 없음.

ASA-108 IN PROGRESS: UI 공통 스타일 적용 조건·세부 정렬·실제 화면 검증을 프로젝트 필수 규칙으로 명시.

ASA-108 DONE: AGENTS.md에 UI 스타일 작업 필수 규칙 추가. 부모 선택자/기본 여백/터치 조건 확인, 공통 원인 수정, 세부 간격 실측, 관련 상태·테마·화면 크기 및 증거 기록 의무화. 문서 내용 재확인 및 AGENTS.md diff --check 통과. 문서만 변경하여 실행 테스트는 재실행하지 않음.

ASA-109 IN PROGRESS: 입력 항목 내부 중복 margin/gap 제거, 체크박스 가로 배치와 연결 이름·삭제 하단 행 정리, 실제 화면 실측.

ASA-109 DONE: 입력 본문 gap16px 및 중복 margin 제거, 체크박스 가로 배치, 연결 이름/작은 삭제 버튼 하단 행 정리. 실제 요소 top/gap/폭 실측 및 밝은·어두운/좁은 화면/기본값 토글/접기 검증. backend192 tests(211.49초)/ruff(src)/mypy, frontend typecheck/build 통과. docs/worklogs/2026-10-31-input-field-compact.md. 사용자 저장 데이터 변경 없음.

ASA-110 DONE: 기존 모니터링에 OpenAI 공식 Costs/Usage 조회 추가. Codex·수동잔액 제외. Admin Key 미설정 확인(값 미출력), 실제 계정 연동은 설정 후 검증 필요.

- ASA-110 최종 검증: backend pytest 203 passed (186.78s), ruff/mypy 통과, frontend typecheck/build 통과. 실제 화면 밝게/어둡게/좁은 화면과 연결 필요 상태 확인. Admin API Key 미설정으로 실제 계정 금액 및 정상 집계 화면은 미검증. Codex·수동 잔액 없음.

ASA-111 IN PROGRESS: DB 연결 풀, 트랜잭션 변경 알림 기반 SSE와 워커 대기 적용. 유휴 조회 감소와 큐/실시간 상태 회귀 검증.

ASA-111 DONE: 프로세스별 연결 풀 및 PostgreSQL LISTEN/NOTIFY 적용. 유휴 워커 알림 대기/30초 복구 확인, 변경 시 SSE 전송, 캐릭터·자동화 polling 제거. 중첩 풀 교착/잠금 대기 busy loop 보완. 실제 로컬 migration/API·3종 워커 재시작 및 작업 화면 확인. 유휴 10초 신규 연결 56→0, 트랜잭션133→15 관측. backend213 tests(87.84s)/ruff(src)/mypy 및 frontend typecheck/build 통과. 유료 AI 호출 없이 큐·중복·알림 복구·동시성 회귀 검증. docs/worklogs/2026-10-31-db-events.md.

ASA-112 IN PROGRESS: 누적 완료 변경 커밋·push 준비. 코드/테스트/템플릿/문서 131개 선별, .local/비밀값/캐시 제외. CACHE_POLICY.md 부재로 디스크 삭제 보류. 기존 검증 213 tests/ruff/mypy/typecheck/build 통과 결과 유지, EOF 공백 정리.

ASA-112 DONE: 완료 변경 131개 파일의 커밋 포함 목록 확인 및 비밀값 검사 완료(예시 CHANGE_ME만 검출). 불필요 EOF 공백 3곳 정리. 로컬 산출물·비밀값·캐시 제외 유지, 실제 삭제 0개. 직전 전체 검증 결과 재확인. main 커밋·원격 push 진행.

ASA-113 IN PROGRESS: CACHE_POLICY.md 작성. 사용자 자료/생성 자산/DB/활성 런타임 보존 조건으로 로컬 캐시와 일회성 보조 파일 조사·정리.

ASA-113 DONE (2026-11-01): CACHE_POLICY.md 추가. 승인 범위의 검사 캐시 5개 디렉터리와 이전 커밋 보조 스크립트 1개 정리(파일20개, 논리112,590,896 bytes/약107.4MiB; C드라이브 여유 관측 +112,599,040 bytes). .env와 .local/work·verification·bootstrap 보존 파일1,121개 전후 SHA256 일치. DB/생성 이미지/로그/.next/의존성 보존, API ready(DB 연결)·웹 HTTP200 확인. 코드 변경 없어 전체 테스트/빌드 재실행 생략(캐시 재생성 방지). 삭제 상세 로컬 기록 .local/cache-cleanup-2026-11-01.json. 커밋·push 미실행.

ASA-114 IN PROGRESS: 캐릭터 이미지·버전·확정은 유지하고 하단 수정/설정/제외를 수정 및 확인 disclosure로 묶기. 생성 전에는 펼침, 진행/오류는 외부 노출. 실제 화면 검증 예정.

ASA-114 DONE: 캐릭터 카드 하단 수정 및 확인 토글 적용. 이미지/버전/확정 유지, 성공 중복 상태 제거, 진행·실패 외부 노출. 실제 밝게/어둡게·클릭/Enter 접힘 검증(77px, 내부 gap/margin16px, summary44px). 760px 폭 overflow 없음 실측, 좁은 화면 스크린샷은 캡처 timeout으로 미확인. 테마/viewport 복원. backend213 tests(78.64s)/ruff 및 frontend typecheck/build 통과(빌드 EPERM은 권한 환경 재실행 통과). 화면 .local/verification/character-edit-collapsed.png. 사용자 이미지/확정 데이터 변경 및 유료 호출 없음.

ASA-115 IN PROGRESS: 참고 facts/proposed 편집 및 primary appearance/image_prompt 우선순위 분리. 요청 전달/버전 보존 회귀 검증 및 화면 설명 적용.

ASA-115 DONE: facts/proposed 편집 및 draft 요청 연결. primary_settings/reference_context 분리, 수정 요청>우선 설정>충돌 없는 참고 순서를 프롬프트에 명시. 단위 테스트 red→green 및 이미지 큐 통합 테스트로 네 수정값의 DB/worker/API 인자 전달·기존 버전 보존 검증. backend214 tests(76.37s), ruff/mypy, frontend typecheck/build 통과. 실제 두 필드 입력 후 원문 복원, 안내/간격16px·760px overflow 없음 확인. UI 테마·펼침 복원. 이미지 작업0건 확인 후 워커 재시작 적용. 유료 이미지 호출/시각적 결과 준수 테스트는 미실행. 화면 .local/verification/character-reference-edit.png.

ASA-116 IN PROGRESS: 상단 캐릭터 선택+단일 큰 카드/이전다음 구성. 카드 컴포넌트 유지로 이동 중 입력 보존, 이미지·설정 2열 및 좁은 화면1열 검증.

ASA-116 DONE: 상단 이름/상태 선택 및 이전·다음 이동, 본문 단일 큰 카드 적용. 이미지/편집2열·1100px 이하1열, 외형 여러줄 입력, 일괄 선택 대신 개별 생성에 집중. 숨긴 카드 컴포넌트 유지로 설정/수정요청 이동 중 보존. 실제 1개 표시·이전다음·수정문 유지 후 원복·미생성 버튼·760px 1열 overflow없음 확인. 다크 색상 확인, 좁은 화면 캡처 timeout으로 시각 증거 미확보. 테마/viewport/선택 복원. backend214 tests(76.57s)/ruff/mypy 및 frontend typecheck/build 통과. 유료 호출·DB 변경 없음. 화면 .local/verification/character-single-card.png.

ASA-117 IN PROGRESS: 이미지 모델 제목 옆 공통 ? 도움말로 비교/요금 안내 이동. 별도 큰 disclosure 제거, 접근성 및 실제 화면 검증.

ASA-117 DONE: 이미지 모델 라벨 옆 공통 ? HelpText로 비교/비용 안내 이동, 큰 disclosure 제거. 선택창 공통 character-field 스타일 유지. 실제 클릭/Enter/Escape, 라벨 중앙정렬/gap8px, 선택창44px, 다크 색상 및760px 펼침 overflow 없음 실측. 밝게/viewport/접힘 복원. 스크린샷 .local/verification/image-model-help.png. backend214 tests(77.08s)/ruff/mypy 및 frontend typecheck/build 통과. 최초 제한환경 DB 오류/빌드 복사 경고는 권한 환경 재검증 통과. 유료 호출·사용자 데이터 변경 없음.

ASA-118 IN PROGRESS: 개별 이미지와 답변 전체 관리 분리. 명시적 버튼 이름/범위 안내 및 화면 검증.

ASA-118 DONE: 에이전트 답변 관리 section을 이미지/답변 article 밖에 분리. 전체 답변 범위 안내 및 에이전트 답변 수정/답변 텍스트 복사로 이름 변경. 실제 편집 진입/취소, 경계24px/내부12px, 다크 색상/760px overflow 없음 확인. 테마/viewport 복원. 복사 동작은 기존 handler 유지(클립보드 덮어쓰기 미실행). backend214 tests(78.88s)/ruff/mypy 및 frontend typecheck/build 통과. 화면 .local/verification/answer-management.png. 사용자 데이터 변경/유료 호출 없음.

ASA-119 IN PROGRESS: 캐릭터 선택 카드 균등 grid/높이, 자동 줄바꿈 및 긴 이름 처리. 실제 크기/반응형 검증.

ASA-119 DONE: 선택 카드 auto-fill 균등 grid/동일 높이, 이름 줄바꿈·상태 하단정렬. 실제 desktop6열168.48px/높이99.49px, 마지막 줄 동일폭,760px2열213.34px/overflow없음 확인. 다음 줄 Enter 선택 및 다크 상태 검증 후 테마/선택/viewport 복원. backend214 tests(74.38s), frontend typecheck/build 통과. 화면 .local/verification/character-picker-grid.png. 사용자 데이터 변경 없음.

ASA-120 DONE: ASA-114~119 완료 변경11개 파일 선별 및 커밋 준비. 단일 캐릭터 편집/참고 설정 우선순위/공통 도움말/답변 관리 분리/균등 선택 카드와 회귀 테스트·문서 포함. 직전214 tests/ruff/mypy/typecheck/build 통과 확인. 비밀값 패턴 검출0, 로컬 자료·이미지·캐시 제외 및 보존, 실제 삭제0. 사용자 요청으로 main 커밋·push 진행.
