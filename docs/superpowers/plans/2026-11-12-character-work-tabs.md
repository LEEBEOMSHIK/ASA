# 캐릭터 작업 탭

사용자가 승인한 상단 요약+작업 중심 탭을 character_images 후속 작업에만 적용한다. 다른 에이전트 화면은 기존 유지.

1. 작업/workspace/user별 탭 저장 키와 유효값 검증, 저장 실패 fallback 및 회귀 테스트.
2. WorkHistory: 작품명·에이전트·AI/후속 상태와 검토 버튼, 접는 작업 정보. 기존 요청 정보는 이력 탭에 배치.
3. ScriptStage/CharacterResults: 공통 설정, 캐릭터 이미지, 요청/답변 이력으로 분리. hidden으로 마운트 상태 유지, 원본/수정/비교/재요청 유지. 나레이션 portal 유지.
4. 토큰 기반 탭/요약 공통 스타일, 키보드 방향키/Home/End, aria 상태. 사이드바 불변.
5. 실제 브라우저에서 탭/새로고침/초안/정렬/테마/좁은화면 확인. 미검증 명시. backend pytest/ruff/mypy, frontend typecheck/build와 탭 테스트.
