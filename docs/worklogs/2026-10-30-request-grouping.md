# ASA-078 요청 라벨/본문 묶음

- 입력 원문 바로 위에 '내가 보낸 요청'을 배치하고 같은 배경/테두리 안에 묶음.
- 항목 설명은 박스 밖으로 이동. 라벨과 본문 사이 안내 제거. 테스트 배지는 라벨 옆에 유지.
- 원문/DB/API 변경 없음. object 입력 각 항목과 단일 값 입력에 동일한 형태 적용.
- 브라우저 실제 성공 요청에서 시각 확인. 증거: .local/verification/request-grouped.png.
- 추가 AI 호출 없음.

검증: pytest162 (159.98초), backend src ruff/mypy34, frontend typecheck/build, diff check 통과.
