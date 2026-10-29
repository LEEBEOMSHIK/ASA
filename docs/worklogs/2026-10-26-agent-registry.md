# ASA-009 검증 기록 — 2026-10-26

## 구현

- FastAPI owner 세션, Origin/CSRF, 서버 유래 workspace, 입력 크기 제한, 비밀 입력 제외 오류 응답.
- PostgreSQL 초안 revision 충돌 검사, 불변 버전 snapshot, 동일 revision 게시 멱등성, 도구 binding.
- 제한 스키마 검증·확정 시 정규화, 허용 도구·자기 참조·의존 순환 검사.
- 에이전트 목록/편집/입출력 필드/버전 보기, ASA 도구와 사용자 에이전트 통합 목록.
- 실행 준비 중을 명시한 비활성 실행 버튼. 미구현 미디어 도구 선택 차단.
- 전용 PostgreSQL 로컬 클러스터와 비관리자 앱 역할, bootstrap/start/stop 및 명시 migration.

## 실제 검증

`scripts/check.ps1` 최종 종료0: pytest **26 passed**, ruff 통과, mypy 17개 소스 통과,
frontend typecheck와 production build 통과. DB 검사는 별도 테스트 DB의 임시 스키마를 사용했고 skip 없이 실행했다.
workspace 접근 거절·CSRF·revision 충돌·과거 snapshot 유지·동시 게시·자기 참조·스키마 상한을 검사했다.

브라우저에서 owner 로그인→샘플 생성→저장→검증→v1 확정→초안 재저장→도구 목록을 확인했다.
저장하지 않은 변경에서 로그아웃 확인이 표시되고 ‘계속 편집’으로 입력을 유지하는 것을 확인했다.
샘플 이름은 ‘샘플 · 채널 대본 작가’이며 AI 생성 결과가 아니다.

독립 코드 검토의 변경 이탈 보호·스키마 기본 상한·매우 큰 숫자 처리 지적을 반영했다.
등록 화면 링크는 전체 문서 이동을 사용하고 beforeunload와 로그아웃 확인을 적용했다.
새 에이전트에서 기본 도구가 자기 참조로 잘못 표시되던 조건도 수정했다.

## 환경 및 한계

DB 55439, API 8127, 웹3001. 기존 다른 프로젝트 서비스는 유지했다.
초기 DB 준비 실패 잔여 폴더는 `.local/bootstrap-incomplete-20261026`에 보존했다.
검증 과정에서 생성한 로컬 접속 정보는 교체했으며 .env와 .local이 Git에서 제외됨을 확인했다.
유료 AI·외부 게시·Docker 빌드·SaaS 인증·모든 화면 크기/테마·자동화 실행은 검증하지 않았다.
DB 등록 통합 검사는 LangGraph 재시작 복구 검증을 대신하지 않는다.
커밋·push는 수행하지 않았다.
