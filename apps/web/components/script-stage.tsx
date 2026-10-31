"use client";
import { useEffect, useRef, useState } from "react";
import { api, message, setCsrf, type SchemaNode } from "../lib/registry";
import { AnswerView, AnswerEditor, answerText } from "./agent-answer";
import { CharacterResults, isCharacterAnswer } from "./character-studio";
import { RequestProgress } from "./request-progress";
import { Button, Card, Field, StatusBadge } from "./ui";

type Version = { answer: unknown; version: number; title: string; narration: string; source: "manual" | "ai"; base_version: number | null; instruction: string; created_at: string };
type LiveOutput = {understanding?: string; direction?: string; value?: unknown};
type Attempt = { live_output?: LiveOutput; id: string; status: "queued" | "running" | "succeeded" | "unknown" | "cancelled" | "failed"; base_version: number; instruction: string; result_version: number | null; created_at: string; started_at?: string; provider?: string; model?: string; error_code?: string };
type Stage = { requires_approval: boolean; output_schema: SchemaNode; revision: number; head_version: number; approved_version: number | null; versions: Version[]; attempts: Attempt[]; model_configured: boolean; tools_supported: boolean; execution_enabled: boolean; worker_online: boolean; queue_ahead: number; request_input: unknown; agent_instructions: string };
const attemptLabels: Record<Attempt["status"], string> = { queued: "실행 대기", running: "작성 중", succeeded: "작성 완료", unknown: "결과 확인 필요", cancelled: "취소됨", failed: "실행하지 못함" };

