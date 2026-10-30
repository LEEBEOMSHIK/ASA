# OpenAI 공식 집계

합의 범위: 기존 /monitoring에 요청 추적과 공식 집계 구분. Codex/잔액 입력/잔액 추정 제외. 결제 화면 링크 제공.

1. 별도 SecretStr Admin key, 선택적 OpenAI project ID 서버 설정. 로컬 소유자 및 설정 workspace만 공식 계정 데이터 접근. 일반 admin은 ASA ledger만 접근.
2. 공식 costs/completions usage 페이지네이션, USD Decimal 합계, UTC 오늘/월/최근7·30일. 비용과 텍스트 토큰의 수집 범위를 명시.
3. 앱 인스턴스 메모리 캐시15분, 실패 시 이전 정상 데이터와 오류/오래됨 표시. 잠금으로 동시 갱신 통합, 최소30초 재조회 간격. 재시작 시 재조회. 영구 스냅샷/백그라운드 스케줄러는 이번 범위 아님.
4. 기존 UI 공통 컴포넌트와 2개 탭. 보이는 동안15분 갱신, 요약/접이식 일별·모델 상세. 숫자미지원과 실제0 구분.
5. MockTransport로 페이지네이션/집계/권한/미설정/실패캐시 검증, 기존 전체검사, 브라우저 미연결 화면 확인. 실제키 없는 상태를 실제연동 성공으로 주장하지 않음.

공식 근거: https://developers.openai.com/cookbook/examples/completions_usage_api
