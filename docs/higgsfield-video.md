# Higgsfield 영상 연결

기존 Alibaba WAN 연결과 별도 제공자로 관리한다. 최초 지원 프로필은 `hf-wan3` (WAN 3.0, 720p)이며 이후 모델은 검증한 모델별 계약과 설정 프로필을 추가한다. 미검증 모델 이름을 그대로 외부 API 경로로 사용하지 않는다.

## 연결과 참조

- 서버 `ASA_HIGGSFIELD_API_KEY`에 콘솔에서 복사한 전체 자격 증명을 설정한다. 브라우저·로그·Git에 키를 포함하지 않는다. 기존 Alibaba 지역별 키는 그대로 유지한다.
- 사용자가 생성 실행을 선택한 뒤에만 저장된 씬 이미지, 선택한 캐릭터 이미지, 지정 음성 구간(WAV), 선택한 기존 영상(MP4)을 업로드한다. 모델 선택·모달 열기·비용 안내는 업로드나 생성하지 않는다.
- `/files/generate-upload-url`로 받은 업로드 주소에 반환 헤더와 파일만 전송하고, 성공한 뒤 `public_url`을 모델 입력으로 사용한다. 저장소 PUT에는 API 인증 정보를 전달하지 않는다.
- 업로드 전 workspace와 원본 자료 권한·해시를 검증한다. 원본 파일을 수정하지 않으며 기존 요청은 접수 당시 제공자·모델을 유지한다. Higgsfield 음성 참조에는 ASA 외부 HTTPS 공개 주소가 필요하지 않다.
- 음성 참조는 일관성을 돕는 입력이며 음색 일치를 보장하는 음성 복제 계약이 아니다. 참조 기반 생성은 시작 이미지의 완전한 첫 프레임 고정과 구분한다.

## 비용과 보존

- 공개 요금 기준 WAN 3.0 720p는 영상 참조가 없으면 출력 1초당 USD 0.0750, 영상 참조가 있으면 USD 0.1493. 이미지·오디오만 참조하는 경우는 전자에 해당한다. 계정 실제 견적이 없으면 공개 요금 예상값임을 표시하며 미확인을 0으로 표시하지 않는다.
- 웹 구독과 API 잔액은 별도다. 최종 과금은 제공자 계정의 견적·청구를 따른다.
- 요청 ID와 멱등 키를 보존한다. 조회 실패를 새 생성 요청으로 바꾸지 않는다. 공급자 처리 시작 후에는 취소가 불가능할 수 있다.
- 공급자 결과 URL은 영구 보관소가 아니다. 완료 결과를 기존 앱 저장소에 내려받아 유지한다.

## 공식 계약 확인 (2026-11-20)

- https://open.higgsfield.ai/models/alibaba/wan-3.0/reference-to-video/api-reference
- https://open.higgsfield.ai/models/alibaba/wan-3.0/reference-to-video/playground
- https://docs.higgsfield.ai/docs/concepts/file-uploads
- https://docs.higgsfield.ai/docs/concepts/billing-and-retention
- https://docs.higgsfield.ai/docs/concepts/requests

실제 계정 인증·업로드·영상 생성은 별도 검증 항목이다. 구현의 모의 테스트 통과가 유료 모델 호출 성공을 의미하지 않는다.


## 복수 모델 지원 (2026-11-20)

관리 화면과 작업 입력에서 Higgsfield → 모델을 선택한다. 아래는 기존 720p 프로필의 요금이며 화면 비율은 9:16·16:9다. 전체 Higgsfield 모델을 자동 등록하는 것은 아니다.

| 모델 키 | 모델 | 허용 길이 | 참조 파일 | 출력 초당 USD (영상 참조 없음 / 있음) |
| --- | --- | --- | --- | --- |
| hf-wan3 | WAN3.0 | 2–30초 | 이미지·음성·영상 | .075 / .1493 |
| hf-seedance25 | Seedance2.5 | 4–30초 | 이미지·음성·영상 | .2647 / .3264 |
| hf-seedance20 | Seedance2.0 | 4–15초 | 이미지·음성·영상 | .1735 / .2128 |
| hf-kling4 | Kling4.0 | 3–30초 | 이미지·영상 (음성 참조/생성 제어 미지원) | .1257 / .1544 |

