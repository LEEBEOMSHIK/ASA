export type VideoConnectionCheck = {
  status: "unchecked" | "authenticated" | "denied" | "unreachable" | "unsupported" | "missing_key" | "missing_workspace";
  checked_at: string | null;
  http_status?: number | null;
  provider_code?: string | null;
  request_id?: string | null;
};

export function connectionAuthenticated(check?: VideoConnectionCheck): boolean {
  const age = check?.checked_at ? Date.now() - Date.parse(check.checked_at) : NaN;
  return check?.status === "authenticated" && age >= 0 && age < 5 * 60 * 1000;
}

export function connectionLabel(check?: VideoConnectionCheck): string {
  if (check?.status === "authenticated") return connectionAuthenticated(check) ? "계정 인증 확인됨" : "인증 재확인 필요";
  const labels: Record<string, string> = {
    unchecked: "계정 인증 미확인", denied: "계정 인증·권한 거부", unreachable: "공급자 응답 확인 불가",
    unsupported: "연결 확인 미지원", missing_key: "API 키 미설정", missing_workspace: "작업 공간 ID 미설정",
  };
  return labels[check?.status ?? "unchecked"] ?? "계정 인증 미확인";
}

export function videoTimestamp(value?: string | null): string {
  if (!value || !Number.isFinite(Date.parse(value))) return "기록 없음";
  return new Date(value).toLocaleString("ko-KR", {timeZone: "Asia/Seoul", hour12: false}) + " KST";
}
