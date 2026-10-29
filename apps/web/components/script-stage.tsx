"use client";
import { useEffect, useRef, useState } from "react";
import { api, message, setCsrf } from "../lib/registry";
import { Button, Card, Field, StatusBadge } from "./ui";

type Version = { version: number; title: string; narration: string; source: "manual" | "ai"; base_version: number | null; instruction: string; created_at: string };
type Attempt = { id: string; status: "queued" | "running" | "succeeded" | "unknown" | "cancelled"; base_version: number; instruction: string; result_version: number | null; created_at: string };
type Stage = { revision: number; head_version: number; approved_version: number | null; versions: Version[]; attempts: Attempt[]; model_configured: boolean; tools_supported: boolean };
const attemptLabels: Record<Attempt["status"], string> = { queued: "실행 대기", running: "작성 중", succeeded: "작성 완료", unknown: "결과 확인 필요", cancelled: "취소됨" };

export function ScriptStage({ requestId, onDirtyChange }: { requestId: string; onDirtyChange?: (dirty: boolean) => void }) {
  const [stage, setStage] = useState<Stage | null>(null);
  const [opened, setOpened] = useState(false);
  const [selected, setSelected] = useState(0);
  const [title, setTitle] = useState("");
  const [narration, setNarration] = useState("");
  const [instruction, setInstruction] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [compare, setCompare] = useState(false);
  const operation = useRef<{ fingerprint: string; id: string } | null>(null);
  const path = `/work-requests/${requestId}/script`;
  const version = stage?.versions.find(v => v.version === selected);
  const dirty = title !== (version?.title || "") || narration !== (version?.narration || "");
  const active = stage?.attempts.find(attempt => ["queued", "running"].includes(attempt.status));
  const unknown = stage?.attempts.some(attempt => attempt.status === "unknown");
  function choose(data: Stage, number = data.head_version) {
    const current = data.versions.find(v => v.version === number);
    setSelected(number); setTitle(current?.title || ""); setNarration(current?.narration || "");
  }
  useEffect(() => {
    onDirtyChange?.(dirty);
    return () => onDirtyChange?.(false);
  }, [dirty, onDirtyChange]);
  useEffect(() => {
    let live = true;
    api<Stage>(path).then(data => { if (live) { setStage(data); choose(data); } }).catch(e => { if (live) setError(message(e)); });
    return () => { live = false; };
  }, [path]);
  useEffect(() => {
    if (!dirty) return;
    const guard = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", guard);
    return () => window.removeEventListener("beforeunload", guard);
  }, [dirty]);
  async function refresh() {
    setBusy(true); setError("");
    try {
      const data = await api<Stage>(path); setStage(data);
      if (!dirty) choose(data);
      else setNotice("최신 상태를 불러왔습니다. 작성 중인 입력은 유지됩니다.");
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  async function mutate(action: string, body: Record<string, unknown>, withId = false) {
    if (!stage || busy) return;
    setBusy(true); setError(""); setNotice("");
    const fingerprint = JSON.stringify({ action, body });
    if (operation.current?.fingerprint !== fingerprint) operation.current = { fingerprint, id: crypto.randomUUID() };
    try {
      const session = await api<{ csrf_token: string }>("/session"); setCsrf(session.csrf_token);
      await api(path + action, "POST", { ...body, ...(withId ? { id: operation.current.id } : {}) });
      const data = await api<Stage>(path); setStage(data); choose(data); operation.current = null;
      setNotice(action === "/versions" ? "새 대본 버전으로 저장했습니다. 이전 버전은 그대로 남아 있습니다." : action === "/approve" ? "현재 대본을 확정했습니다. 다음 제작 단계는 아직 연결 전입니다." : action === "/generate" ? "대본만 다시 만드는 요청을 저장했습니다. 로컬 워커가 실행하기 전까지 대기합니다." : "대기 요청을 취소했습니다. 기존 대본은 유지됩니다.");
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  if (!stage) return <Card><h2>대본 제작</h2>{error ? <><p role="alert">{error}</p><Button onClick={refresh} disabled={busy}>다시 불러오기</Button></> : <p role="status">대본 단계를 불러오는 중…</p>}</Card>;
  if (!opened && stage.versions.length === 0 && stage.attempts.length === 0) return <Card><p className="eyebrow">SHORTS PRODUCTION</p><h2>이 요청으로 쇼츠 대본을 만들어 볼까요?</h2><p className="muted">먼저 대본을 작성하고 수정·확정합니다. 이미지와 영상은 이후 단계에서 연결됩니다.</p><Button onClick={() => setOpened(true)}>대본 단계 시작하기</Button></Card>;
  const approved = stage.head_version > 0 && stage.approved_version === stage.head_version;
  const stateLabel = active ? attemptLabels[active.status] : approved ? "확정됨" : stage.head_version ? "검토 필요" : "작성 전";
  const previous = stage.versions.find(v => v.version < selected);
  return <section className="script-stage" aria-labelledby="script-stage-title">
    <div className="page-heading"><div><p className="eyebrow">SHORTS PRODUCTION</p><h2 id="script-stage-title">대본부터 한 단계씩 완성하세요</h2><p className="muted">대본 수정은 이 단계에만 적용됩니다. 다른 제작 단계는 실행하지 않습니다.</p></div><Button variant="secondary" disabled={busy} onClick={refresh}>대본 상태 새로고침</Button></div>
    <ol className="production-steps" aria-label="제작 단계"><li aria-current="step"><strong>1. 대본</strong><span>{stateLabel}</span></li>{["장면 구성", "이미지", "장면 영상", "음성·자막", "최종 영상"].map((name, i) => <li key={name}><strong>{i + 2}. {name}</strong><span>준비 중</span></li>)}</ol>
    {error && <p role="alert" className="field-error">{error}</p>}{notice && <p role="status" className="preview-banner">{notice}</p>}
    {active && <Card><StatusBadge tone="warning">{attemptLabels[active.status]}</StatusBadge><p>{active.status === "queued" ? "요청이 저장되었습니다. 현재 자동 실행 서비스는 연결 전이며, 운영자가 로컬 워커를 실행해야 작성이 시작됩니다." : "AI가 대본을 작성하고 있습니다. 새로고침으로 결과를 확인하세요. 응답이 멈춘 경우 자동 재실행하지 말고 호출 결과를 확인해야 합니다."}</p><p className="muted">수정 범위: 대본만 · 기준 {active.base_version ? `v${active.base_version}` : "최초 요청"}</p>{active.status === "queued" && <Button variant="secondary" disabled={busy} onClick={() => mutate(`/attempts/${active.id}/cancel`, {})}>대기 요청 취소</Button>}</Card>}
    <div className="script-stage-grid"><Card><div className="card-heading"><h3>대본 결과 · 직접 수정</h3><StatusBadge tone={approved ? "success" : "neutral"}>{stateLabel}</StatusBadge></div>
      {stage.versions.length > 0 && <Field id="script-version" label="확인할 대본 버전" hint="이전 버전도 보존됩니다. 내용을 수정해 저장하면 새 버전이 됩니다.">{props => <select {...props} value={selected} disabled={busy || dirty} onChange={e => { choose(stage, Number(e.target.value)); setCompare(false); }}>
        {stage.versions.map(v => <option key={v.version} value={v.version}>v{v.version} · {v.source === "ai" ? "AI 작성" : "직접 작성"}{stage.approved_version === v.version ? " · 확정" : ""}</option>)}
      </select>}</Field>}
      <form onSubmit={e => { e.preventDefault(); void mutate("/versions", { expected_revision: stage.revision, base_version: selected, title, narration }, true); }}><fieldset className="request-fields" disabled={busy || Boolean(active)}>
        <Field id="script-title" label="영상 제목">{props => <input {...props} required maxLength={120} value={title} onChange={e => setTitle(e.target.value)} placeholder="영상의 제목을 작성하세요" />}</Field>
        <Field id="script-narration" label="대본" hint="도입·본문·마무리를 자연스럽게 작성하세요. 최대 6,000자.">{props => <textarea {...props} required maxLength={6000} rows={12} value={narration} onChange={e => setNarration(e.target.value)} placeholder="아직 대본이 없습니다. 직접 작성하거나 오른쪽에서 AI 작성을 요청하세요." />}</Field>
        <div className="script-actions"><Button type="submit" disabled={!dirty || !title.trim() || !narration.trim()}>새 버전으로 저장</Button>{dirty && <Button variant="secondary" onClick={() => choose(stage, selected)}>입력 변경 취소</Button>}</div>
      </fieldset></form>
      {dirty && <p className="helper-text">저장하지 않은 수정이 있습니다. 저장한 뒤 다른 작업으로 이동하세요.</p>}
      {version && <><p className="helper-text">{new Date(version.created_at).toLocaleString("ko-KR")} · {version.source === "ai" ? "AI가 작성한 결과" : "사용자가 직접 작성한 결과"}</p><Button variant="secondary" disabled={busy || dirty || Boolean(active) || selected !== stage.head_version || approved} onClick={() => mutate("/approve", { expected_revision: stage.revision, version: selected })}>{approved && selected === stage.head_version ? "현재 대본 확정됨" : "현재 대본으로 확정"}</Button><p className="helper-text">최신 버전을 확정할 수 있습니다. 새 버전을 만들면 다시 검토해야 합니다.</p></>}
      {previous && <><Button variant="secondary" onClick={() => setCompare(value => !value)} aria-expanded={compare}>이전 대본과 비교</Button>{compare && <div className="notice"><h4>이전 v{previous.version}: {previous.title}</h4><p className="run-entered-value">{previous.narration}</p><h4>선택한 v{selected}: {version?.title}</h4><p className="run-entered-value">{version?.narration}</p></div>}</>}
    </Card><div className="stack"><Card><h3>{stage.head_version ? "대본만 다시 만들기" : "AI에게 첫 대본 요청하기"}</h3><p className="muted">{selected ? `v${selected}을 기준으로 원하는 변경을 적어 주세요.` : "원래 요청을 바탕으로 원하는 길이와 분위기를 적어 주세요."}</p>
      <form onSubmit={e => { e.preventDefault(); void mutate("/generate", { expected_revision: stage.revision, base_version: selected, instruction, acknowledge_unknown: acknowledged }, true); }}><fieldset className="request-fields" disabled={busy || Boolean(active) || !stage.tools_supported}>
        <Field id="script-revision-request" label="어떻게 작성하거나 고칠까요?" hint="예: 도입을 질문으로 시작하고, 30초 안에 읽을 수 있게 줄여 주세요.">{props => <textarea {...props} required maxLength={2000} rows={5} value={instruction} onChange={e => setInstruction(e.target.value)} />}</Field>
        <div className="notice"><strong>다시 만드는 범위: 대본만</strong><p>이전 대본과 원래 요청은 유지합니다. 이미지·영상·음성은 실행하지 않습니다.</p></div>
        {unknown && <label className="script-ack"><input type="checkbox" checked={acknowledged} onChange={e => setAcknowledged(e.target.checked)} />이전 호출 결과·사용량을 확인했으며 새 요청에서 중복 비용이 발생할 수 있음을 확인했습니다.</label>}
        <Button type="submit" disabled={dirty || !instruction.trim() || Boolean(unknown && !acknowledged)}>{selected ? "대본 재작성 요청 저장" : "첫 대본 요청 저장"}</Button>
      </fieldset></form>
      {!stage.tools_supported && <p className="field-error">이 에이전트에는 연결된 도구가 있습니다. 도구 실행은 아직 지원하지 않으므로 대본은 직접 작성하거나 도구가 없는 에이전트를 사용하세요.</p>}
      <p className="helper-text">{stage.model_configured ? "모델 설정이 준비되어 있습니다." : "AI 모델 설정이 아직 준비되지 않았습니다."} 요청 저장만으로 유료 호출하지 않습니다. 실제 실행은 로컬 워커가 담당하며 공급자 비용이 발생할 수 있습니다. 예상 비용 계산은 아직 제공하지 않습니다.</p>
    </Card>{stage.attempts.length > 0 && <Card><h3>대본 실행 내역</h3><ul className="script-attempts">{stage.attempts.map(attempt => <li key={attempt.id}><StatusBadge tone={attempt.status === "unknown" ? "warning" : "neutral"}>{attemptLabels[attempt.status]}</StatusBadge><p>{attempt.instruction}</p><small className="muted">{new Date(attempt.created_at).toLocaleString("ko-KR")}{attempt.result_version ? ` · 결과 v${attempt.result_version}` : ""}</small>{attempt.status === "unknown" && <p className="field-error">호출 결과를 확정할 수 없습니다. 기존 대본을 보존했으며 자동 재시도하지 않습니다.</p>}</li>)}</ul><details><summary>운영자용 실행 정보</summary><p className="run-entered-value">작업 ID: {requestId}</p>{stage.attempts.map(a => <p key={a.id} className="run-entered-value">요청 ID: {a.id} · {attemptLabels[a.status]}</p>)}<p className="muted">로컬 개발 문서의 대본 워커 절차를 사용하세요.</p></details></Card>}</div></div>
  </section>;
}
