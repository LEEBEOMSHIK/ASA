# 목표시간 자동 채움 제거
사용자 승인: 목표까지 무음 채우지 않고 부족분 표시, 행동/반응 시간근거 공통지침.
1. audio_timing summarize에서 target 하한 제거, 완료시 shortfall 반환. 회귀로 29.5/30 확인.
2. SceneTimingPlan planned_duration을 목표와 별개로 전달, timing_preview_seconds에 계획길이 저장; finish_timing은 계획끝만 사용해 trailing 계산. 누락시 마지막 발화끝으로 대체.
3. SceneTimingReview에서 구성 길이와 부족분/측정중 구분. 기존4열 토큰 유지.
4. 공통 pacing 문서/템플릿/live 씬 지침 revision검증 저장. 이전답변/음성 보존.
5. 전체pytest/ruff/mypy/typecheck/build, live v4 29.5초와 간격/양테마/좁은화면 점검.