모델별 image-to-video/reference-to-video 요청 필드를 분리한다. Kling에 generate_audio/audio_urls를 보내지 않으며 음성 요청은 사전 차단한다. Seedance I2V는 시작 이미지 비율을 따르므로 aspect_ratio와 WAN전용 enable_thinking을 보내지 않는다. 앱의 기존 참조 파일 수·구간·권한·해시 검증은 유지한다. 미지원 입력은 자동 삭제하지 않는다.

클립 길이는 비디오 프롬프트 AI가 대본·씬 시간과 모델 허용 길이에 따라 정하고 사용자가 결과에서 검토·확정한다. 변경은 클립 계획 수정 요청으로 수행한다. 관리 모달은 모델별 기본 해상도·클립 길이 저장과 별도의 접힌 요금 계산기를 제공한다. 계산 예시 길이 자체는 저장되지 않는다. 현재 계획을 모델 선택만으로 바꾸지 않는다.

공식 근거 (모델별 계약과 공개 standard self-serve 요금 우선):
- https://open.higgsfield.ai/models/bytedance/seedance-2.5/reference-to-video/api-reference
- https://open.higgsfield.ai/models/bytedance/seedance-2.5/image-to-video/api-reference
- https://open.higgsfield.ai/models/bytedance/seedance-2.5/reference-to-video/playground
- https://open.higgsfield.ai/models/bytedance/seedance-2.0/reference-to-video/api-reference
- https://open.higgsfield.ai/models/bytedance/seedance-2.0/image-to-video/api-reference
- https://open.higgsfield.ai/models/bytedance/seedance-2.0/reference-to-video/playground
- https://open.higgsfield.ai/models/kling-video/v4.0/reference-to-video/api-reference
- https://open.higgsfield.ai/models/kling-video/v4.0/image-to-video/api-reference
- https://open.higgsfield.ai/models/kling-video/v4.0/reference-to-video/playground

공식 카탈로그 확인과 계정 권한·잔액·실제 생성 성공은 구분한다. 이번 검증에서 유료 생성·참조 파일 전송은 하지 않는다.

## 해상도 선택 및 사용자 세부설정

- WAN 3.0 / Seedance 2.5: 480p·720p·1080p. Seedance 2.0: 480p·720p·1080p·4K. Kling 4.0: 720p·1080p.
- 공개 단가 원본은 위 모델별 playground의 standard self-serve 표이며 `higgsfield_models.RESOLUTION_RATES`에 영상 참조 유무별로 관리한다. 관리 화면 해상도 선택은 기본값 저장 전까지 임시 값이다. 예상 총액은 선택 해상도의 단가 × 출력 길이이며 실제 청구와 다를 수 있다.
- `영상 생성 관리 → 사용자 세부설정 허용` ON: 사용자 선택 해상도·클립 길이만 적용하며 관리자 기본값은 섞지 않는다. OFF: 모델별 저장된 관리자 기본값을 서버에서 적용하고 사용자 선택은 적용하지 않는다. 길이 0은 AI 자동 판단이다. 기본값 미저장 시 기존 720p 프로필과 자동 길이를 사용한다. 생성 권한/비용 승인과는 별개이며 스위치 변경만으로 생성하지 않는다.
- 기존 720p 프로필 키와 스냅샷은 변경하지 않는다. 다른 해상도는 `<기존 키>-<해상도>`의 독립 프로필로 저장해 계획, 비용 및 생성 요청의 해상도를 일치시킨다. UI 모델 목록은 같은 모델을 한 번만 표시한다.
- registry migration의 `video_generation_controls.user_details_enabled`, `model_defaults` 컬럼이 필요하다. 구버전 관리 클라이언트에서 필드를 생략하면 기존 값을 유지한다. 권한·workspace·revision 충돌 및 모델/길이 지원 조건을 검증한다.
- 새 답변 접수 시 `submitted_request`는 사용자 원본, `original_request`는 실제 적용 입력, `video_execution_settings`는 출처·정책 revision·모델·해상도·길이 스냅샷이다. 정책 변경은 접수 후 작업을 변경하지 않는다. AI 출력/수동 저장/영상 생성 접수에서도 스냅샷과 모델·길이 일치를 검증한다. 기존 스냅샷이 없는 답변은 원래 계약을 유지하고, 클립 단독 수정은 부모 답변 설정을 상속한다.
- Alibaba 직접 연결과 Runway의 기존 720p 계약은 유지한다. 이번 다중 해상도 연결은 Higgsfield의 위 네 모델에 적용한다.
