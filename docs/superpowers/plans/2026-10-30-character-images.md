# Character reference images implementation plan

**Goal:** 대본과 장면에서 캐릭터 설정을 만들고 사용자가 기준 이미지를 생성·수정·확정한다.
**Architecture:** 기존 등록 에이전트/고객 요청 큐로 캐릭터 설정을 생성한다. 검증된 답변을 캐릭터 프로젝트로 가져온 뒤 이미지 전용 영속 큐/워커가 OpenAI Images API를 호출한다. 워크스페이스별 인증된 이미지 응답, 불변 이미지 버전, 명시적 확정을 사용한다.
**Tech stack:** FastAPI, PostgreSQL, existing LangChain agent worker, OpenAI SDK, Next.js.

- [x] 이미지 도구 요청/응답·요율 계산 테스트 → 구현. 모델은 서버 설정, 재시도0.
- [x] 프로젝트/작업 DB·권한 API·전용 워커. 중복 UUID, 동시 실행, 재시작 후 불확실 상태 테스트.
- [x] 등록 가능한 캐릭터 설정 에이전트 템플릿. 캐릭터 사실/제안/장면 연결/이미지 지침 포함.
- [x] 캐릭터 화면: 기존 자동화 결과 가져오기 또는 원문 입력, 설정 확인, 개별 생성/수정/확정과 이력.
- [x] 실제 키로 설정 생성→이미지1장→수정1장 검증, 사용량/비용/기준 버전 확인.
- [x] pytest/ruff/mypy, frontend tests/typecheck/build, 실제 화면 확인 및 문서 갱신.

Ruling: 최초 버전은 이미지를 workspace-scoped DB bytea로 보관한다. 외부 URL을 가져오지 않아 SSRF를 피하고, 운영 자산 규모 증가 전 object storage로 옮긴다. 이번에는 설명 또는 이 작업에서 만든 이미지를 기준으로 삼는다.
Ruling: 이미지 도구는 전용 큐에서 실행한다. 자동화 블록의 동기 실행으로 장시간 호출/승인을 우회하지 않는다. 캐릭터 에이전트 답변→이미지 도구 입력 연결은 캐릭터 화면에서 명시적으로 수행한다.

Review: 네 가지 중요 UI 복구/상태 문제 수정 및 재검토. 상세 검증은 작업 기록 참고. 실제 사용자 확정은 남기고 격리 DB에서 확정 동작 검증.
