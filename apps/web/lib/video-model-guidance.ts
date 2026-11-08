// Reviewed official sources; exact identifiers prevent guidance leaking to a different version.
const runway = {
  checkedOn: "2026-11-06",
  confirmed: "입력 이미지가 구도·조명·화풍의 기준이 되며, 프롬프트로 동작과 카메라 움직임을 지시합니다.",
  caution: "흐릿한 얼굴·손 등 원본 이미지의 결함이 영상에서 커질 수 있습니다. 이미지가 암시하는 움직임과 반대되는 지시는 반복 조정이 필요할 수 있습니다.",
  sources: [
    {name:"Gen-4.5 공식 소개",url:"https://help.runwayml.com/hc/en-us/articles/46974685288467-Creating-with-Gen-4-5"},
    {name:"이미지→영상 공식 가이드",url:"https://help.runwayml.com/hc/en-us/articles/48324313115155-Image-to-Video-Prompting-Guide"},
  ],
};
const suggestions: Record<string, string> = {
  animation_2d: "확정한 2D 씬 이미지의 선·색·구도를 기준으로 움직임을 붙일 때 고려하세요. 동작의 속도와 타이밍을 구체적으로 적고, 선과 캐릭터 형태가 유지되는지 확인하세요.",
  animation_3d: "확정한 3D 씬 이미지에 캐릭터 동작과 카메라 이동을 더할 때 고려하세요. 원하는 동작 순서를 적고, 재질·조명·캐릭터 형태가 이어지는지 확인하세요.",
  live_action: "실사 씬 이미지에서 인물 동작과 카메라 연출을 구체적으로 지시할 때 고려하세요. 공식 자료는 순차 동작과 세밀한 카메라 지시를 주요 특성으로 설명합니다.",
};

export function modelStyleGuidance(provider: string, model: string, style: string) {
  if (provider === "alibaba" && model === "wan3.0-video" && Object.hasOwn(suggestions, style)) {
    return {
      checkedOn:"2026-11-06", suggestion:style === "live_action"
        ? "확정 실사 이미지에서 시작해 인물의 동작과 카메라 이동을 명확히 적으세요. 얼굴·손·소품의 일관성과 동작 사이의 연결을 확인하세요."
        : suggestions[style],
      confirmed:"첫 프레임 이미지 기반 생성, 2~30초 길이와 네이티브 오디오를 지원합니다. ASA 초기 연결은 720p, 세로·가로 비율을 사용합니다.",
      caution:"ASA는 작성한 프롬프트를 그대로 전달하기 위해 공급자의 자동 프롬프트 재작성을 끕니다. 이미지의 구도와 요청 비율을 맞추고, 중국어·영어 프롬프트를 사용하세요. 계정의 리전별 모델 권한을 확인해야 합니다.",
      sources:[{name:"WAN 3.0 공식 API",url:"https://docs.modelstudio.console.alibabacloud.com/en/model-studio/wan3-video-generation-api-reference"}],
    };
  }
  if (provider !== "runway" || model !== "gen4.5" || !Object.hasOwn(suggestions, style)) return null;
  return {...runway, suggestion:suggestions[style]};
}
