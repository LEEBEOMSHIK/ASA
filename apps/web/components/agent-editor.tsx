"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, message, type Agent, type Definition, type Issue, type Tool, type Version, type SchemaNode } from "../lib/registry";
import { Button, Card, Field, StatusBadge } from "./ui";
import { ExecutionExample, GroupedTools, FriendlyFields, starters, starterDefinition } from "./agent-guide";
import { AgentRunPreview } from "./agent-run-preview";
import { useDirtyGuard } from "./registry-shell";

const initial: Definition = {
  name: "", description: "", instructions: "", model_profile: "default", tools: [],
  input_schema: { type: "object", properties: { topic: { type: "string", description: "영상으로 만들 주제" } }, required: ["topic"] },
  output_schema: { type: "string" },
  limits: { model_calls: 10, tool_calls: 20, depth: 2, seconds: 300 },
};

export function AgentEditor({ id }: { id?: string }) {
  const router = useRouter();
  const [draft, setDraft] = useState<Definition>(initial);
  const outputDrafts = useRef<{ free?: SchemaNode; structured?: SchemaNode }>({});
  const [preview, setPreview] = useState(false);
  const wasPreview = useRef(false);
  const previewButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!preview && wasPreview.current) previewButton.current?.focus();
    wasPreview.current = preview;
  }, [preview]);
  const [selectedStarter, setSelectedStarter] = useState<number | null>(null);
  const [revision, setRevision] = useState(0);
  const [versions, setVersions] = useState<Version[]>([]);
  const [tools, setTools] = useState<Tool[]>([]);
  const [loading, setLoading] = useState(true);
  const [failedLoad, setFailedLoad] = useState(false);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const setUnsaved = useDirtyGuard();
  useEffect(() => { setUnsaved(dirty); return () => setUnsaved(false); }, [dirty, setUnsaved]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [issues, setIssues] = useState<Issue[]>([]);
  useEffect(() => {
    let active = true;
    Promise.all([api<Tool[]>("/tools"), id ? api<Agent>(`/agents/${id}`) : Promise.resolve(null)])
      .then(([catalog, agent]) => { if (!active) return; setTools(catalog);
        if (agent) { setDraft(agent.draft); setRevision(agent.revision); setVersions(agent.versions || []); }
      }).catch(e => { if (active) { setError(message(e)); setFailedLoad(true); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id]);
  useEffect(() => { const warn = (e: BeforeUnloadEvent) => { if (dirty) { e.preventDefault(); e.returnValue = ""; } };
    window.addEventListener("beforeunload", warn); return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  function edit(next: Definition) { setDraft(next); setDirty(true); setUnsaved(true); setNotice(""); setIssues([]); }
  function changeOutputMode(free: boolean) {
    outputDrafts.current[draft.output_schema.type === "string" ? "free" : "structured"] = draft.output_schema;
    const output_schema = free ? outputDrafts.current.free || { type: "string" } : outputDrafts.current.structured || {
      type: "object", properties: { result: { type: "string", description: "완성된 답변" } }, required: ["result"],
    };
    edit({ ...draft, output_schema });
  }
  async function action(kind: "save" | "validate" | "publish") {
    setBusy(true); setError(""); setNotice(""); setIssues([]);
    try {
      if (kind === "save") {
        const saved = await api<Agent>(id ? `/agents/${id}/draft` : "/agents", id ? "PATCH" : "POST", draft, id ? revision : undefined);
        setRevision(saved.revision); setDraft(saved.draft); setDirty(false); setUnsaved(false);
        if (!id) router.replace(`/agents/${saved.id}`); else setNotice("초안을 저장했습니다.");
      } else if (kind === "validate") {
        const result = await api<{ issues: Issue[] }>(`/agents/${id}/validate`, "POST");
        setIssues(result.issues); setNotice(result.issues.length ? "수정할 항목이 있습니다." : "저장된 초안의 검증을 통과했습니다.");
      } else {
        await api(`/agents/${id}/publish`, "POST", {}, revision);
        const saved = await api<Agent>(`/agents/${id}`);
        setVersions(saved.versions || []); setNotice("버전을 확정하고 내 도구 목록에 등록했습니다. 실행 기능은 준비 중입니다.");
      }
    } catch (e) { setError(message(e)); if (e instanceof ApiError) setIssues(e.issues); }
    finally { setBusy(false); }
  }
  if (loading) return <p role="status">에이전트 설정을 불러오는 중입니다…</p>;
  if (failedLoad) return <p role="alert">{error} <Link href="/agents">목록으로 이동</Link></p>;
  if (preview) return <AgentRunPreview definition={draft} onBack={() => setPreview(false)} />;
  return <>
    <a className="back-link" href="/agents">← 나의 에이전트</a>
    <div className="page-heading"><div><p className="eyebrow">AGENT WORKSPACE</p><h1>{id ? draft.name || "에이전트 편집" : "어떤 일을 맡겨볼까요?"}</h1>
      <p className="muted">에이전트는 반복할 일을 맡아주는 AI 도우미예요. 역할과 필요한 정보를 정해 주세요.</p></div>
      <StatusBadge tone={dirty ? "warning" : "neutral"}>{dirty ? "저장 전 변경 있음" : id ? "저장됨" : "새 에이전트"}</StatusBadge></div>
    <form onInvalidCapture={e => {
      if (e.target instanceof HTMLElement) {
        let parent = e.target.parentElement;
        while (parent) { if (parent instanceof HTMLDetailsElement) parent.open = true; parent = parent.parentElement; }
      }
    }} onSubmit={e => { e.preventDefault(); void action("save"); }}>
      <fieldset disabled={busy} className="editor-fieldset">
        {!id && <section className="starter-section" aria-labelledby="starter-title"><div className="section-heading"><div><h2 id="starter-title">처음이라면, 예시로 시작하세요</h2>
          <p className="muted">하나를 선택하면 아래 내용이 채워집니다. 나에게 맞게 바꿔도 좋아요.</p></div><span className="muted">선택 사항</span></div>
          <div className="starter-grid">{starters.map((s, i) => <button type="button" key={s.name} className="starter-card" aria-pressed={selectedStarter === i}
            onClick={() => { setSelectedStarter(i); edit(starterDefinition(i)); }}><span className="starter-mark">{s.mark}</span><strong>{s.name}</strong><span>{s.description}</span><span className="starter-action">{selectedStarter === i ? "선택한 예시 ✓" : "이 예시로 시작 →"}</span></button>)}</div>
          {dirty && <p className="helper-text">다른 예시를 선택하면 작성 중인 내용이 해당 예시로 바뀝니다.</p>}
        </section>}
        <div className="guided-layout"><div className="stack">
          <section id="role" className="editor-section"><div className="section-heading"><span className="step-number">1</span><div><h2>어떤 일을 하는 도우미인가요?</h2><p className="muted">이름을 붙이고, 동료에게 부탁하듯 맡길 일을 적어 주세요.</p></div></div>
            <Field id="agent-name" label="에이전트 이름">{p => <input {...p} required maxLength={80} placeholder="예: 우리 채널의 쇼츠 작가" value={draft.name} onChange={e => edit({ ...draft, name: e.target.value })} />}</Field>
            <Field id="agent-description" label="한 줄 소개" hint="어떤 상황에 쓰는 도우미인지 알아볼 수 있게 적어 주세요.">{p => <input {...p} maxLength={400} placeholder="예: 어려운 과학 이야기를 30초 대본으로 바꿔요." value={draft.description} onChange={e => edit({ ...draft, description: e.target.value })} />}</Field>
            <Field id="agent-instructions" label="맡길 일" hint="해야 할 일, 말투, 꼭 지킬 규칙을 포함하면 더 분명해져요.">{p => <textarea {...p} required rows={6} maxLength={8000} placeholder="예: 주어진 주제로 30초 대본을 써 주세요. 첫 문장은 질문으로 시작하고, 전문 용어는 쉽게 풀어 주세요." value={draft.instructions} onChange={e => edit({ ...draft, instructions: e.target.value })} />}</Field>
          </section>
          <section id="information" className="editor-section"><div className="section-heading"><span className="step-number">2</span><div><h2>실행할 때 쓸 입력 양식과 결과 항목</h2><p className="muted">1번은 ‘항상 지킬 작업 지침’, 2번은 ‘실행할 때마다 바뀔 정보’를 정하는 곳이에요.</p></div></div>
            <div className="run-preview-entry"><div><strong>직접 입력해 보면 더 쉬워요</strong><p className="muted">현재 작성한 항목으로 실행 화면을 열어 봅니다. 저장하지 않은 설정도 반영되며, 실제 AI 호출은 하지 않아요.</p></div>
              <button ref={previewButton} className="button button--secondary" type="button" onClick={() => setPreview(true)}>실행 화면 미리보기 →</button></div>
            <div className="io-section"><div className="io-heading"><span aria-hidden="true">↘</span><h3>실행 전에 무엇을 물어볼까요?</h3></div><p className="muted">아래에는 ‘고양이 이야기’ 같은 실제 값 대신 ‘영상으로 만들 주제’처럼 항목의 설명을 적어 주세요. 바꾼 뒤 실행 화면 미리보기를 열면 입력란에 반영돼요.</p>
              <FriendlyFields kind="input" value={draft.input_schema} onChange={input_schema => edit({ ...draft, input_schema })} /></div>
            <div className="io-section"><h3>답변 받는 방식</h3><p className="muted">답변 내용은 실행 후에 알 수 있어요. 여기서는 답변을 자유롭게 받을지, 정해진 항목으로 나눠 받을지만 선택합니다.</p>
              <fieldset className="output-mode"><legend className="sr-only">답변 받는 방식</legend>
                <label className="tool-choice"><input type="radio" name="output-mode" checked={draft.output_schema.type === "string"} onChange={() => changeOutputMode(true)} />
                  <span><strong>자유로운 답변으로 받기</strong><span className="muted">기본 · 별도 설정 없이 AI의 답변을 텍스트로 받아요.</span></span></label>
                <label className="tool-choice"><input type="radio" name="output-mode" checked={draft.output_schema.type !== "string"} onChange={() => changeOutputMode(false)} />
                  <span><strong>항목별로 받기</strong><span className="muted">AI가 채워줄 답변 항목을 정하세요. 예: 제목 · 대본 · 해시태그</span></span></label>
              </fieldset>
              {draft.output_schema.type !== "string" && <><p className="muted">예를 들어 ‘제목’, ‘대본’, ‘해시태그’를 항목으로 정하면, 실행할 때 AI가 각 항목에 맞는 내용을 작성해요. 아래에는 답변 자체가 아니라 AI가 작성할 항목의 설명을 적어 주세요.</p><FriendlyFields kind="output" value={draft.output_schema} onChange={output_schema => edit({ ...draft, output_schema })} /></>}</div>
            <details className="advanced"><summary>구체적인 입력값과 결과 예시 더 보기</summary><ExecutionExample /></details>
          </section>
          <section id="tools" className="editor-section"><div className="section-heading"><span className="step-number">3</span><div><h2>함께 쓸 도구</h2><p className="muted">선택 사항 · {draft.tools.length}개 선택됨</p></div></div>
            <p className="muted">필요한 경우만 선택하세요. 도구 없이도 에이전트를 등록할 수 있어요.</p>
            <GroupedTools tools={tools} selected={draft.tools} agentId={id} onChange={tools => edit({ ...draft, tools })} />
          </section>
          <details className="advanced editor-section"><summary>고급 설정 <span>모델과 실행 한도</span></summary><p className="muted">처음에는 기본값을 유지하세요. 실행 기능이 연결되면 적용할 상한입니다.</p>
            <Field id="model-profile" label="사용할 모델">{p => <select {...p} value={draft.model_profile} onChange={e => edit({ ...draft, model_profile: e.target.value })}><option value="default">작업 공간 기본 모델</option></select>}</Field>
            {([['model_calls', '모델 호출 횟수', 1, 20], ['tool_calls', '도구 호출 횟수', 0, 40], ['depth', '하위 호출 깊이', 0, 3], ['seconds', '실행 시간(초)', 1, 900]] as const).map(([key, label, min, max]) =>
              <Field key={key} id={`limit-${key}`} label={label}>{p => <input {...p} type="number" required min={min} max={max} value={draft.limits[key]} onChange={e => edit({ ...draft, limits: { ...draft.limits, [key]: e.target.valueAsNumber } })} />}</Field>)}
          </details>
        </div><aside className="editor-summary"><Card><p className="eyebrow">한눈에 보기</p><div className="agent-avatar" aria-hidden="true">A</div><h2>{draft.name || "나의 새 에이전트"}</h2><p className="muted">{draft.description || "맡길 일을 정하면 도우미의 모습이 완성돼요."}</p>
          <div className="summary-flow"><span>받을 정보</span><p>{Object.entries(draft.input_schema.properties || {}).map(([k, v]) => v.description || k).join(" · ") || "세부 형식 참고"}</p><span className="flow-arrow" aria-hidden="true">↓</span><span>답변 받는 방식</span><p>{draft.output_schema.type === "string" ? "자유로운 답변" : "항목별 답변 · " + (Object.entries(draft.output_schema.properties || {}).map(([k, v]) => v.description || k).join(" · ") || "사용자 지정 형식")}</p></div>
          <p className="muted">선택한 도구 {draft.tools.length}개</p><div className="notice"><strong>지금은 설정을 준비하는 단계예요</strong><p>실제 AI 실행은 아직 제공되지 않아요. 이 요약은 생성 결과가 아닙니다.</p></div>
        </Card><div className="save-guide"><strong>작성한 다음에는</strong><ol><li>초안을 저장해 내용을 보관하세요.</li><li>다른 에이전트가 쓸 수 있게 하려면 도구로 등록하세요.</li></ol><p>등록해도 외부에 공개되지 않습니다.</p></div></aside></div>
        <div className="editor-actions"><div><strong>{dirty ? "변경 내용을 저장해 주세요" : id ? "초안이 저장되어 있어요" : "준비되면 초안을 저장하세요"}</strong><p className="muted">{!id || dirty ? "저장한 다음 도구로 등록할 수 있어요." : "등록된 버전은 보관되며, 초안을 수정해도 바뀌지 않아요."}</p></div>
          <div className="badge-row"><Button variant="secondary" type="submit" disabled={busy}>{busy ? "처리 중…" : "초안 저장"}</Button><Button disabled={!id || dirty || busy} onClick={() => action("publish")}>도구로 등록</Button></div>
        </div>
      </fieldset>
      <div className="editor-feedback" aria-live="polite">{error && <p role="alert" className="field-error">{error}</p>}{notice && <p role="status">{notice}</p>}
        {issues.length > 0 && <ul role="alert" className="validation-list">{issues.map((issue, i) => <li key={i}><a href={issue.field_path.includes("schema") ? "#information" : "#role"}>설정 확인</a>: {issue.message} <small>({issue.field_path})</small></li>)}</ul>}</div>
    </form>
    <details className="version-section advanced"><summary>등록한 버전 <span>{versions.length}개</span></summary>{versions.length === 0 ? <p className="muted">도구로 등록하면 이곳에서 이전 설정을 확인할 수 있어요.</p> : versions.map(v =>
      <div key={v.version} className="version-card"><h3>버전 {v.version} · {v.definition.name}</h3><p>{v.definition.description}</p><p className="muted">이 버전은 보관되어 있으며 현재 초안 수정의 영향을 받지 않습니다.</p><details><summary>전체 설정 보기</summary><pre>{JSON.stringify(v.definition, null, 2)}</pre></details></div>)}</details>
  </>;
}
