# 작업 상세 리소스 경로

- UI 작업 상세 주소를 `/works/{requestId}`, 특정 답변 주소를 `/works/{requestId}/answers/{version}`으로 전환했다. 조회 API의 GET은 REST 조회 방식에 맞으므로 유지한다.
- Next 동적 페이지와 UUID/양의 정수 경로 검증을 추가했다. 최근 작업·생성 완료·답변 버전 선택·보관함 원본 링크·관리 링크와 backend library origin을 새 주소로 통일했다.
- 기존 `/?request=...&answer=...`는 인증/도구 로드 후 replaceState로 정규 경로로 바꿔 같은 내용을 표시한다. 로그인 링크는 현재 상세 경로를 next로 전달한다. 새 작업 이동은 `/`로 복귀한다. 에이전트/다시작업 입력 query는 이번 상세 리소스 변경 범위 밖이다.
- IndexedDB 초안 키는 URL이 아닌 기존 사용자/workspace/request/version/draft ID를 그대로 사용한다. 사용자 입력과 저장 자료 변경 없음.
- Node 경로 테스트: 상세/답변 경로 생성·기존 링크 파싱 일치·잘못된 UUID/버전/경로 거절 통과.
- Chrome 실제 캐릭터 작업 클릭→새 path, reload→동일 작업 복원. 기존 answer=1 주소→새 답변경로, 해당 경로 reload→상세 유지. 새 작업→root, back→답변경로/상세 복원 확인. 증거 `.local/diagnostics/restful-work-detail.png`.
- 레이아웃/CSS 변경 없음. 로그인 만료 흐름, 권한없는 작업, 보관함 모든 링크 클릭, 밝은/좁은화면은 이번 실브라우저 미검증. API 권한 계약 변경 없음.
- pytest473(172.11초), Ruff/mypy85/typecheck/최종build/diff-check 통과. AI호출/사용자저장/커밋·푸시 없음.
