"use client";

import { useContext, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api, ApiError, message } from "../lib/registry";
import { DraftScope, useWorkDraft } from "../lib/work-draft";
import { Button, DisclosureButton, ActionIcon, Field, StatusBadge, Switch } from "./ui";

import {retainUnsavedSpeakers} from "../lib/voice-direction-save";
import {writeDraft, journalDraft} from "../lib/work-draft-storage";

type Speaker = {id:string;name:string;role:"character"|"narrator";video_enabled?:boolean;
  voice:{instructions:string;language:string;speed:number}};
type Settings = {speakers:Speaker[]};
type State = {revision:number;settings:Settings};

export function VoiceDirections({requestId,version,characterId,narrationTarget}:{
  requestId:string;version:number;characterId?:string;narrationTarget?:HTMLElement|null;
}) {
  const scope=useContext(DraftScope);
  const path=`/audio/work/${requestId}/${version}`,prefix=useId(),lock=useRef(false);
  const [state,setState]=useState<State|null>(null),[draft,setDraft]=useState<Settings|null>(null);
  const [dirty,setDirty]=useState(false),[busy,setBusy]=useState(false),[open,setOpen]=useState(false);
  const [automaticSaving,setAutomaticSaving]=useState<string|null>(null);
  const [error,setError]=useState(""),[notice,setNotice]=useState("");
  const pending=useWorkDraft(state?`audio:${requestId}:v${version}:r${state.revision}`:undefined,draft,
    saved=>{if(saved){setDraft(saved);setDirty(true);}},Boolean(state&&draft),dirty);
  function accept(value:State){setState(value);setDraft(value.settings);setDirty(false);
    setOpen(false);}
  useEffect(()=>{let alive=true;api<State>(path).then(value=>{if(alive)accept(value);})
    .catch(e=>{if(alive)setError(message(e));});return()=>{alive=false;};},[path]);
  async function save(speaker:Speaker){
    if(!state||!draft||lock.current)return;
    lock.current=true;setBusy(true);setAutomaticSaving(speaker.video_enabled===false?speaker.id:null);setError("");setNotice("");
    try{
      const value=await api<State>(path+"/voice-directions","PUT",{revision:state.revision,
        speakers:[speaker].map(s=>({id:s.id,...s.voice,enabled:s.video_enabled!==false}))
          .map(({id,instructions,language,speed,enabled})=>({id,instructions,language,speed,enabled}))});
      const next={speakers:retainUnsavedSpeakers(value.settings.speakers,draft.speakers,speaker.id)};
      const remaining=JSON.stringify(next.speakers)!==JSON.stringify(value.settings.speakers);
      if(remaining&&scope){
        const key=`asa-input-draft:v1:${scope}:audio:${requestId}:v${version}:r${value.revision}`;
        const record={format:1 as const,time:Date.now(),value:next};
        try{await writeDraft(key,record);}catch{try{journalDraft(key,record);}catch{setError("다른 목소리의 임시 입력을 보관하지 못했습니다. 새로고침 전에 저장해 주세요.");}}
      }
      pending.clear();setState(value);setDraft(next);setDirty(remaining);
      if(speaker.role==="narrator")setOpen(false);
      setNotice(speaker.video_enabled===false?`${speaker.name} 목소리를 자동 설정으로 변경했습니다.`:`${speaker.name} 목소리 설정을 저장했습니다.`);
    }catch(e){setError(e instanceof ApiError&&e.code==="audio_settings_changed"
      ?"다른 화면에서 설정이 변경됐습니다. 입력을 복사해 두고 최신 설정을 다시 불러와 주세요.":`${speaker.video_enabled===false?"자동 설정으로 변경하지 못했습니다. 직접 설정과 입력은 유지됩니다. ":""}${message(e)}`);}
    finally{lock.current=false;setBusy(false);setAutomaticSaving(null);}
  }
  if(!state||!draft)return <section className="voice-directions">{error?<p role="alert">{error}</p>:<p role="status">목소리 특징을 불러오는 중…</p>}</section>;
  const update=(id:string,patch:Partial<Speaker>)=>{setDraft({...draft,speakers:draft.speakers.map(s=>s.id===id?{...s,...patch}:s)});setDirty(true);setNotice("");};
  const changed=(s:Speaker)=>JSON.stringify(s)!==JSON.stringify(state.settings.speakers.find(v=>v.id===s.id));
  const form=(s:Speaker)=><fieldset key={s.id} className="voice-direction-fields"><legend>{s.name}</legend>
    <Switch label={s.role==="narrator"?"나레이션 목소리 직접 설정":`${s.name} 목소리 직접 설정`} checked={s.video_enabled!==false} disabled={busy} onChange={()=>{if(s.video_enabled===false)update(s.id,{video_enabled:true});else void save({...s,video_enabled:false});}}/>
    {automaticSaving===s.id&&<p role="status">자동 설정으로 저장 중…</p>}
    {s.video_enabled!==false?<><Field id={prefix+s.id+"description"} label="목소리 특징" hint="나이 느낌·음역·음색·말투·발음을 적어 주세요. 영상 모델에 전달할 설명이며, 별도 음성 샘플을 만들지 않습니다.">{p=><textarea {...p} rows={3} maxLength={1000}
      disabled={busy||s.video_enabled===false} value={s.voice.instructions}
      placeholder={s.role==="narrator"?"예: 따뜻하고 차분한 중저음, 또렷한 발음과 부드러운 이야기체. 장면 사이에는 짧게 쉬어 주세요.":"예: 밝고 높은 음역의 어린아이 느낌, 가볍고 맑은 음색. 호기심 많은 말투로 또렷하게 말해 주세요."}
      onChange={e=>update(s.id,{voice:{...s.voice,instructions:e.target.value}})}/>}</Field>
    <div className="voice-direction-grid"><Field id={prefix+s.id+"language"} label="언어">{p=><input {...p} maxLength={80} value={s.voice.language} disabled={busy||s.video_enabled===false} onChange={e=>update(s.id,{voice:{...s.voice,language:e.target.value}})}/>}</Field>
      <Field id={prefix+s.id+"speed"} label="말하기 속도 의도" hint="0.75~1.25배 · 실제 속도는 생성 영상에서 확인합니다.">{p=><input {...p} type="number" min={.75} max={1.25} step={.05} value={s.voice.speed} disabled={busy||s.video_enabled===false} onChange={e=>update(s.id,{voice:{...s.voice,speed:Number(e.target.value)}})}/>}</Field></div></>:<p className="muted">자동 설정 · {s.role==="narrator"?"대본의 나레이션은":"캐릭터의 대사는"} 유지하고, {s.role==="narrator"?"이야기 내용":"캐릭터 설정과 이야기 내용"}·장면 분위기·이미지에 어울리는 목소리와 말투를 정합니다. 이전에 입력한 특징은 보관됩니다.</p>}
    {s.video_enabled!==false&&<div className="voice-speaker-save"><Button variant="secondary" disabled={busy||(!changed(s)&&state.revision>0)||((!s.voice.language.trim()||!Number.isFinite(s.voice.speed)||s.voice.speed<.75||s.voice.speed>1.25))} onClick={()=>void save(s)}><ActionIcon kind="save"/>{busy?"저장 중…":`${s.role==="narrator"?"나레이션":s.name} 목소리 저장`}</Button></div>}
  </fieldset>;
  const feedback=<>{pending.notice.includes("못")&&<p role="alert">{pending.notice}</p>}{error&&<div className="voice-direction-feedback" role="alert"><p>{error}</p><Button variant="secondary" disabled={busy} onClick={()=>void api<State>(path).then(value=>{pending.clear();accept(value);setError("");}).catch(e=>setError(message(e)))}>최신 설정 다시 불러오기</Button></div>}{notice&&<p role="status">{notice}</p>}</>;
  const narrators=draft.speakers.filter(s=>s.role==="narrator");
  const narration=<section className="voice-directions work-narration" aria-label="작품 공통 · 나레이션"><div className="voice-direction-heading"><div><h3>작품 공통 · 나레이션</h3><p className="muted">{narrators.map(s=>s.video_enabled===false?"자동 설정 · 이야기와 장면에 맞는 목소리":s.voice.instructions||"자동 설정 · 직접 입력한 특징 없음").join(" / ")}</p><StatusBadge>{narrators.some(changed)?"저장 전 변경":"설명으로 영상에 전달"}</StatusBadge></div><DisclosureButton variant="secondary" aria-expanded={open} aria-controls={prefix+"narration"} onClick={()=>setOpen(v=>!v)}>{open?"나레이션 접기":"나레이션 설정"}</DisclosureButton></div>
    <div id={prefix+"narration"} hidden={!open} className="voice-direction-panel"><p className="muted">이 캐릭터 작업에 연결된 작품 공통 설정입니다. 캐릭터마다 반복해서 정하지 않아도 됩니다.</p>{narrators.map(form)}</div>{feedback}</section>;
  return <>{narrationTarget?createPortal(narration,narrationTarget):narration}
    <section className="voice-directions" aria-label="캐릭터 목소리 특징"><div><h3>캐릭터 목소리 특징</h3><p className="muted">저장한 특징을 비디오 프롬프트와 영상 생성에 전달합니다. 클립마다 완전히 같은 음색이 유지되는지는 영상 모델에 따라 달라집니다.</p></div>
      {draft.speakers.filter(s=>s.role==="character"&&(!characterId||s.id===characterId)).map(form)}{feedback}
    </section></>;
}
