"use client";
import { useEffect, useRef, useState } from "react";
import { api, message, type Tool } from "../lib/registry";
import { Button, Card, StatusBadge, Switch } from "./ui";
import { ImageJobProgress, type ImageJob } from "./image-job-progress";
import { ImageReviewPanel, type AssetReview } from "./image-review-panel";
import { ImageModelSelect } from "./image-model-select";
import { itemStateLabel, progressLabel, progressCounts, type WorkProgress } from "../lib/work-progress";
import "./character-studio.css";
import { CharacterHandoff } from "./character-handoff";
import { SceneReferenceVersions, type UsedReference } from "./scene-reference-versions";
import { ImageTaskManager } from "./image-task-manager";
import { AudioProduction } from "./audio-production";

type Character = { id: string; name: string; facts: string; appearance: string; proposed: string; scene_ids: string; image_prompt: string };
type Job = ImageJob & { scene_context?:{reference_overrides?:Record<string,string>;references?:{characters:UsedReference[]}}; review_error_code?:string|null; id: string; character_id: string; version: number; model: string; character: Character; change: string; base_id: string | null; status: string; error_code: string | null; estimated_usd: string | null };
type SceneSource = {script:string;script_matched:boolean;scene:string;scene_matched:boolean;characters:{id:string;name:string;image_id:string|null;role?:string}[]};
type Project = { scene_sources?:Record<string,SceneSource>; kind: "character"|"scene"; blocked?:Record<string,string[]>; context?:{plan:{summary:string;checks:string[];shots:{scene_id:string;shot_id:string;video_notes:string;review_notes:string}[]};input:{aspect_ratio?:string}}; reviews: AssetReview[]; review_config: {agent_ref:string;mode:string}|null; id: string; name: string; request_id: string; source_version: number; characters: Character[]; approved: Record<string,string>; approved_versions?: Record<string,string[]>; jobs: Job[]; worker_online: boolean; excluded: string[]; work_progress: WorkProgress };
type Options = { agents: Tool[]; models: string[]; enabled: boolean };
type LibraryEntry = {id:string;name:string;request_id:string;source_version:number};
const states: Record<string,string> = {queued:"이미지 생성 대기", running:"이미지 생성 중", succeeded:"검토 가능", failed:"생성 실패", unknown:"호출 결과 확인 필요", cancelled:"생성 취소됨"};

export function isCharacterAnswer(value: unknown): boolean {
  if (!value || typeof value !== "object" || !("characters" in value)) return false;
  const chars = (value as {characters:unknown}).characters;
  return Array.isArray(chars) && chars.length > 0 && chars.every(c => c && typeof c.id === "string" && typeof c.name === "string" && typeof c.image_prompt === "string");
}

export function CharacterStudio() {
  const [projects,setProjects]=useState<LibraryEntry[]>([]);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(true);
  useEffect(()=>{api<LibraryEntry[]>("/characters/projects").then(setProjects).catch(e=>setError(message(e))).finally(()=>setLoading(false));},[]);
  return <div className="character-studio"><header><p className="eyebrow">CHARACTER LIBRARY</p><h1>캐릭터 보관함</h1><p className="muted">에이전트 답변에서 만든 캐릭터를 모아 봅니다. 이미지 생성·수정·확정은 해당 실행 결과에서 이어집니다.</p></header>
    {error && <p role="alert">{error}</p>}{loading && <p role="status">보관함을 불러오는 중…</p>}
    {!loading && !error && !projects.length && <Card><p>아직 보관된 캐릭터가 없습니다. 캐릭터 설정 에이전트를 실행한 뒤 답변에서 생성할 인물을 선택하세요.</p><a href="/">작업 공간으로 이동 →</a></Card>}
    <div className="character-grid">{projects.map(p=><Card key={p.id}><h2>{p.name}</h2><p className="muted">에이전트 답변 v{p.source_version}</p><a className="button button--secondary" href={`/?request=${p.request_id}&answer=${p.source_version}`}>실행 결과에서 확인 →</a></Card>)}</div>
  </div>;
}

