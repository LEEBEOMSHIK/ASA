"use client";
import { useEffect, useRef, useState } from "react";
import { api, message, type Tool } from "../lib/registry";
import { Button, Card, StatusBadge } from "./ui";
import { ImageModelSelect } from "./image-model-select";
import { itemStateLabel, progressLabel, progressCounts, type WorkProgress } from "../lib/work-progress";
import "./character-studio.css";

type Character = { id: string; name: string; facts: string; appearance: string; proposed: string; scene_ids: string; image_prompt: string };
type Job = { id: string; character_id: string; version: number; model: string; character: Character; change: string; base_id: string | null; status: string; error_code: string | null; estimated_usd: string | null };
type Project = { id: string; name: string; request_id: string; source_version: number; characters: Character[]; approved: Record<string,string>; jobs: Job[]; worker_online: boolean; excluded: string[]; work_progress: WorkProgress };
type Options = { agents: Tool[]; models: string[]; enabled: boolean };
type LibraryEntry = {id:string;name:string;request_id:string;source_version:number};
const states: Record<string,string> = {queued:"이미지 생성 대기", running:"이미지 생성 중", succeeded:"검토 가능", failed:"생성 실패", unknown:"호출 결과 확인 필요"};

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

export function CharacterResults({requestId,version}:{requestId:string;version:number}) {
  const [project,setProject]=useState<Project|null>(null);
  const [options,setOptions]=useState<Options>({agents:[],models:[],enabled:false});
  const [error,setError]=useState("");
  const [selected,setSelected]=useState<string[]>([]);
  const [busy,setBusy]=useState(false);
  const [model,setModel]=useState("");
  const ids=useRef<Record<string,string>>({});
  const [drafts,setDrafts]=useState<Record<string,Character>>({});
  const [retry,setRetry]=useState(0);
  async function refresh() {if(project){const p=await api<Project>(`/characters/projects/${project.id}`);setProject(p);setSelected(v=>v.filter(id=>!p.excluded.includes(id) && !p.jobs.some(j=>j.character_id===id)));}}
  useEffect(()=>{
    let alive=true;
    Promise.all([api<Options>("/characters/options"),api<Project>("/characters/projects","POST",{id:crypto.randomUUID(),request_id:requestId,source_version:version,name:`캐릭터 설정 · 답변 v${version}`})]).then(([o,p])=>{if(alive){setOptions(o);setModel(o.models[0] || "");setProject(p);setError("");}}).catch(e=>{if(alive)setError(message(e));});
    return()=>{alive=false;};
  },[requestId,version,retry]);
  useEffect(()=>{
    if(!project)return;
    const id=project.id;
    const events=new EventSource(`/api/v1/characters/projects/${id}/events`);
    events.addEventListener("snapshot",event=>{
      const p=JSON.parse((event as MessageEvent).data) as Project;
      setError(v=>v.startsWith("실시간 연결을 복구")?"":v);
      setProject(p);setSelected(v=>v.filter(id=>!p.excluded.includes(id) && !p.jobs.some(j=>j.character_id===id)));
    });
    const disconnected=()=>setError("실시간 연결을 복구하고 있습니다. 이미지 작업을 다시 요청할 필요는 없습니다.");
    events.onerror=disconnected;events.addEventListener("unavailable",disconnected);
    return()=>events.close();
  },[project?.id]);
  async function generateSelected(){
    if(!project || busy)return;
    setBusy(true);setError("");
    const accepted:string[]=[];
    try{
      for(const id of selected){
        const character=drafts[id] || project.characters.find(c=>c.id===id);if(!character || project.excluded.includes(id) || project.jobs.some(j=>j.character_id===id)){accepted.push(id);continue;}
        const key=JSON.stringify({id,model,character});
        ids.current[key] ||= crypto.randomUUID();
        await api(`/characters/projects/${project.id}/images`,"POST",{id:ids.current[key],character,model});
        accepted.push(id);
      }
    }catch(e){setError(`일부 요청이 접수되지 않았습니다. 접수된 인물은 아래 상태에서 확인할 수 있습니다. ${message(e)}`);}
    finally{setSelected(v=>v.filter(id=>!accepted.includes(id)));try{await refresh();}catch(e){setError(message(e));}setBusy(false);}
  }
  return <section id="followup-character_images" className="character-studio" aria-label="등장인물과 기준 이미지"><div className="character-heading"><h2>등장인물과 기준 이미지</h2><a href="/characters">보관함</a></div>
    {error && <p role="alert" className="notice">{error}{!project && <Button variant="secondary" onClick={()=>setRetry(n=>n+1)}>다시 불러오기</Button>}</p>}
    {!project && !error && <p role="status">등장인물을 불러오는 중…</p>}
    {project && <><Card><div className="character-form"><div className="character-heading"><h3>생성할 캐릭터 선택 · {project.characters.length}명</h3><StatusBadge tone={project.worker_online?"success":"warning"}>{project.worker_online?"이미지 워커 연결됨":"이미지 워커 연결 대기"}</StatusBadge></div>
      <div className="character-progress" role="status"><strong>{progressLabel(project.work_progress)}</strong><p>{progressCounts(project.work_progress)}</p></div>
      <p className="muted">필요한 이미지를 모두 확정하면 작업이 완료됩니다. 필요 없는 인물은 아래 카드에서 생성 대상에서 제외하세요. 제외는 삭제가 아니며 언제든 복원할 수 있습니다.</p>
      <div className="character-roster">{project.characters.map(c=>{const jobs=project.jobs.filter(j=>j.character_id===c.id);const state=project.work_progress.items.find(i=>i.id===c.id)?.state || "pending";return <div key={c.id} className="character-choice"><label><input type="checkbox" checked={selected.includes(c.id)} disabled={busy || jobs.length>0 || state==="excluded"} onChange={e=>setSelected(v=>e.target.checked?[...v,c.id]:v.filter(id=>id!==c.id))}/><span><strong>{c.name}</strong><small>{itemStateLabel(state,"character_images")}</small></span></label><a className="character-jump" href={`#character-${c.id}`} aria-label={`${c.name} 작업으로 이동`}>확인 →</a></div>;})}</div>
      <ImageModelSelect label="선택한 인물의 이미지 모델" value={model} options={options.models} onChange={setModel} disabled={busy}/>
      <div><Button disabled={busy || !selected.length || !options.enabled || !model} onClick={()=>void generateSelected()}>{busy?"생성 요청 접수 중…":`선택한 ${selected.length}명 이미지 생성`}</Button></div><p className="muted">인물당 1장 · 유료 API 호출. 이미 작업한 인물은 아래 카드에서 수정하거나 다시 요청할 수 있습니다.</p>
      {!project.worker_online && <p role="status" className="notice">이미지 워커가 연결되면 저장된 요청을 순서대로 처리합니다.</p>}
    </div></Card>
    <div className="character-grid">{project.characters.map(c=><CharacterCard key={`${project.id}:${c.id}`} character={c} project={project} options={options} refresh={refresh} onError={setError} onDraftChange={draft=>setDrafts(v=>({...v,[c.id]:draft}))}/>)}</div></>}
  </section>;
}

