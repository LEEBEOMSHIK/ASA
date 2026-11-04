"use client";
import { useEffect, useState } from "react";
import { api, type SchemaNode } from "../lib/registry";
import { Button, Field, StatusBadge } from "./ui";

type Catalog = {models: {key:string; label:string; provider:string; model:string}[];
  enabled:boolean; key_configured:boolean; worker_online:boolean};
const checks:Record<string,string> = {authenticated:"Runway 계정 인증 확인", missing:"API 키 미설정",
  denied:"키 또는 계정 권한 확인 필요", unreachable:"Runway 응답 확인 불가"};

export function VideoModelInput({node,id,label,required,value,onChange}: {
  node:SchemaNode; id:string; label:string; required:boolean; value:string; onChange:(v:string)=>void;
}) {
  const [data,setData] = useState<Catalog|null>(null);
  const [results,setResults] = useState<Record<string,string>>({});
  const [busy,setBusy] = useState(false);
  const [failed,setFailed] = useState(false);
  useEffect(()=>{let live=true;
    api<Catalog>("/video-planning/models").then(v=>{if(live)setData(v);})
      .catch(()=>{if(live)setFailed(true);});
    return ()=>{live=false;};
  },[]);
  function supportsCheck(catalog: Catalog | null, key: string) {
    return catalog?.models.some(m=>m.key===key && m.provider==="runway" && m.model==="gen4.5");
  }
  function status(key:string) {
    if (failed) return "상태 조회 실패";
    if (!data) return "상태 조회 중";
    if (!supportsCheck(data,key)) return "생성 연결 없음";
    if (!data.key_configured) return "API 키 미설정";
    if (!data.enabled) return "영상 생성 꺼짐";
    return data.worker_online ? "생성 설정 준비됨" : "워커 연결 대기";
  }
  async function verify() {
    setBusy(true);
    try {
      const current=await api<Catalog>("/video-planning/models");
      setData(current);setFailed(false);
      let result="이 모델의 연결 확인을 지원하지 않습니다.";
      if (supportsCheck(current,value)) {
        const code=current.key_configured
          ? (await api<{status:string}>("/video-planning/runway-connection","POST")).status
          : "missing";
        result=code==="missing" ? "관리자가 Runway API 키를 등록하면 계정 연결을 확인할 수 있습니다." : checks[code];
      }
      setResults(old=>({...old,[value]:result}));
    } catch {setResults(old=>({...old,[value]:"연결 상태를 확인하지 못했습니다. 다시 시도해 주세요."}));} finally {setBusy(false);}
  }
  const selectedLabel=data?.models.find(m=>m.key===value)?.label ?? value;
  const tone = failed ? "danger" : !data ? "neutral" :
    supportsCheck(data,value) && data.key_configured && data.enabled && data.worker_online ? "success" : "warning";
  const actionLabel=selectedLabel+(busy?" 연결 확인 중":" 연결 확인");
  return <div className="field"><Field id={id} label={label} hint="클립 길이와 영상 생성에 사용할 모델입니다. 연결 전에도 프롬프트를 계획할 수 있어요.">{p=>
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
  </div>;
}
