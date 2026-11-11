export type SampleStatus = { label: string; tone: "neutral" | "warning" | "success" | "danger" };
type Sample = { status: string; error_code: string | null };
export function voiceSampleStatus({changed, saved, selected, sample}: {changed: boolean; saved: boolean; selected: boolean; sample?: Sample}): SampleStatus {
  if (changed) return {label: "저장 전 변경", tone: "warning"};
  if (selected) return {label: "목소리 선택 완료", tone: "success"};
  if (!sample) return {label: saved ? "설정 저장됨 · 맞춤 샘플 없음" : "맞춤 샘플 생성 전 · 설정 저장 필요", tone: "neutral"};
  if (sample.status === "queued") return {label: "맞춤 샘플 생성 대기", tone: "neutral"};
  if (sample.status === "running") return {label: "맞춤 샘플 생성 중", tone: "neutral"};
  if (sample.status === "unknown") return {label: "맞춤 샘플 호출 결과 확인 필요", tone: "warning"};
  if (sample.status === "failed" || sample.error_code) return {label: "맞춤 샘플 생성 실패", tone: "danger"};
  if (["review", "approved"].includes(sample.status)) return {label: "맞춤 샘플 듣고 선택", tone: "warning"};
  return {label: "맞춤 샘플 상태 확인 필요", tone: "warning"};
}
