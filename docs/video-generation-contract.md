# 모델별 비디오 클립 계획과 생성 요청

## Runway 연결 · ASA-208

비디오 프롬프트 에이전트의 새 답변은 클립 카드로 표시된다. 확정 씬 이미지를 시작 프레임으로 사용하는 독립 클립 생성 방식이다. 클립을 선택해 유료 생성을 접수하고, 영상 재생 후 선택 확정할 수 있다. 하나의 답변 버전에서 같은 클립을 중복 접수하면 기존 작업을 유지한다. 내용을 바꿔 새 답변 버전을 저장하면 별도로 생성할 수 있다.

로컬 서버의 .env에 ASA_RUNWAY_API_KEY와 ASA_VIDEO_AI_ENABLED=true를 설정하고 API를 재시작한다. 로컬 프로세스로 `uv run --locked --project services/backend python -m asa.video_worker`를 실행한다. 앱 서버와 워커는 같은 DB, workspace, 모델 설정을 사용한다. 배포 시 기존 마이그레이션 명령과 별도 워커 프로세스가 필요하다.

Gen-4.5 기본 프로필은 앱에서 5초와 10초, 720p 세로·가로 생성을 제공한다. 가격은 초당 12크레딧 기준 예상 USD이며 모델 프로필의 usd_per_second로 조정한다. 생성 요청마다 요율을 고정하고 실제 영상을 저장한 경우에만 모니터링에 예상액을 기록한다. 공급자 응답을 잃은 요청은 결과 확인 필요로 남긴다. 키와 유료 실행 옵션은 기본 비활성이다.

[Runway API 안내](https://docs.dev.runwayml.com/guides/using-the-api/) · [요금표](https://docs.dev.runwayml.com/guides/pricing/)

## 처리 흐름

1. 서버 설정의 영상 모델 프로필을 선택한다.
2. 대본·장면·확정 씬 이미지를 전체 문맥으로 분석하여 장면별 클립을 계획한다.
3. 사람에게 원본 장면/대본 구간, 이미지, 동작, 시작·종료 상태, 분할 이유를 보여준다.
4. 생성 전 모델 revision, 허용 길이·비율·음성, 이미지 소유권·확정 상태를 검증한다.
5. 영상 공급자에는 해당 클립의 프롬프트와 시작 이미지, 길이·비율·해상도만 전달한다.

2번의 기존 에이전트 실행에는 opt-in 입력 속성 `x-video-model: true`를 사용할 수 있다.
값은 서버 프로필 key다. 이름이나 지침 문자열로 에이전트 용도를 추정하지 않는다.
프로젝트의 비디오 프롬프트 에이전트는 클립 출력 계약을 사용한다. 실행 시 서버 모델 제한을 별도의 시스템 메시지로 전달한다.
AI의 계획도 제출 전 서버 검증을 통과해야 하며 지침만으로 제한을 보장하지 않는다.

## 모델 프로필

`ASA_VIDEO_MODEL_PROFILES` JSON 설정. 미설정 시 Runway Gen-4.5 앱 기본 프로필을 사용한다.
프로필 하나는 공급자/model/mode/resolution 조합 하나다. API에서 검증한 값만 관리자가 등록한다.

- provider, model, label, revision, enabled
- durations: 실제 허용하는 초 목록. 최대 길이 이하라고 모든 초를 허용하지 않는다.
- aspect_ratios, resolution, max_prompt_chars
- supports_audio, supports_extension (기본 false)
- documentation_url, verified_on

이 설정은 비밀키를 포함하지 않는다. 프로필 변경 시 revision을 바꾼다.
## 준비 API

모든 경로는 로그인 세션이 필요하다. 이미지 조회는 principal.workspace_id로 제한한다.

- `GET /api/v1/video-planning/models`: 활성 프로필과 생성 연결 여부.
- `POST /api/v1/video-planning/durations`: model_key, model_revision, seconds.
  생성 여분 시간을 최소화하고 같은 여분이면 호출 수를 최소화한 길이 조합.
  대사나 동작 경계를 임의로 나누지 않는다. 결과는 AI/사용자의 계획 보조값이다.
- `POST /api/v1/video-planning/prepare`: VideoPreparation 계약 검증.
  clips는 순서대로 빈 구간/겹침 없이 연결되어야 한다. 허용 길이와 원본 편집 길이를
  분리하고 여분은 trim_seconds로 표시한다. 최대 100개 클립/32개 확정 씬 이미지.
  반환 상태는 `prepared_not_submitted`; DB 저장이나 유료 접수가 아니다.

응답의 `reference_snapshot`은 원본 추적용이다. 전체를 영상 API에 보내면 안 된다.
`generation_input`만 공급자 adapter의 입력으로 사용한다. start_image_id는 내부 ID이며
adapter가 workspace 범위에서 파일을 확인해 업로드해야 한다. URL을 그대로 신뢰하지 않는다.
source_excerpt는 아직 원문 일치 검증이 없는 계획 입력이다. UI에서 원문으로 표시하기 전
원본 request/version 및 구간 offset 연결·검증을 추가해야 한다.

## 실행 정책과 후속 확장 기준

- 승인한 plan revision, 모델 프로필, 원본 request/answer version, 이미지 버전을 접수 때 고정한다.
- 큐 키는 workspace/plan revision/clip ID/작업 종류/idempotency key. 사용자 재생성과
  네트워크 재전송은 구분한다. 중복 클릭만으로 추가 비용이 발생하지 않게 한다.
- 공급자 job ID를 저장하고 폴링은 제출과 분리한다. 제출 응답이 유실되면 unknown으로
  표시하고 무조건 재제출하지 않는다. 워커 재시작으로 exactly-once를 주장하지 않는다.
- queued/submitting/running/review/approved/failed/unknown/cancelled 상태를 제공한다.
  취소 가능 여부와 이미 공급자에게 제출된 요청의 과금 가능성을 구분한다.
- 같은 씬의 독립 클립은 이전 클립을 자동으로 기억하지 않는다. 연결 방식은 기준 이미지,
  이전 마지막 프레임, 공급자의 native extension으로 구분한다. 후자의 두 방식은
  선행 클립 완료 후 실행하며 지원되는 adapter에서만 허용한다.
- 모델을 바꾸면 새 계획을 검증한다. 기존 확정 영상은 삭제하거나 새 모델 결과로 표시하지 않는다.
- 공급자 asset 재사용은 저장·전송량 절약이다. 모델이 전체 이야기를 기억하거나 토큰 과금이
  자동 면제된다는 뜻은 아니다. 호출별 실제 청구 단위에 따라 비용을 기록한다.
- 관리 UI는 제목·개수 왼쪽, 선택 생성·확정 오른쪽, 상태 요약과 동일 크기 클립 카드.
  상세에는 원본 대본/장면, 확정 씬 이미지, 생성 프롬프트, 영상·버전·검수·경과 시간을 둔다.
  이미지 전용 API를 우회 재사용하지 않고 영상 작업 adapter를 구성한다.

## 검증

사용자의 테스트 보류 요청에 따라 pytest/ruff/mypy/typecheck/build 및 실제 API 호출을
실행하지 않았다. 클립 카드·실제 브라우저·워커 실행은 미검증이다.
