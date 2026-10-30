# 체크박스 공통 정렬 (ASA-107)

원인: `.checkbox`에 붙인 정렬 규칙이 `.field-row .checkbox`로 한정되어 있었다. 승인 설정과 입력 양식 편집은 다른 컨테이너여서 공통 클래스를 사용해도 flex/gap이 적용되지 않았다. input의 브라우저 기본 margin도 그대로 남았다.

수정: 부모 조건을 제거해 `.checkbox` 자체에 flex/중앙 정렬/gap8px/최소44px 클릭 영역을 적용. 자식 체크박스 margin0, 20px 축소 금지. 데이터/승인 정책은 변경하지 않았다.

실제 브라우저: 사용자 확정 필요(미선택), 필수 입력(선택), 기본값 사용(미선택)의 간격과 중앙 정렬을 확인. 사용자 값을 변경하지 않고 포커스만 이동했다. `.local/verification/checkbox-spacing.png` 증거 저장.

검증: frontend typecheck/build, backend src ruff/mypy 통과. 전체 backend pytest 결과는 WORKBOARD ASA-107에 기록한다.
