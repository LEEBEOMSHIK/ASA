# Work speech review implementation plan

Goal: 기존 작업에서 대사별 음성을 검토하고 연결된 이전 답변 음성을 보존한다.
Architecture: 선택 답변의 base_version 계보만 따라 가장 가까운 음성 설정/작업을 읽는다. 다른 분기나 이후 버전은 가져오지 않는다. 출처 버전을 표시하며 확인은 원본 음성에 기존 승인 검증을 적용한다. 지침·음성·답변 데이터는 복제하지 않는다.
Tech stack: FastAPI/Postgres, React, 공통 UI와 토큰.

- [x] 실패 회귀: v3→v2 음성 상속, 분기/미래/타workspace 차단, 원문불일치/이전설정 분류, 확인시간초과 차단.
- [x] audio_service 조회와 audio_routes review endpoint. 기존 승인 API 재사용.
- [x] 공통 WorkSpeechReview를 ScriptStage에 연결. 대사·화자·실측/배정·플레이어·확인 버튼, 접힌 제외결과와 사유. 기존 제작 UI 유지.
- [x] backend pytest/ruff/mypy, frontend typecheck/build.
- [x] 실제 v3의 유효8/제외1 확인. 저장·확정 없이 양테마·좁은화면·실제재생·DOM간격 확인. WORKBOARD 기록.

사용자는 직전 제안한 대사별 확인 영역과 v2→v3 연결 방식을 승인했다. 별도 승인 재요청 없이 현재 checkout에서 진행한다. 유료 생성은 하지 않는다.
