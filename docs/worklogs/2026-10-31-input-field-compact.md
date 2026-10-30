# 입력 항목 내부 여백 (ASA-109)

원인: stack gap24px, actions margin-top16px, Field/p margin이 겹쳤고 actions의 grid 배치로 체크박스와 삭제 버튼이 세로로 늘어졌다.

수정: input-field-body 전용 grid/gap16px, 상단16px. Field와 도움말 p의 margin 제거. 체크박스 가로 flex + wrap. 하단 연결 이름과 삭제 버튼은 space-between + wrap. 데이터 저장/삭제 동작은 변경하지 않음.

실제 Chrome 확인:
- 기본 데스크톱에서 두 입력창 top 값 동일(251.0764px), 항목 높이345.61px, 내부 gap16px, 삭제 버튼84.79px.
- viewport override390x844 테스트에서 브라우저 CSS viewport433px(사용자 기존 배율 유지). 1열310.45px, 수평 overflow 없음, 체크박스 두 라벨 top 동일/높이44px. 하단은 자연스럽게 줄바꿈.
- 기본값 선택 시 입력창 표시, 해제 시 숨김 확인. 접기/펼치기 및 키보드 포커스 확인. 밝은/어두운 테마 확인 후 원래 밝은 테마와 viewport로 복원.
- 사용자 입력·설정 저장/삭제 없음. 기존 값 복원. 증거 .local/verification/input-field-compact.png.
- 오류/비활성 검증 로직 변경 없음. 해당 상태 별도 유발 테스트는 수행하지 않음.

검증 명령 결과는 WORKBOARD ASA-109에 기록.
