"use client";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, message, type Issue, type SchemaNode, type Tool } from "../lib/registry";
import { Button, Card, Field, StatusBadge } from "./ui";
import { GraphIcon } from "./graph-icon";
import { GraphEditor } from "./automation-graph-editor";
import { newGraph, convertGraph, type AutomationDraft } from "../lib/automation-graph";
import { AutomationLauncher } from "./automation-launcher";
import { useDirtyGuard } from "./registry-shell";

type Binding = { source: string; field?: string; value?: unknown };
type Step = { id: string; label: string; tool_id: string; review_after?: boolean; bindings: Record<string, Binding> };
type Draft = AutomationDraft;
type Saved = { id: string; revision: number; draft: Draft };
type Result = { id: string; kind: string; input: unknown; output?: unknown; message?: string };
const blank = (): Draft => ({name: "새 자동화", description: "", steps: [], graph: newGraph()});
const schemaFields = (s?: SchemaNode): [string, SchemaNode][] => !s ? [] : s.type === "object" ? Object.entries(s.properties || {}) : [["$", s]];
const fieldName = (key: string, s: SchemaNode) => s.description || (key === "$" ? "내용" : key);
function parseValue(text: string, schema: SchemaNode): unknown {
  if (schema.type === "string") return text;
  try { return JSON.parse(text); } catch { return text; }
}
function valueText(value: unknown) { return typeof value === "string" ? value : value === undefined ? "" : JSON.stringify(value, null, 2); }

