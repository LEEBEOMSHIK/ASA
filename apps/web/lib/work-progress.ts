export type FollowupState = "pending" | "queued" | "running" | "review" | "approved" | "excluded" | "failed" | "unknown";
export type WorkProgress = {
  kind: string; label: string; source_version: number; required: number;
  status: "pending" | "running" | "review" | "attention" | "complete" | "not_required";
  counts: Record<FollowupState, number>;
  items: {id: string; name: string; state: FollowupState}[]; resume_anchor: string;
  groups?: WorkProgress[];
};
const states: Record<FollowupState, string> = {pending:"미진행", queued:"대기", running:"진행 중", review:"검토 필요", approved:"확정", excluded:"제외", failed:"실패", unknown:"결과 확인 필요"};
export function itemStateLabel(state: FollowupState, kind: string) {
  if (state === "pending") return kind === "character_images" ? "미생성" : "미진행";
  if (state === "running" && kind === "character_images") return "이미지 생성 중";
  if (state === "queued" && kind === "character_images") return "이미지 생성 대기";
  return states[state];
}
export function progressLabel(p: WorkProgress) {
  return ({pending:"작업 필요",running:p.kind === "character_images" ? "이미지 생성 중" : "작업 진행 중",review:"검토 필요",attention:"확인 필요",complete:"작업 완료",not_required:"대상 없음"})[p.status];
}
export function progressCounts(p: WorkProgress): string {
  if(p.groups?.length) return p.groups.map(g=>`${g.label}: ${progressCounts(g)}`).join(" / ");
  const order: FollowupState[] = ["running", "queued", "review", "pending", "failed", "unknown", "approved", "excluded"];
  return order.filter(s=>p.counts[s]>0).map(s=>`${itemStateLabel(s,p.kind)} ${p.counts[s]}`).join(" · ");
}
