# 클립별 영상 계획 확정
사용자 승인: 전체 확정 대신 클립별 계획 확정 후 생성. 기존 자료 보존.
1. migration.sql: workspace/request/version/clip 단위 승인 기록. 최초 도입 시에만 기존 전체 확정을 legacy 기록으로 보존. 생성 job/과금 이벤트 만들지 않음.
2. registry/video_plan_approvals.py: 클립 및 공통 모델/화풍/해당 발화/연속 선행클립 fingerprint. 기존 새 승인에서 동일 내용만 이어받음. 새 답변/변경 내용은 승인 불일치. legacy는 동일 버전만 인정.
3. video_jobs.py: GET 승인 상태·fingerprint/latest 반환, POST plan-approve는 최신/클라이언트 fingerprint 검증. 생성은 선택한 모든 클립 승인 검사(원자적 거절). 영상 approve API는 별도 유지.
4. VideoClipManager/script-stage/work_progress: 전체 확정 제거, 클립 계획 확정과 영상 확정 라벨 분리, 선택 생성은 승인된 미생성 클립만. 실제 유료 호출 없이 모바일/light/dark 검증.
5. unit/integration: 독립 클립 변경, 연속 종속, 목소리 변경, 부분 확정·혼합 생성 거절·이전버전·workspace·CSRF·무비용·legacy 보존. pytest/ruff/mypy/typecheck/build.
