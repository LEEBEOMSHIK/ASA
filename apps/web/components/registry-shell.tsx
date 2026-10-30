"use client";
import { SidebarToggle, useSidebarCollapse } from "./sidebar-toggle";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { api, ApiError, message, setCsrf } from "../lib/registry";
import { Button, StudioNavigation } from "./ui";
import { ThemeSelect } from "./theme-provider";

const DirtyContext = createContext<(value: boolean) => void>(() => {});
export function useDirtyGuard() { return useContext(DirtyContext); }

export function RegistryShell({ children }: { children: ReactNode }) {
  const sidebar = useSidebarCollapse();
  const pathname = usePathname();
  const active = pathname.startsWith("/characters") ? "/characters" : pathname.startsWith("/models") ? "/models" : pathname.startsWith("/monitoring") ? "/monitoring" : pathname.startsWith("/automations") ? "/automations" : pathname.startsWith("/agents") ? "/agents" : "/tools";
  const title = active === "/characters" ? "캐릭터 보관함" : active === "/models" ? "AI 모델 관리" : active === "/monitoring" ? "AI 사용량·비용" : active === "/automations" ? "자동화 빌더" : active === "/agents" ? "에이전트" : "도구 라이브러리";
  const [roleLabel, setRoleLabel] = useState("");
  const [admin, setAdmin] = useState(false);
  const [status, setStatus] = useState<"loading" | "error" | "ready">("loading");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [unsaved, setUnsaved] = useState(false);
  const [confirmLogout, setConfirmLogout] = useState(false);
  useEffect(() => {
    let active = true;
    api<{ csrf_token: string; roles: string[] }>("/session").then(data => {
      if (active) { setRoleLabel(data.roles?.includes("owner") ? "소유자 · 관리자 권한" : data.roles?.includes("admin") ? "관리자" : "일반 사용자"); setAdmin(data.roles?.some(role => role === "owner" || role === "admin") ?? false); setCsrf(data.csrf_token); setStatus("ready"); }
    }).catch(e => {
      if (!active) return;
      if (e instanceof ApiError && e.status === 401) {
        window.location.replace(`/login?next=${encodeURIComponent(window.location.pathname)}`);
      } else { setError(message(e)); setStatus("error"); }
    });
    return () => { active = false; };
  }, []);
  async function logout(discard = false) {
    if (unsaved && !discard) { setConfirmLogout(true); return; }
    setBusy(true);
    try {
      await api("/session", "DELETE"); setCsrf(""); setStatus("loading"); setConfirmLogout(false);
      // Unmount the editor before navigation so confirmed discard does not prompt again.
      window.setTimeout(() => window.location.replace("/login"), 0);
    }
    catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  return <DirtyContext.Provider value={setUnsaved}>
    <a className="skip-link" href="#main">본문으로 건너뛰기</a>
    <div className={`studio-app ${sidebar.collapsed ? "is-sidebar-collapsed" : ""}`}>
      <aside id="studio-navigation" className="studio-sidebar" aria-label="작업 탐색"><SidebarToggle collapsed={sidebar.collapsed} toggle={sidebar.toggle} controls="studio-navigation"/><a className="brand sidebar-brand" href="/"><span className="brand-mark" aria-hidden="true">A</span>AI Shorts Studio</a>
        <a href="/" className="button button--primary studio-new">＋ 새 작업</a><StudioNavigation active={active} includeAdmin={admin}/>
        <div className="studio-sidebar-note"><strong>내 작업 공간</strong><p>에이전트를 준비하고<br/>나만의 작업 흐름을 만드세요.</p></div>
        <div className="sidebar-footer"><ThemeSelect />{status === "ready" && <Button variant="secondary" disabled={busy} onClick={() => logout()}>로그아웃</Button>}</div>
      </aside>
      <div className="studio-content"><header className="customer-topbar"><span>스튜디오 <span className="muted"> / {title}</span></span><span className="muted">{roleLabel || "권한 확인 중"}</span></header>
      <details className="studio-mobile-nav"><summary>스튜디오 메뉴 · {title}</summary><StudioNavigation active={active} includeAdmin={admin}/><ThemeSelect />{status === "ready" && <Button variant="secondary" disabled={busy} onClick={() => logout()}>로그아웃</Button>}</details>
    <main id="main" className="shell registry-shell studio-main">
      {confirmLogout && <section role="alert" className="notice"><p>저장하지 않은 변경이 있습니다. 변경을 버리고 로그아웃할까요?</p>
        <div className="badge-row"><Button variant="secondary" onClick={() => setConfirmLogout(false)}>계속 편집</Button>
          <Button disabled={busy} onClick={() => logout(true)}>변경을 버리고 로그아웃</Button></div></section>}
      {status === "loading" ? <p role="status">작업 공간을 여는 중입니다…</p> : status === "error" ?
        <><p role="alert">{error}</p><Button onClick={() => window.location.reload()}>다시 시도</Button></> :
        <>{error && <p role="alert">{error}</p>}{children}</>}
    </main>
    </div></div>
  </DirtyContext.Provider>;
}
