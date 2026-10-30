# 에이전트 확정 설정과 입력 정렬 (ASA-106)

- AgentDraft.requires_approval 기본 false. 저장/등록 버전별 유지. 개별 에이전트 결과는 종류와 무관하게 최신 답변의 사용자 확정을 기다린다.
- 편집 2번 ‘실행할 때 쓸 입력 양식과 결과 항목’ 하단 ‘답변 확인과 확정’에 노출. 초안 저장 후 새 버전 등록 안내. 자동화 승인과는 구분해 기존 검토 단계 사용을 안내한다.
- 결과의 ‘이 답변 확정’은 기존 서버 revision/latest-version 검증을 사용한다. 답변 수정·재생성은 확정 해제. 답변과 이미지 검토가 함께 있으면 통합 상태와 그룹별 개수를 최근 작업에 표시한다.
- 공통 필드 라벨 행 최소44px로 도움말 터치 영역과 정렬. 입력 편집 그리드 margin 제거. 상세 펼치기는 chevron. AgentIcon으로 고정 A 교체, 카드 하단 정렬.

## 검증
- backend 전체 pytest: 192 passed, 218.89초. 신규 통합 테스트에서 이전 버전 설정 보존, 일반 텍스트 답변의 검토→확정→수정 후 재검토, 오래된 확정 거절, 최근 작업 반영 확인.
- ruff: backend src 및 test_work_progress.py 통과. 전체 tests까지 넓힌 ruff 검사에는 기존 테스트 파일들의 스타일 오류가 남아 있음(이번 범위 외 파일은 일괄 변경하지 않음).
- mypy: 39 source files 통과.
- frontend typecheck, 33 Node tests, 최종 build 통과.
- 정적 코드 리뷰: 수정 필요 결함 없음.
- 실제 Chrome에서 입력창 높이 정렬, 에이전트 SVG, 확정 옵션 선택/해제 확인. 사용자 기존 설정/등록 버전/확정 결과는 변경하지 않음. 스크린샷 .local/verification/agent-input-alignment.png, agent-approval-setting.png.
- API8127 재시작 완료. 유료 AI 호출 없음. 실제 AI 신규 생성 후 확정 클릭은 수행하지 않았으며 비유료 API 통합 테스트로 상태 전환 검증.
