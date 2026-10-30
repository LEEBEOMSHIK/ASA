# 선택지 편집 UX 검증 · 2026-10-30

- 라디오/선택 목록 공통 ChoiceOptionsEditor 적용. 기존 enum 데이터는 그대로 사용.
- 개별 입력, 추가/삭제, 빈 값과 공백 정규화 중복 검사, 브라우저 validity를 통한 잘못된 저장 차단.
- 기본값 이름 변경 동기화와 기본 선택지 삭제 시 해제 안내.
- 실제 무서운 쇼츠 대본 작가 편집 화면에서 이름 변경→기본값 동기화, 중복 invalid, 기본 선택지 삭제→안내/기본값 해제, 추가→포커스/빈 값 invalid 확인.
- 브라우저 테스트 변경은 저장하지 않고 임시 탭 종료. 사용자 초안과 기존 입력 항목은 유지.

- 최종 검증: frontend typecheck/build 통과. backend ruff src/mypy src 통과. 전체 pytest는 169 통과·5 실패(기존 모델 테스트 fixture에 input_schema 누락); tests까지 포함한 ruff는 기존 26건(import/줄 길이) 실패. 이번 변경은 프런트엔드 선택지 편집에 한정하며 해당 백엔드 파일을 변경하지 않음.
- 화면: .local/verification/choice-options-editor.png
