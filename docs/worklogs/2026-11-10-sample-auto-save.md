# 맞춤 샘플 자동 저장 후 생성 (2026-11-10)

- 원인: AudioProduction 샘플 버튼은 dirty/revision0에서 disabled였고 별도 save를 요구했다.
- 나레이션/캐릭터 공통 createSample은 변경 설정 또는 최초 설정을 PUT한 뒤 응답 revision으로 sample POST한다. 변경이 없으면 불필요한 PUT을 생략한다.
- 저장 실패 시 POST하지 않고 입력을 유지한다. POST 실패 시 저장 상태는 유지하고 해당 화자 버튼 아래 오류를 표시한다. POST 접수 뒤 GET 실패는 재생성 오류로 표시하지 않고 접수 완료/갱신 대기 안내를 표시한다.
- 저장 중/생성 요청 중/워커 대기·실행 상태를 표시한다. useRef 잠금으로 중복 클릭을 막고 요청 중 편집을 비활성화한다. 자동 저장은 나레이션을 접지 않는다.
- 별도 설정 저장은 선택 사항으로 유지한다. 현재 음성 설정 전체(나레이션·캐릭터)가 함께 저장되는 기존 계약을 유지한다.
- 단위 테스트 3건: 저장 완료 후 새 revision 사용, 저장 실패 시 생성 미호출, 변경 없는 경우 저장 생략 및 생성 실패 전달. 실제 AI 호출 없이 검증.
- 실제 Chrome dark desktop: 사용자의 기존 말투 초안 보존, 나레이션·캐릭터 생성 버튼 enabled 확인. DOM grid gap16px/action gap12px/align center 확인, screenshot .local/diagnostics/sample-auto-save.png. 사용자 설정 저장/샘플 생성은 하지 않았다.
- 미검증: 실제 유료 샘플 생성, 브라우저에서 저장/요청 실패·진행 상태, 밝은 테마·좁은 화면 시각 상태. 해당 분기는 단위 테스트/코드 검증 범위이며 시각 검증 완료를 주장하지 않는다.
- typecheck/build/Ruff/mypy(85 files)/diff-check 통과. 전체 pytest 결과는 WORKBOARD 참조.
