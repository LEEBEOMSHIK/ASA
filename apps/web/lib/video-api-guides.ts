// Official documentation reviewed 2026-11-06. These are integration guides,
// not the executable ASA model catalog or the Higgsfield price snapshot.
export type VideoApiGuide = {
  id: string;
  route: string;
  model: string;
  setup: string;
  request: string;
  result: string;
  note: string;
  sources: { label: string; href: string }[];
};

const runwaySources = [
  { label: "Runway 모델 ID", href: "https://docs.dev.runwayml.com/guides/models/" },
  { label: "키 발급·충전", href: "https://docs.dev.runwayml.com/guides/setup/" },
  { label: "요청 명세", href: "https://docs.dev.runwayml.com/api/" },
  { label: "API 요금", href: "https://docs.dev.runwayml.com/guides/pricing/" },
];
function runway(id: string, model: string, note: string): VideoApiGuide {
  return {
    id, model, route: id === "runway" ? "Runway 직접 API · 문서 확인" : "Runway 중개 API · 문서 확인",
    setup: "Runway 개발자 프로젝트에서 API 키를 발급하고 API 크레딧을 충전합니다. Authorization: Bearer <키>, X-Runway-Version: 2024-11-06을 사용합니다.",
    request: "POST https://api.dev.runwayml.com/v1/image_to_video — 위 model ID와 promptImage, promptText, duration, ratio를 전달합니다. 길이·해상도·추가 필드는 해당 모델 명세를 따릅니다.",
    result: "반환된 작업 ID로 GET /v1/tasks/{id}를 조회합니다. SUCCEEDED이면 output의 영상 URL을 저장하고, 실패 상태는 별도로 처리합니다.",
    note, sources: runwaySources,
  };
}
function seedance(id: string, model: string, version: string): VideoApiGuide {
  return {
    id, model, route: "BytePlus ModelArk 직접 API · 문서 확인",
    setup: "ModelArk에서 모델 사용 권한·과금을 확인하고 API 키를 발급합니다. 서버의 ARK_API_KEY로 Bearer 인증합니다.",
    request: "POST https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks — model과 content 배열에 텍스트·이미지를 전달합니다. 첫 프레임 이미지는 image_url 및 role: first_frame으로 지정합니다.",
    result: "GET /api/v3/contents/generations/tasks/{id}로 조회하고 succeeded일 때 content.video_url을 저장합니다.",
    note: `Runway 중개 ID는 ${id === "seedance25" ? "seedance2_5" : "seedance2"}입니다. 키·요금·요청 형식은 별개입니다. 실제 인물 얼굴 참조에는 ModelArk의 인물 자산 조건이 적용됩니다. 계정별 사용 권한은 미검증입니다.`,
    sources: [
      { label: `Seedance ${version} 공식 안내`, href: `https://docs.byteplus.com/en/docs/ModelArk/seedance-${version.replace(".", "-")}` },
      { label: "생성 요청", href: "https://docs.byteplus.com/en/docs/modelark/create-video-generation-task-api" },
      { label: "결과 조회", href: "https://docs.byteplus.com/en/docs/modelark/get-video-generation-task-api" },
      { label: "중개 API 모델·요금", href: "https://docs.dev.runwayml.com/guides/models/" },
    ],
  };
}

