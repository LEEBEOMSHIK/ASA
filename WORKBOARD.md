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

### 다른 세션 변경 통합 및 비디오 프롬프트 구조 검토 · DONE
- 사용자 요청에 따라 남은 소스·테스트·문서 변경을 선별하여 커밋·푸시한다. 임시 로그·테스트 산출물·사용자 자료는 제외한다.
- 비디오 전문 모듈의 설정·선택 우선순위·접수 스냅샷·개별/자동화 실행 연결 및 실제 활성화 범위를 검토한다. 유료 AI 호출과 사용자 설정 저장은 하지 않는다.
- 검토 수정: 비디오 모듈의 문자열/배열 입력 필드 조회 예외를 수정했다. 두 회귀 사례의 수정 전 실패 및 수정 후 통과, 활성 번들의 모의 모델 system 메시지 전달을 검증했다(모듈 25건). 작업 삭제 후 보존된 확정 캐릭터 이미지를 후속 씬에서 거부하던 조건도 수정했고, 제외/미확정 차단을 유지하는 회귀 검증 4건을 통과했다.
- 범위: 기존 세션의 작업 관리·프로필·조건부 입력·이미지 버전 선택·비디오 비교·전문 프롬프트 연결 및 의존 소스/문서 82개 파일을 통합한다. `.tmp-comparison-*.log`, backend `.test-tmp`, `.local`은 로컬 보존하며 커밋하지 않는다. 파일 삭제는 하지 않았다.
- 한계: 전문 모듈 4개는 비활성이며 본문 미제공 상태다. DB 큐/그래프에서 활성 전문 모듈을 사용한 통합 실행과 유료 생성 품질은 미검증이다. 이번 통합 검토에서 전체 기존 UI의 시각 검증을 반복하지 않았으며 기존 작업별 미검증 기록을 유지한다.
- 최종 검증: 격리 PostgreSQL 전체 pytest 362건 통과(102.05초), mypy 63개 소스 및 frontend typecheck/production build 통과. 수정한 두 회귀 영역의 ruff 통과, 전체 ruff는 기존 97건 오류가 남아 있다. diff-check 통과. 유료 호출·실제 사용자 설정/자료 변경 없음.

### 로그인 화면 브랜드 로고·파비콘 연결 · REVIEW
- 로그인 헤더의 고정 브랜드와 인증 후 전용 조회로 인한 누락을 수정한다. 배포 설정의 workspace에 한정한 공개 이름·로고 조회와 공통 StudioBrand를 연결하며 기존 저장값은 변경하지 않는다.
- 로그인 전 조회·관리 API 인증 유지 회귀 테스트, backend pytest/ruff/mypy 및 frontend typecheck/build, 실제 브라우저 테마·좁은 화면·파비콘 확인을 진행한다. 기존 다른 작업의 변경은 보존한다.
- 구현: `/branding/public`은 서버 설정의 workspace 이름·로고만 반환하고 캐시를 금지한다. 기존 관리 API 인증·CSRF·권한 검사는 유지한다. 로그인 헤더가 `StudioBrand`를 재사용하고 앱 소유 `#asa-favicon`만 동기화한다. 헤더는 사이드바 전용 여백을 받지 않는다.
- 검증: 신규 통합 회귀 테스트가 수정 전 404로 실패하고 수정 후 통과. 브랜드 관련 3건 및 전체 pytest 358건 통과, mypy 63개 소스와 frontend typecheck/build 통과. 전체 ruff는 기존과 같은 97건 오류, 수정한 branding.py는 통과. 초기 uv 캐시/DB 연결·테스트 임시 폴더·빌드 출력 권한 문제는 기존 venv, 임시 폴더 생성 및 승인된 로컬 재실행으로 해소했다.
- 실제 Chrome: 로그인 전 저장된 PNG 로고 로드와 favicon href 일치, 어두운/밝은 테마, 1600×823 데스크톱 및 실제 CSS viewport 433×938(밝게)/360×800(어둡게) 전체 화면을 확인했다. 헤더 확대 및 computed style/요소 경계에서 로고 약32px·문구 간격 약12px·세로 중심 일치·이중 문자 로고 제거·헤더 패딩0·가로 넘침 없음 확인. 키보드 브랜드 포커스와 잘못된 키의 오류 상태에서도 로고 유지 확인.
- 다른 사용처: 로그인 후 관리 사이드바에서 이미지 로드·파비콘 일치를 DOM으로 확인했다. 해당 탭의 확대 캡처는 도구 시간 초과로 미확보. 실제 브랜드 저장값은 변경하지 않았으며, 임시 테마·viewport·입력·로그인 세션은 원래 상태로 복원했다. 브라우저 확대 배율은 변경하지 않았다.
- 시각 검증 한계: 긴 브랜드명·로고 미설정/조회 실패·일시적 로딩/비활성의 전체 조합은 미검증이다. 기본 브랜드 반환은 API 테스트로 확인했다. 로고 자체에는 선택/펼침 상태가 없어 해당 없음. 전체 UI 상태 검증 완료를 뜻하지 않는다.
- 증거: `.local/diagnostics/login-branding/`의 `login-final.jpg`, `login-brand-detail.jpg`, `desktop-light.jpg`, `mobile-light.jpg`, `mobile-dark.jpg`, `brand-focus.jpg`, `mobile-error.jpg` 및 검사 로그. 후속 커밋·푸시 요청에 따라 이 수정과 관련 기록만 선별하며 다른 작업·로컬 진단 산출물은 제외한다.

### Codex 다른 세션 반복 최적화 조사 · DONE
- 범위: `AI Shorts Studio 초기 구조 설계`의 최근 로고·파비콘 요청에서 명령/대화 최적화가 반복된 원인과 실제 진척을 읽기 전용 세션 기록으로 확인한다. 기존 기능 수정·커밋·푸시는 이번 조사 범위 밖이다.
- 근거와 제한은 `.local/diagnostics/codex-compaction-2026-11-06/`에 기록한다. 원본 세션·설정은 변경하지 않는다.
- 확인: 최근 요청 한 턴 32분 41.707초, 최적화 22회, 명령 44회(모두 exit 0), local-development 문서 읽기 15회. 해당 턴의 수정·검증·커밋·푸시 실행 증거 없음. 압축 후에도 많은 과거 메시지·이미지가 보존된 패턴을 확인했으며 내부 압축/재연결의 정확한 원인은 미확정이다.
- 검증: 원본 이벤트와 앱 기록의 개수·시각 대조 및 파생 JSON 집계 확인. 진단 산출물 Git 제외 확인. 기능 코드 변경 없는 세션 조사이므로 backend/frontend 검사와 화면 검증은 실행하지 않았다. 기존 로고·favicon 작업의 완료를 뜻하지 않는다.

### Video Prompt Director 동적 전문 모듈 연결 기반 · DONE
- 기존 지침을 보존하는 선택적 설정 계약, 신뢰된 모듈 레지스트리, 우선순위·충돌 기록 및 실행 스냅샷을 추가했다. 개별 실행과 자동화 실행의 모델 호출에 연결했다.
- 공통/2D/3D/실사 본문은 미제공 상태로 모두 비활성화했다. 기존 에이전트 DB 설정과 지침은 변경하지 않았다. 관리자 UI와 AI 화풍 분류는 이번 연결 기반 범위에 포함하지 않는다.
- 검증: 신규 22건 포함 backend pytest 357건 통과, mypy 63개 소스 통과, 변경 backend 파일 ruff 통과, frontend typecheck/build 통과. 전체 ruff는 기존 기록과 동일한 97건 오류가 남아 있다.
- 기본 임시 경로 권한 오류는 프로젝트 내부 basetemp로 재실행해 해소했다. 성공한 전체 테스트 종료 뒤 DB 풀 연결 시간 초과 경고가 출력되어 기록한다.
- UI 변경 없음: 시각 검증 해당 없음. 실제 유료 AI 호출·전문 지침 활성화·생성 품질은 미검증. 구성과 활성화 절차는 `docs/video-prompt-modules.md`에 정리했다.

### 영상 AI 비교 화면 · REVIEW
- Runway와 사용자 제공 8개 후보의 비용 기준·검증 범위·ASA 연결 상태를 내부 화면에서 비교한다.
- 공식 API 요금과 사용자 제공 힉스필드 가격을 분리하며 미검증 성능을 점수로 표시하지 않는다.
- `/video-comparison` 및 사용자 메뉴에 비교 화면 추가. 검색·필터·최대 3개 비교 선택·길이별 예상 비용과 서버 설정 기반 연결 상태를 제공한다. 유료 생성은 수행하지 않았다.
- 검증: frontend typecheck/build, backend mypy 통과. Ruff는 기존 오류 97건으로 실패. Pytest는 샌드박스의 로컬 테스트 DB 접속 차단으로 완료를 확인하지 못했다.
- 미검증: 브라우저 도구가 현재 URL을 검증하지 못해 Computer Use가 중단됐다. 밝음/어두움·모바일 및 실제 화면 동작·스크린샷 검증은 미완료다.

### 씬별 이미지 버전 선택 및 보관함 출처 표시 · DONE
- 확정 이미지는 기본값으로 유지하고, 씬별로 이전 성공 버전과 당시 설정을 선택한다.
- 생성 요청에 선택 버전을 고정하여 비디오 프롬프트까지 실제 참조 정보를 전달한다.
- 보관함에 생성 시각과 원본 작업 이동을 표시한다. 유료 생성 없이 검증한다.
- 검증: backend pytest 335건 통과, src 및 추가 테스트 ruff·src mypy 통과, frontend typecheck·build(15개 경로) 통과. 전체 tests ruff의 기존 97건은 별도 미해결이다.
- Chrome 1280×900 밝음/어두움, 390×844 모바일에서 버전 선택·기본값 복원·보관함 출처·가로 넘침을 확인했다. 임시 선택은 복원했으며 저장·확정·유료 AI 호출은 하지 않았다.
- 화면 근거: .local/verification/scene-version-{light,dark,mobile}.png, version-library-provenance.png, video-scene-version-{light,mobile}.png.
- 실제 씬 이미지에는 v1만 있어 비디오 입력의 v2→v1 전달은 테스트 데이터로 검증했다. 실제 화면은 사용 가능한 버전 표시와 기본값 복원을 검증했다.

ASA-229 DONE · 격리 PostgreSQL에서 API 접수·워크 큐·워커 tick·답변 v1 저장 후 동일 요청을 관리자 API로 영구 삭제. 상세 404·최근 목록 제거·삭제 기록 1건·사용량과 예상 비용 보존·모니터링 본문 제거 검증. 공급자 호출은 테스트 응답으로 대체. 실제 계정의 작업 삭제 및 유료 호출 없음. 집중 3건·전체 306건 통과, mypy/typecheck/build 통과. 전체 ruff 기존 99건.

ASA-228 DONE · 개별 에이전트 최근 작업 숨김·복원, 소유자/관리자 삭제 미리보기와 삭제 기록, 결과물 기본 보존·참조 차단·재전송 멱등 처리. 로컬 마이그레이션 적용. 격리 PostgreSQL에서 권한/차단/부분 실패 롤백/비용 보존/중복 삭제·감사 및 이미지·영상 보존/삭제 검증. pytest 306 통과, mypy·typecheck·build 통과, 전체 ruff 기존 99건. 로컬 Chrome 1280×900 밝음·390×844 어두움 관리자 미리보기·범위 전환·취소·삭제 기록 탭 확인(.local/verification/work-delete-*.png). 실제 사용자 작업으로 숨김·영구 삭제 미실시. 최근 작업 메뉴 추가 실화면 점검은 자동 승인 검토에서 실제 상태 변경 위험으로 차단.

ASA-227 DONE · 공식 집계의 별도 배지 행을 제거하고 제목 우측에 연결 상태 배치. Chrome 320·390·1280px에서 제목과 배지 중심 정렬 및 간격 8px 확인(.local/verification/usage-title-*.png). typecheck/build/mypy/pytest 304 통과, 전체 ruff 기존 99건.

ASA-226 DONE · 공식 집계 정상 조회는 초록색 성공 배지, 혜택 크레딧은 별도 영역에서 OpenAI Credit grants로 이동. ASA가 조회하는 사용량·비용 응답에는 혜택 잔액 없음. Chrome 1280 밝음/390 어두움 배지 색·링크 목적지·가로 넘침 확인(.local/verification/credit-grants-*.png). 외부 조직의 실제 잔액은 미확인. typecheck/build/mypy/pytest 304 통과, 전체 ruff 기존 99건.

ASA-225 DONE · 이미지 보관함에 캐릭터/씬 분리, 씬 검토본과 확정본 조회 및 상세 버전·장면 설정·원래 작업 링크. 기존 확정 씬 선택 API는 확정본만 조회. 로컬 Chrome 1280×900 밝음·390×844 어두움에서 캐릭터 9장과 씬 14장, 실제 이미지 상세·가로 넘침·원본 링크 확인(.local/verification/scene-gallery-*.png). 테스트 DB에서 미확정/최신 검토본 및 버전·종류 분리 확인. pytest 304건·mypy·typecheck·build 통과, 전체 ruff 기존 99건. 사용자 이미지 생성/확정은 수행하지 않음.

ASA-224 DONE · 도구 라이브러리는 ASA 도구만 표시, 준비 중인 항목은 접기. 기존 에이전트별 목록 및 최신 연결 선택을 유지하고 그래프·순차 편집에 연결 당시 버전과 새 접수 기준을 표시. Chrome 1280 밝음·390 어두움에서 카드 4→7, 가로 넘침 없음, 에이전트 9장 확인(.local/verification/tool-library-*.png). 유료 자동화 실행·예약, 빌더 버전 문구의 시각 검증은 미실시. typecheck/build/mypy/pytest 304 통과, 전체 ruff 기존 99건.

ASA-223 DONE · 프로필 모달은 배경에서 시작해 배경에서 끝난 클릭만 배경 닫기로 처리. 임시 Chrome에서 수정 전 내부→외부 드래그로 편집값 유실 재현, 수정 후 양방향 드래그 유지·배경 클릭 닫기 검증(320×568 어두움, 390×844 밝음, 1280×900 양 테마, .local/work/profile-drag.cjs). 실제 사용자 설정 저장·실기기 터치는 미검증. typecheck·build·mypy·pytest 304건 통과. 전체 ruff 기존 99건.

ASA-222 DONE · 프로필 사진 제목을 파일 선택 동작에서 분리하고 클릭 범위를 점선 영역으로 제한. Chrome 320·390·1280px에서 제목 클릭 시 파일 선택 창 0회, 영역과 버튼은 각 1회, 드롭 미리보기 확인(.local/verification/profile-picker-*.png). 원계정 저장 및 실기기는 미검증. 타입 검사·빌드·mypy·pytest 304개 통과, 전체 ruff 기존 99건.

