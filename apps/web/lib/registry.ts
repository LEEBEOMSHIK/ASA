import type { AgentIconId } from "./agent-icons";
export type SchemaNode = {
  type: string; description?: string; properties?: Record<string, SchemaNode>; required?: string[];
  items?: SchemaNode; maxLength?: number; maxItems?: number; minimum?: number; maximum?: number;
  enum?: (string | number | boolean)[]; default?: string | number | boolean;
  "x-widget"?: "text" | "textarea" | "radio" | "select" | "slider" | "number";
};
export type Definition = {
  icon?: AgentIconId;
  name: string; description: string; instructions: string; model_profile: string;
  requires_approval?: boolean;
  purpose?: "general" | "image_review";
  after_tasks?: {image_review?: {agent_ref: string; mode: "manual" | "automatic"} | null};
  provider?: "openai" | "anthropic" | null; model?: string | null;
  input_schema: SchemaNode; output_schema: SchemaNode; tools: string[];
  limits: { model_calls: number; tool_calls: number; depth: number; seconds: number };
};
export type Version = { version: number; source_revision: number; definition: Definition; digest: string };
export type Agent = { id: string; revision: number; draft: Definition; versions?: Version[] };
export type Tool = {
  icon?: AgentIconId;
  id: string; name: string; version: number; kind: "asa" | "agent"; agent_id?: string;
  description: string; available: boolean; execution_available: boolean; unavailable_reason: string;
  input_schema?: SchemaNode; output_schema?: SchemaNode; dependencies?: string[];
  purpose?: "general" | "image_review";
  usage?: string; example_input?: unknown; example_output?: unknown; launch_path?: string;
};
export type Issue = { code: string; field_path: string; message: string };
export type WorkItem = { work_progress?: import("./work-progress").WorkProgress | null; error_code?: string | null; is_test: boolean; id: string; name: string; version: number; status: string; created_at: string };
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
    review_image_required: "이미지 검수 에이전트는 캐릭터 이미지 결과의 AI 검수 요청으로 실행하세요.",
    review_not_configured: "이 작업의 에이전트 등록 버전에 이미지 검수 연결이 없습니다. 설정에서 연결한 새 버전으로 시작하세요.",
    review_already_running: "이 이미지의 AI 검수가 이미 대기하거나 진행 중입니다.",
    image_not_configured: "이미지 API 실행을 활성화하고 서버 키를 확인해 주세요.",
    image_model_not_allowed: "서버에서 허용한 이미지 모델을 선택해 주세요.",
    image_already_running: "이 캐릭터의 이미지 요청이 이미 진행 중입니다.",
    work_item_excluded: "생성 대상에서 제외된 항목입니다. 대상으로 복원한 뒤 진행해 주세요.",
    work_scope_changed: "다른 화면에서 생성 대상이 변경됐습니다. 최신 상태를 확인하고 다시 선택해 주세요.",
    image_daily_limit: "최근 24시간 이미지 요청 한도에 도달했습니다.",
    image_reference_invalid: "이 캐릭터의 완료된 이미지를 수정 기준으로 선택해 주세요.",
    image_reference_required: "수정할 이전 이미지를 먼저 선택해 주세요.",
    image_approval_changed: "다른 곳에서 기준 이미지를 바꿨습니다. 새로 확인한 후 확정해 주세요.",
    image_review_changed: "새 이미지 버전이 추가됐습니다. 최신 이미지를 확인한 뒤 다시 확정해 주세요.",
    character_plan_invalid: "캐릭터 설정 답변 형식이 맞지 않습니다. 에이전트의 답변 항목을 확인해 주세요.",
    character_plan_not_ready: "캐릭터 설정 답변이 아직 완료되지 않았습니다.",
    model_already_registered: "이미 등록된 모델입니다. 저장된 목록을 다시 확인하세요.",
    model_catalog_full: "모델은 최대 100개까지 등록할 수 있습니다.",
    provider_key_missing: "이 공급자의 API 키를 서버에 먼저 설정하세요.",
    provider_auth_failed: "공급자가 API 키 인증을 거부했습니다. 키와 접근 권한을 확인하세요.",
    provider_rate_limited: "공급자 조회 한도에 도달했습니다. 잠시 후 다시 시도하세요.",
    provider_lookup_failed: "모델 목록을 불러오지 못했습니다. 잠시 후 다시 시도하세요.",
    invalid_model_selection: "활성화된 공급자와 모델을 선택하세요. 관리자 모델 설정을 확인해 주세요.",
    admin_required: "관리자만 사용량과 요청 상세를 확인할 수 있습니다.",
    usage_not_found: "호출 기록을 찾을 수 없습니다.",
    invalid_usage_period: "조회 기간을 확인하세요. 최대 366일 범위로 조회할 수 있습니다.",
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
    script_execution_disabled: "대본 실행 서비스가 꺼져 있습니다. 관리자에게 확인해 주세요.",
    script_queue_full: "대기 중인 요청이 많습니다. 잠시 후 같은 요청으로 다시 시도해 주세요.",
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
