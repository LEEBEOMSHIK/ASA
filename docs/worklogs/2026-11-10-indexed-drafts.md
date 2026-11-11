# IndexedDB 비동기 임시 저장

- IndexedDB `asa-work-drafts` / `drafts`를 기본 저장소로 사용한다. 기존 scope/key를 그대로 사용해 사용자·workspace·작업·버전·신규 draft UUID 경계를 유지한다.
- 입력 후400ms debounce로 저장한다. IndexedDB request 성공이 아니라 transaction complete를 저장 완료로 표시한다. 입력마다 localStorage 본문을 쓰지 않는다.
- beforeunload/pagehide/visibility hidden/unmount에서는 미완료 최신 레코드만 localStorage 복구 저널에 동기 보존하고 비동기 저장도 시도한다. 종료 이벤트에서 IDB 완료를 기다릴 수 없기 때문에 복구저널을 유지한다. 다음 로드에서 IDB/기존 localStorage/복구저널 중 최신 유효 레코드를 선택하고 IDB commit 이후만 이전본을 지운다.
- 정상 저장/초안 삭제는 시각이 포함된 삭제표식을 사용한다. 늦게 완료된 이전 쓰기가 새 입력이나 삭제를 덮어쓰지 않도록 트랜잭션에서 시각을 비교한다. 복원 대기 중 입력과 작업 전환 후 늦은 복원도 덮어쓰지 않는다.
- IndexedDB 쓰기 실패는 복구저널로 보호하며, 둘 다 실패하면 저장되지 않았음을 안내한다. 브라우저 강제 종료/OS 강제 종료·저장소 삭제·용량 초과에서 무조건 무손실이라고 보장하지 않는다. 같은 브라우저의 임시저장이고 기기간 동기화는 아니다.
- 유효기간30일 유지. 이관은 해당 초안을 열 때 수행한다. 비밀키/파일 바이너리/인증토큰을 추가 저장하지 않는다.

## 검증
- Node5테스트: 빠른 입력 debounce/최종 flush, 읽기 중 입력/종료, 삭제 후 되살아남 방지, 세션 분리/IDB 쓰기 실패 복구, 최신 레코드·삭제·잘못된/만료 레코드 선택 통과.
- 실제 Chrome/IndexedDB: 생산 storage 모듈을 임시 검증 페이지에서 실행, 기존 localStorage 텍스트 이관 및 commit후 삭제/IDB 재조회, 종료 복구저널 최신값 반영, B작업 보존 모두 pass=true. 검증키와 임시 public 페이지2개 정리.
- 실제 캐릭터 에이전트 새 입력 A 작성 직후 같은 호출에서 reload→마지막 전체문구/복원안내 확인. 동일 에이전트 새 B는 다른UUID/빈입력, A재방문은복원. 임시 입력 지우기→즉시 reload 후 빈입력 확인. 정식 작업 저장·AI호출 없음.
- 증거 `.local/diagnostics/indexed-draft-restore.png`. dark1600 화면. 기존 UI 구조 유지, 별도 밝은/좁은화면 및 실제 음성/답변 편집 화면의 모든 종료조합은 이번 미검증. 강제프로세스종료/저장공간고갈은 실제브라우저 미검증.
- 전체 pytest473(171.02초), Ruff/mypy85/typecheck/build/diff-check 통과. 커밋/푸시 없음.
