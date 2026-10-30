# 이미지 모델 선택 안내

- 일괄 캐릭터 생성과 캐릭터별 이미지 생성에서 공통 ImageModelSelect 사용.
- Sunburst는 복잡한 요청의 품질 우선, Flare는 품질을 확인하며 속도 개선을 비교할 선택으로 설명.
- 선택 즉시 설명 변경, 접는 비교 영역에 표준 토큰 단가/현재 생성 설정/확인 날짜/공식 출처 제공.
- 미등록 모델은 비교 정보 없음으로 안내. 모델 ID와 API 요청 값은 유지.
- 공식 문서 확인일: 2026-10-31.
  - https://developers.openai.com/api/docs/guides/image-prompting#migrate-an-existing-workflow
  - https://developers.openai.com/api/docs/pricing
- 실제 브라우저에서 두 선택 영역 표시, Flare 전환 후 안내 변경, 비교 펼치기를 확인. Sunburst 선택으로 복원.
- 캡처: .local/verification/image-model-guide.png (커밋 제외).
- 새 유료 이미지 호출이나 두 모델의 실측 품질/속도 비교는 수행하지 않음.

- 검증: backend pytest 186 passed (211.01초), ruff/mypy 통과; frontend 32 tests/typecheck/build 통과.
- git diff --check에는 기존 agent-run-preview.tsx, tools/catalog.py의 EOF 빈 줄 경고가 있으며 이번 변경 대상이 아니어서 유지.
