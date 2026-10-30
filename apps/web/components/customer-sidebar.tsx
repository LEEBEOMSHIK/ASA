"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, message, type WorkItem } from "../lib/registry";
import { workStatus } from "./work-history";
import { Button, StatusBadge, StudioNavigation } from "./ui";
import { ThemeSelect } from "./theme-provider";
import { progressLabel, progressCounts } from "../lib/work-progress";

export function CustomerSidebar({ roles, ready, saving, view, activeId, refreshKey, onNew, onHistory }: {
  roles: string[]; ready: boolean; saving: boolean; view: "new" | "history"; activeId?: string; refreshKey: number;
  onNew: () => void; onHistory: (id: string) => void;
}) {
  const [items, setItems] = useState<WorkItem[]>([]);
  const [pollError, setPollError] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [retry, setRetry] = useState(0);
  const [more, setMore] = useState(false);
  const scrollArea = useRef<HTMLElement>(null);
  const sentinel = useRef<HTMLDivElement>(null);
  const offset = useRef(0);
  const hasMore = useRef(true);
  const busy = useRef(false);
  const generation = useRef(0);
  const loadMore = useCallback(async () => {
    if (!ready || busy.current || !hasMore.current) return;
    const current = generation.current;
    busy.current = true; setLoading(true); setError("");
    try {
      const data = await api<{ items: WorkItem[]; has_more: boolean }>(`/work-requests?offset=${offset.current}`);
      if (current !== generation.current) return;
      setItems(previous => {
        const merged = new Map(previous.map(item => [item.id, item]));
        data.items.forEach(item => merged.set(item.id, item));
        return [...merged.values()];
      });
      offset.current += data.items.length;
      hasMore.current = data.has_more && data.items.length > 0;
      setMore(hasMore.current);
    } catch (e) { if (current === generation.current) setError(message(e)); }
    finally { if (current === generation.current) { busy.current = false; setLoading(false); } }
  }, [ready]);
  useEffect(() => {
    generation.current += 1; busy.current = false; offset.current = 0; hasMore.current = true;
    setItems([]); setMore(false); setError(""); setLoading(false);
    if (scrollArea.current) scrollArea.current.scrollTop = 0;
    void loadMore();
    return () => { generation.current += 1; };
  }, [loadMore, refreshKey, retry]);
  useEffect(() => {
    if (!ready || loading || error || !more || !sentinel.current) return;
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) void loadMore();
    }, { root: scrollArea.current, rootMargin: "0px 0px 120px 0px" });
    observer.observe(sentinel.current);
    return () => observer.disconnect();
  }, [ready, loading, error, more, loadMore]);
  useEffect(() => {
    if (!ready) return;
    const events = new EventSource(`/api/v1/work-requests/events?pages=${Math.min(100, Math.max(1, Math.ceil(items.length / 20)))}`);
    events.addEventListener("snapshot", event => {
      const data = JSON.parse((event as MessageEvent).data) as {items: WorkItem[]};
      const updates = new Map(data.items.map(item => [item.id, item]));
      setItems(previous => {
        const merged = new Map(previous.map(item => [item.id, item]));
        updates.forEach((item, id) => merged.set(id, item));
        const next = [...merged.values()].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at) || b.id.localeCompare(a.id));
        offset.current = next.length;
        return next;
      });
      setPollError("");
      window.dispatchEvent(new CustomEvent("asa-work-update", {detail: data.items}));
    });
    const disconnected = () => setPollError("실시간 연결 복구 중 · 마지막 확인 상태입니다.");
    events.addEventListener("unavailable", disconnected);
    events.onerror = disconnected;
    return () => events.close();
  }, [ready, Math.ceil(items.length / 20)]);
  return <div className="customer-sidebar-content">
    <a className="brand sidebar-brand" href="/"><span className="brand-mark" aria-hidden="true">A</span><span>AI Shorts Studio</span></a>
    <nav aria-label="작업 메뉴" className="sidebar-navigation">
      <button className="sidebar-link sidebar-new" disabled={!ready || saving} aria-current={view === "new" ? "page" : undefined} onClick={onNew}><span aria-hidden="true">＋</span>새 작업</button>
    </nav>
    <StudioNavigation active="/" includeAdmin={ready && roles.some(role => role === "owner" || role === "admin")} />
    <section ref={scrollArea} className="sidebar-recent" aria-label="최근 작업"><div className="sidebar-section-heading"><h2>최근 작업</h2>{ready && <button className="sidebar-refresh" disabled={loading || saving} onClick={() => setRetry(value => value + 1)} aria-label="최근 작업 새로고침">↻</button>}</div>
      {!ready ? <p className="muted sidebar-note">로그인하면 이전 작업을 확인할 수 있어요.</p> : <>
      {pollError && <p role="status" className="sidebar-note">{pollError}</p>}
      {items.length > 0 &&
      <ul className="sidebar-work-list">{items.map(item => <li key={item.id}><button disabled={saving} className="sidebar-work" aria-current={view === "history" && activeId === item.id ? "page" : undefined} onClick={() => onHistory(item.id)}>
        <span className="sidebar-work-name">{item.name}</span>{item.is_test && <StatusBadge>테스트 요청</StatusBadge>}<span className="sidebar-work-meta"><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })}</time><span className="work-state" data-active={(["queued", "running"].includes(item.status) || item.work_progress?.status === "running")}>{(["queued", "running"].includes(item.status) || item.work_progress?.status === "running") && <span className="work-state-dot" aria-hidden="true" />}{item.error_code === "ai_timeout" && item.status === "failed" ? "시간 초과" : (item.status === "succeeded" && item.work_progress ? progressLabel(item.work_progress) : workStatus(item.status))}</span></span>
        {item.work_progress && <span className="sidebar-followup"><strong>{item.work_progress.label}</strong><span>{progressCounts(item.work_progress)}</span><span className="sidebar-followup-action">{item.work_progress.status === "complete" ? "결과 확인" : "이어서 작업"} →</span></span>}
      </button></li>)}</ul>}
      {loading && <p role="status" className="muted sidebar-note">작업을 더 불러오는 중…</p>}
      {error && <div className="sidebar-note"><p role="alert">{error}</p><Button variant="secondary" onClick={() => void loadMore()}>다시 시도</Button></div>}
      {!loading && !error && items.length === 0 && <p className="muted sidebar-note">저장한 작업이 여기에 모입니다.</p>}
      <div ref={sentinel} className="sidebar-load-more">{more && !loading && !error && <Button variant="secondary" onClick={() => void loadMore()}>오래된 작업 더 보기</Button>}</div>
      {!loading && !error && !more && items.length > 0 && <p className="muted sidebar-note">모든 작업을 불러왔어요.</p>}
      </>}
    </section>
    <div className="sidebar-footer"><ThemeSelect /><span className="muted">내 작업 공간</span><span className="muted">{ready ? roles.includes("owner") ? "소유자 · 관리자 권한" : roles.includes("admin") ? "관리자" : "일반 사용자" : "로그인 전"}</span></div>
  </div>;
}
