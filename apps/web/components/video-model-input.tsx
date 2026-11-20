"use client";
import { useEffect, useState } from "react";
import { api, type SchemaNode } from "../lib/registry";
import { ActionIcon, Button, ExternalLink, Field, StatusBadge } from "./ui";
import { modelStyleGuidance } from "../lib/video-model-guidance";
import {VideoReferenceSupport,type ReferenceSupport} from "./video-reference-support";
import {VideoCostPreview} from "./video-cost-preview";
import { videoStyles } from "../lib/video-prompt-settings";
import {videoModelChoices,videoModelName,videoProviders,videoModelFamilies,sameVideoModel,appliedVideoModel,type VideoDefaults} from "../lib/video-model-selection";

import { connectionAuthenticated, connectionLabel, videoTimestamp, type VideoConnectionCheck } from "../lib/video-connection";

type Catalog = {model_defaults:VideoDefaults;user_details_enabled:boolean;models: {resolution:string;reference_support?:ReferenceSupport;supports_audio:boolean;usd_per_second:number|null;usd_per_second_with_video:number|null;key:string; label:string; revision:string; durations:number[]; provider:string; model:string; connection_state:string; connection_check?:VideoConnectionCheck; generation_supported:boolean}[];
  enabled:boolean; key_configured:boolean; worker_online:boolean};
