export type WorkTab = "common" | "images" | "history";
export function entryWorkTab(aiStatus: string, progress: {status:string;counts:Record<string,number>} | null | undefined): WorkTab {
  if (aiStatus !== "succeeded" || !progress) return "history";
  const remaining=["pending","queued","running","review","failed","unknown"].some(state=>(progress.counts[state] || 0)>0);
  return remaining || !["complete","not_required"].includes(progress.status) ? "images" : "history";
}
export function initialWorkTab(preferred:WorkTab, saved:string|null, reload:boolean):WorkTab {
  return reload && ["common","images","history"].includes(saved || "") ? parseWorkTab(saved) : preferred;
}
export function parseWorkTab(value: string | null): WorkTab {
  return value === "common" || value === "history" ? value : "images";
}
export function workTabKey(scope: string, request: string): string | null {
  return scope && request ? `asa-work-tab:v1:${scope}:${request}` : null;
}
