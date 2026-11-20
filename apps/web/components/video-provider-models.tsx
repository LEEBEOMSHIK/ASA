"use client";
import {useEffect,useId,useState} from "react";
import {api} from "../lib/registry";
import {videoModelName,videoModelFamilies,sameVideoModel,type VideoDefaults} from "../lib/video-model-selection";
import {connectionAuthenticated,connectionLabel,type VideoConnectionCheck} from "../lib/video-connection";
import {ActionIcon,Button,Field,StatusBadge} from "./ui";
import {VideoReferenceSupport,type ReferenceSupport} from "./video-reference-support";
import {VideoCostPreview} from "./video-cost-preview";

type Model={reference_support?:ReferenceSupport;key:string;provider:string;label:string;model:string;revision:string;durations:number[];aspect_ratios:string[];resolution:string;supports_audio:boolean;generation_supported:boolean;connection_state:string;connection_check?:VideoConnectionCheck;usd_per_second_with_video:number|null;usd_per_second:number|null};
type Catalog={models:Model[];enabled:boolean;worker_online:boolean};
export function VideoProviderModels({provider,defaults={},canManage=false,busy=false,onSave}:{provider:string;defaults?:VideoDefaults;canManage?:boolean;busy?:boolean;onSave?:(family:string,value:{model_key:string;duration_seconds:number})=>void}){
  const id=useId();
  const [catalog,setCatalog]=useState<Catalog|null>(null),[error,setError]=useState(false);
  const [selected,setSelected]=useState('');
  const [duration,setDuration]=useState<number|null>(null);
  useEffect(()=>{
    let live=true,pending=false;
    async function load(){
      if(pending)return;pending=true;
      try{const value=await api<Catalog>('/video-planning/models');if(live){setCatalog(value);setError(false);}}
      catch{if(live)setError(true);}finally{pending=false;}
    }
    void load();const timer=setInterval(()=>{if(!document.hidden)void load();},3000);
    return()=>{live=false;clearInterval(timer);};
  },[]);
  const models=catalog?.models.filter(m=>m.provider===provider)??[];
  const candidate=models.find(m=>m.key===selected)??models[0];
  const defaultValue=candidate?defaults[`${candidate.provider}:${candidate.model}`]:undefined;
  const model=selected?candidate:models.find(m=>m.key===defaultValue?.model_key)??candidate;
  const seconds=duration??defaultValue?.duration_seconds??0;
  const families=videoModelFamilies(models);
  const family=model?families.find(m=>sameVideoModel(m,model)):undefined;
  const resolutions=model?models.filter(m=>sameVideoModel(m,model)):[];
  const lengths=[...(model?.durations??[])].sort((a,b)=>a-b);
  const durationLabel=lengths.length>1&&lengths.every((n,i)=>i===0||n===lengths[i-1]+1)
    ?`${lengths[0]}–${lengths[lengths.length-1]}초`:lengths.length?`${lengths.join(' · ')}초`:'미확인';
  function availability(m:Model){
    if(error)return '모델 상태 조회 실패';
    if(!m.generation_supported)return '생성 연결 미지원';
    if(m.connection_state==='disabled')return '제공자 사용 중지';
    if(m.connection_state==='missing_key')return 'API 키 미설정';
    if(m.connection_state==='missing_workspace')return '작업 공간 미설정';
    if(m.connection_state!=='configured')return '연결 설정 확인 필요';
    if(!connectionAuthenticated(m.connection_check))return connectionLabel(m.connection_check);
    if(!catalog?.enabled)return '새 영상 생성 중지';
    return catalog.worker_online?'생성 가능':'영상 처리 연결 대기';
  }
  return <section className="video-provider-models" aria-label="제공자 모델 정보">
    {error&&<p role="alert">모델 정보를 불러오지 못했습니다. 잠시 후 자동으로 다시 확인합니다.</p>}
    {!catalog&&!error&&<p role="status">모델 목록을 불러오는 중…</p>}
    {catalog&&!models.length&&<p className="helper-text">이 제공자에 등록된 사용 가능 모델이 없습니다.</p>}
    {model&&<>
      <Field id={`${id}-model`} label="영상 모델" hint="모델별 관리자 기본값을 확인합니다. 저장한 값은 사용자 세부설정을 허용하지 않을 때 새 요청에 적용됩니다.">{props=><select {...props} value={family?.key??model.key} onChange={event=>{const next=models.find(m=>m.key===event.target.value);setSelected(next?defaults[`${next.provider}:${next.model}`]?.model_key??next.key:event.target.value);setDuration(null);}}>
        {families.map(m=><option key={m.key} value={m.key}>{videoModelName(m)}</option>)}
      </select>}</Field>
      {resolutions.length>1&&<Field id={`${id}-resolution`} label="기본 영상 해상도" hint="저장 전에는 기존 설정이 바뀌지 않습니다.">{props=><select {...props} value={model.key} onChange={event=>setSelected(event.target.value)}>
        {resolutions.map(m=><option key={m.key} value={m.key}>{m.resolution==='4k'?'4K':m.resolution}</option>)}
      </select>}</Field>}
      <Field id={`${id}-duration`} label="기본 클립 생성 길이" hint="AI 자동 판단 또는 각 클립의 생성 길이를 지정합니다. 대본 전체 길이가 아닙니다.">{p=><select {...p} value={seconds} onChange={event=>setDuration(Number(event.target.value))}>
        <option value="0">AI 자동 판단</option>{model.durations.map(n=><option key={n} value={n}>{n}초</option>)}
      </select>}</Field>
      {canManage&&onSave&&<Button variant="secondary" disabled={busy||error||(seconds!==0&&!model.durations.includes(seconds))} onClick={()=>onSave(`${model.provider}:${model.model}`,{model_key:model.key,duration_seconds:seconds})}><ActionIcon kind="save"/>이 모델 기본값 저장</Button>}
      <p className="helper-text">저장된 기본값 · {models.find(m=>m.key===defaultValue?.model_key)?.resolution??'720p'} · {defaultValue?.duration_seconds?`${defaultValue.duration_seconds}초`:'AI 자동 판단'}</p>
      <div className="video-management-row"><strong>{videoModelName(model)}</strong><StatusBadge tone={availability(model)==='생성 가능'?'success':'warning'}>{availability(model)}</StatusBadge></div>
      <dl className="video-provider-model-facts">
        <div><dt>해상도</dt><dd>{model.resolution}</dd></div>
        <div><dt>화면 비율</dt><dd>{model.aspect_ratios.join(' · ')}</dd></div>
        <div><dt>생성 길이</dt><dd>{durationLabel}</dd></div>
        <div><dt>오디오 생성</dt><dd>{model.supports_audio?'지원':'미지원'}</dd></div>
      </dl>
      <VideoReferenceSupport support={model.reference_support}/>
      <p className="helper-text">적용할 길이와 해상도로 요금을 비교합니다. 생성 전에는 영상 계획을 확인·확정해야 합니다.</p>
      {provider==='higgsfield'&&model.durations.length>0?<VideoCostPreview key={model.key+model.revision+seconds} initialSeconds={seconds||undefined} modelKey={model.key} modelLabel={videoModelName(model)} revision={model.revision} durations={model.durations} supportsVideoReference={model.reference_support?.video??false} rate={model.usd_per_second} videoRate={model.usd_per_second_with_video}/>:<p className="helper-text">{model.usd_per_second==null?'예상 요금 미확인':`공개 요금 기준 1초당 $${model.usd_per_second} USD · 실제 청구액과 다를 수 있음`}</p>}
    </>}
  </section>;
}
