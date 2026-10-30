# ASA-083 대본 생성 → 길이 검사 실제 자동화

- 저장된 자동화: 테스트 · 1분 대본 생성과 길이 검사 (42b73253-53dd-4ddd-9898-26cab5e68522), 구성 v1.
- 흐름: 주제 입력 → 쉬운 대본 작가 v4 → 대본 길이 검사 v1 → 검사 결과.
- writer.topic ← 최초 요청, inspect.text ← writer.result, inspect.limit ← 600. 에이전트 자체의 도구 연결은 변경하지 않았다.
- 로컬 ASA_AUTOMATION_AI_ENABLED 활성화, API 재시작, 상시 자동화 워커 실행. 시작 전 다른 queued/running 작업 및 활성 예약0건 확인. 예약 생성 없음.
- 실행: f1e5d580-4492-4966-bf1f-41388466fb0f. 고양이 상자 주제/약1분/차분한 존댓말로 실제 AI 1회 호출.

## 결과
- 시작·대본 생성·검사·종료4개 노드 모두 succeeded.
- 생성 답변444자. 검사 도구 입력이 생성된 result 문자열 전체와 정확히 일치한다.
- 검사 결과 characters444, limit600, exceeded=false. 계산값과 Python len 재계산 일치.
- 별도 무과금 경계 확인: 600자는 초과false, 601자는 초과true.
- 검사는 공백을 포함한 문자 수 검사이며 실제60초 낭독 여부는 판정하지 않는다. 음성 길이 측정 미실시.

## 사용량
이벤트 9b3c50e2-6e3c-496c-adfe-16ed8539ec26: source=automation, 해당 automation_id/run_id, step_id=writer:1, step_name=쉬운 대본 작가로 연결됐다.
gpt-6.1-terra, 입력997/출력358토큰, 캐시0, 모델 응답8978ms, 예상USD0.002787, succeeded.
이 실행의 AI 사용량 이벤트는1건이다. 길이 검사는 로컬 함수로 외부 AI 비용과 토큰이 없으며 AI 사용량 이벤트를 만들지 않는다. 검사 결과는 실행 단계 이력에 저장된다.
증거: .local/verification/automation-writer-inspect-*.json (커밋 제외).

브라우저 검증: 자동화 목록/실행 기록/4개 단계 결과와 관리자 작업별 집계·호출 기록의 자동화 이름·블록명·997/358토큰·8.98초·USD0.002787 표시 확인. 결과 스크린샷 .local/verification/automation-writer-inspect-screen.png.

최종 검증: pytest166(158.83초), backend src ruff/mypy34, frontend typecheck/build 통과. 소스 코드 변경 없이 설정/자동화 데이터/검증 기록만 추가했다.
