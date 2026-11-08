# 목소리 선택과 시간 측정 음성 구분

- 승인 설계: 캐릭터 설정의 나레이션/캐릭터 설정 저장→샘플 생성·재생→목소리 선택→비디오 작업에 가져오기→대사 생성/검토/확정. 기존 오디오 워커와 호출 제한·작업 지문·CSRF/workspace 검증 재사용.
- sample_job_id와 현재 설정 일치 검증. 새 제작 음성은 선택한 샘플 없이 접수·워커 실행·최종 확정·합성 불가. 역할/이름으로 목소리 품질을 보장하지 않으며 사용자가 샘플로 결정한다. UI에서 샘플 ended 후 선택 활성화; 서버가 실제 청취를 증명한다고 주장하지 않는다.
- 기존 이루리 씬 v2의9음성을 백업 후 timing으로 분류. 정상8/전사불일치1. 이미 approved인1개 포함 파일sha/status/원문 보존, 목적과 목적별 지문만 갱신. v3 계보에서도 제작0/시간측정8/제외1 및 확정버튼0 확인. 백업 `.local/scene-tts/before-purpose-classification.json`.
- 초기 단위 회귀2건 실패 확인 후 구현. mock 외부 음성으로 샘플 대기/생성/선택/제작/설정변경 무효화/시간측정 차단 및 기존 음성 회귀7건 통과. 새 유료 API 호출·사용자 목소리 선택/저장·확정 없음.
- Chrome CSS1600px 양테마에서 캐릭터와 나레이션 별도 영역·비활성샘플·최초설정 저장 버튼 확인. input/select 높이43.99px, 같은 행 시작 y동일, fieldset/샘플 gap16px. 기존 사이드바 폭 유지. 좁은 CSS433px에서1열302.465px/문서가로넘침없음. 모바일 screenshot timeout으로 시각검증 미완료. API비활성 상태라 실제 새 샘플의 재생/선택 완료 UI는 미검증(서버흐름은 mock검증).
- 화면 증거 `.local/diagnostics/voice-selection/character-dark.png`, `character-light.png`, `timing-dark.png`. 테마/viewport 복원, 기존 이루리v3열어둠.
- 최종 전체 pytest462 통과(174.83초, exit0 종료후오류없음). Ruff0/mypy82/typecheck/build16routes/diff-check 통과. 이전 작업 변경 보존, 커밋·푸시 없음.