export function CharacterResults({requestId,version,scene=false}:{requestId:string;version:number;scene?:boolean}) {
  const unit=scene?"씬":"캐릭터";
  const [project,setProject]=useState<Project|null>(null);
  const [options,setOptions]=useState<Options>({agents:[],models:[],enabled:false});
  const [error,setError]=useState("");
  const [activeId,setActiveId]=useState("");
  const [retry,setRetry]=useState(0);
  const drafts=useRef<Record<string,Character>>({});
  const referenceDrafts=useRef<Record<string,Record<string,string>>>({});
  async function refresh() {if(project){const p=await api<Project>(`/characters/projects/${project.id}`);setProject(p);}}
  useEffect(()=>{
    let alive=true;
    Promise.all([api<Options>("/characters/options"),api<Project>("/characters/projects","POST",{id:crypto.randomUUID(),request_id:requestId,source_version:version,name:`${unit} 이미지 · 답변 v${version}`})]).then(([o,p])=>{if(alive){setOptions(o);setProject(p);setError("");}}).catch(e=>{if(alive)setError(message(e));});
    return()=>{alive=false;};
  },[requestId,version,retry]);
  useEffect(()=>{
    if(!project)return;
    const id=project.id;
    const events=new EventSource(`/api/v1/characters/projects/${id}/events`);
    events.addEventListener("snapshot",event=>{
      const p=JSON.parse((event as MessageEvent).data) as Project;
      setError(v=>v.startsWith("실시간 연결을 복구")?"":v);
      setProject(p);
    });
    const disconnected=()=>setError("실시간 연결을 복구하고 있습니다. 이미지 작업을 다시 요청할 필요는 없습니다.");
    events.onerror=disconnected;events.addEventListener("unavailable",disconnected);
    return()=>events.close();
  },[project?.id]);
  const activeIndex=Math.max(0,project?.characters.findIndex(c=>c.id===activeId) ?? 0);
  const currentId=project?.characters[activeIndex]?.id;
  return <section id={scene?"followup-scene_images":"followup-character_images"} className="character-studio" aria-label={scene?"씬별 이미지":"등장인물과 기준 이미지"}><div className="character-heading"><h2>{scene?"씬별 이미지":"등장인물과 기준 이미지"}</h2><a className="button button--secondary" href={scene?"/characters?view=scenes":"/characters"}>이미지 보관함</a></div>
    {error && <p role="alert" className="notice">{error}{!project && <Button variant="secondary" onClick={()=>setRetry(n=>n+1)}>다시 불러오기</Button>}</p>}
    {!project && !error && <p role="status">이미지 작업을 불러오는 중…</p>}
    {project && <><div className="character-overview">
      <div className="character-heading"><h3>{unit} 선택 · {project.characters.length}개</h3><StatusBadge tone={project.worker_online?"success":"warning"}>{project.worker_online?"이미지 워커 연결됨":"이미지 워커 연결 대기"}</StatusBadge></div>
      <div className="character-progress" role="status"><strong>{progressLabel(project.work_progress)}</strong><p>{progressCounts(project.work_progress)}</p></div>
      {!scene && <CharacterHandoff project={project}/>}
      {scene && project.context && <div className="scene-preflight"><strong>AI 분석 요약 · 참고</strong><p>{project.context.plan.summary}</p><details><summary>AI 참고 의견 보기</summary><ul>{project.context.plan.checks.map((c,i)=><li key={i}>{c}</li>)}</ul></details><p className="helper-text">AI 의견은 참고용이며 생성·수정 여부는 사용자가 결정합니다. 실제 기준 이미지 누락이나 연결 오류가 있을 때만 생성을 제한합니다. 대본·장면 원문은 변경하지 않습니다.</p></div>}
      <ImageTaskManager key={project.id} title={`${unit} 이미지 관리`} unit={unit} project={project} options={options} currentId={currentId} onSelect={setActiveId} getReferenceOverrides={c=>referenceDrafts.current[`${project.id}:${c.id}`] || {}} getDraft={c=>drafts.current[`${project.id}:${c.id}`] || c} refresh={refresh}/>
      <p className="muted">{unit}별로 설정을 확인하고 이미지를 생성·확정하세요. 다른 {unit}으로 이동해도 입력은 유지됩니다. 페이지를 떠나기 전에는 생성·수정 요청을 보내야 변경 내용이 저장됩니다.</p>
    </div>
    <div className="character-navigation"><Button variant="secondary" disabled={activeIndex===0} onClick={()=>setActiveId(project.characters[activeIndex-1].id)}>← 이전 {unit}</Button><span aria-live="polite">{activeIndex+1} / {project.characters.length} · {project.characters[activeIndex].name}</span><Button variant="secondary" disabled={activeIndex===project.characters.length-1} onClick={()=>setActiveId(project.characters[activeIndex+1].id)}>다음 {unit} →</Button></div>
    <div className="character-workbench">{project.characters.map(c=><div key={`${project.id}:${c.id}`} hidden={c.id!==currentId}><CharacterCard character={c} project={project} options={options} refresh={refresh} onError={setError} onReferences={value=>{referenceDrafts.current[`${project.id}:${c.id}`]=value;}} onDraft={value=>{drafts.current[`${project.id}:${c.id}`]=value;}}/></div>)}</div></>}

    {!scene&&project&&<AudioProduction key={requestId+":"+version} requestId={requestId} version={version} voicesOnly characterId={currentId}/>}
  </section>;
}

