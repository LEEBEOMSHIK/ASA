"use client";
import { useEffect, useState } from "react";
import { api, type SchemaNode } from "../lib/registry";
import { Button, ExternalLink, Field, StatusBadge } from "./ui";
import { modelStyleGuidance } from "../lib/video-model-guidance";
import { videoStyles } from "../lib/video-prompt-settings";

type Catalog = {models: {key:string; label:string; provider:string; model:string; connection_state:string; generation_supported:boolean}[];
  enabled:boolean; key_configured:boolean; worker_online:boolean};
const checks:Record<string,string> = {authenticated:"Runway 계정 인증 확인", missing:"API 키 미설정",
  denied:"키 또는 계정 권한 확인 필요", unreachable:"Runway 응답 확인 불가"};

export function VideoModelInput({node,id,label,required,value,onChange,videoStyle=""}: {
  node:SchemaNode; id:string; label:string; required:boolean; value:string; onChange:(v:string)=>void; videoStyle?:string;
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
    if (!data.enabled) return "영상 생성 비활성";
    return data.worker_online ? "생성 가능" : "영상 처리 연결 대기";
  }
  async function verify() {
    setBusy(true);
    try {
      const current=await api<Catalog>("/video-planning/models");
      setData(current);setFailed(false);
      let result="이 모델의 연결 확인을 지원하지 않습니다.";
      if (supportsCheck(current,value)) {
        const model=current.models.find(m=>m.key===value);
        if (model?.provider==="alibaba") {
          result=model.connection_state==="configured"
            ? "서버 키·리전·작업 공간 설정 확인. 계정 인증·모델 권한·잔액은 실제 호출 전 별도 확인이 필요합니다."
            : "관리자가 WAN API 키와 Alibaba 작업 공간 ID를 설정해야 합니다.";
        } else {
        const code=model?.connection_state==="configured"
          ? (await api<{status:string}>("/video-planning/runway-connection","POST")).status
          : "missing";
        result=code==="missing" ? "관리자가 Runway API 키를 등록하면 계정 연결을 확인할 수 있습니다." : checks[code];
        }
      }
      setResults(old=>({...old,[value]:result}));
    } catch {setResults(old=>({...old,[value]:"연결 상태를 확인하지 못했습니다. 다시 시도해 주세요."}));} finally {setBusy(false);}
  }
  const selectedLabel=data?.models.find(m=>m.key===value)?.label ?? value;
  const selected=data?.models.find(m=>m.key===value);
  const styleName=videoStyles.find(s=>s.id===videoStyle)?.name;
  const guidance=selected ? modelStyleGuidance(selected.provider,selected.model,videoStyle) : null;
  const tone = failed ? "danger" : !data ? "neutral" :
    supportsCheck(data,value) && selected?.connection_state==="configured" && data.enabled && data.worker_online ? "success" : "warning";
  const actionLabel=selectedLabel+(selected?.provider==="alibaba" ? " 설정 확인" : " 연결 확인")+(busy?" 중":"");
  return <div className="field video-model-input"><Field id={id} label={label} required={required} hint="클립 길이와 영상 생성에 사용할 모델입니다. 연결 전에도 프롬프트를 계획할 수 있어요.">{p=>
    <div className="video-model-row"><div className="video-model-control"><select {...p} required={required} disabled={busy} value={value} onChange={e=>onChange(e.target.value)}>
      <option value="">모델 선택</option>{node.enum?.map(v=><option key={String(v)} value={String(v)}>
        {data?.models.find(m=>m.key===v)?.label ?? String(v)} · {status(String(v))}</option>)}</select>
      <span className="video-model-face" aria-hidden="true">
        <span className="video-model-name">{value ? selectedLabel : "모델 선택"}</span>
        {value && <StatusBadge tone={tone}>{status(value)}</StatusBadge>}
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="m4 6 4 4 4-4" stroke="currentColor" strokeWidth="1.5"/></svg>
      </span></div>
      {value && (supportsCheck(data,value) || failed) && <Button className="video-model-check" variant="secondary" disabled={busy} title={actionLabel} aria-label={actionLabel} onClick={verify}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M8 3v5m8-5v5M6 8h12v3a6 6 0 0 1-12 0V8Zm6 9v4"/>
        </svg>
      </Button>}</div>}</Field>
    {(busy || (value && results[value])) && <span role="status" className="helper-text">{busy ? actionLabel+"…" : selectedLabel+" · "+results[value]}</span>}
    {value&&data&&!data.enabled&&<p className="helper-text">영상 생성이 중지되어 있습니다. 관리자에게 문의해 주세요. 프롬프트 작성은 가능합니다.</p>}
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
