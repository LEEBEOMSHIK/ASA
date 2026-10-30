# OpenAI 공식 사용량·비용 집계 (ASA-110)

- 기존 요청 추적과 별도 보기로 Costs/Completions Usage API 집계를 추가했다.
- 서버 Admin API Key, 선택적 project scope, 설정 workspace의 owner 권한을 요구한다.
- UTC 비용 4기간, 일별 비용, 모델별 토큰, 캐시 입력/요청 수를 제공한다.
- 잔액은 결제 화면 링크로 안내한다. Codex와 수동 잔액은 제외했다.
- 메모리 캐시 15분, 강제 갱신 최소 30초, 실패 시 정상 스냅샷 보존과 오류 코드를 사용한다. 서버 재시작 후 캐시는 없다.
- 코드 리뷰에서 캐시 TTL과 화면 타이머의 오차로 갱신이 늦어지는 문제를 수정했다.

## 실제 화면 검증
- 로컬 API를 재시작하고 /monitoring에서 공식 집계 보기, 새로고침, 연결 안내 펼침/접힘을 확인했다.
- 키 미설정 시 연결 필요/마지막 정상 조회 없음 표시, 거짓 0원 금액 카드 없음.
- 기존 요청별 보기 전환 시 24px grid 간격 유지. 공식 카드 내부 gap 16px.
- 밝은/어두운 테마, 390px viewport 검증. 측정 CSS viewport 416px, scrollWidth 416px로 가로 넘침 없음.
- 링크 text-decoration none 확인. 테마와 viewport는 원복했다.

## 검증 한계
- Admin API Key가 없어 실제 OpenAI 계정 금액/토큰 및 정상 데이터의 브라우저 렌더링은 미검증이다.
- 집계 수치/페이지 순회/권한 거부/잘못된 응답/캐시 유지/빈 정상 응답은 mock 테스트로 검증했다.
- 공식 조회는 AI 생성 호출을 수행하지 않는다. 사용자 에이전트와 생성 데이터는 변경하지 않았다.

- 정적 검증: backend ruff/mypy, frontend typecheck/build 통과. 새 집계 테스트 11건 통과. 전체 회귀 테스트 203 passed (186.78s).
- 이번 변경 파일 diff whitespace 검사 통과. 전체 작업 트리의 기존 다른 파일 3개에는 EOF 공백 경고가 있어 덮어쓰지 않았다.
