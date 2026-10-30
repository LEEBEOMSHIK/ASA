# 입력 방식 도움말 실화면 검증 (2026-10-30)

- PostgreSQL 55439, API 8127, Next.js 3001을 로컬 프로세스로 재시작. 실행 워커/유료 AI는 이번 화면 확인에서 시작하지 않음.
- 무서운 쇼츠 대본 작가 편집에서 ‘사용자가 답하는 방식’, 선택별 설명/예시 및 ? 펼침/닫힘 확인.
- 6가지 방식을 각각 선택하여 해당 설명으로 바뀌는 것을 확인. 검증 중 편집은 저장하지 않고 탭을 종료하여 원본 초안 보존.
- 도움말을 펼칠 때 인접 입력이 늘어나는 현상 발견: input-form-grid에 align-items:start 적용 후 스크린샷 확인.
- frontend typecheck/build 통과. 화면 증거: .local/verification/input-mode-help.png.
- backend ruff src/mypy src 통과. 전체 pytest는 결과 없이 대기하여 중단했으며 완료 여부 미검증.
