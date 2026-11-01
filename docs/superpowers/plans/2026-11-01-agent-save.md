# Single-save agent settings
Goal: 저장 한 번으로 새 실행에 적용하고 접수된 실행 기록은 보존한다.
Architecture: 기존 immutable registry_versions는 내부 snapshot으로 유지. atomic save API가 초안 갱신과 snapshot을 한 트랜잭션으로 수행. 신규 접수는 latest snapshot 해석, 기존 작업 수정/재접수는 고정 유지.
- [x] 저장 API 원자성/충돌/이력 보존 테스트와 구현
- [x] 개별 요청·자동화·예약·검수 접수 최신 설정 및 멱등 테스트와 구현
- [x] 편집 UI 단일 저장, 연결 버전 관리 제거, 적용 시점 안내
- [x] 전체 backend/frontend 검증, 실제 화면 확인
Ruling: 기존 미등록 초안을 일괄 적용하지 않는다. 사용자가 저장할 때 실행 설정으로 적용한다. 과거 기록은 삭제하지 않는다.
Ruling: 예약의 흐름은 예약 저장 당시를 유지하되 각 실행 접수에서 연결 에이전트만 최신으로 해석한다.

검증: backend231 tests, ruff, mypy44 files; frontend11 tests/typecheck/build 통과. 실제 캐릭터 설정 화면 저장 버튼1개·버전 등록 없음 확인. 유료 호출 및 기존 에이전트 저장 미실행.
