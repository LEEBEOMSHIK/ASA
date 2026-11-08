# 목소리 선택 후 제작

사용자 승인: 캐릭터 설정에서 내레이터·각 캐릭터의 목소리 설정 → 샘플 생성/청취 → 선택 → 대사 생성/검토. 씬의 기존 음성은 시간 측정용이며 최종 확정·합성에서 제외한다.

설계: speech job input의 purpose로 production/timing/sample 구분. 샘플은 기존 워커·과금 제한·멱등 계약을 재사용하고 고정 문구를 읽는다. Speaker에 선택한 sample_job_id를 보존, 서버가 같은 workspace의 선택 완료 샘플과 목소리 설정 일치를 검증한다. 목소리 변경 시 샘플 선택을 다시 요구한다. 실제 청취의 자동 판정은 불가능하며 재생 후 사용자가 선택한다. 기존 자료/파일은 보존한다.

1. 시간측정 확정 차단/샘플 fingerprint/선택 전 생성 차단 회귀 작성.
2. audio_contracts/service/routes/worker에 목적·샘플·선택검증 연결.
3. AudioProduction의 내레이터/캐릭터 샘플 UI 및 WorkSpeechReview의 시간측정 표시.
4. 알려진 시간측정 작업의9음성만 목적 분류(백업/내용·파일 보존).
5. pytest/ruff/mypy/typecheck/build, 실제 UI 양테마·좁은화면 및 간격 확인. 새 유료호출/사용자 확정 없음.