ASA-221 DONE · 최근 작업 접기 제거. 계정 행의 남은 너비를 프로필 버튼으로 사용하고 화면 모드·로그아웃은 톱니바퀴로 분리. 브랜드 및 프로필은 ImageDropzone을 공유. 개발 도구 표시가 프로필을 가리지 않도록 상단으로 이동. Chrome 390×844 밝은 작업 공간, 320×568 어두운 에이전트, 1280×900 양 테마에서 행 우측 hover·설정·잘못된 파일 드롭·PNG 미리보기·저장 버튼 접근·포커스 복귀 확인. 증거 .local/verification/account-controls-*.png. 실제 사용자 사진 저장 및 실기기 검증 제외. pytest 304 통과, mypy·typecheck·build 통과. 전체 ruff 기존 99건.

ASA-220 DONE · 개인 프로필을 탐색 하단에 배치. 표시 이름·사진 편집, 계정별 저장, 권한·작업 공간 조회, 테마·로그아웃을 연결했다. 모바일 메뉴에서 파비콘 동기화 중복과 프로필 닫기 이벤트 간섭을 제거하고 좁은 편집 폼의 가로 넘침을 수정했다.
검증 · Chrome 390×844 밝은 작업 공간, 320×568 어두운 에이전트, 1280×900 양쪽 메뉴에서 열기·편집·닫기, 포커스 복귀, 요소 경계와 가로 넘침 확인. 증거 .local/verification/profile-390-light.png 및 profile-320-dark.png. 실제 계정 정보 저장·로그아웃과 실기기 Safari는 미검증. pytest 304 통과, mypy·typecheck·build 통과, 변경한 Python 파일 ruff 통과, 전체 ruff 기존 99건 남음.

ASA-219 기본 상태: 최근 작업 패널은 작업 공간 진입·새로고침 시 펼침. 접기 선택은 현재 화면에서만 유지하며 메뉴·너비 저장과 분리. 변경 파일 diff 점검 통과.

ASA-219 복구: 최근 작업 접힘 상태를 전체 메뉴 접힘 클래스와 분리하고 폐기된 고객 사이드바 숨김 선택자를 제거. 로컬 Chrome 데스크톱 버튼 조작에서 패널 279→0→279px, 레일 60px·토글 높이 44px 유지 확인. 사용자 설정 변경 없음.

ASA-219 홈 바로가기: 접힌 데스크톱 레일의 열기 버튼 바로 아래에 작업 공간 홈 링크 배치. 같은 목적지의 목록 항목 중복 제거. 실화면 검증 보류.

ASA-219 전체 메뉴: 데스크톱 스튜디오와 작업 공간의 기본 탐색을 아이콘 레일로 통일. 상단 버튼으로 메뉴 이름을 펼치고 선택을 기억한다. 최근 작업은 별도 시계 버튼과 독립 너비 설정을 사용한다. 모바일 기존 탐색 유지. 실제 화면 미검증.

ASA-219 최근 작업 목록: 스크롤바 안쪽의 중복 패딩 12px 제거. 목록의 4px 포커스 여백만 유지. 실화면 미검증.

ASA-219 간격 조정: 데스크톱 최근 작업 스크롤 영역을 패널 오른쪽 경계까지 확장하고 너비 조절 영역을 본문 쪽에 배치. 카드 여백 보존. 실화면 미검증.

ASA-219 REVIEW: 작업 공간 데스크톱 메뉴를 아이콘 레일로 분리하고 최근 작업 패널은 독립적으로 접거나 너비 조절. 드래그·좌우 방향키·Home/End, 로컬 너비 복원, 모바일 기존 메뉴 유지. 실화면 검증 보류.

ASA-218 REVIEW: 영상별 메모·전체 목표·AI 적용 후보·제외 조건을 분리한 분석 전달문, 클립별 스타일 반영 및 후반 편집 항목 추가. 로컬 영상 분석가 revision 5, 비디오 프롬프트 에이전트 revision 7 저장 및 등록본에 규칙 포함 확인. 기존 답변 호환, 유료 재분석·클립 생성·화면 확인 미실행.

ASA-217 배치 개선: 작업 공간 헤더 바로 아래 로그인 후 공통 상태 줄에 에이전트 워커 상태를 한 번만 표시. 선택·입력·이력 이동 간 유지, 오프라인 시 전체 대기 안내. 요청별 진행 카드는 유지. 실화면 검증 보류.

ASA-217 REVIEW: 접수 전·대기 이력 상단에 인증된 작업 공간 워커 heartbeat 기반 온라인/오프라인/미확인 표시. 로컬 워커 복구 및 yt-dlp 플러그인 차단 옵션·720p 이하 화면 트랙 선택 수정. 사용자 승인 요청에서 24개 표본, 동일 이력 답변 v1 성공 및 SSE용 이해·방향 필드 저장 확인. 수정 반영 워커 온라인 확인. 브라우저 수신과 전체 회귀 미검증.

ASA-215 안내 개선: 참고 영상 제목 옆에 그룹 전체의 필수 여부·합산 개수를 표시하고 입력 방식 안내는 보통 굵기로 분리. 단일·선택 입력에 맞는 안내 유지. 실화면 검증 보류.

ASA-216 검색 표시: 검색어·카테고리·즐겨찾기 조건을 먼저 적용하고 결과가 있는 그룹만 표시. 전체 결과 0건은 안내 한 번만 표시. 필터 없는 관리자 분류의 빈 드롭 영역 유지. 실화면 검증 보류.

ASA-216 색상 조정: 등록된 별은 두 테마 모두 공통 노란색 #ffda00 사용. 실화면 미검증.

ASA-216 별 인터랙션: 호버 시 크기·형태를 고정하고 작은 중성 배경만 부드럽게 표시. 선택된 별은 테마별 금색 단색, 모션 감소 설정에서는 즉시 전환. 실화면 확인 보류.

ASA-216 호버 재조정: 기본 포인터 media 조건 제거, 직접 hover/focus 시 전용 배경색·별 1.12배 강조. 로컬 Edge 포인터 확인을 시도했으나 계산 스타일 결과를 얻지 못해 실화면 미검증.

ASA-216 호버 조정: 선택한 별은 노란 단색 채움, 카드 별 호버는 테마별 원형 강조 배경. 키보드 포커스 유지. 실제 화면 미검증.

ASA-216 카드 별 개선: 상시 배경·외곽선을 없애고 선택된 별만 노란색으로 표시. 아이콘 22px, 터치 영역 44px, 키보드 포커스 유지. 실제 화면 미검증.

ASA-216 후속 REVIEW: 밝은·어두운 테마에 즐겨찾기 전용 노란색 토큰 적용. 카드와 필터의 빈 별/채워진 별 구분 및 저장 성공 시 추가·해제 알림. 실제 화면·동작 테스트 보류.

ASA-216 후속 REVIEW: 에이전트·새 작업 필터 바의 컨트롤 하단 정렬 및 공통 높이, 카테고리 폭 제한, 모바일 검색 단독 행, 카드·필터 별 아이콘과 선택색 통일. 실화면 검증 보류.

ASA-216 REVIEW: 에이전트 목록·새 작업 공통 별 버튼 및 검색/카테고리와 조합되는 즐겨찾기 필터. workspace·로그인 사용자·버전 독립 에이전트 ID로 저장. 테스트와 브라우저 확인 보류.

ASA-215 후속 REVIEW: 참고 영상 그룹 설명과 빈 입력 오류를 ‘파일 또는 공개 링크 1개 이상’으로 통일. 두 입력 방법을 동등한 패널로 배치하고 컨테이너 폭에 따라 세로 전환. 실화면·실행 테스트 보류.

ASA-215 REVIEW: 참고 영상 파일·링크 합산 상한 5개를 입력 UI, 접수 검증, 서버 분석, 템플릿, 기존 로컬 영상 분석가에 적용. 저장된 maxItems=5 확인. 링크 목록은 플랫폼명·식별 주소·원본 열기·선택 메모로 정리. 테스트·실제 화면 미검증.

ASA-214 REVIEW: 빈 참고 영상 슬롯 제거. 한 드롭 영역의 복수 파일 직접 업로드와 주소 입력 후 링크 추가를 같은 목록에 반영. 영상별 메모·삭제, 합산 4개, 용량 초과·전송 실패·업로드 중 분석 검증 유지. 테스트 및 실화면 검증 보류.

ASA-213 REVIEW: 편집 제목 옆에서 해당 에이전트의 최신 저장 설정을 작업 공간 입력 화면으로 여는 바로가기 추가. 미저장 편집 중에는 새 탭에서 저장본 열기. 실행 요청은 사용자가 입력 후 접수. 테스트·실화면 미검증.

ASA-212 후속 REVIEW: 최근 작업을 요청 ID별 독립 카드로 표시. 기본 카드 경계, 선택 카드 강조선, 포커스, 후속 작업 요약 배치 적용. 실화면 미검증.

ASA-212 REVIEW: 사이드바 ‘최근 작업’의 메뉴 경계·제목 강조, 작업명과 날짜의 위계 정리, 완료·후속 작업 필요·실패를 공통 상태 배지로 구분. 테스트 보류로 실화면 미검증.

ASA-211 후속 REVIEW: 실행 항목 제목을 1.25rem으로 강조하고 영상 모델 연결 확인을 콤보박스 오른쪽의 독립된 플러그 아이콘 버튼으로 이동. 모델별 접근성 이름·확인 중 안내와 상태 배지 유지. 실제 화면 확인 및 테스트 보류.

ASA-211 REVIEW: 에이전트 실행·미리보기 입력 항목의 경계를 공통 구분선과 섹션 간격으로 표시. 제목은 1.125rem 굵은 글자, 필수·선택 보조 문구는 작은 글자로 구분. 테스트 보류에 따라 테마별 실제 화면·모바일은 미검증.

ASA-210 후속 REVIEW: 닫힌 영상 모델 선택기에 공통 상태 배지 복원. 네이티브 선택·키보드 동작과 모델별 연결 확인 유지. 밝은/어두운 테마·모바일 실화면은 테스트 보류로 미검증.

ASA-210 REVIEW: 영상 모델 선택 목록과 닫힌 콤보박스에 모델명·설정 상태 표시. 선택한 모델의 연결 확인 동작을 라벨 옆에 배치하고 결과를 모델 키별로 분리. 테스트·실제 화면·공급자 호출 미검증.

ASA-209 REVIEW: 비디오 프롬프트 실행 입력에 모델 표시명·로컬 생성 준비 상태·Runway 계정 인증 조회 추가. 기존 참고 스타일 필드의 이전 답변 출처 설정을 로컬 DB에서 읽기 확인. 현재 키 미설정·생성 비활성. 테스트·화면·공급자 응답 검증 보류.

ASA-208 REVIEW (코드·로컬 DB 적용, 실행 미검증): Runway Gen-4.5 독립 클립 큐·워커와 답변 카드, 선택 생성·재생·사람 확정, 작업별 사용량/예상 비용 기록 구현. ASA 로컬 PostgreSQL 기동, 기존 비디오 프롬프트 에이전트 revision 6에 모델 입력·구조화된 클립 답변 적용. Runway 키 미설정 및 유료 생성 비활성 확인. 테스트/브라우저/실제 영상 호출 보류. 자동 마지막 프레임 추출·이어붙이기는 후속. [설정 문서](docs/video-generation-contract.md)

ASA-207 REVIEW (준비 계층 구현·미검증): 모델 프로필 설정, 길이 배분 제안, 로그인 기반 video-planning models/durations/prepare API와 확정 씬 workspace/버전·모델 revision 검증 추가. opt-in 입력 계약의 모델 제한을 LLM에 전달하고 템플릿에 클립 분할/최소 전달 규칙 보강. 기존 DB 지침·이미지 불변. 사용자 요청에 따라 테스트·유료 호출 미실행. 실제 공급자 adapter/큐·워커·클립 관리 UI·DB 에이전트 적용은 남아 있으며 전체 영상 생성 기능 완료가 아님. [범위와 후속 계약](docs/video-generation-contract.md)

ASA-167 DONE: 텍스트 입력의 이전 작업 답변 선택·버전/항목 미리보기 제공. 원문 복사 후 직접 수정 유지. 자동화 앞 에이전트 출력과 확정 이미지 동시 전달·workspace 격리 검증. 유료 생성 없이 모델 호출 경계 검증.

ASA-166 DONE: 추가 지침 공란 보존·첨부 이미지 기본 기준/충돌 확인 규칙 적용. 실제 로컬 씬 이미지 에이전트 기존 지침 보존 후 revision6 저장(8,520자), 지침 한도12,000자. 빈 지침/공백 실제 이미지 전달 테스트, pytest271 passed95.66s, src ruff/mypy50/typecheck/build/diff-check 통과. 실제 다크 화면 안내 확인, 유료 이미지 생성 및 이번 모바일/라이트 재검증 미실행. [기록](docs/worklogs/2026-11-02-image-reference-default.md)

ASA-165 DONE: 직접 이미지 업로드·드롭 영역·캐릭터 연결/수정·보관함 저장 및 실제 이미지+설정 전달. workspace/파일/변조 검증, pytest268·src ruff/mypy50·frontend typecheck/build 통과. 실제 파일 선택·저장·연결 변경/해제·보관함 보존, 밝게/어둡게/모바일 확인. OS 파일 드래그 제스처와 유료 AI 호출은 미실행. docs/worklogs/2026-11-02-character-uploads.md 참조.

ASA-164 DONE: 이미지 선택 버튼 공통 12px 간격·줄바꿈, 화면 비율의 방향·용도·적용 범위 안내. 실제 다크/모바일 화면과 원래 비율 값 유지 확인. pytest262·src ruff/mypy49·frontend typecheck/build 통과. docs/worklogs/2026-11-02-input-spacing.md 참조.

ASA-163 DONE: 이미지 카드 보관함·작업/에이전트 출처·검색/필터/이전 버전, 확정 이미지 선택 입력 및 설정+실제 이미지 전달. 사용자 데이터 보존, workspace/확정/제외 검증, 실제 다크·모바일 화면 확인. 전체 pytest 261 + 선택 계약 큐 2건, src ruff/mypy/typecheck/build 통과. 유료 호출 없이 실제 이미지 2장·설정·원문 전달 확인. docs/worklogs/2026-11-02-character-library.md 참조.

ASA-162 DONE: 씬 이미지 지침·대본 전체 필수 입력을 로컬 에이전트 revision2에 적용(다른6개 불변). 개별 큐/수동 실행에 공통 확정 이미지 첨부 연결. 실제 원문 대본2581자/씬4206자/확정 이미지7장 모델 메시지 포함 확인(유료 호출 대체·0건). DB 큐 통합 및 pytest260·src/new-test ruff·mypy48·typecheck/build 통과. 유휴 개별 워커 재시작·오류 없음 확인. 실제 AI 품질·씬 이미지 생성은 미검증/후속 범위. [기록](docs/worklogs/2026-11-02-scene-image-inputs.md)

