"use client";
import { AgentIconPicker } from "./agent-icon-picker";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, message, type Agent, type Definition, type Issue, type Tool, type Version, type SchemaNode } from "../lib/registry";
import { AgentIcon, Button, Card, Field, StatusBadge, HelpText } from "./ui";
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
  const [models, setModels] = useState<{id:string;label:string;provider:"openai"|"anthropic"}[]>([]);
  const [defaultModel, setDefaultModel] = useState<string | null>(null);
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
    Promise.all([api<{models: typeof models;default_model:string|null}>("/ai-models"), api<Tool[]>("/tools"), id ? api<Agent>(`/agents/${id}`) : Promise.resolve(null)])
      .then(([modelCatalog, catalog, agent]) => { if (!active) return; setModels(modelCatalog.models); setDefaultModel(modelCatalog.default_model); setTools(catalog);
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
        setVersions(saved.versions || []); setNotice("에이전트 버전을 등록했습니다. 등록만으로 AI가 실행되지는 않습니다.");
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
      <StatusBadge tone={dirty ? "warning" : "neutral"}>{dirty ? "저장 전 변경 있음" : id ? "초안 저장됨" : "새 에이전트"}</StatusBadge></div>
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
        <details className="advanced editor-section"><summary>AI에 어떤 내용이 전달되나요?</summary>
          <ul><li><strong>에이전트 지침:</strong> 실행에 선택된 등록 버전의 지침을 전달합니다. 편집 중인 초안이 바로 적용되지는 않습니다.</li>
          <li><strong>사용자 입력:</strong> 실행 화면에 입력한 주제·자료 등 실제 값이 전달됩니다. 이 화면에서는 입력 항목을 설정합니다.</li>
          <li><strong>답변 형식:</strong> 개별 실행과 자동화 모두 등록한 답변 형식을 사용합니다. 자유로운 답변은 글로, 항목별 답변은 설정한 항목으로 받습니다.</li>
          <li><strong>대본 수정:</strong> 이전 대본과 수정 요청도 함께 전달됩니다. 서비스가 정한 대본 작성 범위와 기본 지침도 포함됩니다.</li>
          <li><strong>관리용 설정:</strong> 이름·한 줄 소개는 현재 생성 프롬프트에 포함되지 않습니다. 모델 선택과 실행 한도는 호출을 제어하는 설정입니다.</li></ul>
          <p className="muted">저장·등록·화면 미리보기만으로는 AI에 전송하지 않습니다. 실제 실행 시 선택한 공급자의 API로 전달됩니다. 자동화의 도구 결과는 다음 블록의 입력으로 연결한 경우 전달됩니다.</p>
        </details>
        <div className="guided-layout"><div className="stack">
          <section id="role" className="editor-section"><div className="section-heading"><span className="step-number">1</span><div><h2>에이전트 기본 설정</h2><p className="muted">이름을 붙이고, 에이전트가 실행할 때마다 따를 지침을 적어 주세요.</p></div></div>
            <Field id="agent-name" label="에이전트 이름" annotation="관리용">{p => <input {...p} required maxLength={80} placeholder="예: 우리 채널의 쇼츠 작가" value={draft.name} onChange={e => edit({ ...draft, name: e.target.value })} />}</Field>
            <AgentIconPicker value={draft.icon} onChange={icon=>edit({...draft,icon})}/>
            <Field id="agent-description" label="한 줄 소개" annotation="관리용" hint="어떤 상황에 쓰는 도우미인지 알아볼 수 있게 적어 주세요.">{p => <input {...p} maxLength={400} placeholder="예: 어려운 과학 이야기를 30초 대본으로 바꿔요." value={draft.description} onChange={e => edit({ ...draft, description: e.target.value })} />}</Field>
            <Field id="agent-purpose" label="에이전트 용도" hint="이미지 검수는 이미지 결과 화면에서 실행합니다. 이미지를 볼 수 있는 모델을 선택하세요.">{p=><select {...p} value={draft.purpose || "general"} onChange={e=>edit({...draft,purpose:e.target.value as "general"|"image_review"})}><option value="general">일반 에이전트</option><option value="image_review">이미지 검수 에이전트</option></select>}</Field>
            <Field id="agent-instructions" label="에이전트 지침" annotation="AI에 전달" help="이 에이전트가 매번 지킬 작업 규칙입니다. 예: ‘30초 대본을 쓰고, 첫 문장은 질문으로 시작하세요.’ ‘고양이가 상자를 좋아하는 이유’ 같은 이번 주제는 여기 대신 실행 화면에 입력하세요." hint="매번 실행할 때 적용할 역할, 말투, 꼭 지킬 규칙을 적어 주세요. 주제처럼 실행마다 달라지는 내용은 실행 화면에서 입력합니다.">{p => <textarea {...p} required rows={6} maxLength={8000} placeholder="예: 주어진 주제로 30초 대본을 써 주세요. 첫 문장은 질문으로 시작하고, 전문 용어는 쉽게 풀어 주세요." value={draft.instructions} onChange={e => edit({ ...draft, instructions: e.target.value })} />}</Field>
            <Field id="model-profile" label="사용할 AI 모델" annotation="호출 설정" help="누가 답변을 만들지 선택합니다. 기본 모델은 관리자가 정한 현재 모델을 따르고, 특정 모델을 고르면 그 모델을 계속 사용합니다. 모델에 따라 답변 특성·속도·비용이 달라집니다. 새 버전을 등록해도 이전 작업의 기록은 바뀌지 않습니다." hint="기본 모델을 선택하면 새 실행 시 작업 공간의 현재 기본 모델을 따릅니다. 특정 모델을 선택하면 해당 모델을 사용합니다. 선택을 변경한 뒤에는 초안 저장 후 새 버전을 등록하세요.">{p => <select {...p} value={draft.model ? `${draft.provider}:${draft.model}` : ""} onChange={e => { const selected = models.find(m => `${m.provider}:${m.id}` === e.target.value); edit({ ...draft, provider: selected?.provider ?? null, model: selected?.id ?? null }); }}><option value="">작업 공간 기본 모델{defaultModel ? ` · ${defaultModel}` : " · 관리자 설정 필요"}</option>{draft.model && !models.some(m => m.id === draft.model && m.provider === draft.provider) && <option value={`${draft.provider}:${draft.model}`}>{draft.model} · 사용할 수 없음</option>}{models.map(m => <option key={`${m.provider}:${m.id}`} value={`${m.provider}:${m.id}`}>{m.provider === "openai" ? "OpenAI" : "Claude"} · {m.label}</option>)}</select>}</Field>
          </section>
          <section id="information" className="editor-section"><div className="section-heading"><span className="step-number">2</span><div><h2>실행할 때 쓸 입력 양식과 결과 항목</h2><p className="muted">1번은 ‘항상 지킬 작업 지침’, 2번은 ‘실행할 때마다 바뀔 정보’를 정하는 곳이에요.</p></div></div>
            <div className="run-preview-entry"><div><strong>직접 입력해 보면 더 쉬워요</strong><p className="muted">현재 작성한 항목으로 실행 화면을 열어 봅니다. 저장하지 않은 설정도 반영되며, 실제 AI 호출은 하지 않아요.</p></div>
              <button ref={previewButton} className="button button--secondary" type="button" onClick={() => setPreview(true)}>실행 화면 미리보기 →</button></div>
            <div className="io-section"><div className="io-heading"><span aria-hidden="true">↘</span><div className="help-row"><h3>사용자가 입력할 항목</h3><HelpText ai label="사용자가 입력할 항목 · 실행 시 입력값을 AI에 전달">실행할 때 사용자에게 받을 정보의 이름과 설명을 정합니다. 예: ‘영상 주제’, ‘대상 시청자’. 여기에는 입력 항목을 만들고, 실제 주제나 시청자는 실행 화면에서 입력합니다.</HelpText></div></div><p className="muted">항목 이름과 입력 방식, 선택지, 필수 여부, 기본값을 정하세요. 실행 화면 미리보기에서 사용자가 보게 될 입력 양식을 바로 확인할 수 있어요.</p>
              <FriendlyFields kind="input" value={draft.input_schema} onChange={input_schema => edit({ ...draft, input_schema })} /></div>
            <div className="io-section"><div className="help-row"><h3>답변 받는 방식</h3><HelpText ai label="답변 받는 방식 · 자동화의 AI 응답 형식"><strong>자동화의 AI 응답 형식입니다. </strong>글로 읽기만 한다면 자유로운 답변을 선택하세요. 제목·대본·해시태그를 따로 확인하거나 다음 자동화 블록에 전달하려면 항목별 답변을 선택하세요. 실제 내용은 실행할 때 AI가 작성합니다.</HelpText></div><p className="muted">답변 내용은 실행 후에 알 수 있어요. 여기서는 답변을 자유롭게 받을지, 정해진 항목으로 나눠 받을지만 선택합니다.</p>
              <fieldset className="output-mode"><legend className="sr-only">답변 받는 방식</legend>
                <label className="tool-choice"><input type="radio" name="output-mode" checked={draft.output_schema.type === "string"} onChange={() => changeOutputMode(true)} />
                  <span><strong>자유로운 답변으로 받기</strong><span className="muted">기본 · 별도 설정 없이 AI의 답변을 텍스트로 받아요.</span></span></label>
                <label className="tool-choice"><input type="radio" name="output-mode" checked={draft.output_schema.type !== "string"} onChange={() => changeOutputMode(false)} />
                  <span><strong>항목별로 받기</strong><span className="muted">AI가 채워줄 답변 항목을 정하세요. 예: 제목 · 대본 · 해시태그</span></span></label>
              </fieldset>
              {draft.output_schema.type !== "string" && <><p className="muted">예를 들어 ‘제목’, ‘대본’, ‘해시태그’를 항목으로 정하면, 실행할 때 AI가 각 항목에 맞는 내용을 작성해요. 아래에는 답변 자체가 아니라 AI가 작성할 항목의 설명을 적어 주세요.</p><FriendlyFields kind="output" value={draft.output_schema} onChange={output_schema => edit({ ...draft, output_schema })} /></>}</div>
            <div className="approval-setting"><div className="help-row"><h3>답변 확인과 확정</h3><HelpText label="사용자 확정 필요">개별 실행의 답변을 사용자가 확인한 뒤 완료하도록 설정합니다. 대본, 장면 구성 등 답변 종류와 관계없이 적용됩니다. 자동화의 진행 승인은 자동화 빌더의 검토 단계에서 설정하세요.</HelpText></div><label className="checkbox"><input type="checkbox" checked={Boolean(draft.requires_approval)} onChange={e=>edit({...draft,requires_approval:e.target.checked})}/>사용자 확정 필요</label><p className="muted">켜면 답변이 나와도 ‘검토 필요’로 표시됩니다. 사용자가 확정해야 완료되고, 수정하거나 다시 생성하면 재검토가 필요합니다.</p><p className="helper-text">초안 저장 후 새 버전을 등록하면 이후 해당 버전으로 실행하는 작업에 적용됩니다. 이전 작업의 설정은 바뀌지 않습니다.</p></div>
            <details className="advanced"><summary>구체적인 입력값과 결과 예시 더 보기</summary><ExecutionExample /></details>
          </section>
          {draft.purpose!=="image_review" && <section className="editor-section after-task-settings"><h2>답변 이후 작업</h2>
            <p className="muted">캐릭터 이미지 결과에서 사용할 검수 에이전트를 연결합니다. 이미지 생성·사람의 확정과는 별개이며, 검수가 없어도 작업할 수 있습니다.</p>
            <Field id="image-review-agent" label="이미지 검수 에이전트" hint="검수 에이전트를 먼저 만들고 버전을 등록하면 목록에 나타납니다.">{p=><select {...p} value={draft.after_tasks?.image_review?.agent_ref || ""} onChange={e=>edit({...draft,after_tasks:{image_review:e.target.value?{agent_ref:e.target.value,mode:draft.after_tasks?.image_review?.mode || "manual"}:null}})}><option value="">사용 안 함 · 직접 확인</option>{tools.filter(t=>t.purpose==="image_review" && t.agent_id!==id).map(t=><option key={t.id} value={t.id}>{t.name} · v{t.version}</option>)}</select>}</Field>
            {draft.after_tasks?.image_review && <Field id="image-review-mode" label="검수 실행 시점">{p=><select {...p} value={draft.after_tasks!.image_review!.mode} onChange={e=>edit({...draft,after_tasks:{image_review:{...draft.after_tasks!.image_review!,mode:e.target.value as "manual"|"automatic"}}})}><option value="manual">이미지에서 ‘AI 검수 요청’을 누를 때</option><option value="automatic">이미지가 생성되면 자동으로</option></select>}</Field>}
            <p className="helper-text">검수도 별도 API 비용이 발생합니다. 자동 재생성·자동 확정은 하지 않습니다. 초안 저장 후 새 버전을 등록하면 새 작업에 적용되며, 이전 요청과 자동화 블록에는 소급 적용되지 않습니다.</p>
          </section>}
          <section id="tools" className="editor-section"><div className="section-heading"><span className="step-number">3</span><div><div className="help-row"><h2>사용할 도구와 에이전트</h2><HelpText label="사용할 도구와 에이전트">ASA 기본 도구는 길이 검사 같은 기능이고, 내가 만든 에이전트는 지침과 모델을 등록한 AI 도우미입니다. 선택은 자동화의 실행 순서를 정하는 것이 아닙니다. 현재는 연결 설정만 저장되며, 실행 중 이들을 호출하는 기능은 아직 지원하지 않습니다.</HelpText></div><p className="muted">선택 사항 · {draft.tools.length}개 선택됨</p></div></div>
            <p className="muted">현재는 연결 설정만 저장됩니다. 에이전트가 실행 중 도구나 다른 에이전트를 호출하는 기능은 아직 지원하지 않습니다. 선택하지 않아도 등록할 수 있습니다.</p>
            <GroupedTools tools={tools} selected={draft.tools} agentId={id} onChange={tools => edit({ ...draft, tools })} />
          </section>
          <details className="advanced editor-section"><summary>고급 설정 <span>실행 한도</span></summary><div className="help-row"><span>실행 한도 안내</span><HelpText label="실행 한도">한 번의 작업이 AI나 도구를 너무 많이 호출하거나 오래 실행되지 않도록 정하는 제한입니다. 처음에는 기본값을 유지하세요. 도구 호출·위임 한도는 해당 실행 기능이 제공된 뒤 적용됩니다.</HelpText></div><p className="muted">실행 제한을 위한 설정입니다. 도구 호출과 에이전트 위임은 현재 지원하지 않으며, 해당 한도는 기능 연결 후 적용됩니다.</p>
            {([['model_calls', '모델 호출 횟수', 1, 20], ['tool_calls', '도구 호출 횟수', 0, 40], ['depth', '에이전트 위임 단계 제한', 0, 3], ['seconds', '실행 시간(초)', 1, 900]] as const).map(([key, label, min, max]) =>
              <Field key={key} id={`limit-${key}`} label={label} hint={key === "depth" ? "예: A가 B에게 위임하면 1단계, B가 C에게 다시 위임하면 2단계입니다." : undefined}>{p => <input {...p} type="number" required min={min} max={max} value={draft.limits[key]} onChange={e => edit({ ...draft, limits: { ...draft.limits, [key]: e.target.valueAsNumber } })} />}</Field>)}
          </details>
        </div><aside className="editor-summary"><Card><p className="eyebrow">한눈에 보기</p><AgentIcon icon={draft.icon}/><h2>{draft.name || "나의 새 에이전트"}</h2><p className="muted">{draft.description || "에이전트의 역할과 지침을 설정해 주세요."}</p>
          <div className="summary-flow"><span>사용자가 입력할 항목</span><p>{Object.entries(draft.input_schema.properties || {}).map(([k, v]) => v.description || k).join(" · ") || "세부 형식 참고"}</p><span className="flow-arrow" aria-hidden="true">↓</span><span>답변 받는 방식</span><p>{draft.output_schema.type === "string" ? "자유로운 답변" : "항목별 답변 · " + (Object.entries(draft.output_schema.properties || {}).map(([k, v]) => v.description || k).join(" · ") || "사용자 지정 형식")}</p></div>
          <p className="muted">선택한 도구·에이전트 {draft.tools.length}개</p><div className="notice"><strong>현재 초안 요약</strong><p>초안 저장은 편집 내용을 보관하고, 버전 등록은 실행에 사용할 설정을 확정합니다. 실제 AI 호출은 별도의 실행 요청과 워커 처리가 필요합니다.</p></div>
        </Card><div className="save-guide"><div className="help-row"><strong>작성한 다음에는</strong><HelpText label="초안 저장과 버전 등록">초안 저장은 작성 중인 설정을 보관합니다. 에이전트 등록 또는 새 버전 등록은 실행에 사용할 설정을 확정합니다. 수정 후에는 두 단계를 모두 진행하세요. 등록만으로 작업이 실행되거나 AI 비용이 발생하지 않으며, 이전 버전은 유지됩니다.</HelpText></div><ol><li>초안을 저장해 내용을 보관하세요.</li><li>처음에는 에이전트를 등록하고, 수정 후에는 새 버전을 등록하세요.</li></ol><p>등록해도 외부에 공개되지 않습니다.</p></div></aside></div>
        <div className="editor-actions"><div><strong>{dirty ? "변경 내용을 저장해 주세요" : id ? "초안이 저장되어 있어요" : "준비되면 초안을 저장하세요"}</strong><p className="muted">{!id || dirty ? "초안을 저장한 다음 에이전트 버전을 등록할 수 있어요." : "등록된 버전은 보관되며, 초안을 수정해도 바뀌지 않아요."}</p></div>
          <div className="badge-row"><Button variant="secondary" type="submit" disabled={busy}>{busy ? "처리 중…" : "초안 저장"}</Button><Button disabled={!id || dirty || busy} onClick={() => action("publish")}>{versions.length ? "새 버전 등록" : "에이전트 등록"}</Button></div>
        </div>
      </fieldset>
      <div className="editor-feedback" aria-live="polite">{error && <p role="alert" className="field-error">{error}</p>}{notice && <p role="status">{notice}</p>}
        {issues.length > 0 && <ul role="alert" className="validation-list">{issues.map((issue, i) => <li key={i}><a href={issue.field_path.includes("schema") ? "#information" : "#role"}>설정 확인</a>: {issue.message} <small>({issue.field_path})</small></li>)}</ul>}</div>
    </form>
    <details className="version-section advanced"><summary>에이전트 버전 이력 <span>{versions.length}개</span></summary>{versions.length === 0 ? <p className="muted">에이전트 버전을 등록하면 이곳에서 등록한 설정을 확인할 수 있어요.</p> : versions.map(v =>
      <div key={v.version} className="version-card"><h3>버전 {v.version} · {v.definition.name}</h3><p>{v.definition.description}</p><p className="muted">이 버전은 보관되어 있으며 현재 초안 수정의 영향을 받지 않습니다.</p><details><summary>설정 원본 보기(JSON)</summary><pre>{JSON.stringify(v.definition, null, 2)}</pre></details></div>)}</details>
  </>;
}