export function VideoModelInput({node,id,label,required,value,onChange,videoStyle="",duration="0",onDurationChange}: {
  node:SchemaNode; id:string; label:string; required:boolean; value:string; onChange:(v:string)=>void; videoStyle?:string;duration?:string;onDurationChange?:(value:string)=>void;
}) {
  const [data,setData] = useState<Catalog|null>(null);
  const [results,setResults] = useState<Record<string,string>>({});
  const [busy,setBusy] = useState(false);
  const [failed,setFailed] = useState(false);
  useEffect(()=>{
    let live=true, pending=false;
    async function refresh() {
      if(pending || document.hidden)return;
      pending=true;
      try {
        const next=await api<Catalog>("/video-planning/models");
        if(live){setData(next);setFailed(false);}
      } catch {if(live)setFailed(true);}
      finally {pending=false;}
    }
    void refresh();
    const timer=setInterval(()=>void refresh(),3000);
    const onVisible=()=>{void refresh();};
    window.addEventListener("focus",onVisible);
    document.addEventListener("visibilitychange",onVisible);
    return ()=>{live=false;clearInterval(timer);window.removeEventListener("focus",onVisible);document.removeEventListener("visibilitychange",onVisible);};
  },[]);
  function supportsCheck(catalog: Catalog | null, key: string) {
    return catalog?.models.some(m=>m.key===key && m.generation_supported);
  }
  function status(key:string) {
    if (failed) return "상태 조회 실패";
    if (!data) return "상태 조회 중";
    if (!supportsCheck(data,key)) return "생성 연결 없음";
    const model=data.models.find(m=>m.key===key);
    if (model?.connection_state==="disabled") return "공급자 사용 비활성";
    if (model?.connection_state==="missing_workspace") return "공급자 작업 공간 미설정";
    if (model?.connection_state!=="configured") return "API 키 미설정";
    if (!connectionAuthenticated(model.connection_check)) return connectionLabel(model.connection_check);
    if (!data.enabled) return "영상 생성 비활성";
    return data.worker_online ? "생성 가능" : "영상 처리 연결 대기";
  }
  async function verify() {
    setBusy(true);
    try {
      const current=await api<Catalog>("/video-planning/models");
      setData(current);setFailed(false);
      const model=current.models.find(m=>m.key===value);
      let result="이 모델의 연결 확인을 지원하지 않습니다.";
      if (model?.generation_supported) {
        const check=await api<VideoConnectionCheck>(`/video-planning/provider-connection/${encodeURIComponent(model.provider)}`,"POST");
        result=connectionLabel(check)+" · 확인 시각 "+videoTimestamp(check.checked_at)+". 영상 생성·모델 권한·잔액을 검증한 결과는 아닙니다.";
        setData({...current,models:current.models.map(m=>m.provider===model.provider?{...m,connection_check:check}:m)});
      }
      setResults(old=>({...old,[value]:result}));
    } catch {setResults(old=>({...old,[value]:"연결 상태를 확인하지 못했습니다. 다시 시도해 주세요."}));} finally {setBusy(false);}
  }
  const selectedLabel=data?.models.find(m=>m.key===value)?.label ?? value;
  const selected=data?appliedVideoModel(data.models,value,data.user_details_enabled,data.model_defaults??{}):undefined;
  const appliedDuration=data?.user_details_enabled?Number(duration):data?.model_defaults?.[`${selected?.provider}:${selected?.model}`]?.duration_seconds??0;
  const choices=videoModelChoices(node.enum,data?.models??[],value);
  const provider=choices.find(m=>m.key===value)?.provider??"";
  const providerKeys=[...new Set(choices.map(m=>m.provider))];
  const providerLabel=(key:string)=>videoProviders[key]??(key==="unavailable"?"기존 선택 · 제공자 확인 필요":key);
  const models=videoModelFamilies(choices.filter(m=>m.provider===provider));
  const family=selected?models.find(m=>sameVideoModel(m,selected)):models.find(m=>m.key===value);
  const resolutions=selected?data?.models.filter(m=>sameVideoModel(m,selected)&&choices.some(c=>c.key===m.key))??[]:[];
  const modelName=choices.find(m=>m.key===value);
  const styleName=videoStyles.find(s=>s.id===videoStyle)?.name;
  const guidance=selected ? modelStyleGuidance(selected.provider,selected.model,videoStyle) : null;
  const tone = failed ? "danger" : !data ? "neutral" :
    supportsCheck(data,value) && selected?.connection_state==="configured" && connectionAuthenticated(selected.connection_check) && data.enabled && data.worker_online ? "success" : "warning";
  const actionLabel=selectedLabel+" 연결 확인"+(busy?" 중":"");
  return <div className="field video-model-input">
    <Field id={`${id}-provider`} label="영상 제공자" required={required}>{p=><select {...p} value={provider} disabled={busy} required={required}
      onChange={e=>onChange(choices.find(m=>m.provider===e.target.value)?.key??"")}>
      <option value="">제공자 선택</option>{providerKeys.map(key=><option key={key} value={key}>{providerLabel(key)}</option>)}
    </select>}</Field>
    <section className="video-provider-model" aria-label={provider?`${providerLabel(provider)} 모델 선택`:"영상 모델 선택"}>
    <Field id={id} label={label} required={required} hint="선택한 제공자의 모델입니다. 모델 변경만으로 영상을 생성하지 않습니다.">{p=>
    <div className="video-model-row"><div className="video-model-control"><select {...p} required={required} disabled={busy} value={family?.key??value} onChange={e=>onChange(e.target.value)}>
      <option value="" disabled={Boolean(provider)}>{provider?"모델 선택":"제공자를 먼저 선택하세요"}</option>{models.map(model=><option key={model.key} value={model.key}>
        {videoModelName(model)} · {status(model.key)}</option>)}</select>
      <span className="video-model-face" aria-hidden="true">
        <span className="video-model-name">{modelName ? videoModelName(modelName) : "제공자를 먼저 선택하세요"}</span>
        {value && <StatusBadge tone={tone}>{status(value)}</StatusBadge>}
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="m4 6 4 4 4-4" stroke="currentColor" strokeWidth="1.5"/></svg>
      </span></div>
      {value && (supportsCheck(data,value) || failed) && <Button className="video-model-check" variant="secondary" disabled={busy} title={actionLabel} aria-label={actionLabel} onClick={verify}>
        <ActionIcon kind="refresh"/>{busy?"확인 중":"연결 확인"}
      </Button>}</div>}</Field>
    {(busy || (value && results[value])) && <span role="status" className="helper-text">{busy ? actionLabel+"…" : selectedLabel+" · "+results[value]}</span>}
    {value&&data&&!data.enabled&&<p className="helper-text">영상 생성이 중지되어 있습니다. 관리자에게 문의해 주세요. 프롬프트 작성은 가능합니다.</p>}
    {selected&&(data?.user_details_enabled&&resolutions.length>1?
      <Field id={`${id}-resolution`} label="영상 해상도" hint="이번 영상 계획과 생성 요청에 적용합니다. 해상도에 따라 예상 요금이 달라집니다.">{p=><select {...p} value={value} disabled={busy} onChange={e=>onChange(e.target.value)}>
        {resolutions.map(m=><option key={m.key} value={m.key}>{m.resolution==='4k'?'4K':m.resolution}</option>)}
      </select>}</Field>:<p className="helper-text">영상 해상도 · {selected.resolution==='4k'?'4K':selected.resolution}</p>)}
    {selected&&<>
      <p className="helper-text">{data?.user_details_enabled?'사용자 설정 적용 · 관리자 기본값은 적용하지 않습니다.':'관리자 설정 적용 · 접수 시점의 기본 길이와 해상도로 계획합니다.'}</p>
      {data?.user_details_enabled&&onDurationChange?<Field id={`${id}-duration`} label="클립 생성 길이" hint="자동 판단 또는 각 클립의 생성 길이를 선택하세요. 대본 전체 길이와는 다릅니다.">{p=><select {...p} value={duration} onChange={e=>onDurationChange(e.target.value)}>
        <option value="0">AI 자동 판단</option>{selected.durations.map(seconds=><option key={seconds} value={seconds}>{seconds}초</option>)}
        {appliedDuration!==0&&!selected.durations.includes(appliedDuration)&&<option value={duration} disabled>{duration}초 · 현재 모델 미지원</option>}
      </select>}</Field>:<p className="helper-text">클립 생성 길이 · {appliedDuration?`${appliedDuration}초`:'AI 자동 판단'}</p>}
      {appliedDuration!==0&&!selected.durations.includes(appliedDuration)&&<p role="alert">현재 모델이 지원하는 클립 길이를 다시 선택해 주세요.</p>}
    </>}
    {selected&&<VideoReferenceSupport support={selected.reference_support}/>}
    {selected&&!selected.supports_audio&&<p className="helper-text">이 연결은 오디오 생성을 지원하지 않습니다. 기존 나레이션·음성 지시가 있는 계획은 음성 지원 모델을 사용해 주세요.</p>}
    {selected?.provider==="higgsfield"&&selected.durations?.length>0&&<VideoCostPreview key={selected.key+selected.revision+appliedDuration} initialSeconds={appliedDuration||undefined} modelKey={selected.key} revision={selected.revision} durations={selected.durations} modelLabel={videoModelName(selected)} supportsVideoReference={selected.reference_support?.video??false} rate={selected.usd_per_second} videoRate={selected.usd_per_second_with_video}/>}
    </section>
    {videoStyle!=="auto"&&<section className="video-model-guidance" aria-label="영상 스타일별 모델 안내" aria-live="polite">
      {videoStyle==="auto" ? <p className="helper-text">이번 영상은 기준 이미지의 화풍을 따릅니다. 기준 이미지가 없으면 대본·씬 구성으로 판단합니다.</p>
        : !styleName ? <p className="helper-text">영상 스타일을 먼저 선택하면 모델 활용 안내를 볼 수 있습니다.</p>
        : !value ? <p className="helper-text">{styleName}에 사용할 모델을 선택하면 공식 자료와 활용 안내를 보여드립니다.</p>
        : !data && !failed ? <p className="helper-text">모델 안내를 불러오는 중입니다.</p>
        : !guidance ? <p className="helper-text">{selectedLabel} · {styleName}: 공식 자료 기반 안내가 아직 확인되지 않았습니다. 스타일 적합성은 직접 확인해 주세요.</p>
        : <>
          <strong>{selectedLabel} · {styleName}</strong>
          <p><span className="video-guidance-label">활용 제안</span>{guidance.suggestion}</p>
          <p><span className="video-guidance-label">공식 확인</span>{guidance.confirmed}</p>
          <details><summary>주의점과 공식 자료</summary><div className="video-guidance-details">
            <p>{guidance.caution}</p>
            <p className="helper-text">스타일별 설명은 공식 특성을 바탕으로 한 활용 제안입니다. 모델 간 성능 순위나 화풍 유지 보장은 아니며, 동일 씬으로 직접 비교한 결과는 없습니다.</p>
            <div className="video-guidance-sources">{guidance.sources.map(source=><ExternalLink key={source.url} href={source.url}>{source.name}</ExternalLink>)}</div>
            <p className="helper-text">공식 자료 확인 · {guidance.checkedOn}</p>
          </div></details>
        </>}
    </section>}
  </div>;
}
