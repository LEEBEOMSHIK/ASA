"use client";
import { useCallback, useEffect, useState } from "react";
import { api, message, type WorkDetail } from "../lib/registry";
import { Button, Card, StatusBadge } from "./ui";
import { ScriptStage } from "./script-stage";

const labels: Record<string, string> = { saved: "실행 전", queued: "대기 중", running: "진행 중", succeeded: "완료", failed: "실패", cancelled: "취소됨" };
export function workStatus(value: string) { return labels[value] || "상태 확인 필요"; }
const status = workStatus;
function date(value: string) { return new Date(value).toLocaleString("ko-KR"); }
function content(value: unknown): string { return typeof value === "string" ? value : JSON.stringify(value, null, 2); }

export function WorkHistory({ initialId, onRepeat, onSelect, onDirtyChange }: { initialId: string; onRepeat: (work: WorkDetail) => void; onSelect?: (id: string) => void; onDirtyChange?: (dirty: boolean) => void }) {
  const [id, setId] = useState(initialId || "");
  const [dirty, setDirty] = useState(false);
  const handleDirty = useCallback((value: boolean) => { setDirty(value); onDirtyChange?.(value); }, [onDirtyChange]);
  function canLeave() { return !dirty || window.confirm("저장하지 않은 대본 수정이 있습니다. 변경을 버리고 이동할까요?"); }
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
  return <section><div className="page-heading"><div><p className="eyebrow">YOUR WORK</p><h1>작업 상세</h1><p className="muted">이전 요청과 결과를 확인하고, 이어서 새 작업을 시작하세요.</p></div><Button variant="secondary" disabled={loading || dirty} onClick={() => setRefresh(value => value + 1)}>새로고침</Button></div>
    {loading ? <p role="status">작업을 불러오는 중입니다…</p> : error ? <p role="alert">{error}</p> : detail ? <div className="tool-detail-stack history-detail">
      <Card><div className="card-heading"><h2>{detail.agent.name}</h2><StatusBadge tone={detail.status === "succeeded" ? "success" : detail.status === "failed" ? "danger" : "neutral"}>{status(detail.status)}</StatusBadge></div><p className="muted">버전 {detail.version} · 요청 저장 {date(detail.created_at)}</p><p className="muted">최근 변경 {date(detail.updated_at)}</p>
        {detail.source_id && <p>이전 요청을 바탕으로 만든 작업입니다. <button className="button button--secondary" onClick={() => navigate(detail.source_id!)}>원래 작업 보기</button></p>}
        {detail.status === "saved" && <p className="notice">원래 요청이 저장되어 있습니다. 대본 제작 단계에서 결과를 작성·수정할 수 있습니다.</p>}
        <Button onClick={() => { if (canLeave()) onRepeat(detail); }}>이 요청으로 다시 작업</Button><p className="helper-text">이전 입력과 같은 에이전트 버전을 불러옵니다. 수정 후 저장하면 별도 이력이 만들어집니다.</p>
      </Card>
      <ScriptStage key={id} requestId={id} onDirtyChange={handleDirty} />
      <div className="tool-example-grid"><Card><h2>요청 내용</h2>{detail.agent.input_schema?.type === "object" ? <dl className="tool-fields">{Object.entries(detail.input as Record<string, unknown>).map(([key, value]) => <div key={key}><dt>{detail.agent.input_schema?.properties?.[key]?.description || key}</dt><dd className="run-entered-value">{content(value)}</dd></div>)}</dl> : <p className="run-entered-value">{content(detail.input)}</p>}</Card>
      <Card><h2>작업 결과</h2>{detail.result !== null ? <pre className="tool-example">{content(detail.result)}</pre> : <div className="result-placeholder"><p>{detail.status === "failed" ? "작업에 실패해 결과가 없습니다." : detail.status === "cancelled" ? "취소된 작업입니다." : "아직 생성된 결과가 없습니다."}</p></div>}{detail.error && <p role="alert">{detail.error}</p>}</Card></div>
    </div> : null}
  </section>;
}
