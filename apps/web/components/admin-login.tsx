"use client";
import { useEffect, useState } from "react";
import { api, ApiError, message, setCsrf } from "../lib/registry";
import { Button, Card, Field, StatusBadge } from "./ui";
import { ThemeSelect } from "./theme-provider";

function destination() {
  const next = new URLSearchParams(window.location.search).get("next") || "";
  return next === "/" || /^\/(?:tools(?:\/[A-Za-z0-9:._%-]+)?|agents(?:\/new|\/[0-9a-f-]{36})?)$/.test(next) ? next : "/agents";
}

export function AdminLogin() {
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
  async function login(test = false) {
    setBusy(true); setError("");
    try {
      const data = await api<{ csrf_token: string }>(test ? "/session/test" : "/session", "POST",
        test ? {} : { access_key: accessKey });
      setCsrf(data.csrf_token); setKey(""); window.location.replace(destination());
    } catch (e) { setError(message(e)); setBusy(false); }
  }
  return <>
    <a className="skip-link" href="#main">본문으로 건너뛰기</a>
    <header className="header"><a className="brand" href="/">AI Shorts Studio</a><div className="badge-row"><ThemeSelect /><StatusBadge>관리자</StatusBadge></div></header>
    <main id="main" className="shell"><div className="login-panel"><Card>
      <p className="eyebrow">ADMIN WORKSPACE</p><h1 className="login-title">관리자 로그인</h1>
      <p className="muted">에이전트와 도구를 관리하는 나만의 작업 공간입니다.</p>
      {checking ? <p role="status">로그인 상태를 확인하고 있습니다…</p> : <>
        <form onSubmit={event => { event.preventDefault(); void login(); }}>
          <Field id="owner-key" label="소유자 접근 키" hint="프로젝트 .env의 ASA_OWNER_ACCESS_KEY 값입니다. AI 서비스 API 키와는 다릅니다.">
            {props => <input {...props} type="password" autoComplete="current-password" required
              disabled={busy} value={accessKey} onChange={e => setKey(e.target.value)} />}
          </Field>
          <div className="actions"><Button type="submit" disabled={busy}>관리자로 로그인</Button></div>
        </form>
        {testAvailable && <section className="notice" aria-labelledby="test-login-title">
          <StatusBadge tone="warning">개발 전용</StatusBadge><h2 id="test-login-title">빠르게 둘러보기</h2>
          <p>접근 키 입력 없이 현재 로컬 작업 공간에 로그인합니다. 여기서 저장한 변경은 실제로 반영됩니다.</p>
          <div className="actions"><Button variant="secondary" disabled={busy} onClick={() => login(true)}>테스트 로그인</Button></div>
        </section>}
        {busy && <p role="status">로그인 중입니다…</p>}
        {error && <p role="alert" className="field-error">{error}</p>}
      </>}
    </Card></div></main>
  </>;
}
