"use client";
import { useWorkDraft } from "../lib/work-draft";
import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api, ApiError, message } from "../lib/registry";
import { ActionIcon, Button, DraftNotice, DisclosureButton, DisclosureSummary, Field, StatusBadge, Switch } from "./ui";
import { voiceSampleStatus } from "../lib/voice-sample-status";
import { saveThenGenerateSample } from "../lib/save-voice-sample";
import { voiceLabel } from "../lib/voice-labels";
import { type VideoTimingReference } from "../lib/speech-video-timing";
import { SpeechVideoTiming } from "./speech-video-timing";
import styles from "./audio-production.module.css";

type Voice={model_key:string;voice:string;instructions:string;language:string;speed:number};
type Speaker={id:string;name:string;role:"character"|"narrator";voice:Voice;sample_job_id?:string|null};
type Cue={id:string;speaker_id:string;text:string;start:number;end:number;emotion:string;video_timing?:VideoTimingReference|null};
type Music={asset_id:string|null;offset:number;start:number;end:number|null;volume:number;loop:boolean;fade:number;duck:boolean};
type Settings={purpose?:"production"|"timing";enabled:boolean;speakers:Speaker[];cues:Cue[];music:Music};
type Job={purpose:"production"|"timing"|"sample";id:string;kind:"speech"|"compose";cue_id:string;status:string;duration:number|null;transcript:string|null;error_code:string|null;current:boolean;sample_voice?:Voice;sample_text?:string;created_at:string};
type State={selected_speakers:string[];revision:number;settings:Settings;jobs:Job[]};
type Catalog={models:Record<string,{label:string;voices:string[];provider?:"openai"|"typecast";generation_enabled?:boolean}>;generation_enabled:boolean;sample_text:string};
type Asset={id:string;name:string;duration:number};
type Source={request_id:string;version:number;agent_name:string;characters:{id:string;name:string}[]};
const states:Record<string,string>={queued:"실행 대기",running:"처리 중",review:"검토 필요",approved:"확정",failed:"실패",unknown:"호출 결과 확인 필요"};
const errors:Record<string,string>={audio_voice_selection_required:"캐릭터 설정에서 현재 목소리의 샘플을 듣고 선택해 주세요.",audio_sample_not_ready:"현재 설정과 일치하는 정상 샘플을 먼저 생성해 주세요.",audio_timing_only:"시간 측정용 음성은 최종 확정할 수 없습니다.",audio_video_too_short:"원본 영상이 계획된 길이보다 짧습니다. 영상을 다시 생성하거나 클립 계획을 수정해 주세요.",audio_settings_changed:"다른 화면에서 설정이 변경됐습니다. 최신 설정을 다시 불러와 주세요.",audio_timing_adjustment_required:"음성이 할당 시간보다 깁니다. 대사 또는 시간을 조정해 주세요.",audio_speech_approval_required:"모든 대사·내레이션의 현재 음성을 듣고 확정해 주세요.",audio_video_approval_required:"모든 클립 영상을 먼저 확정해 주세요.",audio_source_changed:"참조 또는 설정이 변경됐습니다. 현재 버전으로 다시 확인해 주세요.",audio_transcript_mismatch:"생성된 음성의 전사문이 대사와 다릅니다. 자동 확정할 수 없습니다.",audio_generation_disabled:"음성 API 키와 생성 활성화 설정이 필요합니다.",audio_original_removal_required:"기존 영상의 소리를 제거하고 별도 음원을 합성하는 데 동의해 주세요.",audio_voice_unavailable:"현재 사용할 수 없는 목소리 또는 모델입니다.",audio_music_timing:"음원 시작 구간과 길이를 확인해 주세요.",audio_timeline_invalid:"대사·음악의 시간이 영상 길이 안에 있는지 확인해 주세요.",audio_upload_invalid:"지원되는 오디오 파일인지 확인해 주세요. 최대 16MB·10분입니다.",worker_interrupted:"워커가 중단됐습니다. 공급자 호출 결과를 확인해야 하며 자동 재시도하지 않습니다."};
function errorText(e:unknown){
  if(e instanceof ApiError){
    if(e.code==="speech_retry_unavailable")return "최신 음성 상태를 다시 불러온 뒤 재생성 가능 여부를 확인해 주세요.";
    if(e.code==="speech_video_timing_unavailable")return "연결한 영상 검수 근거를 확인할 수 없습니다. 발화에서 다시 선택해 주세요.";
    return errors[e.code]||message(e);
  }
  return e instanceof Error?e.message:message(e);
}
const voice=():Voice=>({model_key:"openai-realtime",voice:"marin",instructions:"",language:"한국어",speed:1});
const id=(prefix:string)=>prefix+crypto.randomUUID().replaceAll("-","").slice(0,12);
const canPlay=(job:Job)=>job.status==="review"||job.status==="approved";
const audioUrl=(job:Job)=>`/api/v1/audio/jobs/${job.id}/media`;

function canGenerateVoice(catalog:Catalog,voice?:Voice){
  if(!voice)return false;
  const model=catalog.models[voice.model_key];
  return !!model&&model.voices.includes(voice.voice)&&(model.generation_enabled??catalog.generation_enabled);
}

