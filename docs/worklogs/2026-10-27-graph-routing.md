# ASA-037 연결선 불필요 우회 수정

원인: target.x <= source output.x+60이면 두 블록의 세로 배치와 무관하게 가장 아래쪽+40을 우회했다.
수정: 수직으로 분리된 노드의 중간 공간을 경유한다. 같은 높이의 역방향 연결은 기존 외부 우회를 유지한다. 저장 데이터/실행 의미는 변경하지 않았다.

검증: graph-routing.test.mjs의 아래/위 대상 범위 및 같은행 역방향3개 통과. pytest73(75.21s), ruff, mypy26, frontend typecheck/build 통과. pytest 래퍼가 Windows 정책에서 차단되어 동일 venv의 python -m pytest로 실행했다.
브라우저 검증용 초안에서 source(400,160)/result(570,320) 배치로 하단 고리 제거 확인. 좌표는 저장하지 않고 임시 탭 닫음. screenshot .local/verification/graph-routing-fixed.png. 유료호출 없음.
복잡한 장애물 전체를 탐색하는 자동 라우팅이나 겹친 블록의 회피까지 보장하는 변경은 아니다.

## 재검증: 가까운 오른쪽 대상과 각진 경로
사용자 두 번째 캡처에서 가로 간격40px인 정방향 연결이 기존60px 기준으로 역방향 분류되어, 관계없는 아래 노드까지 감싸는 현상 재현. 기존 테스트에 가까운 정방향/곡률 사례가 빠져 있었음.
오른쪽 대상은 양의 모든 간격에 대해 간격 절반 제어점을 사용한다. 뒤로 가는 경로는 접선이 이어지는 이차곡선 모서리로 처리한다. 세로 간격의 임의16px 제한도 제거했다.
신규2개 테스트가 수정 전 실패/수정 후 통과. 기존3개 포함5개 회귀 통과. 브라우저 start(48,100), AI(320,80), end(80,400) 배치에서 고리제거/둥근 경로 확인, 좌표는 미저장 후 탭닫음. 캡처 .local/verification/graph-routing-rounded.png.
최종 필수 검사: pytest73(100.73s), ruff, mypy26, frontend typecheck/build 통과. 실제 AI 호출 없음.