ASA-161 DONE: 씬 이미지 에이전트 템플릿·로컬 등록. 원문·확정 캐릭터 입력과 장면별 제작 지침·참조 ID·연속성 출력 계약, 사용자 검토 설정. 기존6개 에이전트 불변 확인. 스키마 깊이5 지원·6 거부 테스트, pytest256·src/new-test ruff·mypy48·frontend typecheck/build 통과. 실제 카드/설정 화면 확인. 유료 실행·생성 품질 미검증, 씬 이미지 생성 도구/UI는 후속 범위. [기록](docs/worklogs/2026-11-02-scene-image-agent.md)

ASA-160 DONE: 캐릭터 이미지 선택 일괄 접수 및 대기 요청 취소. 일괄 접수 트랜잭션·중복 방지, 워커 claim 경쟁·취소 후 기존 확정 보존 검증. pytest255·src ruff·mypy48·frontend typecheck/build 통과. 전체 tests ruff 기존71건 유지. 실제 다크 화면의 패널 열기·빈 대상 안내 확인. 현재 사용자 이미지 모두 생성되어 선택 접수/취소 UI 실조작은 미검증, DB 모의 검증 완료. 유료 호출0, 사용자 작업 취소0. [기록](docs/worklogs/2026-11-02-image-batch-cancel.md)

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

ASA-121 IN PROGRESS: 이미지 큐/생성 경과 시간, 불변 요청 요약, 백그라운드 이동 안내. 클라이언트 타이머만 사용하고 SSE 유지.

ASA-121 DONE: 이미지 대기/생성 타이머 및 불변 요청 요약·워커 미연결/백그라운드 안내 추가. SSE 상태 갱신 유지, 매초 DB/API 호출 없음. 실제 뭉실이 서버 기록23초 표시 확인. 임시 모의 화면에서 queued→running/초단위 갱신/상세 토글 검증 후 임시 route 삭제. 좁은 화면 viewport 측정은 적용되지 않아 미검증, active 다크 시각 미검증. frontend3개 렌더/시간 테스트, typecheck/build; backend214 tests(72.39s)/ruff/mypy 통과. 유료 호출/사용자 DB 변경 없음. 화면 .local/verification/image-job-duration.png 및 image-job-progress-preview.png.

ASA-122 IN PROGRESS: 실제 상태 기반4단계 표시와 경과 시간 결합. 생성/저장은 현재 서버의 단일 상태로 표시, 검토/확정 및 오류 구분. 사용자 요청으로 브라우저 시각 확인은 사용자에게 위임.

ASA-122 DONE: 4단계 완료 체크/현재 강조/펄스와 시간 병기. 생성·저장 합산, 사용자 확정 전 검토 필요, 실패/unknown 중단·확인필요 표시. 타이머 cleanup/reduced-motion 지원. frontend5개 회귀 테스트/typecheck/build, backend214 tests(71.94s)/ruff/mypy 통과. 사용자 지시에 따라 브라우저 확인 미실행(사용자 확인 예정). 유료 호출/DB 변경/커밋 없음.

ASA-123 IN PROGRESS: 버전 고정 후속 이미지 검수 연결(선택/수동/자동), 별도 검수 큐·비전 호출/사용량, 이미지별 검수 이력과 설정 변경 안내. 미연결/실패는 생성·사람 확정을 막지 않음.

ASA-123 DONE: 검수 전용 에이전트/purpose 및 after_tasks.image_review(버전고정·수동/자동) 추가. 이미지별 불변 검수 큐/설정/결과 이력, 멱등·활성 중복 방지·workspace 격리·재시작 unknown, 원래 요청 추적과 토큰/비용 기록. 이미지 저장과 자동 검수 접수를 같은 트랜잭션/savepoint로 처리하며 선택적 검수 실패는 이미지 보존. 실제 이미지와 수정 기준 이미지를 비전 입력으로 전달하고 base64는 모니터링에서 제외. 검수 실패/미연결/설정변경 안내, 수동 재검수, 백그라운드 경과 시간 및 SSE 제공. 자동 재생성/사람 확정 없음. 이미지 없이 일반 요청·자동화 블록으로 검수 에이전트 호출 차단(명시적 이미지 검수 블록은 미구현).
검증: backend216 tests(71.87s)/ruff/mypy, frontend7개 렌더·시간 테스트/typecheck/build 통과. 초기 빌드 standalone 복사는 sandbox EPERM으로 실패 후 권한 실행 통과. 추가 요율 테스트 표본의 label 누락을 수정하고 전체 재검증 통과. 유료 AI 호출 없음, 실제 검수 품질 미검증.
로컬 DB migration/API·이미지 워커 재시작 완료. 이미지 검수 에이전트145c3387-2415-415a-8a47-2c282a117ecf v1 생성, 기존 캐릭터 설정 에이전트6d009f0d-a677-48d4-956a-8572436f54f4 v2에 수동 연결. 기존 요청·생성이미지·확정 상태 보존. 실제 설정 화면 선택값·16px간격·필드동일폭·수평넘침없음 확인, 기존 결과에서 검수 미연결/확정2·검토1·미생성4와 워커 연결 확인. 화면 .local/verification/image-review-settings.png. 새 유료 검수 결과의 브라우저 시각 검증/모바일/다크 시각 검증은 미실행. 커밋·push 없음.

ASA-124 DONE: 에이전트별 기본 아이콘 12종 선택, 관리용 저장·등록 버전 반영, 목록/실행/미리보기 공통 표시. 기존 로봇 기본값 유지.

ASA-124 검증: backend pytest 218 passed(아이콘 기본값·허용목록, DB 저장 및 등록 버전 보존 포함), ruff src / mypy src(42 files), frontend typecheck / build / SSR tests 8 passed. 실제 브라우저에서 12종 선택·방향키 이동·요약 아이콘 반영 및 간격 확인(.local/verification/agent-icon-picker.png). API 재시작 적용. 사용자 기존 아이콘·등록 버전은 임의 변경하지 않음, 유료 API 호출 없음. 추가로 tests까지 ruff를 넓혀 실행했을 때 기존 테스트 파일 스타일 위반이 있어 소스 검사 통과와 구분함(이번 추가 행 길이 위반은 수정).

ASA-125 DONE: 기본 아이콘 표시 + 선택적 아이콘 변경 펼침, 관리용 공통 Field 도움말 아이콘 적용.

ASA-125 검증: backend218 tests/ruff src/mypy42 files, frontend8 tests/typecheck/build 통과. 실제 브라우저 기본 로봇·접힘·변경 펼침12종·다시 접기·공통 관리용 아이콘 및 주변 정렬 확인. screenshot .local/verification/agent-icon-default.png. API 실행에 루트 .env를 명시하여 테스트 로그인 복구. 사용자 DB 내용 변경/유료 호출/커밋 없음.

ASA-126 커밋 준비 완료: ASA-121~125 이미지 진행·경과 시간, 선택적 이미지 검수 큐/연결/사용량, 에이전트 아이콘 기본값·선택 UI와 공통 도움말을 하나의 기능 묶음으로 정리. 코드·테스트·템플릿·문서만 포함. 사용자 자료/생성 이미지/DB/.env/.local/캐시는 보존·제외, 실제 삭제 없음. 직전 backend218 tests/ruff src/mypy 및 frontend8 tests/typecheck/build 결과 재사용(이후 실행 코드 변경 없음). 실제 유료 검수 품질과 미기록 테마/모바일 상태는 미검증. 사용자 요청에 따라 main 커밋 및 origin push 진행.

ASA-127 DONE: 용도 선택/역할 기반 제한 제거, 검수 연결에서 실제 이미지 전달 및 공식 모델 이미지 입력 지원 검증. 기존 purpose 필드는 읽기 호환만 유지.

ASA-127 검증: backend227 tests 통과(기존 purpose=image_review/신규 purpose 없는 연결의 큐·자동접수·멱등·결과·사용량·격리, 미지원/미확인/비활성 모델, 기본 모델 변경, 실제 이미지 전달 모의 검증); ruff src/mypy43 files, frontend8 tests/typecheck/build 통과. 실제 DB 기존 연결1건 읽기 전용 검증 True/gpt-6.1-terra, 공식 이미지 입력 지원 확인. 실제 브라우저 용도 필드0개, 전체 등록 에이전트 후보·기존 선택·지원상태 확인(.local/verification/review-connection-capability.png). API/이미지 워커 재시작, 실행 중 작업0 확인. 유료 검수 품질/다크/모바일 미검증. 사용자 데이터/연결/이미지 확정 변경 없음, 커밋 없음.

ASA-128 IN PROGRESS: 뭉실이 v1 실제 검수 요청. 과거 요청v1에는 연결이 없어 검증 명령에서만 현재 검수자v1을 명시(연결 조회 함수만 일회성 대체, 실제 모델·이미지·큐 검증과 워커 호출 유지). 과거 등록 버전/이미지/확정 상태 보존. 결과 및 사용량 확인 진행.
ASA-128 DONE: 뭉실이 v1 실제 유료 이미지 검수 1회 성공. review=5c142d68-d7bf-4829-be2a-95bd503a002e, usage=b3c69f14-aa0e-4765-a502-f1d8c28dae19. gpt-6.1-terra 입력2055/출력566/합계2621 tokens, 예상 USD0.004885(estimated), 모델 호출10.285초/전체약12.9초. 원래 request c408792f-432e-4485-ba40-11b8ecd991ba와 검수step 연결 확인. 설정에 없는 후면 흰 돌기, 후면 페인트 식별성, 요청보다 확장된 시트 구성을 지적; 원본 이미지 육안 비교와 대체로 일치. 자동 품질 보증은 아니며 사람이 최종 판단. 실제 브라우저 뭉실이 선택 후 v1 검수 의견 도착/결과/기록1건 확인. 과거 요청의 연결은 변경하지 않아 미연결 안내는 유지됨(이번 요청만 명시적 검수자 지정). 이미지 재생성/확정 변경 없음. 실행 코드 변경 없이 실제 호출 검증만 수행하여 전체 테스트 재실행 없음.

ASA-129 IN PROGRESS: 보관함 공통 버튼, 검수 의견 제목/목록 표시 및 실행 이력 설명, 요청 원문 기본 접힘. 저장 데이터·유료 호출 변경 없이 UI 개선 및 실제 화면 검증.
ASA-129 DONE: 보관함 공통 secondary 버튼, 검수 제목/목록/강조의 안전한 텍스트 렌더링, 실행 이력 횟수 설명·당시 설정·최신 의견 중복 제거, 과거 검수와 미연결 상태 안내 구분. 내가 보낸 요청 기본 접힘/내용 펼치기·접기와 원문 보존. backend227 tests(79.83s)/ruff src/mypy43files, frontend typecheck/build/9 tests 통과. build 파일복사 sandbox EPERM 후 권한 실행 통과. 실제 뭉실이 화면 제목4/목록9, 12px gap, 보관함 밑줄없음/47.5px 높이, 요청 Enter 펼침/접힘·4개 입력 원문 확인. 밝은/어두운 테마 검수 표시 및 실행 이력 설명 확인. 좁은 화면 실측433px에서 넘침없음/summary44px/토글 확인; 모바일 스크린샷은 CDP timeout으로 전체 시각 검증 미완료. 임시 화면 크기·밝은 테마 복원. 증거 .local/verification/asa129-review.png, asa129-request.png. 유료 호출/사용자 데이터 변경/커밋 없음.

ASA-130 IN PROGRESS: 요청 토글 오른쪽 정렬, 검수 전체폭 대시보드/기존결과 호환/수정지시 복사, 새 검수 구조화 보고서 추가. 기존 지침·답변 계약 보존.
ASA-130 DONE: 우측 토글 화살표/포커스 유지, 이미지 아래 전체폭 검수 대시보드, 기존 결과 미집계·의견3개/별도 수정지시 복사, 새 검수 report 계약+사용자 answer 보존 및 검증. backend228 tests/ruff src/mypy44files, frontend typecheck/build/11 tests 통과. 실제 뭉실이 기존결과 전체폭1022px·지표2열·의견3개·24px gap, 밝은/어두운 테마 하단까지 확인. Enter 토글 회전, 복사 성공 UI 확인(브라우저 clipboard 읽기 값은 빈값으로 내용 재검증 미완료). 좁은 화면600px 지표1열·가로넘침없음 실측, 스크린샷 CDP timeout으로 모바일 시각검증 미완료. 크기 override reset/밝은 테마 복원. 증거 asa130-review.png/asa130-toggle.png. 큐/실행0건 확인 후 이미지 워커 재시작 적용. 실제 유료 새 구조화 응답 호출은 미실행, 단위 테스트로 계약·이미지·사용자지침 전달 검증. 사용자 이미지/확정/등록버전 변경 없음. 커밋 없음.

ASA-131 IN PROGRESS: 검수 확인 필요 배지·의견 수·의견 카드에 공통 warning 색상과 테두리 강조 적용. 의미/판정 데이터는 보존.

ASA-131 DONE: 확인 필요/검수 도착 warning 배지, 의견 수 주의 배경·테두리, 의견 카드 주의 제목·느낌표·4px 강조선 적용. 실제 뭉실이 밝은/어두운 화면에서 토큰 색·카드 gap16px·넘침없음 확인, 테마 복원. 증거 .local/verification/asa131-light.png. backend228 tests(79.57s)/ruff src/mypy44files, frontend11 tests/typecheck/build 통과. 모바일 재검증 미실행(레이아웃 구조 유지), 데이터/유료호출/확정 변경 없음, 커밋 없음.

ASA-132 IN PROGRESS: 캐릭터 설정 지침 DB 초안/v1/v2 동일 확인. 에이전트 카드에 초안의 이미지 검수 연결 이름·버전·수동/자동 표시.

ASA-132 DONE: 카드에 이미지 검수 연결 대상·버전·수동/자동 방식 표시, 호출 도구 수와 구분. DB 읽기 전용 확인: 캐릭터 설정 초안/v1/v2 지침 동일, 초안/v2 검수자v1 수동 연결. 지침/DB 변경 없음. backend228 tests(72.18s)/ruff src/mypy44files, frontend typecheck/build 통과. 실제 목록 밝은 화면 연결 표시·정렬 확인, 증거 .local/verification/asa132-card.png. 다크/모바일 전체 시각 검증 미완료. 유료 호출/커밋 없음.

ASA-133 IN PROGRESS: 목록 연결 상세 박스 제거, 호출 도구/연결 에이전트 개수만 표시. 에이전트 ID 중복 제거.

