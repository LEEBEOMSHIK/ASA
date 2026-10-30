"use client";
import { SidebarToggle, useSidebarCollapse } from "./sidebar-toggle";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, message, setCsrf, type Tool, type WorkDetail } from "../lib/registry";
import { AgentRunPreview } from "./agent-run-preview";
import { Button, Card, StatusBadge } from "./ui";
import { WorkHistory } from "./work-history";
import { CustomerSidebar } from "./customer-sidebar";

export function CustomerWorkspace() {
  const sidebar = useSidebarCollapse();
  const [tools, setTools] = useState<Tool[]>([]);
  const [selected, setSelected] = useState<Tool | null>(null);
  const [view, setView] = useState<"new" | "history">("new");
  const [historyId, setHistoryId] = useState<string>();
  const [source, setSource] = useState<WorkDetail | null>(null);
  const [saving, setSaving] = useState(false);
  const [scriptDirty, setScriptDirty] = useState(false);
  const [sidebarRefresh, setSidebarRefresh] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuDialog = useRef<HTMLDialogElement>(null);
  const main = useRef<HTMLElement>(null);
  const requestRef = useRef<{ fingerprint: string; id: string } | null>(null);
  const [status, setStatus] = useState<"loading" | "login" | "ready" | "error">("loading");
  const [roles, setRoles] = useState<string[]>([]);
  const [testLogin, setTestLogin] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setStatus("loading"); setError(""); setRoles([]);
    Promise.all([api<Tool[]>("/tools"), api<{csrf_token:string;roles:string[]}>("/session")]).then(([data, session]) => {
      if (!active) return;
      setRoles(session.roles || []); setCsrf(session.csrf_token);
      const latest = new Map<string, Tool>();
      for (const tool of data) {
        if (tool.kind !== "agent" || !tool.agent_id || !tool.available) continue;
        const previous = latest.get(tool.agent_id);
        if (!previous || previous.version < tool.version) latest.set(tool.agent_id, tool);
      }
      setTools([...latest.values()]); setStatus("ready");
    }).catch(e => {
      if (!active) return;
      if (e instanceof ApiError && e.status === 401) setStatus("login");
      else { setError(message(e)); setStatus("error"); }
    });
    api<{ test_login_available: boolean }>("/session/options").then(data => { if (active) setTestLogin(data.test_login_available); }).catch(() => {});
    return () => { active = false; };
  }, [retry]);
  useEffect(() => {
    const id=new URLSearchParams(window.location.search).get("request");
    if(id && /^[0-9a-f-]{36}$/i.test(id)){setHistoryId(id);setView("history");}
  }, []);
  async function enterTest() {
    setBusy(true); setError("");
    try {
      const session = await api<{ csrf_token: string }>("/session/test", "POST");
      setCsrf(session.csrf_token); setRetry(value => value + 1);
    } catch (e) { setError(message(e)); }
    finally { setBusy(false); }
  }
  async function saveRequest(input: unknown) {
    if (!selected) return;
    const body = { agent_id: selected.agent_id, version: selected.version, input, source_id: source?.id || null };
    const fingerprint = JSON.stringify(body);
    if (requestRef.current?.fingerprint !== fingerprint) requestRef.current = { fingerprint, id: crypto.randomUUID() };
    setSaving(true);
    try {
      const session = await api<{ csrf_token: string }>("/session");
      setCsrf(session.csrf_token);
      const saved = await api<WorkDetail>("/work-requests", "POST", { ...body, id: requestRef.current.id });
      await api(`/work-requests/${saved.id}/script/start`, "POST", {});
      setHistoryId(saved.id); setSelected(null); setSource(null); setView("history"); requestRef.current = null; setSidebarRefresh(value => value + 1);
    } finally { setSaving(false); }
  }
  function newRequest() { setSelected(null); setSource(null); setView("new"); requestRef.current = null; }
  function closeMenu() { menuDialog.current?.close(); setMenuOpen(false); }
  function canLeaveScript() { return !scriptDirty || window.confirm("저장하지 않은 대본 수정이 있습니다. 변경을 버리고 이동할까요?"); }
  function navigateNew() { if (!canLeaveScript()) return; newRequest(); closeMenu(); main.current?.focus(); }
  function navigateHistory(id: string) { if (!canLeaveScript()) return; setSelected(null); setSource(null); setHistoryId(id); setView("history"); closeMenu(); main.current?.focus(); }
  const sidebarProps = { roles, ready: status === "ready", saving, view, activeId: historyId, refreshKey: sidebarRefresh, onNew: navigateNew, onHistory: navigateHistory };
  return <div className={`customer-app ${sidebar.collapsed ? "is-sidebar-collapsed" : ""}`}>
    <a className="skip-link" href="#main">본문으로 건너뛰기</a>
    <aside id="customer-navigation" className="customer-sidebar" aria-label="작업 탐색"><SidebarToggle collapsed={sidebar.collapsed} toggle={sidebar.toggle} controls="customer-navigation"/><CustomerSidebar {...sidebarProps} /></aside>
    <dialog id="customer-menu" className="customer-menu-dialog" ref={menuDialog} onClose={() => setMenuOpen(false)} aria-label="작업 메뉴"><div className="sidebar-mobile-close"><Button variant="secondary" onClick={closeMenu}>메뉴 닫기</Button></div>{menuOpen && <CustomerSidebar {...sidebarProps} />}</dialog>
    <div className="customer-content"><header className="customer-topbar"><Button variant="secondary" className="customer-menu-toggle" aria-expanded={menuOpen} aria-controls="customer-menu" onClick={() => { setMenuOpen(true); menuDialog.current?.showModal(); }}>☰ 작업 메뉴</Button><span>{view === "new" ? "새 작업" : "작업 상세"}</span><span className="muted">나만의 AI 작업 공간</span></header>
    <main id="main" ref={main} tabIndex={-1} className="shell customer-workspace">
      {status === "ready" && view === "history" && historyId ? <WorkHistory key={historyId} initialId={historyId} onDirtyChange={setScriptDirty} onSelect={setHistoryId} onRepeat={work => { setSource(work); setSelected(work.agent); setView("new"); requestRef.current = null; }} /> : selected?.input_schema ? <><p className="muted">등록 버전 {selected.version}{source ? " · 이전 요청을 불러왔습니다. 내용을 수정하고 새 요청으로 실행하세요." : ""}</p><AgentRunPreview key={`${selected.id}:${source?.id || "new"}`} customer initialInput={source?.input} onSave={saveRequest} definition={{ name: selected.name, description: selected.description, input_schema: selected.input_schema }} onBack={newRequest} /></> : <>
        <section className="customer-welcome"><p className="eyebrow">LET’S CREATE</p><h1>오늘은 어떤 작업을 맡길까요?</h1><p className="intro">함께할 AI 도우미를 고르고, 필요한 내용을 알려 주세요.</p>
          <ol className="customer-steps" aria-label="이용 순서"><li><span>1</span>에이전트 선택</li><li><span>2</span>작업 내용 입력</li><li><span>3</span>결과 확인</li></ol></section>
        {status === "loading" && <p role="status">사용할 수 있는 에이전트를 불러오는 중입니다…</p>}
        {status === "login" && <Card><h2>내 작업 공간에 입장하세요</h2><p>현재는 로컬 개발 단계로, 기존 소유자 로그인으로 등록된 에이전트를 테스트합니다. 고객용 계정 로그인은 추후 연결됩니다.</p><div className="actions">
          {testLogin && <Button disabled={busy} onClick={enterTest}>{busy ? "입장 중…" : "테스트 로그인으로 시작"}</Button>}
          <a href="/login?next=%2F">소유자 로그인</a></div>{testLogin && <p className="muted">개발 전용 로그인입니다. 현재 로컬 작업 공간의 에이전트를 불러옵니다.</p>}</Card>}
        {error && <p role="alert" className="field-error">{error}</p>}
        {status === "error" && <Button variant="secondary" onClick={() => setRetry(value => value + 1)}>다시 불러오기</Button>}
        {status === "ready" && <><div className="section-heading"><div><h2>함께할 에이전트</h2><p className="muted">등록된 최신 버전으로 시작합니다.</p></div><StatusBadge>{tools.length}개</StatusBadge></div>
          {tools.length === 0 ? <Card><h3>아직 준비된 에이전트가 없어요.</h3><p>관리자 화면에서 에이전트를 만들고 ‘에이전트 등록’하면 여기에 표시됩니다.</p><a href="/agents">관리자 화면으로 이동 →</a></Card> :
          <div className="catalog-grid">{tools.map((tool, index) => <Card key={tool.id} className="customer-agent"><div className="card-heading"><span className="agent-avatar" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span><StatusBadge>v{tool.version}</StatusBadge></div><h3>{tool.name}</h3><p className="muted">{tool.description || "필요한 내용을 입력하고 이 에이전트에게 작업을 맡겨 보세요."}</p><Button variant="secondary" disabled={!tool.input_schema?.type} onClick={() => setSelected(tool)} aria-label={`${tool.name} 선택하기`}>이 에이전트 선택 →</Button></Card>)}</div>}
          <p className="customer-footnote">저장한 요청은 왼쪽 최근 작업에서 다시 확인할 수 있습니다. 답변 생성은 대기 순서에 따라 실행되며, 결과는 최근 작업에서 확인할 수 있습니다.</p></>}
      </>}
    </main></div>
  </div>;
}
