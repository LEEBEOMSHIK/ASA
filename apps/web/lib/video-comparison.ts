export type VideoCandidate = {
  id: string;
  name: string;
  family: string;
  seconds: number;
  resolution: string;
  won?: number;
  credits?: number;
  focus: string;
};

// Snapshot transcribed from the user's Higgsfield comparison, not live API pricing.
// These names are comparison labels, never provider API model IDs.
export const videoCandidates: VideoCandidate[] = [
  { id: "runway", name: "Runway Gen-4.5", family: "Runway", seconds: 10, resolution: "720p", focus: "확정 씬 이미지에서 시작하는 클립과 다음 클립의 움직임 연결을 확인합니다." },
  { id: "seedance25", name: "Seedance 2.5", family: "Seedance", seconds: 15, resolution: "720p", credits: 105, won: 7340, focus: "인물이 여러 명인 장면에서 외형과 행동 지시가 유지되는지 확인합니다." },
  { id: "flux3", name: "FLUX.3", family: "FLUX", seconds: 15, resolution: "720p", credits: 90, won: 6290, focus: "정확한 영상 모델명과 API 제공 여부부터 확인해야 합니다." },
  { id: "seedance20", name: "Seedance 2.0", family: "Seedance", seconds: 15, resolution: "720p", credits: 68, won: 4750, focus: "같은 장면으로 2.5와 비교해 재생성 횟수까지 포함한 비용을 확인합니다." },
  { id: "grok", name: "Grok Imagine 1.5", family: "Grok", seconds: 15, resolution: "720p", credits: 67.5, won: 4720, focus: "캐릭터의 얼굴·의상과 지정한 동화 화풍이 유지되는지 확인합니다." },
  { id: "gemini", name: "Gemini Omni Flash 1.1", family: "Gemini", seconds: 10, resolution: "720p", credits: 30, won: 2100, focus: "짧은 클립을 연결했을 때 장면 전환과 동작이 자연스러운지 확인합니다." },
  { id: "kling", name: "Kling 4.0", family: "Kling", seconds: 15, resolution: "720p", credits: 33.75, won: 2360, focus: "손·소품의 움직임과 여러 인물 사이의 상호작용을 확인합니다." },
  { id: "minimax", name: "MiniMax H3", family: "MiniMax", seconds: 15, resolution: "2K", credits: 30, won: 2100, focus: "자료의 모델명과 API 모델의 대응, 2K 출력 조건을 먼저 확인합니다." },
  { id: "wan", name: "WAN 3.0", family: "WAN", seconds: 15, resolution: "720p", credits: 27, won: 1890, focus: "낮은 자료상 가격이 재생성 비용을 포함해도 유리한지 확인합니다." },
];

export const runwayPricingSource = "https://docs.dev.runwayml.com/guides/pricing/";
export const runwayUsdPerSecond = 0.12;

export function estimateVideoCost(candidate: VideoCandidate, duration: number, exchangeRate: number) {
  const clips = Math.ceil(duration / candidate.seconds);
  const unitWon = candidate.id === "runway"
    ? candidate.seconds * runwayUsdPerSecond * exchangeRate
    : candidate.won ?? 0;
  return { clips, generatedSeconds: clips * candidate.seconds, won: clips * unitWon };
}
