# Video voice directions implementation plan

Goal: 캐릭터/공통 나레이션은 특징을 저장하고 영상 모델이 대사와 함께 해석한다.
Architecture: 기존 audio_settings의 instructions/language/speed를 재사용하고 영상용 사용 여부를 추가한다. 별도 PATCH 성격의 voice-directions API가 기존 TTS 설정·음성 자산을 보존한다. 선택된 씬의 실제 캐릭터 참조로 저장 특징을 읽어 비디오 시도에 snapshot을 남긴다. 영상 생성 시 같은 snapshot과 답변의 cues를 조합하며 길이·권한·모델 오디오 지원을 검증한다.
Spec: 사용자의 직전 승인 및 대화에서 합의한 설명→영상 프롬프트→영상 확인 흐름. 사이드바 폭 유지, 기존 데이터 삭제 금지, 시간 측정 TTS 유지.

- [ ] 계약/회귀: 특징 저장의 revision/workspace 검증, 기존 자산 보존, clip별 발화와 상대 시간, 오디오 지원/길이 제한 테스트.
- [ ] backend: voice_directions.py, audio_routes.py에 부분 저장; script_stage.py 요청 snapshot; providers.py 지침 전달; video_jobs.py/ video_planning.py 생성 입력과 조회 미리보기 연결.
- [ ] frontend: voice-directions.tsx 공통 입력 UI, character-studio 연결, video-clip-manager 전달 내역 표시. 이전 음성은 접힌 보존 영역에서 재생. 샘플 생성/기본 음색 선택은 새 캐릭터 흐름에서 제거.
- [ ] 검증: pytest/ruff/mypy, typecheck/build. 밝음/어둠 desktop/narrow 브라우저 및 computed 간격 확인. 유료 호출은 실행하지 않는다.
- [ ] WORKBOARD/문서에 실제 결과와 미검증을 기록. 커밋/푸시는 이번 요청에 없음.

Review focus: 별도 작품 화자 ID 충돌은 실패로 안내; 미설정 목소리는 만들어내지 않기; narration 미사용은 대사에서 제외; 재요청은 최신 설정, 대기/기존 영상은 불변; 기존 별도 오디오 합성은 명시적 이전 기능으로 보존.