export function AutomationBuilder() {
  const inspectorHeading = useRef<HTMLDivElement>(null);
  const picker = useRef<HTMLDialogElement>(null);
  const [insertAt, setInsertAt] = useState(0);
  const [search, setSearch] = useState("");
  function showPicker(at: number) { setInsertAt(at); setSearch(""); picker.current?.showModal(); }
  const [tools, setTools] = useState<Tool[]>([]);
  const [list, setList] = useState<Saved[]>([]);
  const [launch, setLaunch] = useState<{item: Saved; mode: "run" | "schedule" | "history"} | null>(null);
  const [current, setCurrent] = useState<Saved | null>(null);
  const [draft, setDraft] = useState<Draft>(blank);
  const [baseline, setBaseline] = useState(JSON.stringify(blank()));
  const [selected, setSelected] = useState("");
  const [tab, setTab] = useState<"edit" | "test">("edit");
  useEffect(() => {
    if (selected || tab === "test") {
      inspectorHeading.current?.focus({preventScroll: true});
      if (window.matchMedia("(max-width: 1100px)").matches) inspectorHeading.current?.scrollIntoView({block:"start"});
    }
  }, [selected, tab]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [issues, setIssues] = useState<Issue[]>([]);
  const [prompt, setPrompt] = useState("");
  const [samples, setSamples] = useState<Record<string, unknown>>({});
  const [results, setResults] = useState<Result[]>([]);
  const guard = useDirtyGuard();
  const dirty = JSON.stringify(draft) !== baseline;
  useEffect(() => { guard(dirty); return () => guard(false); }, [dirty, guard]);
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => { if (dirty) e.preventDefault(); };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);
  useEffect(() => { let alive = true;
    Promise.all([api<Tool[]>("/tools"), api<Saved[]>("/automations")]).then(([t,l]) => {
      if (alive) { setTools(t); setList(l); }
    }).catch(e => { if (alive) setError(message(e)); }).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);
  function change(next: Draft) { setDraft(next); setResults([]); setIssues([]); setNotice(""); }
  function open(item?: Saved) {
    if (dirty && !window.confirm("저장하지 않은 변경을 버리고 이동할까요?")) return;
    const next = item?.draft || blank();
    setCurrent(item || {id: crypto.randomUUID(), revision: 0, draft: next});
    setDraft(next); setBaseline(JSON.stringify(next)); setSelected("");
    setSamples({}); setResults([]); setIssues([]); setError(""); setNotice(""); setTab("edit");
  }
  const toolFor = (step: Step) => tools.find(t => t.id === step.tool_id);
  const step = draft.steps.find(s => s.id === selected);
  const index = step ? draft.steps.indexOf(step) : -1;
  const selectedTool = step && toolFor(step);
  function updateStep(next: Step) { change({...draft, steps: draft.steps.map(s => s.id === next.id ? next : s)}); }
  function add(tool: Tool) {
    const id = "step_" + crypto.randomUUID().replaceAll("-", "");
    const next: Step = {id, label: tool.name, tool_id: tool.id, bindings: {}};
    change({...draft, steps: [...draft.steps.slice(0,insertAt), next, ...draft.steps.slice(insertAt)]}); setSelected(id); setTab("edit"); picker.current?.close();
  }
  function move(offset: number) {
    const next = [...draft.steps];
    [next[index], next[index + offset]] = [next[index + offset], next[index]];
    change({...draft, steps: next});
  }
  async function action(kind: "save" | "validate" | "preview") {
    setBusy(true); setError(""); setNotice(""); setIssues([]); setResults([]);
    try {
      if (kind === "save") {
        const identity = current || {id: crypto.randomUUID(), revision: 0, draft};
        setCurrent(identity);
        const saved = await api<Saved>("/automations", "POST", {id: identity.id, revision: identity.revision, draft});
        setCurrent(saved); setDraft(saved.draft); setBaseline(JSON.stringify(saved.draft));
        setList(old => [saved, ...old.filter(v => v.id !== saved.id)]);
        setNotice("자동화를 저장했습니다. 기존 예약에는 변경이 자동으로 반영되지 않습니다.");
      } else if (kind === "validate") {
        const data = await api<{issues: Issue[]}>("/automations/validate", "POST", draft);
        setIssues(data.issues);
        if (!data.issues.length) setNotice("구성 검증 완료. 연결 테스트에서 실제 전달 값도 확인하세요. AI 실행 검증은 아닙니다.");
      } else {
        const data = await api<{results: Result[]}>("/automations/preview", "POST", {draft,prompt,samples});
        setResults(data.results);
        setNotice("연결 테스트 결과입니다. AI 호출 0회 · 샘플 결과는 실제 AI 답변이 아닙니다.");
      }
    } catch (e) { setError(message(e)); if (e instanceof ApiError) setIssues(e.issues); }
    finally { setBusy(false); }
  }
  if (loading) return <p role="status">자동화 작업 공간을 여는 중…</p>;
  if (launch) return <AutomationLauncher item={launch.item} initial={launch.mode} onClose={() => setLaunch(null)}/>;
  if (!current) return <section className="flow-library">
    <div className="flow-library-heading"><div><p className="eyebrow">AUTOMATIONS</p><h1>내 자동화</h1><p className="muted">반복하는 작업을 하나의 흐름으로 만들어 보세요.</p></div><Button onClick={() => open()}>＋ 새 자동화</Button></div>
    {error && <p role="alert" className="field-error">{error}</p>}
    {list.length ? <div className="flow-library-grid">{list.map(item => <article className="flow-library-card" key={item.id} aria-label={item.draft.name}>
 <header className="automation-card-heading"><span className="flow-library-icon" aria-hidden="true"><GraphIcon kind="workflow"/></span><span className="automation-version">v{item.revision}</span></header>
 <div className="automation-card-copy"><h2><button className="automation-title" onClick={()=>open(item)} title={item.draft.name}>{item.draft.name}</button></h2><p title={item.draft.description||"나만의 작업 흐름"}>{item.draft.description||"나만의 작업 흐름"}</p></div>
 <div className="flow-library-meta"><span><GraphIcon kind="workflow"/>{item.draft.graph?.nodes.length ?? item.draft.steps.length}개 블록</span><button className="automation-edit" onClick={()=>open(item)} aria-label={`${item.draft.name} 편집`}><GraphIcon kind="edit"/>편집</button></div>
 <footer className="automation-card-actions"><Button onClick={()=>setLaunch({item,mode:"run"})} aria-label={`${item.draft.name} 실행`}><GraphIcon kind="start"/>실행</Button><Button variant="secondary" onClick={()=>setLaunch({item,mode:"schedule"})} aria-label={`${item.draft.name} 시간 예약`}><GraphIcon kind="clock"/>예약</Button><Button variant="secondary" onClick={()=>setLaunch({item,mode:"history"})} aria-label={`${item.draft.name} 실행 기록`}><GraphIcon kind="history"/>기록</Button></footer>
 </article>)}</div> : <Card><h2>첫 자동화를 만들어 보세요</h2><p className="muted">예: 대본 작성 → 길이 검사. 필요한 에이전트와 도구를 순서대로 추가하면 됩니다.</p><Button onClick={() => open()}>자동화 만들기</Button></Card>}
  </section>;
  const panelOpen = tab === "test" || Boolean(step);
  return <div className="flow-editor">
    <header className="flow-toolbar"><div className="flow-toolbar-title"><Button variant="secondary" disabled={busy} onClick={() => {if (dirty && !window.confirm("저장하지 않은 변경을 버리고 목록으로 돌아갈까요?")) return; setCurrent(null);setDraft(blank());setBaseline(JSON.stringify(blank()));}}>← 목록</Button><div><label className="sr-only" htmlFor="automation-name">자동화 이름</label><input id="automation-name" value={draft.name} maxLength={80} disabled={busy} onChange={e => change({...draft,name:e.target.value})}/><span className="flow-save-state">{dirty ? "저장하지 않은 변경" : current.revision ? "저장됨 · 초안" : "새 초안"}</span></div></div><div className="badge-row"><Button variant="secondary" disabled={busy} onClick={() => {setTab("test");setSelected("");}}>연결 테스트</Button><Button disabled={busy || !draft.name.trim()} onClick={() => action("save")}>{busy ? "처리 중…" : "저장"}</Button></div></header>
    {error && <p role="alert" className="field-error flow-feedback">{error}</p>}
    {notice && <p role="status" className="flow-feedback">{notice}</p>}
    {issues.length > 0 && <div className="flow-feedback"><strong>연결을 확인해 주세요</strong><ul>{issues.map((i,n) => <li key={n}><button className="automation-error" onClick={() => {setSelected(i.field_path.split(".")[0]);setTab("edit");}}>{draft.steps.find(s => i.field_path.startsWith(s.id))?.label || "자동화"}: {i.message}</button></li>)}</ul></div>}
    {draft.graph ? <GraphEditor draft={draft} change={change} tools={tools} busy={busy} testOpen={tab === "test"} closeTest={() => setTab("edit")}/> : <><div className="flow-feedback"><span>기존 순차 자동화</span> <Button variant="secondary" disabled={busy} onClick={() => {change(convertGraph(draft));setSelected("");}}>자유 연결 그래프로 전환</Button><p className="muted">전환 후 저장을 눌러야 반영됩니다. 기존 입력 연결은 유지됩니다.</p></div><div className={`flow-workbench ${panelOpen ? "has-panel" : ""}`}>
      <section className="flow-canvas" aria-label="자동화 작업 순서"><div className="flow-canvas-heading"><div><h2>작업 흐름</h2><p>위에서 아래로, 순서대로 이어집니다.</p></div><span>{draft.steps.length}개 단계</span></div>
        <div className="flow-lane"><div className="flow-terminal"><span className="flow-terminal-icon" aria-hidden="true">↳</span><div><strong>시작 요청</strong><small>실행할 때 주제와 조건을 입력해요</small></div></div>
        {Array.from({length:draft.steps.length + 1},(_,n) => <div key={draft.steps[n]?.id || "end"}><div className="flow-connector"><button disabled={busy || draft.steps.length >= 50} onClick={() => showPicker(n)} aria-label={`${n + 1}번째 위치에 작업 추가`}>＋</button></div>{draft.steps[n] && <button disabled={busy} className="flow-block" aria-pressed={selected === draft.steps[n].id && tab === "edit"} onClick={() => {setSelected(draft.steps[n].id);setTab("edit");}}><span className="flow-block-index">{String(n+1).padStart(2,"0")}</span><span><small>{toolFor(draft.steps[n])?.kind === "agent" ? "AI 에이전트" : "ASA 도구"}</small><strong>{draft.steps[n].label}</strong><span className="muted">{Object.keys(draft.steps[n].bindings).length ? `${Object.keys(draft.steps[n].bindings).length}개 입력 연결` : "전달할 내용을 설정하세요"}</span></span><span className="flow-block-edit" aria-hidden="true">↗</span></button>}</div>)}
        {!draft.steps.length && <p className="flow-empty-hint">＋를 눌러 첫 작업을 추가하세요.<br/>대본 작성부터 시작해도 좋아요.</p>}
        <div className="flow-terminal"><span className="flow-terminal-icon" aria-hidden="true">✓</span><div><strong>최종 결과</strong><small>마지막 단계의 결과를 받습니다</small></div></div></div>
        <p className="flow-canvas-footnote">블록을 선택하면 전달할 내용을 설정할 수 있어요.</p>
      </section>
      {panelOpen && <aside className="flow-inspector" aria-label={tab === "test" ? "연결 테스트" : "작업 설정"}><div ref={inspectorHeading} tabIndex={-1} className="flow-inspector-heading"><strong>{tab === "test" ? "연결 테스트" : "작업 설정"}</strong><Button variant="secondary" aria-label="패널 닫기" onClick={() => {setSelected("");setTab("edit");}}>×</Button></div>
      {tab === "edit" ? <Card>{step && selectedTool ? <><h2>{index + 1}. {step.label}</h2><p className="muted">{selectedTool.description}</p><Field id="step-label" label="화면에 표시할 단계 이름">{p => <input {...p} disabled={busy} maxLength={80} value={step.label} onChange={e => updateStep({...step,label:e.target.value})} />}</Field>
        <div className="badge-row"><Button variant="secondary" disabled={busy || index === 0} onClick={() => move(-1)}>위로</Button><Button variant="secondary" disabled={busy || index === draft.steps.length - 1} onClick={() => move(1)}>아래로</Button><Button variant="secondary" disabled={busy} onClick={() => {change({...draft,steps:draft.steps.filter(s => s.id !== step.id)});setSelected("");}}>블록 제거</Button></div>
        <label className="automation-review-toggle"><input type="checkbox" checked={step.review_after || false} disabled={busy} onChange={e => updateStep({...step,review_after:e.target.checked})}/>이 단계 결과를 확인한 뒤 계속하기</label>
        <h3>이 작업에 전달할 내용</h3><p className="muted">시작 요청, 앞 단계의 결과 또는 직접 입력한 값을 연결하세요.</p>
        {schemaFields(selectedTool.input_schema).map(([key,schema]) => {const b = step.bindings[key]; const options = [{value:"input|",label:"시작 · 사용자의 요청"}, ...draft.steps.slice(0,index).flatMap(prev => {const output = toolFor(prev)?.output_schema;return [{value:prev.id+"|",label:prev.label+" · 전체 결과"},...(output?.type === "object" ? Object.entries(output.properties || {}).map(([k,v]) => ({value:prev.id+"|"+k,label:prev.label+" · "+fieldName(k,v)})) : [])];})];
          return <div className="automation-binding" key={key}><Field id={step.id+key} label={fieldName(key,schema)} hint={`${selectedTool.input_schema?.type !== "object" || selectedTool.input_schema.required?.includes(key) ? "필수" : "선택"}`}>{p => <select {...p} disabled={busy} value={b ? b.source+"|"+(b.field || "") : ""} onChange={e => {const bindings = {...step.bindings};if (!e.target.value) delete bindings[key];else {const [source,field] = e.target.value.split("|");bindings[key] = {source,field,...(source === "literal" ? {value:schema.type === "string" ? "" : schema.type === "integer" || schema.type === "number" ? schema.minimum ?? 1 : schema.type === "boolean" ? false : schema.type === "array" ? [] : {}} : {})};}updateStep({...step,bindings});}}><option value="">입력 출처 선택</option>{options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}{b && b.source !== "literal" && !options.some(o => o.value === b.source+"|"+(b.field || "")) && <option value={b.source+"|"+(b.field || "")}>연결을 다시 선택하세요</option>}<option value="literal|">직접 입력</option></select>}</Field>
          {b?.source === "literal" && <Field id={step.id+key+"-value"} label={`${fieldName(key,schema)} 직접 입력`} hint={schema.type === "object" || schema.type === "array" ? "객체/목록은 JSON 형식으로 입력하세요." : undefined}>{p => <textarea {...p} disabled={busy} rows={3} value={valueText(b.value)} onChange={e => updateStep({...step,bindings:{...step.bindings,[key]:{...b,value:parseValue(e.target.value,schema)}}})} />}</Field>}</div>;
        })}
        <details><summary>이 작업이 내보내는 결과</summary><ul>{schemaFields(selectedTool.output_schema).map(([k,s]) => <li key={k}>{fieldName(k,s)}</li>)}</ul><p className="muted">다음 블록의 입력 출처에서 선택할 수 있습니다.</p></details>
      </> : <><h2>블록 설정</h2><p className="muted">가운데 작업 블록을 선택하면 입력 연결을 설정할 수 있습니다.</p></>}</Card> : <Card><h2>입력이 잘 전달되는지 확인하세요</h2><Button variant="secondary" disabled={busy || !draft.name.trim()} onClick={() => action("validate")}>연결 상태 확인</Button><p className="muted">AI 호출 없이 입력 전달을 확인합니다. 에이전트 결과는 아래에 직접 넣은 샘플을 사용하며, 길이 검사 도구는 실제 계산합니다.</p>
        <Field id="flow-test-prompt" label="테스트할 요청">{p => <textarea {...p} rows={3} disabled={busy} maxLength={6000} value={prompt} onChange={e => {setPrompt(e.target.value);setResults([]);}} placeholder="예: 고양이를 주제로 30초 쇼츠 대본을 만들어 줘" />}</Field>
        {draft.steps.filter(s => toolFor(s)?.kind === "agent").map(s => <details key={s.id} open><summary>{s.label} · 샘플 결과 입력</summary>{schemaFields(toolFor(s)?.output_schema).map(([key,schema]) => {const object = toolFor(s)?.output_schema?.type === "object";const value = object ? (samples[s.id] as Record<string,unknown> | undefined)?.[key] : samples[s.id]; return <Field key={key} id={s.id+"-sample-"+key} label={`${s.label}: ${fieldName(key,schema)}`} hint="실제 AI 결과가 아닌 테스트용 값">{p => <textarea {...p} rows={3} disabled={busy} value={valueText(value)} onChange={e => {const v = parseValue(e.target.value,schema);setSamples({...samples,[s.id]:object ? {...(samples[s.id] as Record<string,unknown> || {}),[key]:v} : v});setResults([]);}} />}</Field>;})}</details>)}
        <Button disabled={busy || !draft.steps.length || !draft.name.trim()} onClick={() => action("preview")}>{busy ? "확인 중…" : "입력 전달 테스트"}</Button>
        {results.map(r => <div key={r.id} className="automation-binding"><h3>{draft.steps.find(s => s.id === r.id)?.label}</h3><StatusBadge tone={r.kind === "sample" || r.kind === "local_tool" ? "success" : "warning"}>{{sample:"샘플 결과 전달",local_tool:"로컬 도구 계산",needs_sample:"샘플 필요",invalid_input:"입력 확인 필요",invalid_sample:"샘플 형식 확인 필요"}[r.kind] || r.kind}</StatusBadge><h4>전달된 입력</h4><pre className="automation-json">{valueText(r.input)}</pre>{r.output !== undefined && <><h4>결과</h4><pre className="automation-json">{valueText(r.output)}</pre></>}{r.message && <p>{r.message}</p>}</div>)}
      </Card>}
      </aside>}
    </div>
    </>}
    <dialog ref={picker} className="flow-picker" aria-labelledby="flow-picker-title"><div className="flow-picker-heading"><div><p className="eyebrow">ADD A STEP</p><h2 id="flow-picker-title">어떤 작업을 추가할까요?</h2></div><Button variant="secondary" onClick={() => picker.current?.close()} aria-label="작업 선택 닫기">×</Button></div>
      <Field id="block-search" label="에이전트 또는 도구 찾기">{p => <input {...p} autoFocus value={search} onChange={e => setSearch(e.target.value)} placeholder="이름으로 검색"/>}</Field>
      {(["agent","asa"] as const).map(kind => <section key={kind} className="flow-picker-group"><h3>{kind === "agent" ? "내가 만든 에이전트" : "ASA 기본 도구"}</h3>{tools.filter(t => t.kind === kind && t.name.includes(search)).map(t => <button key={t.id} className="flow-picker-item" disabled={busy || !t.available} onClick={() => add(t)}><span><strong>{t.name}</strong><small>{t.description || "등록된 작업"}</small></span><span>{t.available ? "＋" : "준비 중"}</span></button>)}{!tools.some(t => t.kind === kind && t.name.includes(search)) && <p className="muted">일치하는 항목이 없어요.</p>}</section>)}
    </dialog>
  </div>;
}