function CharacterCard({character,project,options,refresh,onError,onDraft,onReferences}:{character:Character;project:Project;options:Options;refresh:()=>Promise<void>;onError:(s:string)=>void;onDraft:(c:Character)=>void;onReferences:(value:Record<string,string>)=>void}) {
  const scene=project.kind==="scene";
  const blocked=project.blocked?.[character.id] || [];
  const advice=scene ? project.context?.plan.shots[Number(character.id.split("_")[1])-1]?.review_notes : undefined;
  const initialJobs=project.jobs.filter(j=>j.character_id===character.id && j.status==="succeeded");
  const initial=initialJobs.find(j=>j.id===project.approved[character.id]) || initialJobs[0] || project.jobs.find(j=>j.character_id===character.id);
  const [draft,setDraft]=useState(initial?.character || character);const [change,setChange]=useState("");const [model,setModel]=useState(options.models[0] || "");
  const [referenceOverrides,setReferenceOverrides]=useState<Record<string,string>>(initial?.scene_context?.reference_overrides || {});
  useEffect(()=>{onReferences(referenceOverrides);},[referenceOverrides,onReferences]);
  const [chosen,setChosen]=useState("");const [busy,setBusy]=useState(false);
  useEffect(()=>{onDraft(draft);},[draft,onDraft]);
  function updateDraft(value:Character){setDraft(value);onDraft(value);}
  const progressRef=useRef<HTMLDivElement>(null);
  const [submittedJobId,setSubmittedJobId]=useState<string | null>(null);
  useEffect(()=>{
    if(!submittedJobId || !project.jobs.some(j=>j.id===submittedJobId))return;
    const target=progressRef.current;
    if(target && target.getClientRects().length){
      target.focus({preventScroll:true});
      target.scrollIntoView({block:"start",behavior:window.matchMedia("(prefers-reduced-motion: reduce)").matches?"instant":"smooth"});
    }
    setSubmittedJobId(null);
  },[submittedJobId,project.jobs]);
  const dispatch=useRef<{signature:string;id:string} | null>(null);
  const jobs=project.jobs.filter(j=>j.character_id===character.id);
  const success=jobs.filter(j=>j.status==="succeeded");
  const shown=success.find(j=>j.id===chosen) || success.find(j=>j.id===project.approved[character.id]) || success[0];
  const sceneInfo=shown?.character || draft;
  const source=project.scene_sources?.[character.id];
  const active=jobs.find(j=>["queued","running"].includes(j.status));const latest=jobs[0];
  const excluded=project.excluded.includes(character.id);
  const itemState=project.work_progress.items.find(i=>i.id===character.id)?.state || "pending";
  async function setScope() {
    setBusy(true);onError("");
    try {await api(`/characters/projects/${project.id}/characters/${character.id}/scope`,"POST",{excluded:!excluded,expected:excluded});await refresh();}
    catch(e){onError(message(e));await refresh().catch(()=>{});}finally{setBusy(false);}
  }
  async function generate() {
    setBusy(true);onError("");
    try {
      const payload={character:draft,model,change:shown?change:"",base_id:shown?.id || null,reference_overrides:referenceOverrides};
      const signature=JSON.stringify(payload);
      if(dispatch.current?.signature!==signature)dispatch.current={signature,id:crypto.randomUUID()};
      await api(`/characters/projects/${project.id}/images`,"POST",{id:dispatch.current.id,...payload});
      setSubmittedJobId(dispatch.current.id);
      dispatch.current=null;setChange("");await refresh();
    }
    catch(e){onError(message(e));}finally{setBusy(false);}
  }
  const confirmedIds = scene ? [project.approved[character.id]].filter(Boolean) : project.approved_versions?.[character.id] || [project.approved[character.id]].filter(Boolean);
  async function approve(makeDefault = false) {
    if(!shown)return;setBusy(true);
    try {await api(`/characters/images/${shown.id}/approve`,"POST",{expected:project.approved[character.id] || null,expected_latest_version:latest?.version,make_default:makeDefault});await refresh();}
    catch(e){onError(message(e));await refresh().catch(()=>{});}finally{setBusy(false);}
  }
  async function cancel() {
    if(!active || busy)return;
    setBusy(true);onError("");
    try {await api(`/characters/images/${active.id}/cancel`,"POST",{});await refresh();}
    catch(e){onError(message(e));await refresh().catch(()=>{});}finally{setBusy(false);}
  }
  const heading=<div className="character-heading"><div className="character-name-controls"><h3>{character.name}</h3>{!scene && <Switch checked={!excluded} disabled={busy || !!active} label="이 캐릭터 사용" describedBy={`scope-help-${character.id}`} onChange={()=>void setScope()}/>}</div><StatusBadge tone={excluded?"neutral":itemState==="approved"?"success":itemState==="failed" || itemState==="unknown"?"warning":"neutral"}>{excluded?"사용 안 함":itemStateLabel(itemState,"character_images")}</StatusBadge></div>;
  const scopeHelp=<p id={`scope-help-${character.id}`} className="muted">{active?"이미지 생성 중에는 사용 여부를 변경할 수 없습니다.":excluded?"완료 조건과 다음 단계 전달 대상에서 제외했습니다. 다시 켜면 기존 설정과 확정 이미지를 이어서 사용합니다.":"끄면 완료 조건과 다음 단계 전달 대상에서 제외됩니다. 대본·장면 원문과 기존 이미지·확정 기록은 보존됩니다."}</p>;
  if(excluded)return <Card><article id={`character-${character.id}`} className="character-form">{heading}{scopeHelp}</article></Card>;
  return <Card><article id={`character-${character.id}`} className="character-form">{heading}{!scene && scopeHelp}
    {scene && blocked.length>0 && <div className="scene-blocked" role="status"><strong>생성 전 자료 확인 필요</strong><ul>{blocked.map((n,i)=><li key={i}>{n}</li>)}</ul></div>}
    {scene && advice && <aside className="scene-advice"><strong>AI 참고 의견</strong><p>{advice}</p><p className="muted">AI의 해석으로 실제 내용과 다를 수 있습니다. 생성 여부와 수정 필요성은 직접 판단해 주세요. 이 의견은 이미지 생성을 제한하지 않습니다.</p></aside>}
    <p className="muted">{scene?"원본 장면":"등장 장면"} · {character.scene_ids}</p>
    {latest && <div ref={progressRef} tabIndex={-1} className="image-progress-target" aria-label="이미지 생성 진행 상태"><ImageJobProgress approved={project.approved[character.id]===(active || latest).id && itemState==="approved"} job={active || latest} online={project.worker_online} baseVersion={jobs.find(j=>j.id===(active || latest).base_id)?.version}/></div>}
    {active?.status==="queued" && <div className="character-heading"><Button variant="secondary" disabled={busy} onClick={()=>void cancel()}>대기 요청 취소</Button><span className="muted">생성 시작 전 취소할 수 있습니다. 기존 이미지와 확정 기록은 유지됩니다.</span></div>}
    {active?.status==="running" && <p className="muted">이미 생성 처리가 시작되어 중단을 보장할 수 없습니다. API 비용이 발생할 수 있으며, 완성 후 사용할 버전을 선택할 수 있습니다.</p>}
    <div className="character-editor-layout"><div className="character-preview character-form">
    {shown ? <><img className="character-image" src={`/api/v1/characters/images/${shown.id}/asset`} alt={`${character.name} 기준 이미지 v${shown.version}`}/>
      <label className="character-field">이미지 버전<select value={shown.id} onChange={e=>{setChosen(e.target.value);const j=success.find(j=>j.id===e.target.value);if(j){setDraft(j.character);setReferenceOverrides(j.scene_context?.reference_overrides || {});}}}>{success.map(j=><option key={j.id} value={j.id}>v{j.version}{project.approved[character.id]===j.id?" · 기본 이미지":confirmedIds.includes(j.id)?" · 확정":" · 검토본"}</option>)}</select></label>
      <p className="muted">{shown.model} · 예상 비용 {shown.estimated_usd===null?"미확인":`$${Number(shown.estimated_usd).toFixed(5)}`}</p>
      <div className="button-row"><Button variant="secondary" disabled={busy || !!active || (scene ? project.approved[character.id]===shown.id && itemState==="approved" : confirmedIds.includes(shown.id) && itemState==="approved")} onClick={()=>void approve()}>{scene?"이 버전을 기준 이미지로 확정":confirmedIds.includes(shown.id)?"확정된 버전":"이 버전 확정"}</Button>{!scene&&confirmedIds.includes(shown.id)&&project.approved[character.id]!==shown.id&&<Button variant="secondary" disabled={busy||!!active} onClick={()=>void approve(true)}>기본 이미지로 사용</Button>}</div>{!scene&&<p className="helper-text">여러 버전을 확정할 수 있습니다. 기본 이미지는 하나이며, 다른 확정 버전은 필요한 씬에서 선택합니다.</p>}</>
      : <div className="character-empty">{active ? "이미지가 완성되면 여기에 표시됩니다." : scene ? "씬 설정과 참조 자료를 확인하고 이미지를 만들어 보세요." : "설정을 확인하고 첫 기준 이미지를 만들어 보세요."}</div>}
    {latest?.status==="succeeded" && latest.id!==shown?.id && <Button variant="secondary" onClick={()=>{setChosen(latest.id);setDraft(latest.character);setReferenceOverrides(latest.scene_context?.reference_overrides||{});}}>새 이미지 v{latest.version} 확인</Button>}
    {latest && !active && latest.status!=="succeeded" && <p role="status" className="character-status">v{latest.version} · {states[latest.status]}{latest.status==="unknown" && " · 중복 과금 방지를 위해 자동 재시도하지 않습니다."}{latest.status==="failed" && ` · ${latest.error_code || "API 오류"}`}</p>}
    </div><div className="character-form">
    {scene && <section className="scene-image-context" aria-label="이미지와 연결된 장면 내용">
      <div className="character-heading"><h4>{shown?"이 이미지에 담은 장면":"이미지로 만들 장면"}</h4><span className="muted">{shown?`v${shown.version} 생성 당시 설정`:"현재 설정"}</span></div>
      {source && <>
        <SceneReferenceVersions references={source.characters} value={referenceOverrides} onChange={setReferenceOverrides} disabled={busy || !!active} used={shown?.scene_context?.references?.characters}/>
        <details className="scene-source" open><summary>{source.script_matched?"대본 원문 · 일치하는 대응 구간":"대본 원문 · 전체"}</summary>
          {!source.script_matched && <p className="helper-text">대응 구간을 정확하게 찾지 못해 전달받은 대본 전체를 표시합니다.</p>}
          <div className="scene-source-text">{source.script || "전달받은 대본이 없습니다."}</div>
        </details>
        <details className="scene-source"><summary>{source.scene_matched?"장면 구성 원문 · 해당 장면":"장면 구성 원문 · 전체"}</summary>
          {!source.scene_matched && <p className="helper-text">장면 번호를 정확하게 연결하지 못해 장면 구성 전체를 표시합니다.</p>}
          <div className="scene-source-text">{source.scene || "전달받은 장면 구성이 없습니다."}</div>
        </details>
      </>}
      <div><h4>AI 이미지 구성{shown?` · v${shown.version}`:" · 현재 설정"}</h4><p>{sceneInfo.appearance || "등록된 이미지 구성이 없습니다."}</p></div>
      <p className="helper-text">원문은 요청 당시 전달받은 내용을 그대로 표시합니다. AI 이미지 구성은 한 장의 이미지로 표현하기 위한 제안이며 원문과 다를 수 있습니다.</p>
      {shown?.change && <div><strong>이 버전의 수정 요청</strong><p>{shown.change}</p></div>}
      <p className="helper-text">{shown?"AI 이미지 구성은 선택한 이미지 버전을 만들 때의 설정입니다. 아래 설정을 수정해도 기존 이미지는 바뀌지 않습니다.":"아래 설정을 수정하면 AI 이미지 구성이 바뀌며 다음 이미지 요청에 적용됩니다. 위 원문은 그대로 유지됩니다."}</p>
    </section>}
    <details className="character-edit" open><summary>수정 및 확인</summary><div className="character-form">
    <details><summary>{scene?"씬 구성과 제작 지침 확인·수정":"캐릭터 설정 확인·수정"}</summary><div className="character-form">
      <div className="character-reference character-form"><strong>참고 정보 · 수정 가능</strong><p className="muted">{scene ? "대본 대응 구간과 연속성 정보를 참고합니다. 아래 장면 구도와 이미지 제작 지침을 우선 적용하며, 원본 대본과 장면 구성은 변경하지 않습니다." : "대본 해석이나 AI 제안이 맞지 않으면 고쳐 주세요. 이미지 생성 시 아래 외형·의상과 이미지 제작 지침에 어긋나지 않는 범위에서 참고합니다."}</p>
      <label className="character-field">{scene?"대본 대응 구간":"대본에서 확인한 정보"}<textarea rows={3} maxLength={3000} value={draft.facts} onChange={e=>updateDraft({...draft,facts:e.target.value})}/></label>
      <label className="character-field">{scene?"장면 연속성":"AI가 제안한 설정"}<textarea rows={3} maxLength={2000} value={draft.proposed} onChange={e=>updateDraft({...draft,proposed:e.target.value})}/></label></div>
      <div className="character-form"><strong>이미지에 우선 적용할 설정</strong><p className="muted">위 참고 정보를 수정해도 아래 입력값은 자동으로 바뀌지 않습니다. 바꾸고 싶은 모습이 있다면 아래 설정도 함께 확인해 주세요.</p>
      <label className="character-field">{scene?"장면 구도·배경·행동":"외형·의상"}<textarea rows={4} maxLength={3000} value={draft.appearance} onChange={e=>updateDraft({...draft,appearance:e.target.value})}/></label>
      <label className="character-field">이미지 제작 지침<textarea rows={4} maxLength={4000} value={draft.image_prompt} onChange={e=>updateDraft({...draft,image_prompt:e.target.value})}/></label></div><p className="muted">변경 내용은 다음 이미지 생성·수정 요청을 보낼 때 함께 저장하고 적용합니다. 기존 이미지와 확정된 버전은 바뀌지 않습니다. 수정 요청의 ‘바꿀 부분’은 해당 부분에 한해 가장 먼저 적용합니다.</p></div></details>
    <ImageModelSelect label="이미지 모델" value={model} options={options.models} onChange={setModel} disabled={busy || !!active}/>
    {shown && <label className="character-field">v{shown.version}에서 바꿀 부분<textarea rows={3} maxLength={3000} value={change} onChange={e=>setChange(e.target.value)} placeholder="예: 얼굴과 의상은 유지하고 모자 색만 파란색으로 바꿔 주세요."/></label>}
    <Button disabled={busy || !!active || !options.enabled || !model || blocked.length>0 || (!!shown && !change.trim())} onClick={()=>void generate()}>{active?states[active.status]:shown?`v${shown.version} 이미지를 바탕으로 수정 요청`:scene?"씬 이미지 생성":"기준 이미지 생성"}</Button>
    <p className="muted">{scene?`목표 비율 ${project.context?.input.aspect_ratio || "9:16"} · ${project.context?.input.aspect_ratio==="1:1"?"1024 × 1024":project.context?.input.aspect_ratio==="16:9"?"1536 × 1024":"1024 × 1536"} 원본 (영상 제작 시 목표 비율 조정 필요)`:"1024 × 1024"} · 보통 품질 · 1장 · 유료 API 호출</p>
    </div></details></div></div>
    {shown && <ImageReviewPanel scene={scene} key={shown.id} imageId={shown.id} version={shown.version} character={draft} reviews={project.reviews || []} configured={!!project.review_config} online={project.worker_online} enqueueError={shown.review_error_code} refresh={refresh}/>}
  </article></Card>;
}
