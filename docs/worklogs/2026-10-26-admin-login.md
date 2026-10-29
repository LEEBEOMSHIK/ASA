# ASA-014 관리자 로그인 — 2026-10-26

사용자 요청에 따라 `/login`을 관리자 전용 로그인 페이지로 분리했다.
미인증 관리 화면은 next 경로를 보존해 이동하고, 로그인 후 허용된 관리 경로로만 복귀한다.
기존 접근 키 로그인은 유지한다. 서버 장애는 로그인 만료와 구분해 재시도 안내를 제공한다.

테스트 로그인은 development·명시 활성화·loopback 요청 조건이 모두 충족되어야 한다.
Origin allowlist와 loopback origin도 검사한다. 기본 설정과 운영 Docker는 비활성이다.
`scripts/run.ps1 api`가 개발 프로세스에만 활성화하며 종료 시 이전 환경값을 복원한다.
키를 클라이언트로 보내지 않고 기존과 동일한 HttpOnly 세션·CSRF·workspace 경계를 사용한다.
테스트 로그인은 실제 로컬 작업 공간을 사용한다.

구현 전 새 경계 테스트3개 실패 확인 → 구현 후 통과.
전체 `scripts/check.ps1`: 실제 DB 포함 pytest29개, ruff, mypy17개 소스, web typecheck/build 통과.
브라우저에서 기존 세션 자동 이동, 로그아웃, 미인증 /tools→/login?next=/tools,
키 없이 테스트 로그인→/tools 복귀, 다시 로그아웃→/login을 확인했다.
운영·비활성·외부 주소 거절, 누락/외부 Origin, 세션과 CSRF, 로그아웃 후 토큰 무효화를 테스트했다.
Docker 실행과 전체 화면 크기 검증은 수행하지 않았다. 유료 AI 호출·커밋·push 없음.
