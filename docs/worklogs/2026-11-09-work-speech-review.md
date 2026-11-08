# 기존 작업의 대사별 음성 확인

- ScriptStage 답변 아래 공통 WorkSpeechReview 추가. 화자, 대사, 실제 길이, 배정 시간, 영상 구간, 목소리, 플레이어, 개별 확정 제공.
- 선택 버전에서 base_version 계보의 가장 가까운 음성 설정/작업을 찾는다. 타 workspace·분기·미래 버전은 가져오지 않고, 자체 설정(빈 설정 포함)이 있으면 거기서 멈춘다. 원본 음성을 복제하지 않으며 출처 버전을 표시한다.
- 기존 승인 API의 원문/목소리 fingerprint, 전사 오류, 실제 길이 검증 및 CSRF를 유지한다. 제외 결과는 사유와 전사를 접힌 영역에 보존하며 확정 버튼을 제공하지 않는다.
- 실제 이루리 씬 작업에서 v3→v2 정상8개/제외1개, v2 동일 결과, v1 음성 없음 확인. 첫 음성이 3.10초 끝까지 재생되고 media 오류 없음 확인. 음성 품질의 청각 평가는 하지 않았다. 사용자의 음성·답변·지침을 저장하거나 확정하지 않았다.
- UI: Chrome CSS1600px 밝음/어둠, 카드/컨트롤 gap16px 및 재생/확정 버튼 세로 중심 동일 확인. 공통 Card height100%가 중첩 카드에 적용되어 아래 카드와 겹치던 원인을 해당 내장 영역 height:auto로 수정. 부모 경계 안에 포함됨 확인. 기존 사이드바 폭 유지.
- CSS433px 좁은 화면에서 문서 가로 넘침 없음, 정보2열 전환 확인. screenshot CDP timeout으로 모바일 시각 검증 미완료. 양테마 증거 `.local/diagnostics/work-speech-review/{dark,light}.png`. 테마/viewport 복원, v3 열어둠.
- 전체 backend pytest459 통과(170.29초), Ruff 통과, mypy82 통과, frontend typecheck 통과. 확정 성공/실패·권한·계보·변경설정·시간초과는 격리 DB 테스트로 검증. 실제 사용자 데이터의 확정/오류 상태를 강제로 만들지 않았다.
- 유료 API 호출 없음. 커밋/푸시 없음. 이전 작업 변경 보존.
- 최종 frontend build16 routes 통과. 첫 sandbox 빌드의 standalone 복사 EPERM 경고는 권한을 갖춘 재실행에서 해소됨. git diff --check 통과.