export function ScriptStage({ requestId, onDirtyChange }: { requestId: string; onDirtyChange?: (dirty: boolean) => void }) {
  const [stage, setStage] = useState<Stage | null>(null);
  const [editing, setEditing] = useState(false);
  const [selected, setSelected] = useState(0);
  const pinnedVersion = useRef<number | null>(null);
  const [title, setTitle] = useState("");
  const [answer, setAnswer] = useState<unknown>(null);
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
  const generic = version?.answer !== null && version?.answer !== undefined;
  const dirty = generic ? JSON.stringify(answer) !== JSON.stringify(version?.answer) : title !== (version?.title || "") || narration !== (version?.narration || "");
  const active = stage?.attempts.find(attempt => ["queued", "running"].includes(attempt.status));
  const unknown = stage?.attempts.some(attempt => attempt.status === "unknown");
  function choose(data: Stage, number = data.head_version) {
    const current = data.versions.find(v => v.version === number);
    setAnswer(current?.answer ?? null);
    setSelected(number); setTitle(current?.title || ""); setNarration(current?.narration || "");
  }
  useEffect(() => {
    const resume = (event: Event) => {
      const detail = (event as CustomEvent<{requestId:string;version:number;anchor:string}>).detail;
      if (detail.requestId !== requestId || !stage || dirty) return;
      pinnedVersion.current = detail.version;
      choose(stage, detail.version);
      setEditing(false);
      requestAnimationFrame(()=>document.getElementById(detail.anchor)?.scrollIntoView({behavior:"smooth",block:"start"}));
    };
    window.addEventListener("asa-resume-work", resume);
    return ()=>window.removeEventListener("asa-resume-work", resume);
  }, [requestId, stage, dirty]);
  useEffect(() => {
    onDirtyChange?.(dirty);
    return () => onDirtyChange?.(false);
  }, [dirty, onDirtyChange]);
  useEffect(() => {
    let live = true;
    const params = new URLSearchParams(window.location.search);
    pinnedVersion.current = params.get("request") === requestId ? Number(params.get("answer")) || null : null;
    api<Stage>(path).then(data => { if (live) { setStage(data); choose(data, data.versions.some(v=>v.version===pinnedVersion.current)?pinnedVersion.current!:data.head_version); } }).catch(e => { if (live) setError(message(e)); });
    return () => { live = false; };
  }, [path]);
  useEffect(() => {
    if (!dirty) return;
    const guard = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", guard);
    return () => window.removeEventListener("beforeunload", guard);
  }, [dirty]);
  useEffect(() => {
    const events = new EventSource(`/api/v1${path}/events`);
    events.addEventListener("snapshot", event => {
      const data = JSON.parse((event as MessageEvent).data) as Stage;
      setStage(data); setError("");
      if (!dirty) choose(data, data.versions.some(v=>v.version===pinnedVersion.current)?pinnedVersion.current!:data.head_version);
    });
    const disconnected = () => setError("실시간 연결을 복구하고 있습니다. 작업을 다시 실행하지 않아도 최신 상태와 작성 중인 답변을 이어서 보여드립니다.");
    events.onerror = disconnected;
    events.addEventListener("unavailable", disconnected);
    return () => events.close();
  }, [path, dirty]);
  async function refresh() {
    setBusy(true); setError("");
    try {
      const data = await api<Stage>(path); setStage(data);
      if (!dirty) choose(data, data.versions.some(v=>v.version===pinnedVersion.current)?pinnedVersion.current!:data.head_version);
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
      const data = await api<Stage>(path); setStage(data); pinnedVersion.current=null; choose(data); operation.current = null;
      if (action === "/versions") setEditing(false);
      setNotice(action === "/versions" ? "새 답변 버전으로 저장했습니다. 이전 버전은 그대로 남아 있습니다." : action === "/approve" ? "답변을 저장했습니다." : action === "/generate" ? "답변 생성 요청을 접수했습니다. 결과가 나오면 자동으로 표시됩니다." : "대기 요청을 취소했습니다. 기존 답변은 유지됩니다.");
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  if (!stage) return <Card><h2>에이전트 답변</h2>{error ? <><p role="alert">{error}</p><Button onClick={refresh} disabled={busy}>다시 불러오기</Button></> : <p role="status">답변을 불러오는 중…</p>}</Card>;
  const latest = stage.attempts[0];
  const liveOutput = latest?.live_output;
  const latestFailed = latest && ["unknown", "failed"].includes(latest.status);
  const stateLabel = latestFailed ? (latest.error_code === "ai_timeout" ? "시간 초과 · 결과 확인 필요" : "최근 요청 실패 · 결과 확인 필요") : active ? attemptLabels[active.status] : stage.head_version ? "답변 완료" : "답변 없음";
  const previous = stage.versions.find(v => v.version < selected);
  return <section className="agent-response" aria-labelledby="agent-response-title">
    {error && <p role="alert" className="field-error">{error}</p>}{notice && <p role="status" className="preview-banner">{notice}</p>}
    {active && <Card><RequestProgress status={active.status} createdAt={active.created_at} queueAhead={stage.queue_ahead} online={stage.worker_online} instructions={stage.agent_instructions} model={active.model} receiving={Boolean(liveOutput?.understanding || liveOutput?.direction || liveOutput?.value !== undefined)} />
      {active.status === "queued" && <Button variant="secondary" disabled={busy} onClick={() => mutate(`/attempts/${active.id}/cancel`, {})}>대기 요청 취소</Button>}</Card>}

    {(liveOutput?.understanding || liveOutput?.direction) && <Card className="live-agent-brief"><h3>에이전트의 요청 이해와 작성 방향</h3><p className="helper-text">사용자에게 공개하는 작성 안내입니다.</p>{liveOutput.understanding && <section><h4>이렇게 이해했어요</h4><p className="agent-answer-text">{liveOutput.understanding}</p></section>}{liveOutput.direction && <section><h4>이 방향으로 작성해요</h4><p className="agent-answer-text">{liveOutput.direction}</p></section>}</Card>}
    {(active || latestFailed) && liveOutput?.value !== undefined && <Card><div className="card-heading"><h3>{active ? "작성 중인 답변" : "중단되기 전 작성된 내용"}</h3><StatusBadge tone="warning">{active ? "생성 중" : "미완성"}</StatusBadge></div><p className="helper-text">{active ? "도착하는 내용을 실시간으로 보여드립니다. 완료 전에는 내용이 달라질 수 있습니다." : "완성된 답변이 아닙니다. 새 답변 버전으로 저장되지 않았습니다."}</p><AnswerView value={liveOutput.value} schema={stage.output_schema} /></Card>}
    {!stage.execution_enabled && <p className="notice">답변 실행 서비스가 꺼져 있습니다. 관리자에게 실행 설정을 확인해 주세요.</p>}
    <div className="agent-response-stack" id="followup-answer"><Card><div className="card-heading"><h2 id="agent-response-title">에이전트 답변</h2><StatusBadge tone={latestFailed ? "warning" : active ? "neutral" : stage.head_version ? "success" : "neutral"}>{stateLabel}</StatusBadge></div>
      {latestFailed && <p role="status" className="notice">최근 요청의 답변을 확인하지 못했습니다. 자동 재시도하지 않습니다.{stage.head_version > 0 ? " 아래는 이전에 저장된 답변입니다." : ""}</p>}
      {stage.versions.length > 1 && <Field id="script-version" label="이전 답변 보기" hint="이전 버전도 보존됩니다. 내용을 수정해 저장하면 새 버전이 됩니다.">{props => <select {...props} value={selected} disabled={busy || dirty} onChange={e => { pinnedVersion.current=Number(e.target.value); choose(stage, Number(e.target.value)); setCompare(false); }}>
        {stage.versions.map(v => <option key={v.version} value={v.version}>v{v.version} · {v.source === "ai" ? "AI 작성" : "직접 작성"}{stage.approved_version === v.version ? " · 확정" : ""}</option>)}
      </select>}</Field>}
      {!editing && (version ? <><article className="agent-answer" aria-label="답변 내용">{isCharacterAnswer(version.answer) ? <CharacterResults key={`${requestId}:${selected}`} requestId={requestId} version={selected}/> : <AnswerView value={generic ? version.answer : { "제목": version.title, "대본": version.narration }} schema={generic ? stage.output_schema : undefined} />}</article><section className="answer-management" aria-label="에이전트 답변 관리"><div><strong>에이전트 답변 관리</strong><p className="muted">{isCharacterAnswer(version.answer) ? "등장인물 목록과 설정을 포함한 답변 전체를 수정하거나 텍스트로 복사합니다. 이미지 생성·수정·확정은 위 캐릭터 카드에서 진행하세요." : "답변 내용을 직접 고쳐 새 버전으로 저장하거나 텍스트로 복사할 수 있습니다."}</p></div><div className="script-actions"><Button variant="secondary" disabled={busy || Boolean(active)} onClick={() => setEditing(true)}>에이전트 답변 수정</Button><Button variant="secondary" onClick={async () => { try { await navigator.clipboard.writeText(generic ? answerText(version.answer, stage.output_schema) : `${version.title}\n\n${version.narration}`); setNotice("답변을 복사했습니다."); } catch { setError("복사하지 못했습니다. 답변을 선택해 복사해 주세요."); } }}>답변 텍스트 복사</Button></div></section></> : <p className="result-placeholder">{active ? "에이전트가 답변하면 여기에 표시됩니다." : "아직 답변이 없습니다. 아래에서 에이전트에 요청해 주세요."}</p>)}
      {editing && <form onSubmit={e => { e.preventDefault(); void mutate("/versions", { expected_revision: stage.revision, base_version: selected, ...(generic ? { answer } : { title, narration }) }, true); }}><fieldset className="request-fields" disabled={busy || Boolean(active)}>
        {generic ? <AnswerEditor value={answer} schema={stage.output_schema} onChange={setAnswer} /> : <><Field id="script-title" label="영상 제목">{props => <input {...props} required maxLength={120} value={title} onChange={e => setTitle(e.target.value)} placeholder="영상의 제목을 작성하세요" />}</Field>
        <Field id="script-narration" label="답변" hint="도입·본문·마무리를 자연스럽게 작성하세요. 최대 6,000자.">{props => <textarea {...props} required maxLength={6000} rows={12} value={narration} onChange={e => setNarration(e.target.value)} placeholder="답변을 수정하세요." />}</Field></>}
        <div className="script-actions"><Button type="submit" disabled={!dirty || (!generic && (!title.trim() || !narration.trim()))}>새 버전으로 저장</Button><Button variant="secondary" onClick={() => { choose(stage, selected); setEditing(false); }}>수정 취소</Button></div>
      </fieldset></form>}
      {stage.requires_approval && version && <div className="answer-approval"><div className="card-heading"><h3>사용자 확인</h3><StatusBadge tone={stage.approved_version===selected?"success":"warning"}>{stage.approved_version===selected?"답변 확정됨":"검토 필요"}</StatusBadge></div><p className="muted">내용을 확인한 뒤 확정하세요. 수정하거나 다시 생성하면 새 답변을 다시 확인해야 합니다.</p><Button disabled={busy || Boolean(active) || dirty || editing || selected!==stage.head_version || stage.approved_version===selected} onClick={()=>void mutate("/approve",{expected_revision:stage.revision,version:selected})}>이 답변 확정</Button>{selected!==stage.head_version && <p className="helper-text">최신 답변을 선택한 뒤 확정할 수 있습니다.</p>}</div>}
      {dirty && <p className="helper-text">저장하지 않은 수정이 있습니다. 저장한 뒤 다른 작업으로 이동하세요.</p>}
      {version && <p className="helper-text">{new Date(version.created_at).toLocaleString("ko-KR")} · {version.source === "ai" ? "AI가 작성한 답변" : "사용자가 수정한 답변"} · v{version.version}</p>}
      {previous && <><Button variant="secondary" onClick={() => setCompare(value => !value)} aria-expanded={compare}>이전 답변과 비교</Button>{compare && <div className="notice"><h4>이전 v{previous.version}</h4><AnswerView value={previous.answer ?? { "제목": previous.title, "대본": previous.narration }} schema={previous.answer != null ? stage.output_schema : undefined} /><h4>선택한 v{selected}</h4><AnswerView value={version?.answer ?? { "제목": version?.title, "대본": version?.narration }} schema={generic ? stage.output_schema : undefined} /></div>}</>}
    </Card><div className="stack"><Card><details open={stage.head_version === 0}><summary>{stage.head_version ? "AI에게 수정 요청" : "에이전트에 답변 요청"}</summary><p className="muted">{selected ? `v${selected}을 기준으로 원하는 변경을 적어 주세요.` : "원래 요청을 바탕으로 원하는 길이와 분위기를 적어 주세요."}</p>
      <form onSubmit={e => { e.preventDefault(); void mutate("/generate", { expected_revision: stage.revision, base_version: selected, instruction, acknowledge_unknown: acknowledged }, true); }}><fieldset className="request-fields" disabled={busy || Boolean(active) || !stage.tools_supported || !stage.model_configured || !stage.execution_enabled}>
        <Field id="script-revision-request" label="어떻게 작성하거나 고칠까요?" hint="예: 핵심 내용은 유지하고, 구체적인 예시를 더해 주세요.">{props => <textarea {...props} required maxLength={2000} rows={5} value={instruction} onChange={e => setInstruction(e.target.value)} />}</Field>
        <p className="helper-text">같은 에이전트의 지침으로 새 답변을 만듭니다. 원래 요청과 이전 답변은 보존됩니다.</p>
        {unknown && <label className="script-ack"><input type="checkbox" checked={acknowledged} onChange={e => setAcknowledged(e.target.checked)} />이전 호출 결과·사용량을 확인했으며 새 요청에서 중복 비용이 발생할 수 있음을 확인했습니다.</label>}
        <Button type="submit" disabled={dirty || !instruction.trim() || Boolean(unknown && !acknowledged)}>{selected ? "수정 요청 보내기" : "답변 요청 보내기"}</Button>
      </fieldset></form>
      {!stage.tools_supported && <p className="field-error">이 에이전트에는 연결된 도구가 있습니다. 도구 실행은 아직 지원하지 않으므로 답변은 직접 작성하거나 도구가 없는 에이전트를 사용하세요.</p>}
      <p className="helper-text">{stage.model_configured ? "모델 설정이 준비되어 있습니다." : "AI 모델 설정이 아직 준비되지 않았습니다."} 실행하면 공급자 비용이 발생합니다. 토큰과 예상 비용은 관리자 모니터링에 기록됩니다.</p>
    </details></Card>{stage.attempts.length > 0 && <Card><details><summary>요청 이력 · {stage.attempts.length}건</summary><ul className="script-attempts">{stage.attempts.map(attempt => <li key={attempt.id}><StatusBadge tone={attempt.status === "unknown" ? "warning" : "neutral"}>{attemptLabels[attempt.status]}</StatusBadge><p className="helper-text">{attempt.base_version === 0 ? "첫 답변 생성 요청" : "내가 보낸 수정 요청"}</p>{attempt.base_version > 0 && <blockquote className="request-quotation">{attempt.instruction}</blockquote>}<small className="muted">{new Date(attempt.created_at).toLocaleString("ko-KR")}{attempt.result_version ? ` · 결과 v${attempt.result_version}` : ""}</small>{attempt.error_code && <p className="field-error">{attempt.error_code === "ai_timeout" ? "AI 응답 시간 초과 · 결과와 사용량 확인 필요" : attempt.error_code}</p>}{attempt.status === "unknown" && <p className="field-error">호출 결과를 확정할 수 없습니다. 기존 답변을 보존했으며 자동 재시도하지 않습니다.</p>}</li>)}</ul><details><summary>운영자용 실행 정보</summary><p className="run-entered-value">작업 ID: {requestId}</p>{stage.attempts.map(a => <p key={a.id} className="run-entered-value">요청 ID: {a.id} · {attemptLabels[a.status]}</p>)}<p className="muted">이 ID로 관리자 모니터링에서 요청과 AI 사용량을 확인할 수 있습니다.</p></details></details></Card>}</div></div>
  </section>;
}
