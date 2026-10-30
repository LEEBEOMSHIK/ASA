# 후속 작업 상태 Implementation Plan

Goal: AI 응답 완료와 사용자 확정을 분리하고 최근 작업에서 재개한다.
Architecture: 업무 상태는 저장된 작업/확정 기록에서 계산한다. 공통 progress 계약(kind, label, source_version, items, counts, status, resume_anchor)을 사용하고 캐릭터 이미지 adapter를 첫 구현으로 둔다. 제외 선택은 workspace/request/answer version/kind/item 단위의 공통 테이블에 저장한다. 이후 다른 산출물도 adapter로 확장한다. 현재 미구현 매체의 실행을 주장하지 않는다.
Tech Stack: FastAPI/PostgreSQL/Next.js, 기존 SSE snapshot.

- [x] 상태 집계 단위 테스트: 생성중/검토/미생성/확정/제외/실패, 재생성 재개, 전체 제외 별도 상태.
- [x] 공통 계약 및 이미지 adapter, 최신 답변 기준 history/detail 집계. 이미지를 열지 않은 답변도 미생성으로 표시.
- [x] workspace 격리 및 활성 작업 보호를 포함한 제외/복원 API. 생성/확정 경로에서도 제외 검증.
- [x] 최근 작업/상세에 개수와 재개 표시, SSE 반영. 제외 카드 축약/복원, 미완료 항목 바로가기.
- [x] DB 회귀 테스트, 전체 pytest/ruff/mypy/typecheck/build, 실제 브라우저 검증. 유료 호출 없음.

완료 조건: 필요한 항목이 하나 이상 있고 모두 확정이며 진행/미확정 항목이 없을 때만 작업 완료. 모두 제외는 '대상 없음'. 기존 답변의 프로젝트와 제외/확정은 버전별 보존. 현재 최신 답변을 최근 작업의 기준으로 삼음.
