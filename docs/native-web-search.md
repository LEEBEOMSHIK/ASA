# OpenAI / Claude 내장 웹 검색

## 사용
자동화 빌더에서 AI에게 요청 → AI 서비스/모델 선택 → **웹 검색 사용**을 켠다. 검색 답변은 하나의 글로 받고, 후속 블록에 답변과 출처 링크를 함께 전달한다. 미지원 모델 경고가 나오면 서버 설정을 먼저 확인한다. 공급자 변경 시 검색 옵션은 꺼지며 새 공급자에 맞게 다시 선택한다.

서버 `.env`에 기존 모델 목록/키 외에 검색 지원을 확인한 모델 ID 목록을 등록한다.
- OpenAI: `ASA_OPENAI_WEB_SEARCH_MODELS` (JSON 문자열 배열, `ASA_AI_MODEL`/`ASA_AI_MODELS`의 부분집합)
- Claude: `ASA_ANTHROPIC_WEB_SEARCH_MODELS` (`ASA_ANTHROPIC_MODELS`의 부분집합)

설정 후 API와 자동화 워커를 재시작한다. 모델명은 하드코딩하지 않는다. 서버 목록은 관리자가 확인한 지원 목록이며 공급자 계정 권한의 실시간 조회를 대신하지 않는다. 모델/키 미등록이면 실제 실행할 수 없다. 기존 `ASA_AUTOMATION_AI_ENABLED` 활성화 조건도 적용한다. 샘플 테스트는 외부 호출 없이 진행한다.

## 실행 계약
- OpenAI: LangChain → Responses API `web_search`, `store=false`, `max_tool_calls=1`.
- Claude: LangChain → Messages API `web_search_20250305`, `max_uses=1`. 코드 실행을 포함하는 동적 필터링 도구는 사용하지 않는다.
- 각 응답에 검색 도구 호출 상한 1회를 요청한다. API 요청 수와 공급자가 청구하는 검색 쿼리/토큰 수는 동일하다고 보장하지 않는다. 무료 기능이 아니다.
- 모델이 검색 필요성을 판단한다. 검색 호출이 없으면 결과에 **웹 검색 미사용**을 표시한다. 검색 호출을 강제하는 모드는 아니다.
- 출처 메타데이터를 본문 인용 위치(OpenAI) 또는 해당 글 블록 끝(Claude)에 링크로 넣는다. 자동화 결과/샘플 화면은 안전한 HTTP(S) 링크만 클릭 가능하게 표시하며 모델 HTML을 실행하지 않는다. 출처 없는 응답에는 출처 없음 표시.
- 검색 자료를 지시문으로 신뢰하지 않도록 모델에 안내한다. 사용자 코드 실행/임의 도구 호출 권한은 추가하지 않는다.
- 완료되지 않은 응답, Claude pause_turn, 검색 도구 내부 오류는 완료로 처리하지 않는다. 자동 재시도/후속 유료 요청을 하지 않고 기존 needs_attention 경로로 중단한다. 중간 답변/공급자 오류 원문은 출력하지 않는다.
- 실행과 예약에 검색 옵션을 스냅샷으로 고정한다. 워커는 지원 목록을 다시 확인한다. 기존 외부 호출 의도 기록·최근24시간 한도·그래프 실행당 상한·승인 재개를 공유한다. exactly-once는 보장하지 않는다.

## 범위
직접 AI 요청에 제공한다. 등록 에이전트 자체의 설정/기본 대본 생성은 이번 범위에서 바꾸지 않는다. 글 목록/임의 JSON 검색 답변 계약, 별도 출처 객체 포트, 도메인 필터, 검색 강제 실행, 중단 응답 자동 이어받기는 후속이다. 기존 Brave 검색 도구도 계속 독립적으로 사용할 수 있다.

## 공식 계약
- https://developers.openai.com/api/docs/guides/tools-web-search
- https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool
설치된 OpenAI/Anthropic SDK의 HTTP 모의 전송으로 실제 직렬화·응답 변환 경로를 검증한다. 실제 유료 요청은 하지 않는다.
