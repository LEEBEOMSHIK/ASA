export function elapsedTime(start: string | null, end: string | number | null): string {
  if (!start || end === null) return "확인 중";
  const from = Date.parse(start);
  const to = typeof end === "number" ? end : Date.parse(end);
  if (!Number.isFinite(from) || !Number.isFinite(to)) return "확인 중";
  const seconds = Math.max(0, Math.floor((to - from) / 1000));
  return `${Math.floor(seconds / 60)}분 ${seconds % 60}초`;
}
