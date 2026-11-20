# 클립 계획 작업 구현 계획
사용자 승인: 계획 확정 해제와 개별 클립 AI 수정. 사용자 자료/기존 영상/검수 유지, 자동 생성 없음.

1. `video_plan_approvals`에 approved 상태 추가. 최신 동일 fingerprint 결정이 승인을 덮어쓰며 이전 버전 상태는 유지. video_jobs의 공통 승인 검증을 /plan-revoke에도 적용. 검증: 오래된 버전/CSRF/workspace/낡은 fingerprint 거부, 해제 상속·재확정·생성 차단·접수 영상 보존.
2. 기존 script queue에 revise-clip 요청 추가. latest agent + 입력/기준답변/선택클립 고정. 모델 결과의 대상 클립만 서버 병합하고 전체 계약 검증. 테스트 모델이 다른 클립을 바꿔도 기존 원문을 보존하며 실패/재접수/충돌 검증.
3. 영상 클립 UI에 개별/전체 해제 및 AI 수정 모달. 유료 요청은 명시 버튼만, 진행/오류·중복 비용 안내, 같은 작업 새 버전. 공통 아이콘/Modal, 모바일/밝은테마 확인.
4. 독립 코드 검토 후 backend pytest/ruff/mypy와 frontend typecheck/build. 로컬 migration 적용, 유휴 스크립트 워커 정상 재시작만. 실제 유료 호출/영상 생성/커밋/푸시 없음.

결정: 새 계획 전체 재생성 대신 대상 클립만 병합하여 다른 클립 보존을 강제한다. 이미 접수한 영상 생성은 취소하지 않는다. 연속 동작 후속클립은 기존 fingerprint 연쇄로 재검토 처리한다.