ASA-133 DONE: 목록은 호출 도구/연결 에이전트 수만 표시, 상세 박스·전용 CSS 제거. 연결 에이전트는 호출 참조와 검수 참조의 ID를 중복 제거. 실제 브라우저 캐릭터 카드 0개/1개 표시 확인. backend228 tests(72.83s)/ruff/mypy44files, frontend typecheck/build 통과(초기 sandbox DB/빌드 권한 오류 후 권한 실행 성공). 상세 화면·지침·DB 변경 없음. 모바일 시각 검증 미실행.

ASA-134 IN PROGRESS: 단일 저장·신규 접수 최신 에이전트 설정·기존 접수 snapshot 보존. 계획 docs/superpowers/plans/2026-11-01-agent-save.md.

ASA-134 DONE: 단일 저장 API(초안+불변 실행 기록 원자 저장/충돌·검증 실패 롤백), 편집 버튼 저장1개·버전 관리 제거, 신규 요청 최신 설정/기존 요청 재접수·수정 고정. 자동화 기존 참조 최신 해석·스키마 검증, 예약 흐름/직접 AI 설정 유지·연결 에이전트 매 접수 최신 적용, 새 검수 대상 최신 지침·모델 snapshot 및 기존 검수 보존. 이전 미등록 초안 일괄 적용 없음. backend231 tests(78.99s)/ruff/mypy44 files, frontend11 tests/typecheck/build 통과. 실제 캐릭터 편집 화면 저장 버튼1개·안내·간격 확인. 진행 작업0 확인 후 API/자동화/이미지 워커 재시작, 개발 테스트 로그인 확인. 기존 사용자 지침·이미지·확정 변경/유료 호출/커밋 없음. 다크/모바일 재검증 미실행.

ASA-135 IN PROGRESS: 에이전트 저장 바 하단 sticky, 변경/저장/오류 상태와 저장 버튼 항상 접근, 입력 스크롤 여백 및 모바일 배치.

ASA-135 DONE: 편집 폼 하단 sticky 저장 바, 변경/저장 중/성공/실패 상태 및 오류 이동 링크, 모바일 가로 배치·입력 scroll-margin 적용. 실제 지침 입력 위치에서 밝은/어두운 테마 저장 버튼 노출·간격 확인 후 밝게 복원. backend231 tests(80.36s)/ruff/mypy, frontend typecheck/build 통과. 사용자 지침 저장/유료 호출 없음. 모바일 실기기·가상 키보드 검증 미실행.

ASA-136 DONE: 모바일 저장 바 검증 및 ASA127–135 커밋 준비. Chrome viewport 설정 390x844/360x500 및 실제 CSS 360x800에서 지침 편집 중 sticky 저장 버튼 확인. CSS360 화면 document 폭343px로 가로 넘침 없음, 저장 버튼73.3x47.5px·하단16px 여유, Tab 포커스 표시 확인. 낮은 높이에서도 저장 버튼 노출 확인. 브라우저 기존 확대 배율 유지, viewport 복원. 사용자 설정 저장/유료 호출 없음. 실제 모바일 OS 키보드·Safari는 미검증. 기존 전체검증 backend231 tests/ruff/mypy 및 frontend11 tests/typecheck/build 통과 기록 확인. 캐시·사용자 자료·이미지는 커밋 제외.

ASA-137 IN PROGRESS: 에이전트 목록의 반복 저장 배지 제거, 편집 저장 상태 유지.

ASA-137 DONE: 목록 저장된 설정 배지 제거, 편집 저장 상태 유지. 목록 Agent 데이터에 주의/사용중지 상태가 없어 추정 배지는 추가하지 않음. 실제 밝은/어두운 테마 6개 카드 배지 없음·아이콘 행40px 확인, 밝게 복원. backend231 tests(92.89s)/ruff/mypy44 files 및 frontend typecheck/build 통과. 단일 배지 삭제로 반응형 구조 변경 없음; 모바일 재검증 미실행. 사용자 설정·DB 변경/유료 호출/커밋 없음.

ASA-138 IN PROGRESS: 에이전트 관리/실행 선택 카드 hover·키보드 포커스 테두리 공통 강조.

ASA-138 DONE: 관리/실행 선택 카드 hover 및 focus-within primary 테두리+inset1px 강조, 크기 이동 없음. 실행불가 버튼 카드 제외. 브라우저 실제 hover 색 rgb(81,70,217)·inset 및 Tab 포커스 확인. 포인터 미디어가 false인 브라우저에서도 실제 hover 적용되도록 미디어 제한 제거. backend231 tests(82.67s)/ruff/mypy44, frontend typecheck/최종 build 통과. 모바일/다크 재검증 미실행, 공통 테마 토큰 사용. 사용자 데이터 변경·유료호출·커밋 없음.

ASA-139 IN PROGRESS: 캐릭터 제외를 추가 작업 기본접힘으로 이동, 사용 안 함/다시 사용 및 보존 설명 정리.

ASA-139 DONE: 사용 안 함 버튼을 기본 접힌 추가 작업으로 이동. 완료 조건 제외·이미지/확정 기록 보존·복원 가능 설명, 제외 상태 사용 안 함 및 다시 사용 문구 적용. 실제 뭉실이 확정 v1 화면 접힘/펼침·버튼과 안내 간격 확인. 사용자 상태 변경 버튼은 누르지 않음. backend231 tests(79.15s)/ruff/mypy44 및 frontend typecheck/build 통과. 모바일/다크 재검증 미실행, 공통 details/테마 사용. 데이터 변경·유료호출·커밋 없음.

ASA-140 IN PROGRESS: 확정 캐릭터 전달 계약·미확정 차단·제외 필터·자동화 읽기 도구·비전 첨부 및 전달 미리보기. 원문 변경 금지.

ASA-140 DONE: 확정 캐릭터 전달 API/ASA 읽기 도구 및 전달 대상 미리보기 추가. 제외 인물 제거, 필수 인물 미확정 시 전체 전달 차단, 확정 이미지 job의 설정·수정 요청·이미지 ID/버전만 전달. 대본/장면 원문은 별도 입력 유지, 원문/사용자 상태 변경 없음. 다음 자동화 AI 호출에 workspace 검증된 실제 이미지 첨부, 비전 모델 검증·오래된 전달 데이터 거부. backend239 tests(74.88s)/ruff/mypy45 및 frontend typecheck/build 통과. 실제 화면 확정3/미생성4·전달 차단 확인. 모바일 CSS400/document383 가로 넘침 없음·버튼 상태 DOM 확인, 모바일 스크린샷은 캡처 시간초과로 시각 검증 미완료, viewport 복원. 실행 자동화0 확인 후 API/자동화 워커 재시작. 다음 에이전트 지정/사용자 자동화 작성·유료 API 종단 실행은 미실행; 전체 결과 객체를 다음 비전 에이전트 입력에 명시적으로 연결해야 함. 커밋 없음.

ASA-141 IN PROGRESS: 캐릭터 이름 옆 공통 사용 스위치, 제외 시 편집 접기·재사용 시 상태 보존 및 화면 검증.

ASA-141 DONE: 추가 작업 토글/복원 버튼 제거, 이름 옆 공통 Switch 적용. 끄면 생성·수정·검수 영역 숨김, 활성 생성 중 변경 차단 및 이유 안내. 실제 이하나 사용 끄기→키보드 Space로 켜기 검증, 확정 v2 asset ID·모든 입력값 동일 확인, 원래 사용 상태 복원. 밝은/어두운 스위치 정렬·대비 확인 후 밝게 복원. 모바일 CSS400/document383, 스위치44px 높이·제목 옆 배치 DOM 검증, viewport 복원. backend239 tests(77.09s)/ruff/mypy45, frontend typecheck/build 통과. 최초 제한 환경 DB 접근/빌드 EPERM은 권한 허용 재실행으로 통과; 중복 제한 환경 테스트 중단. 유료 생성/원문·이미지 변경/커밋 없음.

ASA-142 IN PROGRESS: 관리자 전용 카테고리 CRUD/순서 및 에이전트 DnD 분류, 일반 실행 화면 반영. workspace 경계·충돌 검사, 원래 지침/실행 버전과 분리.

ASA-143 IN PROGRESS: 기존 에이전트 메뉴는 생성/편집 및 검색·분류 조회 유지, 카테고리/DnD는 관리자 전용 에이전트 관리 메뉴로 분리. ASA142 임시 검증 그룹 제거 및 소속 복원.

ASA-142 DONE: workspace 단위 카테고리 CRUD/순서 및 에이전트 분류 저장, 관리자 권한·동시 저장 충돌 검증. 실제 브라우저 그룹 생성/이름 변경/버튼 순서 변경/에이전트 DnD 및 선택 메뉴 이동과 사용자 실행 목록 반영 확인. 일반 사용자 API 읽기 허용·쓰기403 테스트. 임시 분류는 ASA143에서 제거. backend242 tests/ruff/mypy46 및 frontend typecheck/build 통과. 모바일 및 카테고리 자체 DnD 순서 시각 검증 미실행.

ASA-143 DONE: /agents 기존 생성·편집 카드와 검색/카테고리 필터 유지, 분류 관리 컨트롤 제거. /admin/agents 관리자 전용 화면 및 GNB 에이전트 관리 메뉴 추가, 직접 URL 접근도 관리자 검사. 실제 브라우저 양쪽 메뉴/버튼 분리·6개 에이전트 유지·검색 무서운 결과1개 확인. 테스트 카테고리 2개만 ID/이름 대조 후 제거하고 샘플 소속 미분류 복원(revision7), 지침·이미지 보존. backend242 tests(93.45s)/ruff/mypy46 및 frontend typecheck/build, git diff --check 통과. 일반 사용자 브라우저 별도 로그인·모바일 재검증 미실행; API 권한 테스트 통과. 유료 호출/커밋 없음.

ASA-144 IN PROGRESS: 관리자 분류 카드 전체 드래그, 별도 이동 손잡이 제거, 드래그 후 링크 오작동 방지. 선택 메뉴 대체 조작 유지.

ASA-144 DONE: 관리자 카드 전체 draggable, 이동 손잡이 제거, 드래그 후 링크 클릭 방지와 선택 메뉴 대체 조작 유지. 실제 카드 본문 드래그로 샘플 작가 대본 그룹 이동/저장 확인 후 미분류 복원 확인. 일반 클릭 상세 이동 정상, 화면 확인. backend242 tests(84.42s)/ruff/mypy46 및 frontend typecheck/build 통과. 모바일 터치 드래그는 미검증(선택 메뉴 유지), 유료 호출/커밋 없음.

ASA-145 IN PROGRESS: 카드 위 분류 select 제거, 우상단 더보기 카테고리 이동·현재 분류 표시·Escape/외부 클릭 닫기, 카드 드래그 유지.

ASA-145 DONE: 카드 위 select 제거·우상단 44px 더보기 메뉴, 현재 카테고리 체크 및 그룹 선택 저장, Escape/외부 클릭 닫기 구현. 실제 메뉴 이동 저장·카드 드래그 이동 확인, 샘플 원래 미분류 복원. 밝은/어두운 화면 배치·메뉴 대비 확인 후 밝게 복원. backend242 tests(84.07s)/ruff/mypy46 및 frontend typecheck/build·diff check 통과. 모바일 실기기 미검증. 유료호출/커밋 없음.

ASA-146 IN PROGRESS: 미분류 최상단 고정 및 카테고리 순서 인덱스 보정, GNB 로고/접기 동일 행, 관리자 사용자 메뉴 구분.

ASA-146 DONE: 미분류 최상단 고정(관리/에이전트/실행 공통), 카테고리 순서 버튼 인덱스를 실제 목록 기준으로 보정. 관리자 GNB 사용자/관리자 제목·구분선 분리, 로고와 접기 버튼 동일 행 배치 및 상단 빈 행 제거. 실제 관리/작업 공간 화면 정렬·미분류 순서, 접기/펼치기 확인. 사용자 카테고리/소속 변경 없음. backend242 tests(94.54s)/ruff/mypy46, frontend typecheck/build 및 diff check 통과. 모바일 실기기·다크 이번 변경 재검증 미실행. 커밋 없음.

ASA-147 IN PROGRESS: 다크/모바일 메뉴 구분·접기·카드 메뉴 검증, ASA137–146 변경 선별 및 커밋/푸시.

ASA-147 DONE: 데스크톱 다크 메뉴 사용자/관리자 구분·로고행 버튼 스크린샷 및 접기/열기 확인. viewport390x844/324x720(사용자 확대배율 유지, 실제 CSS433/360)에서 모바일 접이식 메뉴 열기/닫기·사용자/관리자 구분·카드 메뉴 확인. CSS360 document343, 메뉴 left74.8/right294.8, 항목44px; 가로 넘침 없음. 모바일 스크린샷 API 반복 시간초과로 픽셀 시각 검증 미완료(DOM/요소 경계 검증 완료), 실제 iOS/Safari 미검증. 화면모드 밝게·viewport 원복, 데이터 이동/유료호출 없음. 최종 코드 검증 ASA146 backend242 tests/ruff/mypy46 및 frontend typecheck/build 통과 이후 제품 코드 변경 없음. ASA137–146 코드/테스트/문서26개 선별, 사용자자료·생성이미지·DB·비밀·캐시 제외/로컬 보존, 파일 삭제0.

ASA-148 IN PROGRESS: 작업 공간·사용자 에이전트의 미분류 제목/필터 제거, 에이전트 접근 유지 및 관리자 미분류 유지.

ASA-148 DONE: 공통 AgentGroups에서 사용자 화면 미분류 제목/필터 제거, 빈 미분류 영역 숨김. 미분류 에이전트 자체는 전체/검색에서 유지하고 관리자 미분류 그룹·이동 대상 유지. 실제 작업 공간/에이전트 DOM 확인, 관리자 미분류 0개 유지 확인. 에이전트 다크 화면 스크린샷 및 카드6개/카테고리3개/가로 넘침 없음 확인. 현재 미분류0개이므로 미분류 카드 존재 상태와 모바일/밝은 테마 재검증은 미실행(조건부 렌더링 변경, CSS 불변). pytest242 passed87.79s, backend src ruff 및 mypy46, frontend typecheck/build 통과. 전체 backend ruff는 기존 테스트 파일71건 오류로 실패(이번 변경 없음). 샌드박스 uv 캐시/DB/빌드복사 제약은 기존 venv 및 승인된 로컬 실행으로 재검증. 사용자 데이터 변경·유료 호출·커밋 없음.

ASA-149 IN PROGRESS: 관리자 브랜드 설정(이름/로고) 추가, 이미지 드롭/파일선택·미리보기·DB 저장 및 공통 GNB 반영. workspace/관리자/CSRF/충돌/이미지 검증.

