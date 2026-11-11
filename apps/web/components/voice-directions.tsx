"use client";

import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api, ApiError, message } from "../lib/registry";
import { useWorkDraft } from "../lib/work-draft";
import { Button, DisclosureButton, DraftNotice, Field, StatusBadge, Switch } from "./ui";

type Speaker = {id:string;name:string;role:"character"|"narrator";video_enabled?:boolean;
  voice:{instructions:string;language:string;speed:number}};
type Settings = {speakers:Speaker[]};
type Job = {id:string;kind:string;purpose:string;status:string;created_at:string};
type State = {revision:number;settings:Settings;jobs:Job[]};

export function VoiceDirections({requestId,version,characterId,narrationTarget}:{
  requestId:string;version:number;characterId?:string;narrationTarget?:HTMLElement|null;
}) {
  const path=`/audio/work/${requestId}/${version}`,prefix=useId(),lock=useRef(false);
  const [state,setState]=useState<State|null>(null),[draft,setDraft]=useState<Settings|null>(null);
  const [dirty,setDirty]=useState(false),[busy,setBusy]=useState(false),[open,setOpen]=useState(true);
  const [error,setError]=useState(""),[notice,setNotice]=useState("");
  const pending=useWorkDraft(state?`audio:${requestId}:v${version}:r${state.revision}`:undefined,draft,
    saved=>{if(saved){setDraft(saved);setDirty(true);setOpen(true);}},Boolean(state&&draft),dirty);
  function accept(value:State){setState(value);setDraft(value.settings);setDirty(false);
    setOpen(!value.settings.speakers.some(s=>s.role==="narrator"&&(s.voice.instructions||s.video_enabled===false)));}
  useEffect(()=>{let alive=true;api<State>(path).then(value=>{if(alive)accept(value);})
    .catch(e=>{if(alive)setError(message(e));});return()=>{alive=false;};},[path]);
  async function save(){
    if(!state||!draft||lock.current)return;
    lock.current=true;setBusy(true);setError("");setNotice("");
    try{
      const value=await api<State>(path+"/voice-directions","PUT",{revision:state.revision,
        speakers:draft.speakers.map(s=>({id:s.id,...s.voice,enabled:s.video_enabled!==false}))
          .map(({id,instructions,language,speed,enabled})=>({id,instructions,language,speed,enabled}))});
      pending.clear();accept(value);setOpen(false);setNotice("목소리 특징을 저장했습니다. 새 비디오 프롬프트 요청부터 반영됩니다.");
    }catch(e){setError(e instanceof ApiError&&e.code==="audio_settings_changed"
      ?"다른 화면에서 설정이 변경됐습니다. 입력을 복사해 두고 최신 설정을 다시 불러와 주세요.":message(e));}
    finally{lock.current=false;setBusy(false);}
  }
  if(!state||!draft)return <section className="voice-directions">{error?<p role="alert">{error}</p>:<p role="status">목소리 특징을 불러오는 중…</p>}</section>;
  const update=(id:string,patch:Partial<Speaker>)=>{setDraft({...draft,speakers:draft.speakers.map(s=>s.id===id?{...s,...patch}:s)});setDirty(true);setNotice("");};
  const form=(s:Speaker)=><fieldset key={s.id} className="voice-direction-fields"><legend>{s.name}</legend>
    <Switch label={s.role==="narrator"?"나레이션 목소리 직접 설정":`${s.name} 목소리 직접 설정`} checked={s.video_enabled!==false} disabled={busy} onChange={()=>update(s.id,{video_enabled:s.video_enabled===false})}/>
    {s.video_enabled!==false?<><Field id={prefix+s.id+"description"} label="목소리 특징" hint="나이 느낌·음역·음색·말투·발음을 적어 주세요. 영상 모델에 전달할 설명이며, 별도 음성 샘플을 만들지 않습니다.">{p=><textarea {...p} rows={3} maxLength={1000}
      disabled={busy||s.video_enabled===false} value={s.voice.instructions}
      placeholder={s.role==="narrator"?"예: 따뜻하고 차분한 중저음, 또렷한 발음과 부드러운 이야기체. 장면 사이에는 짧게 쉬어 주세요.":"예: 밝고 높은 음역의 어린아이 느낌, 가볍고 맑은 음색. 호기심 많은 말투로 또렷하게 말해 주세요."}
      onChange={e=>update(s.id,{voice:{...s.voice,instructions:e.target.value}})}/>}</Field>
    <div className="voice-direction-grid"><Field id={prefix+s.id+"language"} label="언어">{p=><input {...p} maxLength={80} value={s.voice.language} disabled={busy||s.video_enabled===false} onChange={e=>update(s.id,{voice:{...s.voice,language:e.target.value}})}/>}</Field>
      <Field id={prefix+s.id+"speed"} label="말하기 속도 의도" hint="0.75~1.25배 · 실제 속도는 생성 영상에서 확인합니다.">{p=><input {...p} type="number" min={.75} max={1.25} step={.05} value={s.voice.speed} disabled={busy||s.video_enabled===false} onChange={e=>update(s.id,{voice:{...s.voice,speed:Number(e.target.value)}})}/>}</Field></div></>:<p className="muted">자동 설정 · {s.role==="narrator"?"대본의 나레이션은":"캐릭터의 대사는"} 유지하고, {s.role==="narrator"?"이야기 내용":"캐릭터 설정과 이야기 내용"}·장면 분위기·이미지에 어울리는 목소리와 말투를 정합니다. 이전에 입력한 특징은 보관됩니다.</p>}
  </fieldset>;
  const feedback=<>{error&&<div className="voice-direction-feedback" role="alert"><p>{error}</p><Button variant="secondary" disabled={busy} onClick={()=>void api<State>(path).then(value=>{pending.clear();accept(value);setError("");}).catch(e=>setError(message(e)))}>최신 설정 다시 불러오기</Button></div>}{notice&&<p role="status">{notice}</p>}</>;
  const saveButton=<div className="voice-direction-actions"><p className="muted">나레이션과 캐릭터의 변경 내용을 함께 저장합니다.</p><Button disabled={busy||(!dirty&&state.revision>0)||draft.speakers.some(s=>s.video_enabled!==false&&(!s.voice.language.trim()||!Number.isFinite(s.voice.speed)||s.voice.speed<.75||s.voice.speed>1.25))} onClick={()=>void save()}>{busy?"저장 중…":"목소리 특징 저장"}</Button></div>;
  const narrators=draft.speakers.filter(s=>s.role==="narrator");
  const narration=<section className="voice-directions work-narration" aria-label="작품 공통 · 나레이션"><div className="voice-direction-heading"><div><h3>작품 공통 · 나레이션</h3><p className="muted">{narrators.map(s=>s.video_enabled===false?"자동 설정 · 이야기와 장면에 맞는 목소리":s.voice.instructions||"자동 설정 · 직접 입력한 특징 없음").join(" / ")}</p><StatusBadge>{dirty?"저장 전 변경":"설명으로 영상에 전달"}</StatusBadge></div><DisclosureButton variant="secondary" aria-expanded={open} aria-controls={prefix+"narration"} onClick={()=>setOpen(v=>!v)}>{open?"나레이션 접기":"나레이션 설정"}</DisclosureButton></div>
    <div id={prefix+"narration"} hidden={!open} className="voice-direction-panel"><p className="muted">이 캐릭터 작업에 연결된 작품 공통 설정입니다. 캐릭터마다 반복해서 정하지 않아도 됩니다.</p>{narrators.map(form)}{saveButton}</div>{feedback}</section>;
  return <>{narrationTarget?createPortal(narration,narrationTarget):narration}
    <section className="voice-directions" aria-label="캐릭터 목소리 특징"><div><h3>캐릭터 목소리 특징</h3><p className="muted">저장한 특징을 비디오 프롬프트와 영상 생성에 전달합니다. 클립마다 완전히 같은 음색이 유지되는지는 영상 모델에 따라 달라집니다.</p></div>
      {pending.notice&&<DraftNotice message={pending.notice} hint="특징 저장을 누르면 반영됩니다. 기존 음성은 유지됩니다." actionLabel="저장된 특징으로 되돌리기" disabled={busy} onReset={()=>{pending.clear();setDraft(state.settings);setDirty(false);}}/>}
      {draft.speakers.filter(s=>s.role==="character"&&(!characterId||s.id===characterId)).map(form)}{saveButton}{feedback}
      {!!state.jobs.length&&<details className="voice-direction-archive"><summary>기존 음성 보관 · {state.jobs.length}개</summary><p className="muted">이전에 생성한 음성입니다. 새 영상에 자동으로 합성하거나 목소리 고정에 사용하지 않습니다. 시간 측정용 TTS는 씬 구성에서 계속 사용합니다.</p>{state.jobs.map(j=><div key={j.id}><p>{j.purpose==="timing"?"시간 측정용":j.purpose==="sample"?"이전 샘플":"이전 제작 음성"} · {new Date(j.created_at).toLocaleString("ko-KR")}</p>{["review","approved"].includes(j.status)?j.kind==="compose"?<video controls preload="none" src={`/api/v1/audio/jobs/${j.id}/media`}/>:<audio aria-label="보존된 음성" controls preload="none" src={`/api/v1/audio/jobs/${j.id}/media`}/>:<p className="muted">{j.status==="queued"||j.status==="running"?"기존 생성 처리 중":"재생 가능한 결과 없음"}</p>}</div>)}</details>}
    </section></>;
}
