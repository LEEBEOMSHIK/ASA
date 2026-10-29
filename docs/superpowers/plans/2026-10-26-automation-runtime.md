# Automation runtime implementation plan

사용자가 승인한 카드 실행→결과→시간 예약 방향을 구현한다. 기존 순차 빌더/DB/owner 인증 재사용.
예약은 Asia/Seoul 기준 1회 또는 매일. 저장 입력과 정의/에이전트 버전을 고정한다.
실행은 API가 원자적으로 enqueue하고 별도 로컬 worker가 LangGraph 단계 실행/중간 결과를 저장한다.
중복 run ID 충돌 검사, 동일 workspace worker advisory lock, 호출 전 intent 저장,
워커 중단 후 running은 needs_attention으로 정지. 완료 단계는 재호출하지 않는다.
검토 단계는 waiting_review로 멈추고 확인 후 다음 단계부터 진행한다.
예약 지연은 한 번만 실행하고 다음 미래 시각으로 이동. 활성 실행이 있으면 해당 회차 건너뜀.
호출 불확실 시 연결 예약 비활성. worker heartbeat 표시. 서비스 종료 시 자동 실행 불가.
AI는 외부 API/LangChain, 기본 비활성 opt-in 설정 + 키/모델 필요. 호출/출력 길이/일일 호출 상한.
금액 예산/실제 가격 정산/LLM 도구 선택/미디어/일반 분기/자동 재시도는 후속 범위이며 UI에 오인 표시 금지.
고객이 만든 도구 연결 에이전트는 아직 거부. 단독 에이전트 블록과 ASA 길이 검사만 실행한다.

- 테스트: pinned definition, enqueue 재시도/충돌, workspace/CSRF, 검토 재개, 예약 중복/지연,
  실패/중단 자동 재시도 금지, AI 미설정 차단, 실제 로컬 도구 결과.
- migration + runtime repository/routes + worker + provider 연결.
- 자동화 카드 실행/예약/기록, 선택 실행 상태/결과 UI, review_after 빌더 설정.
- 전체 필수 검사·브라우저 로컬 도구 실행·문서/보드 갱신. 유료 API 테스트 없음.