ASA-149 DONE: 관리자 /admin/branding 메뉴·서비스 이름·PNG/JPG/WebP 5MB 드롭/선택·96px 비율유지 PNG 변환·미리보기·저장·문자 로고 복원 구현. workspace_branding DB 저장/revision409/관리자 권한/CSRF/PNG CRC·크기·압축 검증. 작업 공간/RegistryShell 공통 StudioBrand 반영, 주기조회 없음. 기본 로고/이름은 변경하지 않음. API8127만 재시작 및 추가 테이블 적용, 워커 유지. 테스트251개87.80s 통과, 이미지 저장/재조회 보강 후 관련2개 재통과. src ruff/new unit ruff/mypy47/typecheck/build 통과. 기존 전체 tests lint71건은 별개로 남음. 실제 파일 선택→미리보기→기본문자 복원 확인, 다크 데스크톱/밝은 모바일450CSS폭 스크린샷 및 넘침 없음 확인. 실제 OS 파일 드롭 제스처·사용자 workspace 저장은 미실행(DB저장은 테스트 schema), 기존 테마dark/viewport 원복. 문서 갱신, 사용자 이미지/비밀 커밋 없음. ASA148 미커밋 변경 유지.

ASA-150 IN PROGRESS: 브랜드 설정 전용900px 폭 제한 제거, 공통 관리자 컨테이너 폭 사용 및 실제 경계 확인.

ASA-150 DONE: brand-settings의900px max-width 제거, width100%/min-width0으로 공통 본문 폭 사용. 실제 다크 데스크톱 max-width none/내용폭1473.26px/가로넘침 없음 스크린샷 확인, 모바일 CSS450px/내용399.26px 넘침 없음 DOM확인·viewport 원복. 미리보기 내부 로고만 실제 메뉴 크기 유지. 디자인 시스템 관리자 임의 폭 제한 금지 명시. pytest251 passed85.89s, src ruff/mypy47/typecheck/build/diff-check 통과. 기존 테스트 lint71건은 이전 기록대로 미해결. 데이터/로고 변경 및 커밋 없음.

ASA-151 IN PROGRESS: 로고 드롭 영역 내 선택 이미지 썸네일·교체 안내·이미지 변경 버튼 추가. 기존 사용자 선택값 유지.

ASA-151 DONE: 드롭 영역 내 선택 로고96px 썸네일/선택 상태/교체 안내·이미지 변경 버튼 추가. 동일 draft.logo를 사용해 하단 메뉴 미리보기와 일치. 실제 사용자 선택 이미지 로딩·두 이미지src 일치·96px/16px 간격·가로넘침 없음 스크린샷/DOM 검증. 사용자 미저장 이미지와 입력 유지, 저장/파일교체/화면이동 안함. src ruff/mypy47/frontend typecheck/build/diff-check 통과. 모바일/밝은 테마 이번 변경 재확인 없음. 디자인시스템 업로드 영역 직접 미리보기 규칙 추가.
ASA-151 검증 추가: pytest251 passed84.77s. 기존 테스트 파일 lint71건은 이전 작업 기록과 동일하게 미해결.

### ASA152 · 브랜드 설정 변경 취소 (진행 중)
- 이미지 변경 취소와 전체 변경 취소를 추가. 이미지 처리 중 취소 시 늦게 완료된 결과가 다시 적용되지 않도록 무효화.
- 실제 화면 및 필수 검사 확인 예정.

ASA152 DONE: 이미지 변경 취소(이름 유지) 및 전체 변경 취소(마지막 저장 상태 복원) 구현. 비동기 이미지 변환 결과 무효화. 별도 실제 브라우저 탭에서 파일 선택→이미지만 취소→이름 유지→전체 취소→원래 이름/저장 비활성 확인, 다크 화면 버튼 정렬 확인. 사용자 탭 미저장 이미지 보존, DB 저장 없음. pytest251 passed84.96s, src ruff/mypy47/typecheck 통과. 기존 테스트 lint71건은 별개 미해결. 모바일 이번 변경 미검증.
ASA152 검증 추가: frontend production build 및 git diff --check 통과.

ASA153 IN PROGRESS: 브랜드 이미지/전체 변경 취소를 18px 되돌리기 아이콘·44px 클릭 영역으로 변경, hover/focus 설명과 접근성 이름 유지.

ASA153: 아이콘 취소 UI 적용. 실제 다크 데스크톱 전체 취소 44px 클릭영역/18px SVG/텍스트 없음 확인. 사용자 데이터 변경 없음. 이미지 취소는 같은 컴포넌트 사용, 모바일 및 hover/focus 직접 조작 이번 변경 미검증. typecheck/build/src ruff/mypy47/diff-check 통과. 전체 pytest 진행 중.
ASA153 DONE: 전체 pytest251 passed86.04s. 기존 테스트 파일 lint71건은 이전 기록대로 별개 미해결.

ASA154 IN PROGRESS: 저장된 작업 공간 로고를 favicon에 반영. 기본 A 아이콘 및 로그아웃/미설정 fallback, 저장 이벤트로 갱신. 미저장 선택은 적용하지 않음.

ASA154 DONE: 저장된 logo PNG를 favicon 링크로 적용, 변경 이벤트 재조회 후 갱신 및 unmount 정리. 기본 SVG A 아이콘 제공. 실제 새 브라우저 화면에서 favicon href와 sidebar logo src 동일 확인. DB 변경/로고 저장 없음. pytest251 passed83.72s, src ruff/mypy47/typecheck/build/diff-check 통과. 기존 테스트 lint71건 별개. 저장/로그아웃 조작 이번 검증 미실행.

ASA155 IN PROGRESS: favicon 기본 SVG/사용자 PNG 중복 등록으로 기본 A가 선택되는 문제. metadata 별도 icon 제거하고 head 단일 asa-favicon 링크를 갱신/복원하도록 수정.

ASA156 IN PROGRESS: ASA148~155 변경 범위 검토 후 커밋/푸시. 현재 사용자 탭 favicon 단일 PNG 링크와 메뉴 로고 일치, 로딩 완료 및 console error/warn 없음 확인. 사용자 자료/로컬캐시 제외.

ASA155 DONE: Next head 재조정 시 기본 아이콘 재삽입까지 처리하도록 MutationObserver로 icon href/type을 저장된 로고로 동기화. 값이 다를 때만 변경하고 cleanup 시 observer 해제/기본값 복원. 사용자 화면 및 브랜드 설정 DOM에서 모든 icon 링크가 메뉴 PNG와 동일 확인. 실제 탭 표시 사용자 확인. 로그인 화면 fallback 재검증은 브라우저 CDP timeout으로 미완료.
ASA156 검증 완료: pytest251 passed87.54s, frontend typecheck/build, backend src ruff 및 mypy47, diff-check 통과. 전체 backend ruff 기존 테스트71건 잔존 재확인. 사용자 데이터 저장/변경 없음. ASA148~155 코드/테스트/문서19파일만 포함, .env/.local/.next/.venv 제외 확인. 삭제0건. 커밋/푸시 진행.

ASA157 DONE: 사용자별 자동화 카테고리 CRUD·검색·필터·카드 DnD/메뉴 구현. workspace+user 분리, 변경 즉시 저장·충돌 검증. pytest253·src ruff·mypy48·typecheck/build 통과. 브라우저 검색/미분류 필터/메뉴/Escape/실행·예약·기록 진입 확인. 실제 포인터 DnD 및 모바일 실기기 미검증. [기록](docs/worklogs/2026-11-02-automation-categories.md)

ASA158 DONE: 자동화 분류 기본 꺼짐, 카테고리로 정리 공통 스위치 및 사용자별 enabled 저장. 끄면 검색/평면 카드만 표시, 분류 보존. 브라우저 켜기→새로고침 유지→끄기(카드9/필터0/메뉴0) 확인. pytest253·src ruff·mypy48·typecheck/build·diff-check 통과. 모바일 미검증.

ASA159 검증 완료: ASA157~158 다크/모바일 검증 및 커밋·푸시. CSS viewport400/320px에서 검색·필터·스위치·메뉴/Escape 동작과 경계 확인, 설정 원복. 캡처 API timeout으로 새 시각 증거 확보 불가.

ASA159 최종 검증: pytest253 passed101.46s, src ruff/mypy48/frontend typecheck/build 통과. 13개 코드·테스트·문서만 커밋, 사용자 자료/생성 자산/비밀값/캐시 제외. 삭제0건. 모바일 DOM 검증 완료·캡처 검증 미완료 명시 후 커밋/푸시.

ASA-168 DONE: 이전 답변 가져오기를 입력 항목별 opt-in 설정으로 관리. 저장한 스키마로 실행 화면 표시를 결정하며 자동화 연결은 유지.
ASA-169 DONE: 입력별 출처 에이전트 선택·이전 작업 필터 연결, 씬 이미지 대본/씬 출처 저장 및 작업 공간 공통 스타일 확인.

ASA170 IN PROGRESS: 개별 에이전트 실행 화면 공통 제목/포커스/안내/입력 카드 폭·간격 정리. 씬 전용 분기 없이 적용, 실제 화면 확인.

ASA170 DONE: 공통 AgentRunPreview 제목 32px/아이콘40px, 비대화형 제목 자동포커스 테두리 제거(접근성 포커스 유지), 실행 전 답변생성 배지 제거·안내 간결화. 제목/안내/입력카드 폭 일치, 입력wrapper의 중복 margin 제거 및24px gap. 실제 다크 화면 씬/쉬운작가 폭1136px 동일, 모바일 viewport390(CSS487) 가로넘침 없음 확인. 장면 이전작업 출처 필터 유지 확인. 밝은 테마 전환 캡처는 전환 중 색상으로 완전한 시각 검증 제외. pytest278 passed99.60s, src ruff/mypy51/typecheck/build/diff check 통과. 초기 샌드박스 DB/빌드 권한 제한은 승인 실행으로 재검증. 유료 AI 호출/사용자데이터 변경/커밋 없음.

ASA171 IN PROGRESS: 이전 작업 가져오기 목록을 에이전트 이름 대신 작업 제목·요청 요약 중심으로 표시. 지정 출처 필터 유지, 저장된 답변/요청으로 제목 도출 및 검색 반영.

ASA171 DONE: 이전 작업 목록/선택 미리보기/가져온 출처 문구를 작업 제목으로 변경, 요청 요약240자·두 줄/날짜/답변버전 및 보조 에이전트 출처 표시. 저장 답변 title/기존title/Markdown제목/요청 순으로 도출, 새 AI 호출 없음. 검색에 답변내용 포함, workspace 및 source agent 필터 유지. 실제 다크 화면 하나와 똑똑뿡 도서관의 비밀 작업 표시·선택·3874자 원문 가져오기 확인. API만 재시작, 워커 유지. pytest280 passed107.55s, src ruff 및 신규단위테스트 ruff/mypy51/typecheck/build/diff check 통과. 이번 작업 모바일 재검증 미실행. DB자료 변경·유료호출·커밋 없음.

ASA172 IN PROGRESS: 이전 작업 가져오기 버튼을 입력 제목 옆18px 아이콘/44px 조작영역으로 이동, hover/focus 설명 및 가져온 출처 유지.

ASA172 DONE: 이전 작업 가져오기를 입력 제목 옆18px 아이콘(44px 클릭영역)으로 이동. hover/focus 설명·접근성 이름 유지, 입력 아래 큰 버튼 제거 및 작업제목/답변버전 출처 유지. 실제 다크 화면 제목 정렬/크기·모달 선택·3874자 원문 가져오기 확인. pytest280 passed105.03s, ruff/mypy51/typecheck/build/diff check 통과. pytest 종료 시 pool 연결timeout 로그1건 출력됐으나 실패 없음. 모바일 재검증/유료 AI 호출/DB변경/커밋 없음.

ASA173 IN PROGRESS: ASA160~172 변경을 밝은 테마/모바일에서 확인하고 코드·테스트·문서만 선별하여 커밋/푸시. 사용자 자료 및 캐시 보존.

ASA173 검증 완료: ASA160~172 코드·테스트·템플릿·문서55파일 커밋 대상 확인. 밝은 데스크톱 화면 캡처로 제목/아이콘 정렬 확인(.local/import-light.png). 모바일 viewport390 설정에서 CSS width469=scrollWidth469, 아이콘44px·제목gap8px, Enter로 모달열기/작업선택/3874자 가져오기 및 출처 표시 확인. 모바일 캡처 CDP timeout으로 시각 검증 미완료. viewport reset 호출 후에도 모바일 화면이 남았고 이후 브라우저 응답 timeout으로 테마 원복 확인 불가(밝은 테마로 남을 수 있음). pytest280 passed102.09s, src ruff/mypy51/typecheck/build/diff-check 통과. 비밀패턴 검사0건. .env/.local/.next/.venv 및 사용자자료 제외·삭제0건. 유료 AI 호출 없음. main에 커밋/푸시 진행.

ASA174 ANALYSIS DONE: 사용자 요청으로 지연/간격/씬 결과 읽기 전용 분석. 최근 씬 요청 b4d7d490-80dc-4cd9-977d-ecbb2b4c7816 접수16:56:40.364 시작16:56:40.689 완료16:58:05.904, 큐대기0.325초 실행85.215초. 저장 지침은 실제 생성 역할을 요구하나 tools=[]이고 현재 개별 실행은 구조화 텍스트 모델 경로. shots12개 모두 ready=false, 생성도구 미제공 및 엄마/도서관선생님/뿡이 기준누락을 결과가 명시. 씬 전용 생성/검수/결과 UI 연결 없음. 이해/방향은 같은 모델 스트림 필드가 도착해야 렌더링, 서버250ms throttle이며 최초필드 도착시각은 보존하지 않아20~30초 지연 구간 확정 불가. answer-management 하단margin0 및 인접 answer-approval 외부gap 없음 확인. 코드/사용자지침/DB 변경 및 유료호출 없음. 분석 작업이라 전체 테스트 재실행 없음.

ASA175 IN PROGRESS: 씬 결과를 공통 이미지 큐에 연결. 씬별 자료 검증/개별·일괄 생성/검수/수정/확정 및 즉시 접수 안내·답변 관리 간격 수정. 사용자 지침과 원문 보존.