export const videoApiGuides: VideoApiGuide[] = [
  runway("runway", "gen4.5", "ASA 생성 경로 구현됨. 서버 키·활성화·워커 설정 후 인증과 실제 생성 확인이 필요합니다."),
  seedance("seedance25", "dreamina-seedance-2-5-260628", "2.5"),
  {
    id: "flux3", route: "Black Forest Labs 직접 API · 문서 확인", model: "flux-3-video (엔드포인트)",
    setup: "BFL 계정의 프로젝트에서 API 키를 발급하고 크레딧을 준비합니다. 서버에서 x-key 헤더로 인증합니다.",
    request: "POST https://api.bfl.ai/v1/flux-3-video — mode: i2v, prompt, keyframes에 시작 이미지 URL을 전달합니다. 텍스트만 생성할 때는 mode: t2v를 사용합니다.",
    result: "응답의 polling_url을 조회해 Ready이면 result.sample의 영상 URL을 저장합니다. Error·모더레이션 종료 상태도 처리합니다.",
    note: "공식 명칭은 FLUX 3 Video입니다. 비교표의 FLUX.3 표기와 힉스필드 상품 조건이 동일한지는 미확인입니다. 이미지 생성용 FLUX 모델과 구분하세요.",
    sources: [
      { label: "BFL 영상 API", href: "https://docs.bfl.ai/flux_3/flux3_video" },
      { label: "계정·키 준비", href: "https://docs.bfl.ai/quick_start/get_started" },
      { label: "API 요금", href: "https://docs.bfl.ai/quick_start/pricing" },
    ],
  },
  seedance("seedance20", "dreamina-seedance-2-0-260128", "2.0"),
  {
    id: "grok", route: "xAI 직접 API · 문서 확인", model: "grok-imagine-video-1.5",
    setup: "xAI API Console에서 API 키·결제를 준비합니다. 서버의 XAI_API_KEY로 Authorization: Bearer 인증합니다.",
    request: "POST https://api.x.ai/v1/videos/generations — model, prompt, image.url, duration, resolution을 전달합니다.",
    result: "request_id로 GET /v1/videos/{request_id}를 조회합니다. done이면 video.url을 저장하고 failed는 실패로 처리합니다.",
    note: "Runway 중개 ID는 grok_imagine_1_5입니다. 키와 요청 형식이 다르며 Lite 모델과도 구분해야 합니다.",
    sources: [
      { label: "xAI 이미지→영상", href: "https://docs.x.ai/developers/model-capabilities/video/image-to-video" },
      { label: "키·첫 호출", href: "https://docs.x.ai/developers/quickstart" },
      { label: "모델·API 요금", href: "https://docs.x.ai/developers/models/grok-imagine-video-1.5" },
    ],
  },
  {
    ...runway("gemini", "gemini_omni_flash_1.1", "Google 직접 API는 EAP(사전 접근) 문서의 gemini-omni-1.1-eap 및 Interactions API를 사용합니다. 일반 Gemini 키만으로 접근 가능한 것으로 안내하지 않습니다. EAP 승인·계정 권한은 미검증입니다."),
    route: "Runway 중개 API 확인 · Google 직접 API는 EAP 제한",
    sources: [...runwaySources, { label: "Google EAP 조건", href: "https://ai.google.dev/gemini-api/docs/eap/omni/omni" }],
  },
  {
    ...runway("kling", "kling_4", "Kling 직접 API의 4.0 호출 명세는 이번 확인에서 확보하지 못했습니다(공식 사이트 접근 제한). 위 ID·인증·요금은 Runway 경로 전용이며 Kling 직접 API 값이 아닙니다."),
    route: "Runway 중개 API 확인 · 직접 호출 명세 미확인",
  },
  {
    ...runway("minimax", "hailuo3", "MiniMax 공식 H3 안내에서 직접 API 제공은 확인했으나 직접 호출 명세는 확인하지 못했습니다. 위 ID는 Runway 전용입니다. H3 Max(h3_max)와 다르며, 비교표의 2K 조건을 이 경로에 그대로 적용하면 안 됩니다."),
    route: "Runway 중개 API 확인 · 직접 호출 명세 미확인",
    sources: [...runwaySources, { label: "MiniMax 공식 H3 안내", href: "https://github.com/MiniMax-AI/MiniMax-H3" }],
  },
  {
    id: "wan", route: "Alibaba Cloud Model Studio 직접 API · 문서 확인", model: "wan3.0-video",
    setup: "Model Studio에서 사용 리전·workspace·모델 권한을 확인하고 API 키를 발급합니다. Bearer 인증과 X-DashScope-Async: enable을 사용합니다.",
    request: "POST https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis — model, input.prompt, input.media에 type: first_frame 이미지와 출력 parameters를 전달합니다.",
    result: "같은 호스트의 GET /api/v1/tasks/{task_id}로 완료 여부를 조회하고 결과 영상을 저장합니다. 예시는 싱가포르 리전이며 자신의 workspace·리전 주소를 사용해야 합니다.",
    note: "Runway 중개 ID는 wan3입니다. WAN 3.0 Prime(wan3_prime)과 구분합니다. 리전별 제공 여부·키·과금이 달라 계정에서 확인해야 합니다.",
    sources: [
      { label: "WAN 3.0 연결·키·요금 안내", href: "https://docs.modelstudio.console.alibabacloud.com/en/model-studio/wan3-video-generation-guide" },
      { label: "Runway 중개 모델", href: "https://docs.dev.runwayml.com/guides/models/" },
    ],
  },
];
