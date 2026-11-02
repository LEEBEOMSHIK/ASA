# ASA-169 출처 에이전트 설정과 씬 입력 연결

- 입력 항목별 x-answer-agent를 저장하고 등록된 workspace 에이전트인지 검증한다. 기본 모든 에이전트 선택도 제공한다.
- 실행 화면에서 출처 ID로 이전 작업 목록을 조회한다. ID는 버전에 고정하지 않으므로 해당 에이전트의 과거 답변을 고를 수 있다. 가져오는 것은 선택한 답변 버전의 복사이며 원본을 변경하지 않는다.
- 씬 이미지 에이전트 revision7: script → 무서운 쇼츠 대본 작가, scenes → 장면 구성 에이전트. 기존 지침/다른 에이전트 불변 비교 통과.
- 카드 단독 그룹이 auto-fit 때문에 전체 폭으로 늘어나는 문제를 그룹 공통 auto-fill로 수정. 실제 작업 공간 카드 7개 모두 352px 확인.
- 실제 UI: 씬 입력 목록에 장면 구성 완료 작업 1건만, 대본 입력에 무서운 쇼츠 대본 작가 완료 작업 1건만 표시. 대본 2,519자 가져오기 확인. 유료 실행 안 함.
- 전체 pytest 277 passed(exit0), 이후 추가한 출처 스키마 계약을 포함해 관련 단위 6 passed. ruff/mypy51/typecheck/build/diff check 통과.
- 전체 테스트 종료 시 pool-84 connection timeout 로그 1건 발생했으나 assertion 실패 없이 exit0. UI/API 후속 조회 정상. 이번 모바일 재검증 미실행.
- 화면 증거 .local/scene-agent-cards.png (Git 제외). 커밋/푸시 미실행.