function CharacterCard({character,project,options,refresh,onError,onDraftChange}:{character:Character;project:Project;options:Options;refresh:()=>Promise<void>;onError:(s:string)=>void;onDraftChange:(draft:Character)=>void}) {
  const initialJobs=project.jobs.filter(j=>j.character_id===character.id && j.status==="succeeded");
  const initial=initialJobs.find(j=>j.id===project.approved[character.id]) || initialJobs[0];
  const [draft,setDraft]=useState(initial?.character || character);const [change,setChange]=useState("");const [model,setModel]=useState(options.models[0] || "");
  const [chosen,setChosen]=useState("");const [busy,setBusy]=useState(false);
  function updateDraft(value:Character){setDraft(value);onDraftChange(value);}
  const dispatch=useRef<{signature:string;id:string} | null>(null);
  const jobs=project.jobs.filter(j=>j.character_id===character.id);
  const success=jobs.filter(j=>j.status==="succeeded");
  const shown=success.find(j=>j.id===chosen) || success.find(j=>j.id===project.approved[character.id]) || success[0];
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
      const payload={character:draft,model,change:shown?change:"",base_id:shown?.id || null};
      const signature=JSON.stringify(payload);
      if(dispatch.current?.signature!==signature)dispatch.current={signature,id:crypto.randomUUID()};
      await api(`/characters/projects/${project.id}/images`,"POST",{id:dispatch.current.id,...payload});
      dispatch.current=null;setChange("");await refresh();
    }
    catch(e){onError(message(e));}finally{setBusy(false);}
  }
  async function approve() {
    if(!shown)return;setBusy(true);
    try {await api(`/characters/images/${shown.id}/approve`,"POST",{expected:project.approved[character.id] || null,expected_latest_version:latest?.version});await refresh();}
    catch(e){onError(message(e));await refresh().catch(()=>{});}finally{setBusy(false);}
  }
  if(excluded)return <Card><article id={`character-${character.id}`} className="character-form"><div className="character-heading"><h3>{character.name}</h3><StatusBadge>생성 대상 제외</StatusBadge></div><p className="muted">완료 조건에서 제외했습니다. 기존 이미지와 확정 기록은 보존됩니다.</p><Button variant="secondary" disabled={busy} onClick={()=>void setScope()}>생성 대상으로 복원</Button></article></Card>;
  return <Card><article id={`character-${character.id}`} className="character-form"><div className="character-heading"><h3>{character.name}</h3><StatusBadge tone={itemState==="approved"?"success":itemState==="failed" || itemState==="unknown"?"warning":"neutral"}>{itemStateLabel(itemState,"character_images")}</StatusBadge></div>
    <p className="muted">등장 장면 · {character.scene_ids}</p>
    {shown ? <><img className="character-image" src={`/api/v1/characters/images/${shown.id}/asset`} alt={`${character.name} 기준 이미지 v${shown.version}`}/>
      <label className="character-field">이미지 버전<select value={shown.id} onChange={e=>{setChosen(e.target.value);const j=success.find(j=>j.id===e.target.value);if(j)setDraft(j.character);}}>{success.map(j=><option key={j.id} value={j.id}>v{j.version}{project.approved[character.id]===j.id?" · 확정된 기준":" · 검토본"}</option>)}</select></label>
      <p className="muted">{shown.model} · 예상 비용 {shown.estimated_usd===null?"미확인":`$${Number(shown.estimated_usd).toFixed(5)}`}</p>
      <Button variant="secondary" disabled={busy || !!active || (project.approved[character.id]===shown.id && itemState==="approved")} onClick={()=>void approve()}>이 버전을 기준 이미지로 확정</Button></>
      : <div className="character-empty">설정을 확인하고 첫 기준 이미지를 만들어 보세요.</div>}
    {latest?.status==="succeeded" && latest.id!==shown?.id && <Button variant="secondary" onClick={()=>{setChosen(latest.id);setDraft(latest.character);}}>새 이미지 v{latest.version} 확인</Button>}
    {latest && <p role="status" className="character-status">v{latest.version} · {states[latest.status]}{latest.status==="unknown" && " · 중복 과금 방지를 위해 자동 재시도하지 않습니다."}{latest.status==="failed" && ` · ${latest.error_code || "API 오류"}`}</p>}
    <details><summary>캐릭터 설정 확인·수정</summary><div className="character-form"><p><strong>대본에서 확인한 정보</strong><br/>{character.facts}</p><p><strong>AI가 제안한 설정</strong><br/>{character.proposed}</p>
      <label className="character-field">외형·의상<input value={draft.appearance} onChange={e=>updateDraft({...draft,appearance:e.target.value})}/></label>
      <label className="character-field">이미지 제작 지침<textarea rows={4} value={draft.image_prompt} onChange={e=>updateDraft({...draft,image_prompt:e.target.value})}/></label><p className="muted">변경한 설정은 다음 이미지 요청에 함께 저장됩니다.</p></div></details>
    <ImageModelSelect label="이미지 모델" value={model} options={options.models} onChange={setModel} disabled={busy || !!active}/>
    {shown && <label className="character-field">v{shown.version}에서 바꿀 부분<textarea rows={3} maxLength={3000} value={change} onChange={e=>setChange(e.target.value)} placeholder="예: 얼굴과 의상은 유지하고 모자 색만 파란색으로 바꿔 주세요."/></label>}
    <Button disabled={busy || !!active || !options.enabled || !model || (!!shown && !change.trim())} onClick={()=>void generate()}>{active?states[active.status]:shown?`v${shown.version} 이미지를 바탕으로 수정 요청`:"기준 이미지 생성"}</Button>
    <p className="muted">1024 × 1024 · 보통 품질 · 1장 · 유료 API 호출</p>
    <div className="character-scope"><Button variant="secondary" disabled={busy || !!active} onClick={()=>void setScope()}>생성 대상에서 제외</Button><p className="muted">{active?"진행 중인 생성이 끝난 뒤 제외할 수 있습니다.":"이미지가 필요 없는 인물만 제외하세요. 기존 결과는 삭제되지 않습니다."}</p></div>
  </article></Card>;
}
