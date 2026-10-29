# ASA-036 연결 UX와 작업 종류/모델 선택

사용자 요청: 연결 의도/대상 명확화, 부드러운 이동/연결선, 기본 최종 결과 하나 유지(팔레트 제거), 직접 AI/ASA 도구/사용자 에이전트 구분과 맞춤 설정, 직접 AI 모델 선택.

기존 그래프/실행 구조를 확장한다. 새 라이브러리 없이 DOM/SVG 포인터 편집을 개선하며 진행 중 연결선과 대상 강조/취소를 제공한다. 최종 결과는 기본1개, 삭제/추가 불가. 기존 다중 end 데이터는 자동 삭제하지 않고 검증 안내. 직접 AI 모델은 서버 등록 허용 목록에서 선택한다. 비밀값/임의 endpoint는 노출하지 않는다. 현재 공급자 어댑터(openai) 범위 유지.

## 계약
- GraphNode.model?: string; 없으면 서버 기본 모델.
- Settings.ai_models: list[str] = []; ASA_AI_MODELS JSON 배열. ai_model 기본값과 함께 허용 목록.
- GET /registry/ai-models (기존 API prefix 확인): 인증, {models:[{id,label,provider}],default_model:string|null,configured:boolean}. 프런트 api() 기준 /ai-models.
- 선택값 allowlist 검증, 실행 manifest에 고정, worker가 선택 모델 호출. 허용 목록에서 사라진 모델은 예약/실행 차단. 기본값 저장본의 기존 동작 보존.
- 단일 end를 신규 저장/실행 검증, 기존 저장 데이터 무삭제.

## 작업
- [x] Backend: 허용 모델 설정/catalog/그래프 필드/스냅샷/워커와 회귀 테스트.
- [x] Frontend: 연결 미리보기/대상/취소/포트 문구, 드래그 안정화/경로, 팔레트 세분화/서로 다른 입력, 모델 목록/단일결과.
- [x] 통합: 필수 검사 pytest/ruff/mypy/typecheck/build, 브라우저 직접 구성/연결/모델/저장 확인, docs/WORKBOARD 갱신. 실제 유료 호출 금지, commit/push 금지.
