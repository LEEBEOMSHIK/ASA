# 접기·펼치기 아이콘 (2026-11-10)

- 공통 DisclosureButton/DisclosureSummary에 오른쪽 chevron을 표시하고 펼치면 아래로 회전한다. 텍스트와 native details/버튼 키보드 조작을 유지한다.
- 적용: 작품 공통 나레이션, 기본 음색 비교, 이전 답변 비교, 수정 요청, 재요청 입력, 요청 이력, 운영자 정보.
- sidebar/combobox 및 기존 전용 CSS chevron은 그대로 유지하여 중복 아이콘을 피했다.
- DOM 검증: Chrome desktop에서 16px 아이콘, 8px gap, align-items:center; 접힘 none / 펼침 matrix(0,1,-1,0,0,0). Enter/Space 나레이션, Enter summary, 이력 펼침 확인. 임시 펼침 상태 복원, 사용자 설정 저장/AI 호출 없음.
- 화면 증거: .local/diagnostics/disclosure-icons.png (dark desktop). 좁은 viewport 390x844에서 DOM 간격/회전 확인했으나 screenshot CDP timeout으로 시각 검증 미완료. 밝은 테마 및 모든 상세 컨트롤의 개별 시각 상태는 미검증. 오류 상태는 이번 표시 변경에 해당하지 않음.
- typecheck/build, ruff, mypy(85 files), git diff --check 통과. 전체 pytest 결과는 WORKBOARD에 기록.

## 오른쪽 배치 수정
- 사용자 피드백 반영: 공통 컴포넌트 DOM을 텍스트 → 아이콘 순서로 변경. Summary는 space-between으로 오른쪽 끝 정렬, Button은 문구 뒤 최소 8px 간격 유지.
- Chrome dark desktop 실제 screenshot/DOM에서 visible disclosure 모두 iconAfterText=true, align-items:center, gap8px. 이력 펼침 회전과 Enter 접기 확인 및 상태 복원.
- 증거: .local/diagnostics/disclosure-icons-right.png. 이번 수정의 밝은 테마/좁은 화면 시각 상태는 미검증.
