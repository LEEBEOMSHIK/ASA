# 웹 검색과 결과 항목 연결 — 2026-10-28

## 사용 방법
1. 자동화 빌더의 ASA 도구에서 **웹 검색**을 추가한다. 검색어와 결과 개수(1~10)를 연결한다.
2. **결과 항목 선택** 블록을 추가하고 검색 블록 다음에 연결한다.
3. **첫 검색 결과의 제목·URL·요약 설정**을 누르거나, 항목 이름·자료형·가져올 값을 직접 지정한다.
4. 다음 AI 요청의 입력 출처를 결과 항목 선택 블록으로 지정하고 `snippet` 등 필요한 항목을 선택한다. 직접 AI 요청은 글 입력이므로 전체 객체 대신 글 항목을 연결한다.
5. 연결 테스트에서 **검색 샘플 채우기**를 누르고 샘플로 흐름을 테스트한다. 검색 API나 AI API를 호출하지 않는다.

검색 출력은 `results: [{title, url, snippet}]`이다. 경로 `results.0.title`은 첫 결과 제목이다. 결과 항목 선택은 원래 값을 가져와 이름을 붙이는 기능이며 AI가 새 답변을 작성하는 기능이 아니다. 여러 결과는 `results`를 반복 블록에 연결한다. 검색 결과가 비었는데 첫 항목을 선택하면 오류로 멈춘다. 빈 결과는 조건 분기 또는 반복으로 처리한다. 자동 대체값·임의 JSON 변환·사용자 HTTP 요청·도메인 필터는 이번 범위에 없다.

## 실제 실행 설정
서버 `.env`의 `ASA_SEARCH_PROVIDER=brave`, `ASA_SEARCH_ENABLED=true`, `ASA_SEARCH_API_KEY`를 설정하고 API와 자동화 워커를 다시 시작한다. 키는 서버에서만 읽는다. 실제 검색은 공급자 요금이 발생할 수 있다. 설정되지 않으면 실행 등록을 거부한다. 저장된 자동화의 버튼 실행과 예약 실행 모두 동일한 워커 경로를 사용한다.

Brave 공식 API: https://api-dashboard.search.brave.com/api-reference/web/search/get
고정 HTTPS 호스트를 호출하며 리다이렉트·자동 재시도·검색된 URL 크롤링은 하지 않는다. 응답은 2MB, 결과는 최대 10개로 제한한다. API 오류 원문을 사용자에게 반환하지 않는다. 검색 결과는 외부 자료이므로 후속 에이전트 지시사항으로 신뢰해서는 안 된다.

검색과 AI는 기존 `ASA_AUTOMATION_DAILY_AI_CALLS` 한도를 공유하며 그래프 실행당 외부 호출 최대 20회다. 호출 의도를 DB에 먼저 기록하고 불확실한 실패는 needs_attention으로 남긴다. exactly-once는 보장하지 않는다. 운영 Compose의 기존 worker는 점검 CLI이므로 운영 자동화 워커 배포 완료를 뜻하지 않는다.

## 검증 범위
검색 어댑터는 HTTP 모의 응답으로 검증하며 실서비스 키나 유료 호출을 사용하지 않았다. 샘플 연결·빈 결과·타입 불일치·인증 비활성화·API 실패/잘못된 URL의 오류 숨김을 테스트한다. 실제 외부 API, 예약 검색 실행과 워커 복구 통합 검증은 미검증이다.

## 참고했던 Alli 자료
- https://guide.allganize.ai/alli/assign-variables-to-variables/
- https://guide.allganize.ai/alli/list-variables-file-variables/
- https://docs.allganize.ai/allganize-alli-works-userguide-en/about-alli-works/use-deep-research
