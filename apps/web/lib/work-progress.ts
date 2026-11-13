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
  if (state === "pending") return ["character_images","scene_images"].includes(kind) ? "미생성" : "미진행";
  if (state === "running" && ["character_images","scene_images"].includes(kind)) return "이미지 생성 중";
  if (state === "queued" && ["character_images","scene_images"].includes(kind)) return "이미지 생성 대기";
  return states[state];
}
export function progressLabel(p: WorkProgress) {
  return ({pending:"작업 필요",running:["character_images","scene_images"].includes(p.kind) ? "이미지 생성 중" : "작업 진행 중",review:"검토 필요",attention:"확인 필요",complete:"작업 완료",not_required:"대상 없음"})[p.status];
}
export function progressCounts(p: WorkProgress): string {
  if(p.groups?.length) return p.groups.map(g=>`${g.label}: ${progressCounts(g)}`).join(" / ");
  const order: FollowupState[] = ["running", "queued", "review", "pending", "failed", "unknown", "approved", "excluded"];
  return order.filter(s=>p.counts[s]>0).map(s=>`${itemStateLabel(s,p.kind)} ${p.counts[s]}`).join(" · ");
}

export function workActionTone(p: WorkProgress): "danger" | "warning" | "primary" | "neutral" | "success" {
  if (p.counts.failed > 0 || p.counts.unknown > 0) return "danger";
  if (p.counts.review > 0) return "warning";
  if (p.counts.pending > 0) return "primary";
  return p.status === "complete" ? "success" : "neutral";
}

export function characterNextStep(aiStatus: string, p: WorkProgress): {label:string;tone:ReturnType<typeof workActionTone>;tab:"history"|"images"} {
  if (aiStatus === "running" || aiStatus === "queued") return {label:aiStatus === "running"?"답변 작성 중":"답변 생성 대기 중",tone:"neutral",tab:"history"};
  if (aiStatus === "failed") return {label:"답변 생성 오류 확인",tone:"danger",tab:"history"};
  if (aiStatus === "saved" || aiStatus === "cancelled") return {label:"답변 생성 필요",tone:"primary",tab:"history"};
  if (aiStatus !== "succeeded") return {label:"작업 상태 확인 필요",tone:"danger",tab:"history"};
  const states = [
    ["unknown","이미지 생성 결과 확인 필요","danger"],
    ["failed","이미지 생성 오류 확인","danger"],
    ["review","이미지 검토 필요","warning"],
    ["pending","이미지 생성 필요","primary"],
    ["running","이미지 생성 중","neutral"],
    ["queued","이미지 생성 대기 중","neutral"],
  ] as const;
  for (const [state,label,tone] of states) if (p.counts[state]>0) return {label:`${label} · ${p.counts[state]}개`,tone,tab:"images"};
  return {label:p.status==="complete"?"작업 완료":p.status==="not_required"?"작업 대상 없음":"작업 상태 확인 필요",tone:p.status==="complete"?"success":"neutral",tab:"images"};
}
