# 임시 저장 안내 의미·간격 (2026-11-10)

- 임시 저장 notice는 브라우저 IndexedDB 초안의 복원/저장 상태이며 서버 저장과 다르다. 음성 reset은 초안을 제거하고 현재 로드한 서버 설정으로 되돌린다. 생성 자산을 삭제하지 않는다.
- 공통 DraftNotice를 음성 설정과 새 요청 입력에 적용. copy 묶음 gap8px, 문구/버튼 gap16px. p 기본·상속 여백 제거, 버튼 폭 제한 및 줄바꿈 유지. 화면별 margin 덧붙이기 대신 공통 배치 수정.
- 음성 버튼 이름을 저장된 음성 설정으로 되돌리기로 변경, 자동저장/되돌리기/기존 생성 음성 보존 설명 추가.
- Chrome dark desktop screenshot .local/diagnostics/draft-notice-spacing.png. DOM 실제 gap15.998px, p margin0 확인. viewport390x844(실제 CSS width433)에서 동일gap, overflow없음, 버튼영역내 확인. viewport복원.
- 사용자 입력·설정 저장·초안삭제 없음. 밝은 테마 및 신규 요청 화면의 개별 시각 검증은 미완료. 좁은 화면은 DOM 기하검증만 수행.
- frontend typecheck/build, backend Ruff/mypy85, diff-check 통과. 전체 pytest 결과는 WORKBOARD 참조.