ASA175 DONE: ScenePlan 어댑터 및 공통 이미지 큐 연결. 씬 카드/개별·최대12개 일괄 생성/대기 취소/검수/수정/확정, 원문·실제 캐릭터 참조 이미지 스냅샷 전달, 부족 자료 차단. 최근 작업 scene_images 진행 반영, 씬 결과는 캐릭터 보관함/전달 대상에서 분리. AI 이해 필드 도착 전 즉시 접수 안내 및 답변관리→확정 영역24px 간격 추가. 사용자 지침·대본·장면 원문 보존, runtime 시스템 안내만 추가.
검증: pytest283 passed101.80s, src ruff/mypy52/typecheck/build/diff-check 통과. 신규 실제DB+모의API 검사로 이미지 생성·수정 base+캐릭터 bytes/일괄·중복·취소·확정·격리·토큰비용·씬 검수 참조/원문 전달 확인. 검수 테스트 확장 중 캐릭터 전용 고정 기대값2곳을 씬에도 맞게 수정한 후 전체 재통과.
실제 화면: 기존 사용자 씬 결과12개 카드·개별 전환·일괄 생성 영역·부족자료 생성 차단 확인. 답변관리 간격 DOM23.99px/계산24px 및 밝은 화면 캡처(.local/scene-answer-spacing.jpg). 다크 전환 확인. 모바일390 override의 CSS width469=scrollWidth469 및 씬 전환 확인, 모바일 스크린샷은 CDP timeout으로 시각검증 미완료. viewport reset/밝은 테마 원복 호출 완료.
로컬 migration 적용, API/스크립트·이미지 워커 갱신. 사용자 요청의 엄마/도서관선생님/뿡이 기준자료 부족 및 기존 ready=false 때문에 실제 유료 생성은 미실행. 데이터 보완 후 재분석 필요. 목표9:16은 공급자 원본1024x1536로 생성되므로 후속 영상 비율조정 필요를 UI/문서에 명시. 사용자자료 삭제·지침변경·커밋/푸시 없음.

ASA176 ANALYSIS DONE: 사용자 지적의 이미지7개 누락 여부 읽기 전용 확인. 요청 b4d7d490 input에 이하나/구름할머니/뭉실이/생일친구/원숭이/돼지/무 7개 저장 확인, image_content 검증 결과 image_url7개. 선택 대본·씬은 '하나와 똑똑뿡 도서관의 비밀'로 엄마/도서관선생님/뿡이 등장. 첨부누락이 아니라 선택한 이야기와 캐릭터 세트 불일치이며, 기존AI ready=false 의견을 그대로 안내한 UI라 오해 유발. 과거 공급자 수신 로그 직접확인 없음. 사용자자료/코드/지침 변경 및 유료호출 없음. 분석만 수행하여 테스트 재실행 없음.

ASA-177 ANALYSIS DONE: 이전 작업 가져오기에 웃음 도둑 원본이 누락된 원인 확인.
- 자동화 실행 42cab624-714c-4733-bf71-5015208aa34c의 writer/scenes 출력에 '이하나와 웃음 도둑의 발자국' 원문이 보존되어 있음을 DB 읽기로 확인.
- 캐릭터 테스트 스크립트와 당시 작업 기록은 해당 자동화 단계 출력을 캐릭터 요청 c408792f-432e-4485-ba40-11b8ecd991ba에 전달했음을 확인.
- 현재 이전 답변 가져오기는 customer_requests/script_versions의 개별 실행 답변만 조회하고 자동화 단계 출력은 포함하지 않아 해당 원본이 노출되지 않음. 개별 대본·장면 답변은 다른 작품('하나와 똑똑뿡 도서관의 비밀').
- 원본 삭제 또는 캐릭터 추출 누락으로 단정하지 않음. 원인 조사만 수행; 제품 코드·업무 데이터 변경 및 유료 호출 없음.

ASA178 IN PROGRESS: 이전 작업 가져오기에 자동화 완료 단계 답변 통합. 실행 스냅샷의 에이전트 ID 필터·workspace 격리·원문 보존·출처 표시 및 실제 대본/장면 가져오기 검증.

ASA178 DONE: 이전 작업 가져오기에 자동화 성공 에이전트 단계 답변 추가. 실행 당시 manifest의 agent_id 필터, workspace 격리, 실패·도구·시작/종료 단계 제외. 실행ID+단계인덱스로 상세 선택 및 원문 가져오기, 자동화 이름/단계 출처 표시. 기존 개별 답변 버전 조회 유지.
- 실제 Chrome 밝은 화면에서 '이하나와 웃음 도둑의 발자국' 대본2581자/장면4206자 각각 검색·선택·입력 반영 및 미리보기와 입력값 완전일치 확인. 해당 에이전트만 표시 확인. 원본/사용자지침/이미지 변경 및 유료 실행 없음. 현재 입력 폼에는 두 원문을 가져온 상태를 유지(실행하지 않음).
- 밝은 데스크톱/다크 좁은 화면 시각 확인, 카드gap8px/색상토큰/가로넘침없음 확인. 390 viewport override의 실제 CSS width487/scrollWidth469. 모바일 선택·가져오기 후 viewport reset/밝은 테마 원복. 증거 .local/automation-answer-picker.jpg, .local/automation-answer-mobile-dark.jpg (Git 제외).
- 테스트 먼저 실패 확인 후 구현. backend284 passed104.00s, ruff/mypy52, frontend typecheck/build, diff-check 통과. ASA API만 재시작; 큐/워커 미변경. 커밋/푸시 없음.

ASA179 IN PROGRESS: 씬 분석 실패와 미완성 일반 텍스트 노출 조사. 최신 요청28147cb3에서14개 shots 후 checks 문장 중단·summary 누락, 사용량unknown/공통오류 확인. 출력 예산 및 종료 원인 기록 보강, 씬 준비 UI와 실제 재실행 검증.

ASA179 DONE: 씬 분석용 출력 예산24576(일반 대본8192 유지), 안전한 실패 코드(시간초과/출력한도/출력검증/호출실패) 기록. 생성 중·실패한 씬 답변은 일반 텍스트 나열 대신 장면 준비 카드로 표시하며, 미완성은 생성 버튼을 제공하지 않음. 기존 저장 지침·원문 변경 없음.
- 실제 요청28147cb3 재분석 성공:14개 씬 저장, 입력24324/출력7966토큰, 예상$0.064154. 기존 실패는14개 shots 이후 checks 중단·summary 누락 확인; 당시 상세 예외 미기록으로 정확한 원인은 단정하지 않음.
- 실제 Chrome에서14개 씬 선택·개별 생성·여러 씬 생성 진입점 확인. 서버검증상9개 생성 가능/5개 자료·설정 확인 필요(AI 요약의11개와 별개). 자료부족 차단을 우회하지 않음.
- 첫 씬 '비 오는 날의 그림책방' 실제 생성 성공:21.62초, 참조 이하나 이미지1개, 입력11223(이미지1024포함)/출력343토큰, 예상$0.069477. ai_usage_events 성공 기록 및 화면 결과/검토필요1·미생성13 동기화 확인. 사용자 확정·추가13개 유료생성·AI검수·수정 재호출은 미실행. 화면 증거 .local/scene-ready-179.jpg.
- 전체pytest286passed98.05s, ruff/mypy52/typecheck/build/diff-check 통과. 기존 일반오류 test_request_timeout 기대값을 새 안전한 코드로 갱신 후 전체재통과. 스크립트 워커만 유휴 상태 확인 후 재시작. 커밋/푸시 없음.

ASA180 IN PROGRESS: 씬 이미지와 대본 대응 구간·생성 당시 장면 구성을 함께 표시. 버전별 스냅샷 사용, 미생성은 현재 설정 표시, 원문/이미지 변경 없이 UI 검증.

ASA180 DONE: 씬 이미지 옆 수정 영역 밖에 '이 이미지에 담은 장면' 추가. 대본 대응 구간·장면 구도/배경/행동·해당 버전 수정요청 표시. 생성된 이미지는 shown.character 스냅샷, 미생성은 draft로 현재설정 표시. 원본대본 전체가 아니라 해당 대응구간임을 라벨로 구분. 공통토큰 padding24/gap16, 좁은화면 padding16 및 긴본문 내부스크롤 적용.
- 실제 밝은/다크 데스크톱 확인, 첫씬 이미지와 대응 문장/구성 나란히 표시, 다음 미생성씬 전환시 현재설정 표시 확인. 390 viewport override 실제CSS469/scroll469로 넘침없음 확인; 모바일스크린샷은 캡처 영역 이상으로 시각검증 미완료. 원래씬·밝은테마·viewport 복원. 증거 .local/scene-context-light.jpg. 유료호출/데이터저장 없음.
- pytest286passed108.80s, ruff/mypy52/typecheck/build/diff-check 통과. 최초 build는 .next mkdir EPERM으로 중단, 권한 재실행으로 정상통과. 다중 이미지버전 전환은 테스트대상에1개버전만 있어 실제다중전환 미검증. 커밋/푸시 없음.

ASA181 IN PROGRESS: 씬 원본 대본·장면을 AI 이미지 구성과 분리하고 씬별 참조 캐릭터 이름·이미지 표시. 원문 정확 일치 검증 및 미매칭 시 전체 원문 제공, 원본/지침/생성자산 변경 없음.

ASA181 DONE: 씬 카드에 원본 대본 대응 구간/원본 장면 구성과 AI 이미지 구성을 분리. 원본 장면의 시작·끝 인용이 대본에 유일하게 존재하면 사이 원문 그대로 표시, 아니면 정확 일치 excerpt 또는 전체 원문 fallback. 장면 번호가 불명확하면 전체 원문과 사유 표시. 씬 character_ids에 연결된 캐릭터 이름·기준 이미지 표시, 누락참조는 명시. 원본/지침/이미지/AI생성 경로 변경 없음.
- Chrome 밝은/다크에서 첫 씬(이하나1명), 두 번째 씬(5명) 원문 펼침·전환·이미지 로딩 확인. 5개 이미지 모두 loaded, 카드 scrollWidth=clientWidth484. 원본의 순차연출과 AI의 합친구도를 구분해서 표시. 증거 .local/scene-source-cast-181.jpg. 모바일 별도검증/유료호출/이미지확정 미실행.
- 최종 pytest288passed99.13s, src ruff/mypy52, frontend typecheck 통과. 전체 backend 디렉터리 lint 시 기존 테스트파일 포함92건 확인(이번 범위 밖); 소스 lint 통과. sandbox DB권한으로 실패한 테스트 실행은 중단 후 권한 재실행으로 전체통과. API만 재시작. 커밋/푸시 없음.
- 최종 frontend build14routes 통과. sandbox .next mkdir EPERM 발생 후 권한 재실행 통과. git diff --check 통과.

ASA182 IN PROGRESS: 씬 연결 캐릭터 영역을 기본 접힘 토글로 변경. 이름/인원수 제목 유지, 펼침·접힘과 키보드 및 테마 확인.

ASA182 DONE: 씬 연결 캐릭터 영역을 기본 접힘 details/summary로 변경. 제목에 인원수를 유지하고 펼치면 기존 이름·기준이미지를 표시. 밝은/다크 실제 Chrome에서 5명 펼침 및 Enter 접기 확인, 가로 넘침 없음(483px). 스크린샷 .local/scene-cast-toggle-182.jpg. 모바일 별도 확인 미실행. pytest 288passed102.77s, src ruff/mypy52 통과, frontend typecheck/build14routes 및 diff check 통과. 유료 호출/데이터 변경/커밋 없음.

ASA183 IN PROGRESS: AI 씬 준비 판단을 참고 의견으로 분리. AI ready=false만으로 차단하지 않고 실제 참조 누락·불일치 검증 유지.

ASA183 DONE: AI ready=false와 review_notes는 생성 차단에서 제외. 실제 캐릭터 누락/참조ID 불일치와 실행 시 확정·권한 검증은 유지. 기존 저장 결과도 AI 참고 의견/AI 분석 요약으로 표시하고 최종 판단은 사용자임을 안내. API 재시작 후 Chrome 꼬마 유령의 정체 미생성, 생성버튼 enabled=true 확인. 유료 생성 미실행. pytest289passed108.93s, src ruff/mypy52 통과; frontend typecheck/build 통과. 모바일 별도 미검증. 증거 .local/scene-advice-183.jpg. 원문·이미지·사용자 지침 변경 및 커밋 없음.

ASA184 IN PROGRESS: 개별 이미지 생성·수정 접수 후 해당 작업 진행 영역으로 한 번 스크롤/포커스. SSE 갱신 시 반복이동 방지, reduced-motion 준수.

ASA184 DONE: 개별 씬/캐릭터 생성 및 수정 요청 접수 후 요청 ID가 jobs에 반영되면 진행 영역으로 한 번만 스크롤 및 포커스. 오류 시 이동하지 않고 SSE 반복이동 방지; 숨겨진 카드 포커스 방지와 reduced-motion 준수. pytest289passed99.23s, src ruff/mypy52, frontend typecheck/build14routes 통과. 유료 요청을 통한 실제 스크롤 E2E는 미실행. 커밋 없음.

ASA185 IN PROGRESS: 씬 등장인물/비등장 참고이미지 역할 분리 및 선택 범위 검증, 생성 입력 합집합 전달 회귀 검증.

ASA185 DONE: 등장인물과 비등장 참고이미지 분리. 사용자 입력의 전체 선택 이미지 범위에서 참조 검증; 생성 snapshot에는 등장인물 기준+명시 참조 이미지 합집합과 cast/reference_only 역할 전달. 참고용 인물 자동등장 금지/소품 소유자 변경은 충돌 아님을 이미지 실행 지침에 명시. 사용자 지침/대본/씬 원문 변경 없음. 회귀: 비등장참조 허용·실제 snapshot 포함·역할 분리·선택외 ID 거절·원문 불변. pytest290passed109.99s (종료 후 pool timeout 로그1건), src ruff 수정 후 통과/mypy52, frontend typecheck/build 통과. 이미지 큐0건 확인 후 API/이미지워커 재시작. Chrome 치즈 같은 모자 차단0/생성 enabled 확인. 유료호출 미실행. 증거 .local/scene-reference-185.jpg.

ASA186 IN PROGRESS: 씬 분석 시스템 지침과 저장된 씬 이미지 에이전트 지침의 AI 판단 차단 문구 정합성 수정. 참고용 이미지/등장인물 구분, 사용자 최종 판단, 실제 자료 검증 유지.

ASA186 DONE: 씬 분석 시스템 지침에서 설정·외형 충돌에 따른 차단 지시 제거. AI 의견은 참고/사용자 최종 판단, 등장인물과 비등장 참고 이미지 구분, 원문의 소품 이동 유지 명시. 저장된 씬 이미지 에이전트 지침의 충돌 ready=false 문구와 실행 전 조건/상태 설명 및 output_schema 설명을 save_settings(revision 검증)로 갱신. revision8/latest 지침 일치·다른 설정 보존 확인; 원문/기존 실행 스냅샷/생성 이미지 불변. 저장 과정 trim 정규화로 최초 동등비교 실패 후 정규화 기준 검증 통과. 백업 .local/scene-agent-before-186.json (Git 제외). 큐 대기/실행0 확인 후 대본 워커 재시작 및 프로세스 확인. pytest290passed104.39s, ruff src/mypy52/typecheck/build14routes/diff-check 통과. 실제 유료 AI 재분석은 수행하지 않았으며 기존 표시 의견을 소급 변경하지 않음. 커밋/푸시 없음.

