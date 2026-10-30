"use client";
import { useCallback, useEffect, useState } from "react";
import { api, message, type WorkDetail } from "../lib/registry";
import { Button, Card, StatusBadge } from "./ui";
import { ScriptStage } from "./script-stage";
import { progressLabel, progressCounts } from "../lib/work-progress";

const labels: Record<string, string> = { saved: "실행 전", queued: "대기 중", running: "AI 작성 중", succeeded: "답변 완료", failed: "실패", cancelled: "취소됨" };
export function workStatus(value: string) { return labels[value] || "상태 확인 필요"; }
const status = workStatus;
function date(value: string) { return new Date(value).toLocaleString("ko-KR"); }
function content(value: unknown): string { return typeof value === "string" ? value : Array.isArray(value) ? value.map(content).join("\n") : value !== null && typeof value === "object" ? Object.entries(value).map(([key, item]) => `${key}: ${content(item)}`).join("\n") : String(value ?? ""); }

export function WorkHistory({ initialId, onRepeat, onSelect, onDirtyChange }: { initialId: string; onRepeat: (work: WorkDetail) => void; onSelect?: (id: string) => void; onDirtyChange?: (dirty: boolean) => void }) {
  const [id, setId] = useState(initialId || "");
  const [dirty, setDirty] = useState(false);
  const handleDirty = useCallback((value: boolean) => { setDirty(value); onDirtyChange?.(value); }, [onDirtyChange]);
  function canLeave() { return !dirty || window.confirm("저장하지 않은 답변 수정이 있습니다. 변경을 버리고 이동할까요?"); }
  function navigate(value: string) { if (!canLeave()) return; setId(value); onSelect?.(value); }
  const [detail, setDetail] = useState<WorkDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(""); setDetail(null);
    const request = api<WorkDetail>(`/work-requests/${id}`).then(data => { if (active) setDetail(data); });
    request.catch(e => { if (active) setError(message(e)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id, refresh]);
  useEffect(() => {
    const update = (event: Event) => {
      const items = (event as CustomEvent<WorkDetail[]>).detail;
      const item = items.find(item => item.id === id);
      if (item) setDetail(previous => previous ? {...previous, status: item.status, error: item.error, updated_at: item.updated_at, work_progress: item.work_progress} : previous);
    };
    window.addEventListener("asa-work-update", update);
    return () => window.removeEventListener("asa-work-update", update);
  }, [id]);
  return <section><div className="page-heading"><div><p className="eyebrow">YOUR WORK</p><h1>에이전트와 작업</h1><p className="muted">선택한 에이전트에 맡긴 요청과 답변을 확인하세요.</p></div><Button variant="secondary" disabled={loading || dirty} onClick={() => setRefresh(value => value + 1)}>새로고침</Button></div>
    {loading ? <p role="status">작업을 불러오는 중입니다…</p> : error ? <p role="alert">{error}</p> : detail ? <div className="tool-detail-stack history-detail">
      <Card><div className="card-heading"><h2>{detail.agent.name}</h2><StatusBadge tone={detail.status === "succeeded" ? "success" : detail.status === "failed" ? "danger" : "neutral"}>{detail.work_progress && detail.status === "succeeded" ? "AI 답변 완료" : status(detail.status)}</StatusBadge></div><p className="muted">에이전트 버전 {detail.version} · 보낸 시각 {date(detail.created_at)}</p><p className="muted">마지막 상태 변경 {date(detail.updated_at)}</p>
        {detail.source_id && <p>이전 요청을 바탕으로 만든 작업입니다. <button className="button button--secondary" onClick={() => navigate(detail.source_id!)}>원래 작업 보기</button></p>}
        {detail.status === "saved" && <p className="notice">요청이 저장되어 있습니다. 아래에서 에이전트에 답변을 요청할 수 있습니다.</p>}
        <Button onClick={() => { if (canLeave()) onRepeat(detail); }}>이 요청으로 다시 작업</Button><p className="helper-text">이전 입력과 같은 에이전트 버전을 불러옵니다. 내용을 바꿔 보내면 새로운 요청으로 기록됩니다.</p>
      </Card>
      {detail.work_progress && <Card className="followup-summary"><div className="card-heading"><h2>{detail.work_progress.label} · {progressLabel(detail.work_progress)}</h2><StatusBadge tone={detail.work_progress.status === "complete" ? "success" : "neutral"}>답변 v{detail.work_progress.source_version}</StatusBadge></div><p>{progressCounts(detail.work_progress)}</p><p className="muted">AI 답변 완료와 별개로, 필요한 항목을 모두 확정해야 작업이 완료됩니다. 제외한 항목은 언제든 복원할 수 있습니다.</p><Button variant="secondary" disabled={dirty} onClick={()=>{window.dispatchEvent(new CustomEvent("asa-resume-work",{detail:{requestId:id,version:detail.work_progress!.source_version,anchor:detail.work_progress!.resume_anchor}}));}}>{detail.work_progress.label}에서 이어서 작업 ↓</Button></Card>}
      {["queued", "running"].includes(detail.status) && <p role="status" className="preview-banner"><span className="work-state-dot" aria-hidden="true" /> {detail.status === "queued" ? "요청 접수 완료 · 실행 대기 중입니다." : "AI가 답변을 작성하고 있습니다."} 상태와 답변은 자동으로 갱신됩니다.</p>}
      <Card className="sent-request-card">
        <div className="sent-request-label"><h2>내가 보낸 요청</h2>{detail.is_test && <StatusBadge>테스트 요청</StatusBadge>}</div>
        {detail.agent.input_schema?.type === "object" ? <dl className="sent-request-summary">{Object.entries(detail.input as Record<string, unknown>).map(([key, value]) => <div key={key}><dt>{detail.agent.input_schema?.properties?.[key]?.description || key}</dt><dd>{content(value)}</dd></div>)}</dl> : <p className="sent-request-text">{content(detail.input)}</p>}
      </Card>
      {detail.error && <p role="alert">{detail.error}</p>}
      <ScriptStage key={id} requestId={id} onDirtyChange={handleDirty} />
    </div> : null}
  </section>;
}
