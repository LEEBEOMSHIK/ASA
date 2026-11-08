# 목표 무음패딩 제거 검증

목표와 구성 길이를 분리했다. summarize는 계획끝/실측끝만 사용하며 목표를 하한으로 쓰지 않는다.
측정 누락이 없을 때 shortfall을 계산하고 화면에 부족초를 안내한다. 계획된 여백은 보존한다.
SceneTimingPlan에 planned_duration을 추가하고 timing_preview_seconds에 전달한다.
finish_timing의 뒤 여백도 목표가 아닌 계획끝에서 계산한다. 필드 없는 새 계획은 마지막 발화끝을 사용한다.

공통 행동·반응별 시작/끝/초수/동작/근거/동시진행 규칙을 pacing 문서, scene-planner 템플릿,
현재 씬 구성 에이전트 revision10에 반영했다. 기존 답변·음성은 변경하지 않았다.
워커 유휴 확인 후 정상중지/재시작하여 script/audio running 확인. 새 유료 호출 없음.

검증: 전체pytest468통과172.32초, 이후 계획끝 없음/짧음/김으로 확장한 큐 통합3케이스 모두통과.
Ruff0/mypy84/typecheck/build통과. 변경 테스트의 줄길이 오류1건 수정 후 Ruff 재확인.
실제 v4 화면 구성29.5초/발화14.4초/여백15.1초/부족0.5초, 플레이어duration29.5 확인.
1600px 밝음/어둠 화면, 동일4열 gap16, 부족안내 위아래15.998px 확인.
CSS433px2열/가로넘침없음 DOM확인, 좁은화면 캡처 미검증. 테마/viewport 복원.
증거 .local/diagnostics/timing-shortfall/dark.png 및 light.png.
새 지침으로 AI를 다시 생성한 연출품질은 미검증이며 기존v4의 계획여백을 자동감축하지 않는다.
