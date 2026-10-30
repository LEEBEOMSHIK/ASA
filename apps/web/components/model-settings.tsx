"use client";
import { useEffect, useRef, useState } from "react";
import { ModelCombobox } from "./model-combobox";
import { sortModels, type ModelOption } from "../lib/model-options";
import { api, ApiError, message } from "../lib/registry";
import { Button, Field, SelectCombobox, SettingsSection, StatusBadge } from "./ui";
import { useDirtyGuard } from "./registry-shell";

import { priceStatus, validPrice, type Price } from "../lib/model-pricing";
import { ModelPriceEditor } from "./model-price-editor";
type Metadata = {checked_at:string;sources:string[];web_search_supported:boolean|null;compatible:boolean|null;price:Price|null;note:string;status:string};
type Model = {provider:"openai"|"anthropic";id:string;label:string;enabled:boolean;web_search:boolean;price:Price|null;metadata?:Metadata|null};
type Catalog = {revision:number;models:Model[];default:string;providers?:{id:string;configured:boolean}[]};
export function ModelSettings() {
  const [activeModel,setActiveModel]=useState<number|null>(null); const [modelQuery,setModelQuery]=useState("");
  const [data,setData]=useState<Catalog|null>(null);
  const [error,setError]=useState(""); const [notice,setNotice]=useState("");
  const [busy,setBusy]=useState(false); const [dirty,setDirty]=useState(false);
  const [picker,setPicker]=useState(false); const [provider,setProvider]=useState<Model["provider"]>("openai");
  const [choices,setChoices]=useState<ModelOption[]>([]); const [selected,setSelected]=useState(""); const [lookup,setLookup]=useState(false);
  const [loadingModels,setLoadingModels]=useState(false); const [listError,setListError]=useState(""); const [retry,setRetry]=useState(0);
  const modelCache=useRef<Partial<Record<Model["provider"],Promise<ModelOption[]>>>>({});
  useEffect(()=>{
    if(!picker)return;
    let cancelled=false;setSelected("");setChoices([]);setListError("");setLoadingModels(true);
    if(!modelCache.current[provider])modelCache.current[provider]=api<{models:ModelOption[]}>(`/admin/models/discover/${provider}`).then(result=>sortModels(result.models)).catch(e=>{delete modelCache.current[provider];throw e;});
    void modelCache.current[provider]!.then(models=>{if(!cancelled){setChoices(models);if(!models.length)setListError("공급자가 반환한 모델이 없습니다.");}}).catch(e=>{if(!cancelled)setListError(message(e));}).finally(()=>{if(!cancelled)setLoadingModels(false);});
    return()=>{cancelled=true;};
  },[picker,provider,retry]);
  async function importModel(id:string, index?:number){
    if(!data)return;
    setLookup(true);setError("");setNotice("");
    try{
      const p=index===undefined?provider:data.models[index].provider;
      const meta=await api<Metadata>(`/admin/models/metadata/${p}?model=${encodeURIComponent(id)}`);
      if(meta.compatible===false){setError("이 모델은 현재 ASA의 텍스트·구조화 응답 실행 방식과 호환되지 않습니다.");return;}
      if(index===undefined){
        if(data.models.some(m=>m.provider===p&&m.id===id)){setError("이미 등록한 모델입니다.");return;}
        const entry:Model={provider:p,id,label:choices.find(m=>m.id===id)?.label||id,enabled:true,web_search:meta.web_search_supported===true,price:meta.price,metadata:meta};
        const saved=await api<Catalog>("/admin/models","POST",{revision:data.revision,model:entry});
        // Only the new model is persisted. Keep unrelated edits in this tab as drafts.
        const registered=saved.models.find(m=>m.provider===p&&m.id===id)!;
        setData({...data,revision:saved.revision,models:[...data.models,registered]});
        setPicker(false);setActiveModel(data.models.length);setModelQuery("");
        setNotice(dirty?"모델을 등록하고 저장했습니다. 기존 모델의 편집 내용은 아직 저장 전입니다.":"모델을 등록하고 저장했습니다. 다시 접속해도 목록에 유지됩니다.");
      }else{
        update(index,{metadata:meta,price:meta.price,web_search:meta.web_search_supported===false?false:data.models[index].web_search});
        setNotice("공식 정보를 반영했습니다. 편집 내용을 저장하면 적용됩니다.");
      }
    }catch(e){setError(message(e));}finally{setLookup(false);}
  }
  const guard=useDirtyGuard();
  useEffect(()=>{guard(dirty);return()=>guard(false);},[dirty,guard]);
  useEffect(()=>{void api<Catalog>("/admin/models").then(setData).catch(e=>setError(message(e)));},[]);
  function edit(next:Catalog){setData(next);setDirty(true);setNotice("");setError("");}
  function update(index:number,patch:Partial<Model>){if(!data)return;const models=data.models.map((m,i)=>i===index?{...m,...patch}:m);edit({...data,models,default:models.some(m=>m.enabled&&`${m.provider}:${m.id}`===data.default)?data.default:""});}
  async function save(){if(!data)return;const invalid=data.models.findIndex(m=>!m.label.trim()||!m.id.trim()||(m.price&&!validPrice(m.price)));if(invalid>=0){setActiveModel(invalid);setError(`${data.models[invalid].label||"선택한 모델"}: 이름·모델 ID와 요율을 확인하세요. 요율을 사용하려면 입력·출력 금액을 모두 0 이상의 숫자로 입력해야 합니다.`);return;}setBusy(true);setError("");try{const saved=await api<Catalog>("/admin/models","PUT",{revision:data.revision,models:data.models,default:data.default});setData({...saved,providers:data.providers});setDirty(false);setNotice("모델 설정을 저장했습니다. 새 요청부터 적용됩니다.");}catch(e){setError(e instanceof ApiError && e.issues.length ? e.issues.map(i=>i.message).join(" / ") : message(e));}finally{setBusy(false);}}
  return <div className="model-settings">
    <div className="page-heading"><div><p className="eyebrow">ADMINISTRATION</p><h1>AI 모델 관리</h1><p className="muted">사용 가능한 모델을 정하세요. 각 에이전트와 AI 요청 블록에서 이 목록 중 하나를 선택합니다.</p></div><StatusBadge tone={dirty?"warning":"neutral"}>{dirty?"저장 전 변경 있음":"변경 없음"}</StatusBadge></div>
    {lookup&&<p role="status">공급자의 공식 정보를 확인하는 중입니다…</p>}{error&&<p role="alert" className="field-error">{error}</p>}{notice&&<p role="status">{notice}</p>}
    {!data&&!error&&<p role="status">모델 설정을 불러오는 중입니다…</p>}
    {data&&<form noValidate onSubmit={e=>{e.preventDefault();void save();}}><fieldset disabled={busy||lookup} className="editor-fieldset settings-stack">
      <SettingsSection title="API 키 설정 상태" description="서버의 키 설정 여부입니다. 모델 목록 조회 시 공급자 인증을 확인합니다.">
        <div className="model-connections">{data.providers?.map(p=><div className="model-provider" key={p.id}><span className={`provider-logo provider-${p.id}`} aria-hidden="true"/><strong>{p.id==="openai"?"OpenAI":"Claude"}</strong><StatusBadge tone={p.configured?"success":"warning"}>{p.configured?"키 설정됨":"키 설정 필요"}</StatusBadge></div>)}</div>
      </SettingsSection>
      <SettingsSection title="기본 모델" description="모델을 따로 지정하지 않은 작업에만 적용됩니다.">
        <div className="model-default"><Field id="default-model" label="작업 공간 기본 모델" hint={data.models.length?"특정 모델을 선택한 에이전트와 블록의 설정은 바뀌지 않습니다.":"아래에서 모델을 가져온 후 기본 모델을 선택하세요."}>{p=><select {...p} disabled={!data.models.some(m=>m.enabled)} value={data.default} onChange={e=>edit({...data,default:e.target.value})}><option value="">기본 모델 미지정</option>{data.models.filter(m=>m.enabled&&m.id).map((m,i)=><option key={i} value={`${m.provider}:${m.id}`}>{m.provider==="openai"?"OpenAI":"Claude"} · {m.label||m.id}</option>)}</select>}</Field></div>
      </SettingsSection>
      <section className="settings-stack" aria-labelledby="available-models-title">
        <div className="settings-heading"><div><h2 id="available-models-title">사용 가능한 모델 <span className="muted">{data.models.length}</span></h2><p className="muted">사용을 허용한 모델만 에이전트와 블록에서 선택할 수 있습니다.</p></div><Button variant="secondary" onClick={()=>setPicker(!picker)}>{picker?"등록창 닫기":"+ 새 모델"}</Button></div>
        {picker&&<SettingsSection title="새 모델 등록" description="공급자를 선택하면 사용할 수 있는 모델을 자동으로 보여드립니다.">
          <SelectCombobox label="공급자" searchable={false} options={[{id:"openai",label:"OpenAI"},{id:"anthropic",label:"Claude"}]} value={provider} onChange={id=>setProvider(id as Model["provider"])}/>
          {listError?<div role="alert"><p className="field-error">{listError}</p><Button variant="secondary" onClick={()=>{delete modelCache.current[provider];setRetry(n=>n+1);}}>다시 확인</Button></div>:<ModelCombobox key={provider} options={choices} value={selected} onChange={setSelected} loading={loadingModels}/>}
          <div className="model-picker-footer"><span className="muted">등록 시 공식 정보를 확인하고 바로 저장합니다.</span><Button disabled={!selected||loadingModels} onClick={()=>void importModel(selected)}>{lookup?"등록 중…":"선택한 모델 등록"}</Button></div>
        </SettingsSection>}
        {!data.models.length&&!picker&&<div className="card model-empty"><strong>아직 등록한 모델이 없습니다</strong><p className="muted">새 모델을 눌러 공급자의 목록에서 선택하고 등록하세요.</p></div>}
        {data.models.length>0&&<><Field id="registered-model-search" label="등록된 모델 검색">{p=><input {...p} placeholder="모델명 또는 공급자로 검색" value={modelQuery} onChange={e=>setModelQuery(e.target.value)}/>}</Field>
        <div className="registered-models" aria-label="등록된 모델 목록">{data.models.map((m,i)=>({m,i})).filter(({m})=>`${m.label} ${m.id} ${m.provider} ${m.provider==='anthropic'?'Claude':''}`.toLowerCase().includes(modelQuery.toLowerCase())).map(({m,i})=><button type="button" className="registered-model-row" key={i} aria-expanded={activeModel===i} aria-controls="selected-model-detail" onClick={()=>setActiveModel(activeModel===i?null:i)}><span className={`provider-logo provider-${m.provider}`} aria-hidden="true"/><span className="registered-model-copy"><strong>{m.label||m.id}</strong><small>{m.provider==='openai'?'OpenAI':'Claude'} · {m.id}</small></span><span className="registered-model-status">{data.default===`${m.provider}:${m.id}`&&<StatusBadge>기본</StatusBadge>}<StatusBadge tone={m.enabled?'success':'neutral'}>{m.enabled?'사용 중':'사용 안 함'}</StatusBadge><StatusBadge tone={priceStatus(m.price)==='확인 필요'?'warning':'neutral'}>{priceStatus(m.price)}</StatusBadge></span><span>{activeModel===i?'닫기':'설정'}</span></button>)}{!data.models.some(m=>`${m.label} ${m.id} ${m.provider} ${m.provider==='anthropic'?'Claude':''}`.toLowerCase().includes(modelQuery.toLowerCase()))&&<p role="status">검색 결과가 없습니다.</p>}</div></>}
        <div id="selected-model-detail" className="model-list">{data.models.map((m,i)=>({m,i})).filter(({i})=>i===activeModel).map(({m,i})=><SettingsSection key={i} title={m.label||"새 모델"} action={<div className="model-detail-actions"><label className="settings-check"><input type="checkbox" checked={m.enabled} onChange={e=>update(i,{enabled:e.target.checked})}/> 사용 허용</label><Button variant="secondary" onClick={()=>setActiveModel(null)}>상세 닫기</Button></div>}>
          <div className="settings-fields model-fields"><Field id={`provider-${i}`} label="공급자">{p=><select {...p} disabled={!!m.metadata} value={m.provider} onChange={e=>update(i,{provider:e.target.value as Model["provider"]})}><option value="openai">OpenAI</option><option value="anthropic">Claude</option></select>}</Field>
            <Field id={`model-id-${i}`} label="모델 ID" hint={m.metadata?"공급자 목록에서 가져온 모델 ID입니다.":"공급자의 API 모델 ID를 정확히 입력하세요."}>{p=><input {...p} readOnly={!!m.metadata} required maxLength={200} value={m.id} onChange={e=>update(i,{id:e.target.value})}/>}</Field>
            <Field id={`model-label-${i}`} label="표시 이름">{p=><input {...p} required maxLength={100} value={m.label} onChange={e=>update(i,{label:e.target.value})}/>}</Field></div>
          <div className="model-official-info"><div className="model-information-toolbar"><StatusBadge tone={m.metadata?.web_search_supported===true?"success":"neutral"}>웹 검색 {m.metadata?.web_search_supported===true?"지원":m.metadata?.web_search_supported===false?"미지원":"확인 필요"}</StatusBadge><StatusBadge tone={priceStatus(m.price)==="확인 필요"?"warning":"success"}>{priceStatus(m.price)}</StatusBadge>{m.metadata?.status&&<StatusBadge>{m.metadata.status}</StatusBadge>}<Button variant="secondary" disabled={!m.id} onClick={()=>void importModel(m.id,i)}>공식 정보 갱신</Button></div>
          {m.metadata&&<><p className="muted">{m.price&&m.price.label!=="공식 문서 표준 요율"?"직접 설정한 단일 요율을 사용합니다. 공식 요율로 복원하면 아래 출처의 자동 요율을 다시 적용합니다.":m.metadata.note}</p><p className="muted">최근 확인: {new Date(m.metadata.checked_at).toLocaleString("ko-KR")} · {m.metadata.sources.filter(url=>/^https:\/\/(developers.openai.com|platform.claude.com)\//.test(url)).map((url,n)=><a key={url} href={url} target="_blank" rel="noreferrer">공식 출처 {n+1} </a>)}</p></>}
          </div>
          <label className="settings-check"><input type="checkbox" disabled={m.metadata?.web_search_supported===false} checked={m.web_search} onChange={e=>update(i,{web_search:e.target.checked})}/> 웹 검색 허용</label>
          <ModelPriceEditor price={m.price} officialPrice={m.metadata?.price??null} onChange={price=>update(i,{price})}/>
        </SettingsSection>)}</div>
      </section>
      {dirty&&<div className="settings-actions"><span className="muted">{dirty?"변경 내용을 저장하면 새 요청부터 적용됩니다.":"모델 선택은 각 에이전트와 AI 요청 블록에서 설정하세요."}</span><div><Button variant="secondary" disabled={!dirty||busy} onClick={()=>{setBusy(true);void api<Catalog>("/admin/models").then(saved=>{setData(saved);setDirty(false);setError("");setNotice("저장된 설정으로 되돌렸습니다.");}).catch(e=>setError(message(e))).finally(()=>setBusy(false));}}>편집 취소</Button><Button type="submit" disabled={!dirty||busy}>{busy?"저장 중…":"편집 내용 저장"}</Button></div></div>}
    </fieldset></form>}
  </div>;
}