ASA187 DONE: 씬 작업의 여러 이미지 확정 패널 추가. 검토 필요 이미지 미리보기·버전·검수 의견을 확인하고 사용자가 선택한 이미지 버전만 기존 확정 API로 처리. 실행 중/제외/확정 항목 제외, 중복 클릭 방지, 부분 성공·실패 안내, 버전 변경 충돌 검증 재사용. 실제 Chrome 밝은/다크 화면에서 14개 후보 표시와 선택·해제/버튼 개수·활성 상태 확인. 사용자 이미지 확정 및 유료 AI 호출은 실행하지 않음. 검증: pytest 290 passed, ruff, mypy 52 files, frontend typecheck/build 14 routes, diff --check 통과. 모바일 실기기 및 실제 일괄 확정 클릭은 미검증. 화면 기록: .local/batch-approval-preview.png (커밋 제외).

ASA188 IN PROGRESS: 생성/확정 통합 도구 영역, 한 번에 한 패널 표시, 카드 클릭/키보드 선택과 선택 테두리·배경·체크 표시.
ASA188 DONE: 생성/확정 버튼을 하나의 가로 도구 영역으로 통합하고 한 패널씩 표시. 생성/확정 모두 체크박스 대신 aria-pressed 카드 버튼 사용, 선택 테두리·배경·체크 표시와 hover/focus 적용. 검수 의견은 선택 버튼 밖에서 별도 펼침. 실제 Chrome 밝은/다크에서 클릭 선택·Space 해제·확정 버튼 비활성·패널 전환 확인. 사용자 이미지 확정/유료 생성 미실행. pytest290passed112.10s (종료 후 pool-88 연결 timeout 로그1건), ruff/mypy52/typecheck/build14routes/diff-check 통과. 모바일 실기기 미검증. 증거 .local/batch-selection-188.png.

ASA189 IN PROGRESS: 씬 이미지 관리 제목·구분선·생성/확정 아이콘, 선택 생성/선택 확정 명칭, 검수 없는 카드 반복 문구 제거.
ASA189 DONE: 씬 이미지 관리 제목·구분선으로 도구 범위 구분. 공통 GraphIcon 이미지/확정 아이콘 추가 및 18px 버튼 아이콘 적용. 선택 생성/선택 확정과 생성 가능/검토 필요 개수 표시. 검수 없는 카드 반복 안내 제거, 검수 결과가 있을 때만 AI 검수 의견 보기 제공. Chrome 실제 제목·아이콘·간격 및 선택/해제·패널 토글·제거 문구0건 확인. 사용자 이미지 상태 변경/유료호출 없음. pytest290passed110.54s, ruff, mypy52, frontend typecheck/build14routes, diff-check 통과. 증거 .local/scene-tools-189.png. 모바일 실기기 미검증.

ASA190 IN PROGRESS: 씬 이미지 관리 내부에 공통 씬 카드 목록 통합. 상세/생성/확정 선택 모드와 이미지 버전 미리보기, 기존 API 및 확정 충돌 보호 유지.

ASA190 DONE: 씬 이미지 관리 안에 씬 목록 통합. 일반 모드는 상세 선택, 생성/확정 모드는 동일 공통 카드에서 다중 선택. 확정 모드는 이미지/버전/검수의견 표시, 비대상 비활성화, 생성12개 한도 및 기존 확정 snapshot 충돌검증 유지. 실제 Chrome 밝은/다크 확인, 카드 선택/Space 해제/확정버튼 개수/모드전환/상세이동 확인. 중복 목록1개만 존재. 증거 .local/scene-manager-190.png. 유료생성/사용자이미지 확정/모바일 별도검증 미실행. pytest290passed111.18s(종료 후 pool timeout로그1건), ruff src/mypy52 및 frontend typecheck/build 통과. 커밋/푸시 없음.

ASA191 IN PROGRESS: 씬 관리 버튼 우측 묶음, 상태 개수 별도 요약 및 생성 대상 없음 안내.

ASA191 DONE: 선택 생성/확정 버튼을 제목 우측에 묶고 상태 요약(미생성·생성중·검토필요·확정, 필요 시 대기/실패/확인필요/제외)을 아래 분리. 검토필요는 경고 색 강조. 생성 대상0이면 비활성 및 모든 생성완료/자료확인 사유 tooltip·접근성 설명 제공; 열린 패널은 대상0이 되어도 닫기 가능. 생성모드에서만 생성가능 개수 표시. Chrome 밝은/다크 및 모드토글/생성비활성/안내 확인. 증거 .local/scene-tools-191.png. 모바일 별도 미검증. pytest290passed107.39s, ruff src/mypy52/typecheck/build14routes/diff-check 통과. 유료요청·사용자이미지확정·커밋/푸시 없음.

ASA192 IN PROGRESS: 이미지 작업 관리 UI 공통화. 캐릭터/씬 공통 제목·상태·선택 생성/확정·카드 선택, 향후 이미지 작업 공통 계약 문서화.

ASA193 IN PROGRESS: 이미지 확정 검토 카드 최대3열 및 가용 폭 기반2/1열, 미리보기240~400px 확대. 공통 이미지 관리에 적용.

- ASA193 DONE: 이미지 확정 검토 그리드 최대 3열, 가용 폭에 따라 2/1열, 미리보기 240~400px 및 원본 비율 유지. 캐릭터/씬 공통 ImageTaskManager 적용. 실제 밝은 화면 3열·400px 및 카드 선택/해제 확인, 선택 상태 복원. pytest 290 passed, ruff/mypy(52 files), typecheck/build, diff-check 통과. 모바일·다크 실제 화면은 이번 작업에서 미검증. 스크린샷: .local/image-review-grid-193.png (커밋 제외).
- ASA192 검증 보완: 공통 이미지 관리 UI 적용 후 전체 pytest 290개 통과 확인. ASA193에서 씬 검토 화면의 공통 컴포넌트 렌더링·선택 동작 확인.
`nASA194 IN PROGRESS: 이미지 작업의 중복 답변 확정 제거. 이미지 확정만 완료 기준으로 집계하며 일반 답변 검토는 유지.
`nASA194 DONE: 캐릭터/씬 이미지 답변의 중복 사용자 확인 버튼 제거. 후속 이미지가 있으면 answer 승인 그룹 제외, 필요한 이미지의 확정만 완료 조건으로 사용. 일반 텍스트/다른 후속 작업 승인 유지. 기존 설정·답변 승인·이미지 기록 불변. 에이전트 설정 도움말 및 아키텍처 설명 갱신. 실패 회귀 먼저 확인 후 pytest291passed117.38s, ruff/mypy52/typecheck/build14routes/diff-check 통과. 로컬 API만 재시작, 워커 유지. 브라우저 CDP 응답 지연으로 실제 화면/테마/모바일 미검증. 커밋·푸시 없음.

ASA195 IN PROGRESS: 범용 비디오 프롬프트 에이전트 지침·입력 구성 및 로컬 등록. 기존 사용자 에이전트 보존. 텍스트 계획과 실제 확정 씬 이미지 첨부를 명확히 구분하며 영상 API 호출은 범위 밖.

ASA195 DONE (초기 텍스트 구성): 비디오 프롬프트 에이전트 로컬 등록(4184e76d-bd71-4ccd-97ef-3c56b4aea1dd). 대본 작가·장면 구성·씬 이미지 에이전트를 입력별 이전 답변 출처로 연결, 각각 2개 작업 조회 확인. 기존 에이전트7개 불변 검증. 범용 씬별 움직임/카메라/연속성/원문 보존/AI 제안 구분/사용자 확정 지침 및 JSON 템플릿·범위 문서 추가. 실제 확정 씬 이미지 파일 전달과 영상 API는 미연결이며 입력 설명과 지침에 명시. 유료 호출/실제 생성 품질/브라우저 UI 미검증. pytest291passed106.32s, ruff src/mypy52/typecheck/build14routes/diff-check 통과. 커밋/푸시 없음.

ASA196 IN PROGRESS: 첨부 지침20713자 대비 UI/API12000자 제한 확인. 에이전트 지침65536자 확대, 자동 잘림 제거 및 글자수/초과 안내. 저장된 사용자 지침은 변경하지 않음.

ASA196 DONE: 에이전트 지침 API65536자, UI maxLength 제거로 붙여넣기 원문 보존·Unicode 글자수/초과 안내·저장 차단. 전체 설정64KiB 제한에서 지침을 분리하고 기타 설정 용량 보호 유지. 경계/한글·이모지 JSON 왕복/기타설정 제한 회귀3개 통과. 첨부파일 줄바꿈 정규화19416자 전체 내용 검증·직렬화 보존 확인, DB 지침 자동교체 없음. 실행 API OpenAPI maxLength65536 확인. pytest292passed105.11s(종료 pool-88 timeout로그), ruff/mypy52/typecheck/build14routes/diff-check 통과. 브라우저 붙여넣기 실동작 및 유료AI 호출 미검증. 사용자 원문 재붙여넣기 필요. 커밋/푸시 없음.

ASA197 DONE: 긴 에이전트 지침에 공통 ExpandableTextarea 집중 편집창 적용. 확대창·모바일 전체 화면 CSS·원본 실시간 동기화·닫기 시 보존·글자 수·별도 저장 안내. 실제 밝은 테마 기존 편집 화면에서 열기/배치/닫기 확인(사용자 입력 변경 및 DB 저장 없음). 모바일 실기·다크 테마는 이번에 미검증. backend pytest 292 passed(107.33s), src ruff/mypy, frontend typecheck/build, diff-check 통과.

ASA198 DONE: 지침 제목·AI 도움말·크게 편집을 공통 Field 제목 행에 배치. 별도 버튼 행 제거, 작은 화면 줄바꿈 유지. 실제 밝은 화면 DOM에서 중앙 정렬 및 확대/닫기 확인, 사용자 입력·DB 변경 없음. pytest292passed111.03s(샌드박스 DB 연결 불가 실행 중단 후 로컬 접근 재실행), src ruff/mypy52, frontend typecheck/build 통과. 모바일 실화면은 이번 미검증.

ASA199 DONE: 지침 제목·도움말 왼쪽, 크게 편집 버튼 오른쪽 끝 정렬. 실제 DOM에서 버튼 우측=행 우측 및 제목과 수직 중앙 일치 확인. pytest292passed111.41s, ruff/mypy52/typecheck/build 통과(초기 빌드 EPERM 후 권한 재실행 통과). 사용자 지침·DB 변경 없음.

ASA200 DONE (커밋 준비): 누적 씬 이미지 생성·검수·선택 확정 및 공통 관리 UI, 이전 작업 연결, 비디오 프롬프트 초기 템플릿, 긴 지침 확대 편집 개선을 커밋 대상으로 정리. 코드·테스트·문서 46개 파일만 포함하며 사용자 자료·생성 이미지·로컬 DB·캐시는 보존/제외. 직전 동일 코드 검증: pytest 292 passed, ruff/mypy 52 files, frontend typecheck/build 통과. diff-check 및 비밀값 패턴 점검 통과. 모바일 실화면 미검증 항목은 기존 기록 유지.

ASA201 IN PROGRESS: 비디오 프롬프트에 확정 씬 이미지 선택·실제 첨부 및 장면/캐릭터 설정 스냅샷 연결. 영상 생성은 실행하지 않으며 기존 사용자 지침과 원문 보존.

ASA201 DONE: 비디오 프롬프트의 텍스트 전용 씬 계획 입력을 확정 씬 이미지 선택으로 교체. 실제 이미지 파일·장면 ID·생성 당시 최종 설정/캐릭터 설정 스냅샷을 함께 전달하고 workspace/확정 버전/변조 여부를 서버에서 재검증. 로컬 에이전트 기존 지침 19,416자 보존 후 참조 규칙 추가, 이전 답변 출처 유지. 실제 확정 이미지14장 첨부 및 입력 검증, 밝은 테마 브라우저에서 이미지2장 선택과 썸네일·장면번호·설정 수 표시 확인. pytest295passed115.18s, ruff/mypy53, typecheck/build14routes 통과. 유료 AI 호출·비디오 생성·모바일 실화면은 미검증. 커밋/푸시 없음.

ASA202 IN PROGRESS: 실행 입력을 필수 항목 지정 순서 우선으로 표시. 비디오 프롬프트 대본→장면 구성→확정 씬 이미지→선택 연출 요청 순서로 정리. 지침과 저장 데이터 불변.

ASA202 DONE: 공통 실행·미리보기 입력 순서를 required 배열 순서→선택 항목으로 변경하여 JSONB 키 정렬 영향 제거. 비디오 프롬프트 대본→장면 구성→확정 씬 이미지→추가 연출 요청 순서를 실제 다크 화면에서 확인. DB·지침·사용자 입력 불변. pytest295passed113.89s(종료 pool-88 timeout 로그), frontend typecheck/build 통과. 커밋/푸시 없음.

ASA203 IN PROGRESS: 확정 씬 이미지 선택창에 현재 목록 모두 선택/전체 선택 해제 추가. 검색·필터·현재 페이지 범위 명시, 기존 선택 유지, 32장 초과 일괄 선택 차단.

ASA203 DONE: 확정 씬 이미지 가져오기에 현재 목록 모두 선택/전체 선택 해제 추가. 검색·필터 및 페이지 선택 범위 안내, 기존 선택 합집합 유지, 32장 초과 일괄 선택 차단. 실제 다크 화면에서 14장 일괄 선택→0장 해제와 선택 테두리/버튼 간격 확인. pytest295passed114.39s, ruff/mypy53, frontend typecheck/build14routes 통과. 유료 AI 호출 없음. 모바일·32장 초과 실데이터 UI 검증은 미실시. 커밋/푸시 없음.

ASA204 IN PROGRESS: 영상 분석가 에이전트. 파일/공개 YouTube·Reels 링크 접수, 워커 프레임 추출, 실제 이미지 기반 분석 및 비디오 프롬프트 이전 답변 연결. 음향 미분석·프레임 표본 한계를 명시. 기존 지침/자료 보존.

ASA204 DONE: 영상 분석가 등록 및 비디오 프롬프트의 선택 입력 ‘참고 영상 스타일’에 출처 에이전트 연결. 기존 지침 보존 후 참고 적용 규칙 추가. 파일/공개 링크를 workspace별 저장하고 기존 워커에서 최대24개 프레임을 실제 이미지로 전달. URL 허용 목록·크기/시간 제한·격리 검증. 합성2초 MP4→8 JPEG 추출 확인. pytest301passed85.69s, ruff/mypy55, frontend typecheck/build14routes 통과. 실제 Chrome 데스크톱 다크 입력 화면 및 390×844 밝은 화면/잘못된 링크 오류 안내 확인, computed gap16px·가로 넘침 없음. 실제 유료 분석, 외부 YouTube/Reels 다운로드 성공, 파일 드롭 실동작은 미검증. 원본 자료/생성 이미지 보존. 커밋·푸시 없음.