export function AudioProduction({requestId,version,voicesOnly=false,productionOnly=false,characterId,narrationTarget}:{requestId:string;version:number;voicesOnly?:boolean;productionOnly?:boolean;characterId?:string;narrationTarget?:HTMLElement|null}){
  const prefix=useId(),path=`/audio/work/${requestId}/${version}`;
  const legacy=!voicesOnly&&!productionOnly;
  const reviewSamples=voicesOnly||productionOnly;
  const [state,setState]=useState<State|null>(null),[draft,setDraft]=useState<Settings|null>(null);
  const [catalog,setCatalog]=useState<Catalog|null>(null),[assets,setAssets]=useState<Asset[]>([]),[sources,setSources]=useState<Source[]>([]);
  const [source,setSource]=useState(""),[dirty,setDirty]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
  const [loadAttempt,setLoadAttempt]=useState(0);
  const actionLock=useRef(false);
  const actionVersion=useRef(0);
  const [sampleAction,setSampleAction]=useState<{speakerId:string;phase:"saving"|"requesting"|"accepted"|"error";text:string}|null>(null);
  const [narrationOpen,setNarrationOpen]=useState(true);
  const [heard,setHeard]=useState<Record<string,boolean>>({});
  const [removeOriginal,setRemoveOriginal]=useState(false);
  const pendingDraft=useWorkDraft(state?`audio:${requestId}:v${version}:r${state.revision}`:undefined,draft,saved=>{if(saved){setDraft(saved);setDirty(true);setNarrationOpen(true);}},Boolean(state&&draft),dirty);
  async function reload(){const value=await api<State>(path);setState(value);setDraft(value.settings);setDirty(false);}
  useEffect(()=>{let alive=true;Promise.all([api<State>(path),api<Catalog>("/audio/catalog"),productionOnly?Promise.resolve([]):api<Asset[]>("/audio/assets"),legacy?api<Source[]>("/audio/sources"):Promise.resolve([])]).then(([s,c,a,src])=>{if(alive){setState(s);setDraft(s.settings);setNarrationOpen(!(s.revision>0&&s.settings.speakers.some(speaker=>speaker.role==="narrator")));setCatalog(c);setAssets(a);setSources(src);}}).catch(e=>{if(alive)setError(errorText(e));});return()=>{alive=false;};},[path,legacy,productionOnly,loadAttempt]);
  useEffect(()=>{
    if(!state)return;
    let alive=true;
    let polling=false;
    const timer=setInterval(()=>{
      if(actionLock.current||polling)return;
      const versionAtPoll=actionVersion.current;
      polling=true;
      void api<State>(path).then(next=>{
        if(alive&&actionVersion.current===versionAtPoll)setState(old=>old?{...old,jobs:next.jobs}:next);
      }).catch(()=>{}).finally(()=>{polling=false;});
    },3000);
    return()=>{alive=false;clearInterval(timer);};
  },[path,Boolean(state)]);
  function change(next:Settings){setDraft(next);setDirty(true);setNotice("");}
  async function action(fn:()=>Promise<void>){if(actionLock.current)return;actionLock.current=true;actionVersion.current++;setBusy(true);setError("");setNotice("");try{await fn();}catch(e){setError(errorText(e));}finally{actionLock.current=false;setBusy(false);}}
  async function persistSettings(){
    const saved=await api<State>(path,"PUT",{revision:state!.revision,settings:draft});
    pendingDraft.clear();setState(saved);setDraft(saved.settings);setDirty(false);return saved;
  }
  async function save(){if(!draft||!state)return;await persistSettings();setNarrationOpen(false);setNotice("설정을 저장했습니다.");}
  async function createSample(speaker:Speaker,retry?:Job){
    if(actionLock.current||!state||!draft)return;
    actionLock.current=true;actionVersion.current++;setBusy(true);setError("");setNotice("");
    let phase:"saving"|"requesting"="saving";
    try{
      await saveThenGenerateSample({current:state,needsSave:dirty||state.revision===0,save:persistSettings,
        phase:value=>{phase=value;setSampleAction({speakerId:speaker.id,phase:value,text:value==="saving"?"현재 음색·말투 설정을 저장하고 있습니다.":"샘플 생성 요청을 보내고 있습니다."});},
        generate:revision=>api(path+"/sample","POST",{id:crypto.randomUUID(),revision,cue_id:speaker.id,
          ...(retry?{retry_job_id:retry.id}:{})})});
      setSampleAction({speakerId:speaker.id,phase:"accepted",text:"샘플 생성을 접수했습니다. 오디오 워커가 처리합니다."});
      try{setState(await api<State>(path));}catch{setSampleAction({speakerId:speaker.id,phase:"accepted",text:"생성은 접수됐지만 상태를 불러오지 못했습니다. 잠시 후 자동으로 갱신합니다."});}
    }catch(e){setSampleAction({speakerId:speaker.id,phase:"error",text:(phase==="saving"?"설정을 저장하지 못해 생성을 시작하지 않았습니다. ":"생성 요청을 완료하지 못했습니다. 현재 설정은 저장되어 있습니다. ")+errorText(e)});}
    finally{actionLock.current=false;setBusy(false);}
  }
  async function generate(cue:Cue,retry?:Job){
    const accepted=await api<{id:string;status:string}>(path+"/speech","POST",{id:crypto.randomUUID(),revision:state!.revision,cue_id:cue.id,...(retry&&{retry_job_id:retry.id})});
    setNotice("음성 생성을 접수했습니다. 오디오 워커가 처리합니다.");
    try{setState(await api<State>(path));}catch{
      if(productionOnly&&["queued","running"].includes(accepted.status)){
        const job:Job={...accepted,cue_id:cue.id,purpose:"production",kind:"speech",current:true,duration:null,transcript:null,error_code:null,created_at:new Date().toISOString()};
        setState(old=>old&&!old.jobs.some(result=>result.id===job.id)?{...old,jobs:[job,...old.jobs]}:old);
      }
      setNotice("음성 생성을 접수했습니다. 잠시 후 상태를 자동으로 갱신합니다.");
    }
  }
  async function approve(job:Job){await api(`/audio/jobs/${job.id}/approve`,"POST",{});setState(await api<State>(path));}
  async function upload(file:File){if(file.size>16*1024*1024)throw new Error("음원 파일은 최대 16MB입니다.");const data=await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(",")[1]);reader.onerror=reject;reader.readAsDataURL(file);});const asset=await api<Asset>("/audio/assets","POST",{name:file.name,data});setAssets(old=>[asset,...old]);change({...draft!,music:{...draft!.music,asset_id:asset.id}});}
  if(!draft||!state||!catalog)return <section className="audio-production" aria-label={productionOnly?"음성 제작":"음성·음악 설정"}>
    {error?<>
      <p role="alert">{error}</p>
      {productionOnly&&<div className="audio-actions"><Button variant="secondary" onClick={()=>{setError("");setLoadAttempt(count=>count+1);}}><ActionIcon kind="refresh"/>설정 다시 불러오기</Button></div>}
    </>:<p role="status">음성 설정을 불러오는 중…</p>}
  </section>;
  const editable=!busy;
  const saveDisabled=busy||(!dirty&&state.revision>0);
  const controlsDisabled=busy||dirty||!draft.enabled;
  function updateSpeaker(index:number,patch:Partial<Speaker>){change({...draft!,speakers:draft!.speakers.map((s,i)=>i===index?{...s,...patch}:s)});}
  function updateCue(index:number,patch:Partial<Cue>){change({...draft!,cues:draft!.cues.map((c,i)=>i===index?{...c,...patch}:c)});}
  function speakerStatus(speaker:Speaker){
    const savedSpeaker=state!.settings.speakers.find(s=>s.id===speaker.id);
    const changed=JSON.stringify(speaker)!==JSON.stringify(savedSpeaker);
    return voiceSampleStatus({changed,saved:state!.revision>0,selected:state!.selected_speakers.includes(speaker.id),sample:state!.jobs.find(j=>j.purpose==="sample"&&j.cue_id===speaker.id&&j.current)});
  }
  const speakerCards=draft.speakers.map((speaker,index)=>{
    const model=catalog.models[speaker.voice.model_key];
    const typecast=productionOnly&&model?.provider==="typecast";
    return <fieldset key={speaker.id} className="audio-speaker"><legend>{speaker.name} · {speaker.role==="narrator"?"내레이터":"캐릭터"}</legend><div className="audio-grid">
      {legacy&&<Field id={prefix+speaker.id+"name"} label="화자 이름">{p=><input {...p} disabled={!editable} value={speaker.name} maxLength={100} onChange={e=>updateSpeaker(index,{name:e.target.value})}/>}</Field>}
      <Field id={prefix+speaker.id+"model"} label="음성 모델" hint={productionOnly&&catalog.generation_enabled&&model?.generation_enabled===false?"선택한 모델은 관리자 연결 설정 후 생성할 수 있습니다.":undefined}>{p=><select {...p} disabled={!editable} value={speaker.voice.model_key} onChange={e=>updateSpeaker(index,{voice:{...speaker.voice,model_key:e.target.value,voice:catalog.models[e.target.value].voices[0]}})}>{productionOnly&&!model&&<option value={speaker.voice.model_key} disabled>현재 모델 사용 불가</option>}{Object.entries(catalog.models).map(([key,m])=><option key={key} value={key}>{m.label}</option>)}</select>}</Field>
      <Field id={prefix+speaker.id+"voice"} label="기본 음색">{p=><select {...p} disabled={!editable} value={speaker.voice.voice} onChange={e=>updateSpeaker(index,{voice:{...speaker.voice,voice:e.target.value}})}>{productionOnly&&!model?.voices.includes(speaker.voice.voice)&&<option value={speaker.voice.voice} disabled>현재 음색 사용 불가</option>}{(model?.voices||[]).map(v=><option key={v} value={v}>{voiceLabel(v)}</option>)}</select>}</Field>
      <Field id={prefix+speaker.id+"language"} label="언어">{p=><input {...p} disabled={!editable} value={speaker.voice.language} maxLength={80} onChange={e=>updateSpeaker(index,{voice:{...speaker.voice,language:e.target.value}})}/>}</Field>
      <Field id={prefix+speaker.id+"speed"} label="말하기 속도" hint="0.75~1.25배 · 생성 후 실제 길이를 확인합니다.">{p=><input {...p} type="number" min={.75} max={1.25} step={.05} disabled={!editable} value={speaker.voice.speed} onChange={e=>updateSpeaker(index,{voice:{...speaker.voice,speed:Number(e.target.value)}})}/>}</Field>
    </div><Field id={prefix+speaker.id+"delivery"} label="원하는 목소리·말투 직접 요청" hint={typecast?"Typecast에서는 기본 음색과 속도를 조정할 수 있습니다. 직접 작성한 말투 요청은 적용되지 않습니다.":productionOnly?"억양, 발음, 분위기 등 원하는 말투를 적고 샘플로 확인하세요.":"한국어로 분위기·억양·발음·감정 등을 적어 주세요. 선택한 기본 음색에 연출을 더하며, 새로운 고유 음색을 만들거나 특정인의 목소리를 복제하는 기능은 아닙니다. 요청의 반영 정도는 샘플로 확인하세요."}>{p=><textarea {...p} rows={3} disabled={!editable} readOnly={typecast} value={speaker.voice.instructions} maxLength={1000} placeholder={typecast?undefined:"예: 밝고 호기심 많은 아이 느낌으로, 발음은 또렷하게 읽어 주세요. 과장된 아기 말투는 피하고 놀라는 부분에서만 살짝 높은 톤을 사용해 주세요."} onChange={e=>updateSpeaker(index,{voice:{...speaker.voice,instructions:e.target.value}})}/>}</Field>{reviewSamples&&(()=>{
      const samples=state.jobs.filter(j=>j.purpose==="sample"&&j.cue_id===speaker.id);
      const sample=samples.find(j=>j.current);
      const changed=JSON.stringify(speaker)!==JSON.stringify(state.settings.speakers.find(s=>s.id===speaker.id));
      const status=speakerStatus(speaker);
      const selected=status.tone==="success";
      const retrySample=productionOnly&&!changed&&sample&&(sample.status==="failed"||Boolean(sample.error_code))?sample:undefined;
      const completedSample=Boolean(!changed&&sample&&!["failed","unknown"].includes(sample.status)&&!retrySample);
      return <div className="voice-sample-review">
        <div className="audio-actions"><StatusBadge tone={status.tone}>{status.label}</StatusBadge><Button variant="secondary" aria-describedby={prefix+speaker.id+"sample-feedback"} disabled={busy||!canGenerateVoice(catalog,speaker.voice)||samples.some(j=>["queued","running"].includes(j.status))||completedSample||Boolean(productionOnly&&samples[0]?.status==="unknown")} onClick={()=>void createSample(speaker,retrySample)}><ActionIcon kind="ai"/>{sampleAction?.speakerId===speaker.id&&busy?(sampleAction.phase==="saving"?"설정 저장 중…":"샘플 생성 요청 중…"):sample?.status==="queued"?"맞춤 샘플 생성 대기":sample?.status==="running"?"맞춤 샘플 생성 중…":retrySample?"샘플 다시 생성":"맞춤 샘플 생성"}</Button></div>
        {productionOnly&&samples[0]?.status==="unknown"&&<p className="helper-text">이전 샘플의 처리 결과가 불확실합니다. 관리자에게 호출 기록을 확인해 주세요.</p>}
        {typecast&&<p className="helper-text">Typecast에서 만든 샘플은 원문 일치 확인을 위해 OpenAI 전사를 거칩니다.</p>}
        <p id={prefix+speaker.id+"sample-feedback"} role={sampleAction?.speakerId===speaker.id&&sampleAction.phase==="error"?"alert":"status"} className={sampleAction?.speakerId===speaker.id&&sampleAction.phase==="error"?"field-error":"muted"}>{sampleAction?.speakerId===speaker.id&&!(sampleAction.phase==="accepted"&&sample)?sampleAction.text:"현재 음색·말투 설정을 자동 저장한 뒤 샘플을 생성합니다. 생성 시 API 비용이 발생할 수 있습니다."}</p>
        {!productionOnly&&<div className="voice-sample-guide"><h4>맞춤 샘플 · 내 요청을 적용해 비교</h4><p>{catalog.sample_text}</p><p className="muted">기본 음색·말투를 바꾸고 맞춤 샘플 생성을 누르면 설정 저장과 생성이 이어집니다. 말투·언어·속도도 함께 확인하세요. 생성할 때마다 API 비용이 발생할 수 있습니다. 이전 설정을 불러온 뒤에는 저장하고 샘플을 끝까지 들어 선택하세요.</p>{!catalog.generation_enabled&&<p className="muted">샘플 생성은 음성 API 활성화 후 사용할 수 있습니다.</p>}</div>}
        {!samples.length&&<p className="muted">아직 생성한 샘플이 없습니다. 위의 맞춤 샘플 생성 버튼으로 시작하세요.</p>}
        <div className="voice-sample-list">{samples.map(job=>{
          const active=job.current&&!dirty;
          const chosen=selected&&speaker.sample_job_id===job.id;
          const playable=canPlay(job);
          const available=job.sample_voice&&catalog.models[job.sample_voice.model_key]?.voices.includes(job.sample_voice.voice);
          return <article className="voice-sample-card" key={job.id} aria-label={speaker.name+" "+(job.sample_voice?voiceLabel(job.sample_voice.voice):"이전")+" 샘플"}>
            <div className="audio-actions"><strong>{job.sample_voice?voiceLabel(job.sample_voice.voice):"이전 샘플"}</strong><StatusBadge>{chosen?"선택한 목소리":active?"현재 설정":"비교용 이전 설정"}</StatusBadge><StatusBadge>{states[job.status]||job.status}</StatusBadge></div>
            <p className="muted">{new Date(job.created_at).toLocaleString("ko-KR")} · #{job.id.slice(0,8)}</p>
            {job.sample_voice&&<><p>{catalog.models[job.sample_voice.model_key]?.label||job.sample_voice.model_key} · {job.sample_voice.language} · {job.sample_voice.speed}배</p><p className="voice-sample-delivery">{job.sample_voice.instructions||"별도 말투 요청 없음"}</p></>}
            {job.sample_text&&job.sample_text!==catalog.sample_text&&<p className="muted">다른 문장으로 생성된 이전 샘플: {job.sample_text}</p>}
            {job.error_code&&<p role="alert">{errors[job.error_code]||"샘플 생성 실패 · 설정과 공급자 결과를 확인해 주세요."}</p>}
            {playable&&<audio controls preload="none" aria-label={speaker.name+" "+(job.sample_voice?voiceLabel(job.sample_voice.voice):"이전")+" 목소리 샘플 "+job.id.slice(0,8)} src={"/api/v1/audio/jobs/"+job.id+"/media"} onEnded={()=>setHeard(old=>({...old,[job.id]:true}))}/>}
            {active?<Button variant="secondary" disabled={busy||chosen||!playable||!heard[job.id]||!!job.error_code} onClick={()=>void action(async()=>{const next=await api<State>(path+"/select-voice","POST",{id:job.id,revision:state.revision,cue_id:speaker.id});setState(next);setDraft(next.settings);if(speaker.role==="narrator")setNarrationOpen(false);setNotice("샘플을 들은 목소리를 선택했습니다. 제작 음성을 생성한 뒤 시간표를 다시 확인하세요.");})}><ActionIcon kind="confirm"/>{chosen?"선택한 목소리":"샘플을 듣고 이 목소리 선택"}</Button>:<Button variant="secondary" disabled={busy||!available||!playable||!!job.error_code} onClick={()=>{if(job.sample_voice){updateSpeaker(index,{voice:{...job.sample_voice},sample_job_id:null});setNotice("샘플의 음색·말투·언어·속도를 불러왔습니다. 설정 저장 후 샘플을 듣고 선택해 주세요.");}}}><ActionIcon kind="refresh"/>이 샘플 설정 불러오기</Button>}
          </article>;
        })}</div>
      </div>;
    })()}</fieldset>;
  });
  if(productionOnly){
    const speechByCue=new Map<string,Job[]>();
    for(const job of state.jobs){
      if(job.kind!=="speech"||job.purpose!=="production")continue;
      const jobs=speechByCue.get(job.cue_id)??[];
      jobs.push(job);
      speechByCue.set(job.cue_id,jobs);
    }
    const savedCues=new Map(state.settings.cues.map(cue=>[cue.id,cue]));
    const cues=draft.cues.map((cue,index)=>({cue,index})).sort((a,b)=>(savedCues.get(a.cue.id)?.start??a.cue.start)-(savedCues.get(b.cue.id)?.start??b.cue.start)||a.index-b.index);
    return <section className="audio-production" aria-labelledby={prefix+"production-title"}>
      <div className="audio-heading">
        <div>
          <h3 id={prefix+"production-title"}>음성 제작</h3>
          <p className="muted">화자별 샘플을 듣고 목소리를 선택하세요. 대사와 내레이션을 하나씩 생성하고 확인한 음성을 영상 편집에 사용할 수 있습니다.</p>
        </div>
        <StatusBadge tone={dirty?"warning":"neutral"}>{dirty?"저장 전 변경":state.revision?`설정 v${state.revision}`:"초기 설정"}</StatusBadge>
      </div>
      {pendingDraft.notice&&<DraftNotice compact message={pendingDraft.notice} hint="맞춤 샘플을 생성하거나 설정을 저장하면 현재 입력이 저장됩니다." actionLabel="저장된 설정으로 되돌리기" disabled={busy} onReset={()=>{pendingDraft.clear();setDraft(state.settings);setDirty(false);}}/>}
      {error&&<div className="audio-error" role="alert">
        <p>{error}</p>
        <div className="audio-actions"><Button variant="secondary" disabled={busy} onClick={()=>void action(reload)}><ActionIcon kind="refresh"/>최신 설정 다시 불러오기</Button></div>
      </div>}
      {notice&&<p role="status">{notice}</p>}
      {!catalog.generation_enabled&&<p className="audio-error">관리자가 음성 API를 활성화하면 새 음성과 맞춤 샘플을 생성할 수 있습니다.</p>}

      <section className={styles.section} aria-labelledby={prefix+"speakers-title"}>
        <h4 className={styles.sectionTitle} id={prefix+"speakers-title"}>화자별 목소리</h4>
        {speakerCards.length?<>
          <p className="muted">맞춤 샘플 문장 · {catalog.sample_text}</p>
          <div className="audio-speakers">{speakerCards}</div>
        </>:<p className="muted">이 작업에 연결된 화자가 없습니다.</p>}
      </section>

      <section className={styles.section} aria-labelledby={prefix+"cues-title"}>
        <div className="audio-heading">
          <div>
            <h4 className={styles.sectionTitle} id={prefix+"cues-title"}>대사·내레이션 시간표</h4>
            <p className="muted">시간과 감정을 조정한 뒤 설정을 저장하세요. 음성 생성 시 API 비용이 발생할 수 있습니다.</p>
          </div>
          <Button variant="secondary" disabled={saveDisabled} onClick={()=>void action(save)}><ActionIcon kind="save"/>{busy?"처리 중…":"설정 저장"}</Button>
        </div>
        {!cues.length&&<p className="muted">이 작업에 연결된 대사나 내레이션이 없습니다.</p>}
        {cues.map(({cue,index},position)=>{
          const speaker=draft.speakers.find(s=>s.id===cue.speaker_id);
          const model=speaker&&catalog.models[speaker.voice.model_key];
          const typecast=model?.provider==="typecast";
          const selected=state.selected_speakers.includes(cue.speaker_id);
          const jobs=speechByCue.get(cue.id)??[];
          const latest=jobs[0];
          const job=jobs.find(result=>result.current);
          const previous=jobs.filter(result=>result.id!==job?.id);
          const active=jobs.find(result=>result.status==="queued"||result.status==="running");
          const unknown=latest?.status==="unknown";
          const tooLong=job?.duration!=null&&job.duration>cue.end-cue.start+.02;
          const approved=job?.status==="approved"&&selected&&!tooLong&&!job.error_code;
          const canRetry=job&&["review","approved","failed"].includes(job.status);
          const savedCue=savedCues.get(cue.id);
          const cueChanged=savedCue&&(cue.start!==savedCue.start||cue.end!==savedCue.end||cue.emotion!==savedCue.emotion
            ||JSON.stringify(cue.video_timing??null)!==JSON.stringify(savedCue.video_timing??null));
          const timingError=cue.end<=cue.start?"종료 시간은 시작 시간보다 뒤여야 합니다.":undefined;
          const number=position+1;
          const cuePrefix=`${prefix}${cue.id}-`;
          return <fieldset className="audio-cue" key={cue.id}>
            <legend>발화 {number} · {speaker?.name??"화자"}</legend>
            <Field id={cuePrefix+"source-text"} label="대사·나레이션 원문">{p=><textarea {...p} rows={2} value={cue.text} readOnly/>}</Field>
            <div className={styles.timing}>
              {(["start","end"] as const).map(key=><Field key={key} id={cuePrefix+key} label={key==="start"?"시작 (초)":"종료 (초)"} error={key==="end"?timingError:undefined}>
                {p=><input {...p} type="number" min={0} max={3600} step="any" disabled={busy} value={cue[key]} onChange={e=>updateCue(index,{[key]:Number(e.target.value)})}/>}
              </Field>)}
            </div>
            <Field id={cuePrefix+"emotion"} label="이 발화의 감정·연출" hint={typecast?"Typecast에는 직접 작성한 감정·연출 요청이 적용되지 않습니다.":undefined}>{p=><input {...p} maxLength={300} value={cue.emotion} disabled={busy} readOnly={typecast} onChange={e=>updateCue(index,{emotion:e.target.value})}/>}</Field>
            <SpeechVideoTiming path={path} fieldId={cuePrefix} cue={cue} busy={busy}
              supportsDirection={Boolean(model&&!typecast)}
              take={job&&!cueChanged&&canPlay(job)?{src:audioUrl(job),duration:job.duration}:undefined}
              onApply={adjustment=>{updateCue(index,adjustment);setNotice("영상 참고를 적용했습니다. 발화 시간과 연출을 확인한 뒤 저장하세요.");}}
              onRemove={()=>{updateCue(index,{video_timing:null});setNotice("영상 참고 연결을 해제했습니다. 현재 발화 시간과 연출은 그대로입니다.");}}/>
            <div className="audio-actions">
              <StatusBadge tone={dirty||tooLong||unknown?"warning":job?.status==="failed"||job?.error_code?"danger":approved?"success":"neutral"}>
                {dirty?"설정 저장 후 확인":active?states[active.status]:unknown?states.unknown:tooLong?"시간 조정 필요":job?.status==="approved"&&!selected?"목소리 선택 필요":job?states[job.status]??job.status:"생성 전"}
              </StatusBadge>
              <Button variant={job?"secondary":"primary"} aria-describedby={canRetry?cuePrefix+"retry-cost":undefined} disabled={controlsDisabled||!canGenerateVoice(catalog,speaker?.voice)||!selected||!!active||unknown||Boolean(job&&!canRetry)} onClick={()=>void action(()=>generate(cue,job))}>
                <ActionIcon kind="ai"/>{canRetry?"이 발화 다시 생성":"음성 생성"}
              </Button>
              {cueChanged&&<Button variant="secondary" disabled={saveDisabled||!!timingError} onClick={()=>void action(save)}><ActionIcon kind="save"/>변경한 설정 저장</Button>}
            </div>
            {canRetry&&<p id={cuePrefix+"retry-cost"} className="muted">다시 생성하면 API 비용이 발생할 수 있습니다.</p>}
            {!dirty&&!selected&&<p className="muted">위에서 {speaker?.name??"화자"}의 샘플을 듣고 목소리를 선택하세요.</p>}
            {unknown&&<p className="muted">공급자의 사용 내역에서 이 호출의 처리 결과를 확인하세요.</p>}
            {job?.error_code&&<p role="alert" className="audio-error">{errors[job.error_code]||"음성 생성 결과에 오류가 있습니다."}</p>}
            {job&&canPlay(job)&&<div className="audio-result" key={job.id}>
              <p>실제 음성 {job.duration==null?"미측정":`${job.duration.toFixed(2)}초`} / 배정 {(cue.end-cue.start).toFixed(2)}초</p>
              {tooLong&&<p role="alert" className="audio-error">음성이 배정 시간보다 깁니다. 시작·종료 시간을 조정해 주세요.</p>}
              <audio controls preload="none" aria-label={`${speaker?.name??"화자"} 발화 ${number}`} src={audioUrl(job)} onEnded={()=>setHeard(old=>({...old,[job.id]:true}))}/>
              <p className={`muted ${styles.transcript}`}>음성 전사 · {job.transcript||"확인되지 않음"}</p>
              {(job.status!=="approved"||approved&&!dirty)&&<div className="audio-actions">
                {job.status!=="approved"&&<Button variant="secondary" disabled={controlsDisabled||!selected||!heard[job.id]||tooLong||!!job.error_code} onClick={()=>void action(async()=>{await approve(job);setNotice("확정한 음성을 영상 편집에 사용할 수 있습니다.");})}>
                  <ActionIcon kind="confirm"/>듣고 확인한 음성 확정
                </Button>}
                {approved&&!dirty&&<a className="button button--secondary" download={`speech-${cue.id}.wav`} href={audioUrl(job)}><ActionIcon kind="download"/>확정 음성 다운로드</a>}
              </div>}
            </div>}
            {previous.length>0&&<details className={styles.history}>
              <DisclosureSummary>이전 결과 {previous.length}개</DisclosureSummary>
              <div className={styles.historyList}>
                {previous.map(result=><article key={result.id} className="audio-result">
                  <div className="audio-actions"><StatusBadge>{states[result.status]??result.status}</StatusBadge><p className="muted">{new Date(result.created_at).toLocaleString("ko-KR")}</p></div>
                  {canPlay(result)&&<audio controls preload="none" aria-label={`발화 ${number} 이전 음성 ${result.id.slice(0,8)}`} src={audioUrl(result)}/>}
                </article>)}
              </div>
            </details>}
          </fieldset>;
        })}
      </section>
    </section>;
  }
  const narrators=draft.speakers.filter(s=>s.role==="narrator");
  return <>{pendingDraft.notice&&<DraftNotice message={pendingDraft.notice} hint="맞춤 샘플 생성 또는 설정 저장을 누르면 현재 입력이 저장됩니다. 되돌리기를 누르면 미저장 입력을 버리고 마지막 저장 상태로 돌아갑니다. 기존 생성 음성은 유지됩니다." actionLabel="저장된 음성 설정으로 되돌리기" disabled={busy} onReset={()=>{pendingDraft.clear();setDraft(state.settings);setDirty(false);}}/>}{voicesOnly&&narrationTarget&&createPortal(<section className="audio-production work-narration" aria-label="작품 공통 · 나레이션"><div className="audio-heading"><div><h3>작품 공통 · 나레이션</h3><p className="muted">{narrators.map(s=>`${voiceLabel(s.voice.voice)} · ${s.voice.language} · ${s.voice.speed}배`).join(" / ")||"나레이션을 설정해 주세요."}</p>{narrators.length?narrators.map(s=>{const status=speakerStatus(s);return <StatusBadge key={s.id} tone={status.tone}>{narrators.length>1?s.name+" · ":""}{status.label}</StatusBadge>;}):<StatusBadge>설정 필요</StatusBadge>}</div><DisclosureButton variant="secondary" aria-expanded={narrationOpen} aria-controls={prefix+"narration-panel"} onClick={()=>setNarrationOpen(open=>!open)}>{narrationOpen?"나레이션 접기":"나레이션 설정 펼치기"}</DisclosureButton></div>{error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}<div id={prefix+"narration-panel"} hidden={!narrationOpen} className="narration-panel"><p className="muted">이 캐릭터 작업 전체에 사용하는 나레이션입니다. 캐릭터를 바꿔도 같은 설정이 유지되며 한 번만 선택하면 됩니다.</p><div className="audio-speakers">{speakerCards.filter((_,index)=>draft.speakers[index].role==="narrator")}</div>{!draft.speakers.some(s=>s.role==="narrator")&&<Button variant="secondary" disabled={busy||draft.speakers.length>=30} onClick={()=>change({...draft,speakers:[...draft.speakers,{id:id("narrator"),name:"나레이션",role:"narrator",voice:voice()}]})}>나레이션 추가</Button>}<div className="audio-save"><p className="muted">변경한 나레이션·캐릭터 음성 설정을 함께 저장합니다.</p><Button disabled={saveDisabled} onClick={()=>void action(save)}>음성 설정 저장</Button></div></div></section>,narrationTarget)}<section className="audio-production" aria-label={voicesOnly?"선택한 캐릭터 목소리":"음성·음악 제작"}>
    <div className="audio-heading"><div><h3>{voicesOnly?"선택한 캐릭터 목소리":"음성·음악 제작"}</h3><p className="muted">{voicesOnly?"① 음색·말투 입력 → ② 맞춤 샘플 생성·듣기 (설정 자동 저장) → ③ 목소리 선택. 선택 후 비디오 작업에서 가져와 대사를 생성합니다. 샘플 생성은 API 비용이 발생할 수 있습니다.":"음성을 별도로 생성·확정하고 영상과 합성합니다. 이 기능을 켜면 새 영상은 무음으로 요청합니다. 립싱크 자동 보정은 포함하지 않습니다."}</p></div><StatusBadge>{dirty?"저장 전 변경":"설정 v"+state.revision}</StatusBadge></div>
    {error&&<div className="audio-error" role="alert"><p>{error}</p><Button variant="secondary" disabled={busy} onClick={()=>void action(reload)}>최신 설정 다시 불러오기</Button></div>}
    {notice&&<p role="status">{notice}</p>}
    {!voicesOnly&&<Switch label="별도 음성·음악 제작 사용" checked={draft.enabled} disabled={busy} onChange={()=>change({...draft,enabled:!draft.enabled})}/>}
    {!voicesOnly&&<div className="audio-source"><Field id={prefix+"source"} label="목소리를 가져올 캐릭터 작업" hint="선택한 작업 버전의 설정을 복사합니다. 원본이 나중에 바뀌어도 이 설정은 유지됩니다.">{p=><select {...p} value={source} disabled={busy} onChange={e=>setSource(e.target.value)}><option value="">직접 설정</option>{sources.map(s=><option key={s.request_id+":"+s.version} value={s.request_id+":"+s.version}>{s.characters.map(c=>c.name).join(", ")} · v{s.version} · #{s.request_id.slice(0,8)}</option>)}</select>}</Field><Button variant="secondary" disabled={!source||busy} onClick={()=>void action(async()=>{const [r,v]=source.split(":");const s=await api<State>(`/audio/work/${r}/${v}`);if(draft.cues.some(c=>!s.settings.speakers.some(sp=>sp.id===c.speaker_id)&&!draft.speakers.some(sp=>sp.id===c.speaker_id&&sp.role==="narrator")))throw new Error("현재 대사의 화자 ID와 가져올 캐릭터가 다릅니다. 대사를 확인한 뒤 가져와 주세요.");const narrators=draft.speakers.filter(speaker=>speaker.role==="narrator");change({...draft,speakers:[...s.settings.speakers,...narrators.filter(n=>!s.settings.speakers.some(sp=>sp.id===n.id))]});})}>목소리 가져오기</Button></div>}
    <div className="audio-speakers">{speakerCards.filter((_,index)=>!voicesOnly||(draft.speakers[index].role!=="narrator"&&(!characterId||draft.speakers[index].id===characterId)))}</div>
    {!voicesOnly&&<div className="audio-actions">{(["character","narrator"] as const).map(role=><Button key={role} variant="secondary" disabled={busy||draft.speakers.length>=30||(voicesOnly&&draft.speakers.some(s=>s.role==="narrator"))} onClick={()=>change({...draft,speakers:[...draft.speakers,{id:id(role),name:role==="narrator"?"내레이터":"새 화자",role,voice:voice()}]})}>{role==="narrator"?"내레이터 추가":"화자 추가"}</Button>)}</div>}
    {!voicesOnly&&<><h4>대사·나레이션 시간표</h4><p className="muted">캐릭터 설정에서 샘플을 듣고 선택한 목소리를 가져온 뒤 생성하세요. AI가 제안한 원문과 시간을 확인하세요. 생성한 목소리는 AI 음성입니다. 저장만으로 유료 호출은 실행되지 않습니다.</p>{!catalog.generation_enabled&&<p className="audio-error">음성 생성이 비활성화되어 있습니다. 관리자 서버의 음성 API 설정이 필요합니다. 음악 선택과 로컬 합성 설정은 사용할 수 있습니다.</p>}
      {draft.cues.map((cue,index)=>{const job=state.jobs.find(j=>j.kind==="speech"&&j.purpose!=="sample"&&j.cue_id===cue.id&&j.current);const long=!!job?.duration&&job.duration>cue.end-cue.start+.02;return <fieldset className="audio-cue" key={cue.id}><legend>발화 {index+1}</legend><div className="audio-grid"><Field id={prefix+cue.id+"speaker"} label="화자">{p=><select {...p} disabled={busy} value={cue.speaker_id} onChange={e=>updateCue(index,{speaker_id:e.target.value})}>{draft.speakers.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select>}</Field>{(["start","end"] as const).map(key=><Field key={key} id={prefix+cue.id+key} label={key==="start"?"시작 (초)":"종료 (초)"}>{p=><input {...p} type="number" min={0} max={3600} step={.1} disabled={busy} value={cue[key]} onChange={e=>updateCue(index,{[key]:Number(e.target.value)})}/>}</Field>)}</div><Field id={prefix+cue.id+"text"} label="말할 대사·나레이션 원문">{p=><textarea {...p} rows={3} maxLength={1500} value={cue.text} disabled={busy} onChange={e=>updateCue(index,{text:e.target.value})}/>}</Field><Field id={prefix+cue.id+"emotion"} label="이 발화의 감정·연출">{p=><input {...p} maxLength={300} value={cue.emotion} disabled={busy} onChange={e=>updateCue(index,{emotion:e.target.value})}/>}</Field>
      <div className="audio-actions"><Button disabled={controlsDisabled||!canGenerateVoice(catalog,draft.speakers.find(s=>s.id===cue.speaker_id)?.voice)||!!job||(draft.purpose!=="timing"&&!state.selected_speakers.includes(cue.speaker_id))} onClick={()=>void action(()=>generate(cue))}>음성 생성</Button><Button variant="secondary" disabled={busy} onClick={()=>change({...draft,cues:draft.cues.filter(c=>c.id!==cue.id)})}>발화 제거</Button>{job&&<StatusBadge>{dirty?"설정 변경 · 저장 후 확인":states[job.status]||job.status}</StatusBadge>}</div>
      {job&&<div className="audio-result">{["failed","unknown"].includes(job.status)||job.error_code?<><p className="muted">이전 호출은 자동 재실행하지 않습니다. 공급자 사용 내역을 확인한 후 새 발화로 다시 준비할 수 있습니다. 새 생성은 별도 과금될 수 있습니다.</p><Button variant="secondary" disabled={busy} onClick={()=>updateCue(index,{id:id("cue")})}>새 발화로 다시 준비</Button></>:null}<p>실제 음성 {job.duration?.toFixed(2)??"미측정"}초 / 할당 {(cue.end-cue.start).toFixed(2)}초</p>{long&&<p role="alert" className="audio-error">시간 조정 필요 · 음성을 자르지 않습니다.</p>}{job.error_code&&<p role="alert" className="audio-error">{errors[job.error_code]||"처리 실패 · 설정과 공급자 결과를 확인해 주세요."}</p>}{["review","approved"].includes(job.status)&&<><audio controls preload="none" aria-label={`${draft.speakers.find(s=>s.id===cue.speaker_id)?.name} 발화 ${index+1}`} src={`/api/v1/audio/jobs/${job.id}/media`}/><p className="muted">음성 전사: {job.transcript||"확인되지 않음"}</p><Button variant="secondary" disabled={controlsDisabled||job.purpose!=="production"||long||!!job.error_code||job.status==="approved"} onClick={()=>void action(()=>approve(job))}>듣고 확인한 음성 확정</Button></>}</div>}</fieldset>;})}
      <Button variant="secondary" disabled={busy||!draft.speakers.length||draft.cues.length>=200} onClick={()=>{const end=draft.cues.at(-1)?.end||0;change({...draft,cues:[...draft.cues,{id:id("cue"),speaker_id:draft.speakers[0].id,text:"",start:end,end:end+3,emotion:""}]});}}>발화 추가</Button>
      <h4>배경음악</h4><div className="audio-grid"><Field id={prefix+"music"} label="음원 보관함">{p=><select {...p} value={draft.music.asset_id||""} disabled={busy} onChange={e=>change({...draft,music:{...draft.music,asset_id:e.target.value||null}})}><option value="">배경음악 없음</option>{assets.map(a=><option key={a.id} value={a.id}>{a.name} · {a.duration.toFixed(1)}초</option>)}</select>}</Field><Field id={prefix+"upload"} label="음원 업로드" hint="사용할 권한이 있는 음원 · 최대 16MB / 10분">{p=><input {...p} type="file" accept="audio/*" disabled={busy} onChange={e=>{const file=e.target.files?.[0];e.target.value="";if(file)void action(()=>upload(file));}}/>}</Field></div>
      {draft.music.asset_id&&<><audio controls preload="none" aria-label="선택한 배경음악" src={`/api/v1/audio/assets/${draft.music.asset_id}/media`}/><div className="audio-grid">{([['offset','음원에서 시작할 위치 (초)'],['start','영상에 음악이 시작될 시간 (초)'],['volume','음량 (0~1)'],['fade','페이드 (초)']] as const).map(([key,label])=><Field key={key} id={prefix+key} label={label}>{p=><input {...p} type="number" min={0} step={.1} disabled={busy} value={draft.music[key]} onChange={e=>change({...draft,music:{...draft.music,[key]:Number(e.target.value)}})}/>}</Field>)}<Field id={prefix+"music-end"} label="영상에 음악이 끝날 시간 (초)" hint="비워두면 영상 끝까지 사용합니다.">{p=><input {...p} type="number" min={0} step={.1} disabled={busy} value={draft.music.end??""} onChange={e=>change({...draft,music:{...draft.music,end:e.target.value===""?null:Number(e.target.value)}})}/>}</Field></div><Switch label="짧은 음원 반복" checked={draft.music.loop} disabled={busy} onChange={()=>change({...draft,music:{...draft.music,loop:!draft.music.loop}})}/><Switch label="말하는 동안 음악 낮추기" checked={draft.music.duck} disabled={busy} onChange={()=>change({...draft,music:{...draft.music,duck:!draft.music.duck}})}/></>}
    </>}
    <div className="audio-save"><p className="muted">{dirty?(voicesOnly?"맞춤 샘플 생성 시 현재 설정이 함께 저장됩니다. 설정만 저장할 수도 있습니다.":"먼저 설정을 저장해 주세요."):"원본 대본과 생성 결과는 유지됩니다."}</p><Button disabled={saveDisabled} onClick={()=>void action(save)}>{busy?"처리 중…":"설정 저장"}</Button></div>
    {!voicesOnly&&<div className="audio-composition"><h4>최종 영상 합성</h4><p>확정된 클립과 음성을 연결하고 음악을 한 타임라인에 배치합니다. 대사·음성이 없는 영상도 합성할 수 있습니다. 기존 영상의 소리는 합성본에서 제거됩니다.</p><Switch checked={removeOriginal} disabled={busy} label="기존 영상에 소리가 있어도 제거하고 별도 음원을 사용" onChange={()=>setRemoveOriginal(v=>!v)}/><Button disabled={controlsDisabled} onClick={()=>void action(async()=>{await api(path+"/compose","POST",{id:crypto.randomUUID(),revision:state.revision,remove_original:removeOriginal});setState(await api<State>(path));setNotice("합성을 접수했습니다. 오디오 워커가 처리합니다.");})}>합성 미리보기 만들기</Button>{state.jobs.filter(j=>j.kind==="compose").map(job=><div className="audio-result" key={job.id}><StatusBadge>{states[job.status]||job.status}{!job.current?" · 이전 설정":""}</StatusBadge>{job.error_code&&<p role="alert">{errors[job.error_code]||"합성하지 못했습니다. 원본 영상과 시간표를 확인해 주세요."}</p>}{["review","approved"].includes(job.status)&&<><video controls preload="metadata" aria-label="합성 영상 미리보기" src={`/api/v1/audio/jobs/${job.id}/media`}/><div className="audio-actions"><Button disabled={busy||dirty||!job.current||job.status==="approved"} onClick={()=>void action(()=>approve(job))}>확인한 최종본 확정</Button>{job.status==="approved"&&<a className="button button--secondary" download={`final-${job.id}.mp4`} href={`/api/v1/audio/jobs/${job.id}/media`}>최종본 다운로드</a>}</div></>}</div>)}</div>}
  </section></>;
}
