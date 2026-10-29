# AI Shorts Studio 개발 규칙

- 작업 전 WORKBOARD.md, docs/architecture.md, docs/local-development.md를 읽는다.
- 개발은 로컬 프로세스로 실행한다. Docker는 운영 배포 구성에만 사용한다.
- AI 생성은 외부 API로 수행한다. 로컬 모델을 필수 의존성으로 추가하지 않는다.
- 모델 공급자와 모델명은 설정으로 관리한다. 비밀값을 클라이언트, 로그, Git에 넣지 않는다.
- API는 입력·권한 검증, 서비스는 업무 규칙, 워커는 장시간 작업을 담당한다.
- LangGraph는 흐름·승인·체크포인트, LangChain은 모델 연결·출력 계약을 담당한다.
- 워커 재시작과 외부 호출 중복을 고려한다. 체크포인트만으로 exactly-once를 주장하지 않는다.
- 모든 업무 데이터는 workspace 경계를 갖는다. SaaS 공개 전 인증과 격리 검증이 필수다.
- UI는 apps/web/app/tokens.css와 공통 components/ui.tsx를 사용한다.
- 상태는 텍스트로도 표현하고, 키보드 포커스·입력 label·오류 안내를 유지한다.
- 작업 시작·종료 시 WORKBOARD.md를 갱신하고 실제 검증과 미검증을 구분한다.
- 사용자 자료, 모델 가중치, 생성 영상, 캐시, 비밀값은 커밋하지 않는다.
- 실제 유료 AI 호출과 외부 게시를 단위 테스트에서 실행하지 않는다.
- 완료 전 backend pytest/ruff/mypy, frontend typecheck/build를 실행한다.
- 다른 작업의 변경을 덮어쓰지 않는다. 커밋·push는 요청 범위를 확인한다.