ASA205 IN PROGRESS: 영상 링크 연결 버튼 제거. 입력 시 주소 형식 안내, 분석 시작 시 저장 후 실행, 미리보기는 저장하지 않음.
ASA205 DONE: 링크 연결 버튼 제거. 링크 입력 시 로컬 형식 검증, 분석 시작에서 영상 참조 저장 후 기존 요청 접수. 잘못된 링크 차단 및 수정 시 오류 해제 확인. Chrome 데스크톱 다크/모바일 밝은 화면 확인, 입력 높이44px·가로 넘침 없음(브라우저 배율 유지). 증거 .local/asa205-video-link.png. pytest301passed84.45s, ruff/mypy55 및 frontend typecheck/build 통과. pytest 종료 후 pool-88 연결 시간초과 로그 1건 발생(테스트 실패 없음). 실제 유료 분석·외부 영상 다운로드는 이번 검증에서 실행하지 않음. 기존 CACHE_POLICY/local-development EOF 공백은 이번 작업 범위 밖으로 유지. 커밋/푸시 없음.
ASA206 IN PROGRESS: 영상 파일·링크 혼합 최대4개 입력, 영상별 참고 요청, 통합 스타일 분석. 기존 단일 영상 참조 호환 유지. 실패 자료 구분·빈 입력/업로드 중 차단 및 실제 화면 검증.

ASA206 IMPLEMENTED / 검증 일부 보류: 파일·공개 링크 혼합 최대4개, 개별 참고 요청·추가/삭제·빈 항목/업로드 중 실행 차단, 영상별 관측 자료 및 통합 스타일 지침 반영. 전체 표본 최대48개, 일부 자료 실패 명시·전체 실패 시 AI 호출 차단. 중단 요청 전 pytest304passed82.77s, ruff src/mypy55, frontend typecheck/build14routes 통과. 기존 테스트 파일 전체 ruff 검사에는 기존 위반이 남아 있으며 source 검사와 구분한다. 실제 Chrome 다크 화면에서 빈 입력 차단·4개 추가 제한·행 삭제·링크/참고 문구 유지·합성 MP4 1개 업로드 연결 확인. 사용자 요청으로 추가 테스트 중단: 복수 영상 실제 유료 분석, 외부 링크 다운로드, 모바일/밝은 테마 최종 검증은 미실시. 사용자 자산과 DB 보존.

2026-11-04 커밋 준비: ASA202~206 확정 씬 이미지 입력/일괄 선택 및 영상 분석 기능과 의존 코드·템플릿·문서 포함. 사용자 요청대로 테스트 재실행 없음. .local 테스트 영상/스크립트·DB·비밀값·캐시 제외(파일 삭제 없음).

작업 시작 · 실행 입력 제목에 필수·선택 배지 표시 및 장면 구성·캐릭터 설정의 이전 대본 연결 검증.
추가 요청 · 긴 대본·장면 입력 원문을 별도 읽기 창에서 확인하고 닫으면 입력 유지.
완료 · 장면 구성·캐릭터 설정에 대본 작가 출처, 캐릭터 설정의 장면 입력에 장면 구성 출처를 설정하고 실행용 버전으로 저장. 두 템플릿에도 이전 작업 가져오기 허용. 공통 필수·선택 배지와 긴 글 크게 보기 반영. Chrome 1280×900 밝은 테마, 390×844 어두운 테마에서 대본 2581자와 장면 구성 4206자 가져오기·원문 일치·Escape 후 값 보존 확인. 배지와 가져오기 간격 8px, 읽기 창 가로 넘침 없음. 캡처 .local/verification/read-*.png 및 script-import-*.png. 실기기·유료 AI 실행 제외. pytest 306 통과, mypy 61파일·typecheck·build 통과. 전체 ruff 기존 99건.

조사 시작 · 11월 5일 02:59·03:00 영상 분석 실패 요청, 워커 처리와 링크·모델 단계 대조.
완료 · 동일 YouTube 링크 925초. 두 요청 모두 워커 시작 후 프레임 준비에서 종료. 링크 길이 제한 사유 보존 및 실제 공개 링크 전처리 확인. pytest 307 통과, mypy/typecheck/build 통과, 기존 ruff 99건. 별도 첫 60초 화풍 확인은 5초 간격 12프레임을 직접 검토했으며 유료 모델 재실행 없음.

점검 시작 · 현재 작업 공간의 에이전트·이미지 워커 상태 대조.
점검 완료 · 별도의 이미지 워커가 중지되어 있었고 에이전트 워커는 정상. 이미지 워커 시작 후 기존 요청(03:10:38) 1건이 03:15:17~03:15:35 성공, 이미지 바이트 저장과 양 워커 heartbeat 확인. 대기열 0건. 코드 변경 없음.

작업 시작 · 대본·장면 제목 누락 원인 및 작업 공간 워커 배지 분리.
완료 · 03:08 장면 구성 답변의 제목 미제공·섹션명 오인 확인. 이전 작업 목록은 작품 제목과 대본 원문 제목을 우선 사용하고 없으면 대본 발췌로 표시. 단독·자동화 공통. 새 대본/장면 생성 지침 4개 등록, 지침 외 설정 동일성 확인. 상단에 독립 이미지 워커 상태 표시(이미지 상세와 판정 공유). 실제 Chrome 1280×900 다크 및 390×844 라이트에서 두 배지 온라인과 이전 작업 카드 선택·원문 확인. 캡처 .local/verification/previous-scene-title-*.png 및 workspace-workers-*.png. 유료 재생성·워커 강제 중단·실기기 미검증. pytest 308 통과, mypy/typecheck/build 통과, 전체 ruff 기존 99건.

작업 시작 · 작업 공간 상태 바 스크롤 고정과 범용 입력 조건 검토.
완료 · 상태 바만 작업 공간 상단 sticky. Chrome 1280×900 다크(스크롤 450/2799px), 390×844 라이트(450/3212px)에서 상단 0px·가로 넘침 없음 확인. 증거 .local/verification/sticky-workers-{1280,390}.png. 기존 필수 설정 유지. 선택 영상 생략이 실행 전 검사와 링크 연결 단계에서 막히던 문제 수정, 테스트용 브라우저 설정으로 필수 미입력은 차단·선택 미입력은 요청에서 생략 확인(실제 접수 전 차단, 유료 실행 없음). pytest 308, mypy/typecheck/build 통과. 전체 ruff 기존 99건.

점검 · 이미지 v2 확정 후 v1 재선택 동작 및 범용 입력 적용 범위 확인.
이미지 버전 검증 · 격리 DB 통합 테스트에서 v2→v1 재확정 및 v1·v2 두 기록 보존 확인(1 passed). 실제 사용자 이미지 변경 없음. 새 후속 작업의 확정 참조 검증과 버전별 수정 기준 선택 코드를 확인.

진행 중 · 에이전트 입력별 조건부 필수. 선택형/예·아니오 항목의 값에 따른 조건 1개, UI·저장·단독/자동화 동일 검증. 기존 설정은 사용자가 변경할 때 적용.
완료 · 입력 조건(항상 필수/조건부 필수/선택) 편집과 동적 실행 배지. 선택형·boolean 출처 1개와 선택값 1개를 저장. 조건 삭제·값 변경·자기 참조·중첩 위치·스키마 오류를 검증하고 조건 출처 삭제 안내. 단독 API와 자동화 검증 공통 적용, 고정값과 앞 단계 결과의 조건 검증. 실제 1280×900 밝은/390×844 어두운 편집·미리보기에서 필수 전환/빈 입력 차단/값 보존/삭제 방지/가로 넘침 확인, 데스크톱 조건 콤보박스 y434.39 일치·간격16px. 증거 .local/verification/conditional-editor-*.png 및 conditional-required-*.png. 사용자 설정 저장 없이 새 임시 초안으로 QA. 기존 에이전트 조건 일괄 변경 없음. 실제 저장·요청은 격리 DB 통합 테스트, 유료 AI 호출 없음. 코드 리뷰 2건 보완 후 pytest332(119.75초), mypy62/typecheck/build 통과. 변경 Python lint 통과·전체 기존 Ruff99건. 실행 중 작업 없음 확인 후 기존 에이전트 워커 재시작. 자동화 워커 미실행 상태, 실기기 미검증. 커밋/푸시 없음.
진행 중 · 필수 입력 배지의 시인성 강화. 공통 InputRequirement에 테마별 단색 강조 배경·대비 글자색 적용, 조건부 전환과 좁은 화면 정렬 확인.
완료 · 공통 필수 배지를 primary/on-primary 단색·700 굵기로 강조, 선택은 중립색 유지. 디자인 시스템에 기준 반영. 실제 Chrome 1280×900·390×844 밝은/어두운 4조합에서 조건부 선택→필수 전환, 빈 값 차단·입력 보존 및 가로 넘침 없음 확인. computed margin8px/padding4px8px/height29px 확인, 캡처 .local/verification/required-badge-*.png 및 required-editor-*.png. 밝은 데스크톱과 밝은/어두운 모바일 캡처 시각 확인. pytest332 통과(124.32초, 종료 후 pool-93 연결 timeout 로그 1건), mypy62/typecheck/build 통과. 전체 Ruff 기존99건, git diff --check 통과. 사용자 에이전트 설정·이미지 변경 및 유료 호출 없음. 실기기 미검증. 커밋/푸시 없음.


## 완료 · 캐릭터 복수 확정과 씬 단일 확정
- 캐릭터 확정 버전 목록과 기본 이미지를 구분. 씬별 다른 확정 캐릭터 버전 선택 지원.
- 씬 이미지는 단일 확정본만 새 작업에 전달. 기존 실행 스냅샷과 자산 보존.
- 캐릭터는 확정 버전 목록과 기본 이미지 1개를 따로 저장합니다. 추가 확정은 기본 이미지를 바꾸지 않으며, 확정된 버전에서 ‘기본 이미지로 사용’으로 변경합니다. 보관함 선택과 씬별 버전 변경에는 해당 버전의 설정·이미지를 함께 전달합니다.
- 씬은 단일 확정본만 새 작업에 연결합니다. 이전 씬 버전의 선택과 미확정 캐릭터 버전의 참조는 서버에서도 검증합니다. 기존 실행 스냅샷은 보존합니다.
- 로컬 DB에 멱등 마이그레이션 적용: 기존 기본 이미지를 캐릭터 확정 목록으로 이관했습니다. 사용자 이미지의 신규 확정·생성은 하지 않았습니다.
- 검증: backend pytest 335개 통과, src Ruff 통과, mypy 62개 파일 통과, frontend typecheck/build 통과. 전체 tests 디렉터리 Ruff의 기존 오류는 이번 변경 범위 밖입니다.
- 화면: 1280×900 밝은/어두운 테마, 390×844 밝은/어두운 모바일 에뮬레이션 확인. 버전 선택 후 기본값 복원, 실제 요소 경계·12px 간격·가로 넘침 없음 확인. 증거: .local/verification/multi-confirm-{light,dark,mobile,mobile-light}.png, version-library-provenance.png. 사용자 데이터의 복수 확정은 임의 수행하지 않고 별도 DB 통합 테스트에서 검증했습니다. 실기기 및 유료 생성 호출은 미검증. 커밋/푸시 없음.

### 영상 AI 비교 개선 · IN PROGRESS
- 공급자 선택과 비교 기준을 분리하고 동일 길이·통화 비용, 차액과 근거별 장점을 비교하는 화면으로 개선한다.

진행 중 · 영상 AI 비교 가격 기준을 목표 영상1편·클립 단가/개수·계산식으로 명시, 프롬프트/이미지 비용 별도 설명 및 공식 Runway API 연동 절차 추가. 실제 설정 변경/호출 없음.
완료 · 영상1편 길이·각클립1회·단가×개수 계산식·전체 재생성1회 비용·별도 프롬프트/이미지 제작비 표시. 공식 Runway setup/API/pricing 문서 확인 후 계정/키/크레딧→서버 설정→연결 확인→첫 클립 안내와 기타 모델 추가 절차 추가. 키/설정 변경·유료 호출 없음. Chrome1600×885 밝은/어두운,1분9540원/5분47700원 계산 전환 확인(1325원/USD), API 펼침/접힘·마지막 출처까지 점검. 조건3개 top 동일/높이51.997px, API gap16px·문단8px·단계 왼쪽좌표 동일. 390×844 양테마 DOM 가로넘침없음·명령줄 줄바꿈 확인, 좁은 화면 시각/실기기 미검증. 테마/viewport 복원·임시탭 닫음. 증거 .local/diagnostics/comparison-price-dark.png, comparison-api-dark.png, comparison-api-light.png. pytest389(118.87초)/mypy64/typecheck/build/diffcheck 통과, Ruff 기존97건. 커밋/푸시 없음.

진행 중 · 비교표 9개 모델별 공식 API 경로·모델 ID·인증·생성/조회·출처와 확인 한계 추가. 직접/중개 API 및 ASA 구현 상태 구분, 테마/좁은 화면 간격 검증. 설정 변경·유료 호출 없음.
완료 · 비교표9개 모델의 모델별 펼침 안내 추가: 계정/인증·모델ID·생성/조회·제한·ASA상태·공식 출처. Runway/BytePlus/BFL/xAI/Alibaba 직접 경로와 Gemini/Kling/MiniMax Runway 중개 경로 구분. Gemini 직접EAP 제한, Kling/MiniMax 직접 호출 명세 미확인, FLUX 힉스필드 상품 대응 미확인 표시. 힉스필드 가격과 API요금 분리. Chrome1600×885 밝은/어두운 실제 화면,9개 펼침/키보드 접힘·포커스 확인. desktop dt/dd 시작top 동일·열gap16px,390×844 양테마 DOM 넘침없음·모바일행gap8px(54개 행 어두운 상태검사). 모바일 캡처 CDP timeout으로 좁은화면 시각/실기기 미검증. 읽기안내만으로 오류/비활성/선택 입력 신규상태 해당없음. 테마·viewport복원·임시탭닫음. 증거 .local/diagnostics/model-api-dark.png,model-api-light.png,model-api-limitations.png. pytest389(117.77초)/mypy64/typecheck/build/diffcheck 통과,전체 Ruff 기존97건. 설정변경·유료호출·커밋/푸시 없음.
커밋 준비 · 영상 AI 비교 가격 설명·9개 API 안내와 해당 기록만 포함. 이전 메뉴/프롬프트 변경은 로컬 보존. 직전 전체 검증 결과 유지, 사용자 자료·스크린샷·생성물은 제외.
