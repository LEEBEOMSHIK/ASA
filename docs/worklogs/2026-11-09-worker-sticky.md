# 워커 상태 스티키 복구

- 원인: `.workspace-worker-panel .workspace-worker-strip { position:static }`가 기존 strip sticky를 덮어썼다. 부모 panel은 상태표시줄과 같은 높이여서 strip만 sticky로 되돌려도 이동 범위가 없다.
- 수정: panel을 top0 sticky/z-index30으로 지정하고 불필요한 strip sticky 규칙 제거. 배경·간격·줄바꿈 유지. dialog는 브라우저 top layer라 고정 표시줄 위에 표시된다.
- 실브라우저 dark CSS1600, scrollY1577에서 panel top0 확인, 워커 모달 열기/닫기 정상. CSS433에서 top0/높이112.5px, gap8px 12px/2줄 버튼/가로넘침 없음 DOM 확인. sidebar 폭 변경 없음. viewport 해제 전1600 확인, 임시 override reset.
- 증거 `.local/diagnostics/worker-sticky.png`. 좁은 캡처는 CDP timeout, 밝은테마 및 모든 드롭다운 조합은 미검증. 워커 시작/중지나 사용자 설정 저장 없음.
- 검증: 전체 pytest473(168.28초), Ruff/mypy85/typecheck/build/diff-check 통과. 커밋/푸시 없음.
