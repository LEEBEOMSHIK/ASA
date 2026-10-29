export type SchemaNode = {
  type: string; description?: string; properties?: Record<string, SchemaNode>; required?: string[];
  items?: SchemaNode; maxLength?: number; maxItems?: number; minimum?: number; maximum?: number;
};
export type Definition = {
  name: string; description: string; instructions: string; model_profile: string;
  input_schema: SchemaNode; output_schema: SchemaNode; tools: string[];
  limits: { model_calls: number; tool_calls: number; depth: number; seconds: number };
};
export type Version = { version: number; source_revision: number; definition: Definition; digest: string };
export type Agent = { id: string; revision: number; draft: Definition; versions?: Version[] };
export type Tool = {
  id: string; name: string; version: number; kind: "asa" | "agent"; agent_id?: string;
  description: string; available: boolean; execution_available: boolean; unavailable_reason: string;
  input_schema?: SchemaNode; output_schema?: SchemaNode; dependencies?: string[];
  usage?: string; example_input?: unknown; example_output?: unknown;
};
export type Issue = { code: string; field_path: string; message: string };
export type WorkItem = { id: string; name: string; version: number; status: string; created_at: string };
export type WorkDetail = WorkItem & { agent: Tool; input: unknown; result: unknown; error: string | null; source_id: string | null; updated_at: string };
let csrf = "";
export function setCsrf(value: string) { csrf = value; }
export class ApiError extends Error {
  constructor(public status: number, public code: string, public issues: Issue[] = []) {
    super(code);
  }
}
export async function api<T>(path: string, method = "GET", body?: unknown, revision?: number): Promise<T> {
  const headers: Record<string, string> = {};
  if (method !== "GET") { headers["Content-Type"] = "application/json"; headers["X-CSRF-Token"] = csrf; }
  if (revision !== undefined) headers["If-Match"] = `"${revision}"`;
  const response = await fetch(`/api/v1${path}`, {
    method, headers, credentials: "same-origin", cache: "no-store",
    body: method !== "GET" && method !== "DELETE" ? JSON.stringify(body ?? {}) : undefined,
  });
  const data = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, data?.detail || "connection_failed", data?.issues || []);
  return data as T;
}
export function message(error: unknown): string {
  if (!(error instanceof ApiError)) return "서버에 연결할 수 없습니다. 잠시 후 다시 시도하세요.";
  const messages: Record<string, string> = {
    runtime_search_unconfigured: "웹 검색 실행 설정이 필요합니다. 서버의 검색 API 키와 검색 활성화 설정을 확인하세요.",
    runtime_ai_unconfigured: "AI 실행 설정이 필요합니다. 운영자가 API 연결과 자동화 AI 실행을 활성화한 뒤 다시 시도하세요.",
    runtime_nested_tools_unsupported: "다른 도구를 호출하도록 설정한 에이전트는 아직 실행할 수 없습니다. 각 도구와 에이전트를 별도 작업 블록으로 연결하세요.",
    runtime_tool_unavailable: "아직 실행할 수 없는 도구가 포함되어 있습니다.",
    runtime_schedule_time: "예약 시간을 한국 시간 기준 미래 시각으로 입력하세요.",
    runtime_state_conflict: "작업 상태가 바뀌었습니다. 실행 기록에서 최신 상태를 확인하세요.",
    runtime_queue_full: "대기 중인 작업이 많습니다. 기존 작업을 완료하거나 취소한 뒤 시도하세요.",
    runtime_id_conflict: "이미 등록된 실행과 요청이 다릅니다. 실행 기록을 확인하세요.",
    revision_conflict: "다른 화면에서 변경되었습니다. 현재 입력은 유지됩니다. 내용을 복사한 뒤 새로고침해 최신 버전을 확인하세요.",
    invalid_definition: "설정을 검증할 수 없습니다. 아래 항목을 수정하세요.",
    invalid_access_key: "접근 키가 올바르지 않습니다.",
    not_found: "개발용 로그인이 비활성화되었습니다. 접근 키로 로그인하세요.",
    login_rate_limited: "로그인 시도가 많습니다. 1분 후 다시 시도하세요.",
    owner_login_unconfigured: "로컬 소유자 로그인 설정이 필요합니다.",
    registry_database_unavailable: "저장소 연결 또는 초기화가 필요합니다. 입력은 유지됩니다.",
    login_required: "로그인이 만료되었습니다. 현재 입력을 보관한 뒤 다시 로그인하세요.",
    agent_not_found: "에이전트를 찾을 수 없거나 접근 권한이 없습니다.",
    tool_not_found: "도구를 찾을 수 없거나 접근 권한이 없습니다.",
    work_not_found: "작업을 찾을 수 없거나 접근 권한이 없습니다.",
    invalid_work_input: "입력 형식이 에이전트 설정과 맞지 않습니다. 필수 항목과 값의 형식을 확인하세요.",
    work_conflict: "이미 저장된 요청과 내용이 다릅니다. 작업 이력을 확인한 후 새 작업을 시작하세요.",
    script_revision_conflict: "대본이 다른 화면에서 변경되었습니다. 입력은 유지됩니다. 내용을 복사한 뒤 최신 버전을 다시 불러오세요.",
    script_busy: "대본 재작성 요청이 대기하거나 실행 중입니다. 대기 요청을 취소하거나 완료 후 다시 시도하세요.",
    script_tools_unsupported: "도구 호출이 연결된 에이전트는 아직 대본 AI 실행을 지원하지 않습니다. 직접 작성은 가능합니다.",
    script_unknown_ack_required: "이전 AI 호출의 결과가 불확실합니다. 공급자 사용량을 확인하고 중복 비용 가능성을 확인해 주세요.",
    script_version_not_found: "기준 대본 버전을 찾을 수 없습니다. 최신 상태를 다시 불러오세요.",
    csrf_invalid: "로그인 상태가 변경되었습니다. 다시 로그인하세요.",
    origin_not_allowed: "허용된 로컬 주소로 접속하세요.",
    payload_too_large: "설정 크기가 64 KiB 제한을 초과했습니다.",
  };
  return messages[error.code] || "요청을 처리하지 못했습니다. 입력값과 연결 상태를 확인하세요.";
}
