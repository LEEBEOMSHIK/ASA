"use client";
import { useEffect, useState } from "react";
import { api, ApiError, message, setCsrf } from "../lib/registry";
import { ActionIcon, Button, Card, Field, StatusBadge } from "./ui";
import { ThemeSelect } from "./theme-provider";
import { StudioBrand } from "./studio-brand";

function destination() {
  const next = new URLSearchParams(window.location.search).get("next") || "";
  return ["/", "/automations", "/monitoring", "/models", "/admin/access"].includes(next) || /^\/(?:tools(?:\/[A-Za-z0-9:._%-]+)?|agents(?:\/new|\/[0-9a-f-]{36})?)$/.test(next) ? next : "/";
}

export function AdminLogin() {
  const [mode,setMode]=useState<"user"|"owner">("user");
  const [username,setUsername]=useState("");
  const [accessKey, setKey] = useState("");
  const [testAvailable, setTestAvailable] = useState(false);
  const [checking, setChecking] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api<{ test_login_available: boolean }>("/session/options")
      .then(data => { if (active) setTestAvailable(data.test_login_available); })
      .catch(() => { /* Key login remains available when options cannot be fetched. */ });
    api("/session").then(() => {
      if (active) window.location.replace(destination());
    }).catch(e => {
      if (active) {
        if (!(e instanceof ApiError && e.status === 401)) setError(message(e));
        setChecking(false);
      }
    });
    return () => { active = false; };
  }, []);
  async function login(test: false | "owner" | "member" = false) {
    setBusy(true); setError("");
    try {
      const data = await api<{ csrf_token: string }>(test ? (test === "member" ? "/session/test-member" : "/session/test") : mode==="owner"?"/session":"/session/user", "POST",
        test ? {} : mode==="owner"?{ access_key: accessKey }:{username,password:accessKey});
      setCsrf(data.csrf_token); setKey(""); window.location.replace(test === "member" ? "/" : destination());
    } catch (e) { setError(message(e)); setBusy(false); }
  }
  return <>
    <a className="skip-link" href="#main">본문으로 건너뛰기</a>
    <header className="header login-header"><StudioBrand publicView placement="header"/><div className="badge-row"><ThemeSelect /><StatusBadge>스튜디오</StatusBadge></div></header>
    <main id="main" className="shell"><div className="login-panel"><Card>
      <p className="eyebrow">WORKSPACE</p><h1 className="login-title">스튜디오 로그인</h1>
      <p className="muted">관리자가 부여한 계정으로 로그인하세요.</p>
      {checking ? <p role="status">로그인 상태를 확인하고 있습니다…</p> : <>
        <form onSubmit={event => { event.preventDefault(); void login(); }}>
          <div className="actions"><Button variant="secondary" aria-pressed={mode==="user"} disabled={busy} onClick={()=>{setMode("user");setKey("");}}><ActionIcon kind="edit"/>사용자 로그인</Button><Button variant="secondary" aria-pressed={mode==="owner"} disabled={busy} onClick={()=>{setMode("owner");setKey("");}}><ActionIcon kind="settings"/>관리자 로그인</Button></div>
          {mode==="user"&&<Field id="username" label="로그인 아이디">{props=><input {...props} autoComplete="username" required maxLength={64} disabled={busy} value={username} onChange={e=>setUsername(e.target.value)}/>}</Field>}
          <Field id="owner-key" label={mode==="owner"?"관리자 접근 키":"비밀번호"} hint={mode==="owner"?"기존 프로젝트의 관리자 접근 키입니다. AI 서비스 API 키와는 다릅니다.":undefined}>
            {props => <input {...props} type="password" autoComplete="current-password" required
              disabled={busy} value={accessKey} onChange={e => setKey(e.target.value)} />}
          </Field>
          <div className="actions"><Button type="submit" disabled={busy}><ActionIcon kind="confirm"/>로그인</Button></div>
        </form>
        {testAvailable && <section className="notice" aria-labelledby="test-login-title">
          <StatusBadge tone="warning">개발 전용</StatusBadge><h2 id="test-login-title">빠르게 둘러보기</h2>
          <p>로컬 테스트 계정으로 로그인합니다. 일반 사용자는 관리자 메뉴에 접근할 수 없습니다. 저장한 변경은 실제로 반영됩니다.</p>
          <div className="actions"><Button disabled={busy} onClick={() => login("member")}><ActionIcon kind="confirm"/>일반 사용자로 빠른 로그인</Button><Button variant="secondary" disabled={busy} onClick={() => login("owner")}><ActionIcon kind="settings"/>관리자로 빠른 로그인</Button></div>
        </section>}
        {busy && <p role="status">로그인 중입니다…</p>}
        {error && <p role="alert" className="field-error">{error}</p>}
      </>}
    </Card></div></main>
  </>;
}
