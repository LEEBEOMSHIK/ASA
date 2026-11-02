"use client";
import { useEffect, useId, useState, type ReactNode } from "react";
import { api, message, type SchemaNode } from "../lib/registry";
import { Button, Field, SelectCombobox, StatusBadge } from "./ui";
import { Modal } from "./character-library";
import "./previous-answer-input.css";

type Item = {id:string;name:string;title:string;request_preview:string;version:number;is_test:boolean;created_at:string;source_kind:"agent"|"automation";step_index:number|null;automation_name:string|null;step_label:string|null};
const itemKey=(item:Item)=>`${item.source_kind}:${item.id}:${item.step_index??""}`;
const sourceLabel=(item:Item)=>item.source_kind==="automation"?`자동화 · ${item.automation_name} · ${item.step_label}`:item.name;
type Answer = {version:number;answer:unknown;source:string;created_at:string};
type Detail = {name:string;schema:SchemaNode;versions:Answer[]};
const text = (v:unknown) => typeof v === "string" ? v : JSON.stringify(v,null,2) ?? "";

export function PreviousAnswerInput({label,value,maxLength,onChange,agentId,children}:{children:(trigger:ReactNode,receipt:ReactNode)=>ReactNode;agentId?:string;label:string;value:string;maxLength:number;onChange:(v:string)=>void}) {
  const [open,setOpen]=useState(false);
  const [receipt,setReceipt]=useState<{label:string;text:string}|null>(null);
  const trigger=<span className="previous-answer-trigger"><Button variant="secondary" className="previous-answer-icon" aria-label={`${label} · 이전 작업에서 가져오기`} onClick={()=>setOpen(true)}><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M8 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-3M11 6v7h7M21 3l-10 10"/></svg></Button><span className="previous-answer-tooltip" aria-hidden="true">이전 작업에서 가져오기</span></span>;
  return <>
    {children(trigger,receipt&&<span className="previous-answer-receipt helper-text">{receipt.label}{receipt.text===value?" · 가져온 내용":" · 가져온 뒤 직접 수정함"}</span>)}
    {open&&<AnswerPicker agentId={agentId} label={label} replacing={!!value} maxLength={maxLength} onClose={()=>setOpen(false)} onApply={(v,source)=>{onChange(v);setReceipt({label:source,text:v});setOpen(false);}}/>}
  </>;
}

function AnswerPicker({label,replacing,maxLength,onClose,onApply,agentId}:{agentId?:string;label:string;replacing:boolean;maxLength:number;onClose:()=>void;onApply:(v:string,source:string)=>void}) {
  const id=useId();const [q,setQ]=useState("");const [offset,setOffset]=useState(0);
  const [items,setItems]=useState<Item[]>([]);const [more,setMore]=useState(false);
  const [loading,setLoading]=useState(true);const [error,setError]=useState("");
  const [chosen,setChosen]=useState<Item|null>(null);const [detail,setDetail]=useState<Detail|null>(null);
  const [version,setVersion]=useState("");const [field,setField]=useState("");const [retry,setRetry]=useState(0);
  useEffect(()=>{let alive=true;setLoading(true);setError("");const timer=setTimeout(()=>{
    api<{items:Item[];has_more:boolean}>(`/work-requests/answer-sources?${new URLSearchParams({q,offset:String(offset),...(agentId?{agent_id:agentId}:{})})}`).then(d=>{if(alive){setItems(d.items);setMore(d.has_more);}}).catch(e=>{if(alive)setError(message(e));}).finally(()=>{if(alive)setLoading(false);});
  },200);return()=>{alive=false;clearTimeout(timer);};},[q,offset,retry,agentId]);
  useEffect(()=>{if(!chosen)return;let alive=true;setDetail(null);setError("");setField("");
    api<Detail>(`/work-requests/answer-sources/${chosen.id}?${new URLSearchParams({source_kind:chosen.source_kind,...(chosen.step_index!==null?{step_index:String(chosen.step_index)}:{})})}`).then(d=>{if(alive){setDetail(d);setVersion(String(d.versions[0]?.version??""));}}).catch(e=>{if(alive)setError(message(e));});return()=>{alive=false;};
  },[chosen,retry]);
  const answer=detail?.versions.find(v=>String(v.version)===version);
  const fields=answer&&typeof answer.answer==="object"&&answer.answer!==null&&!Array.isArray(answer.answer)?Object.entries(answer.answer).filter(([,v])=>typeof v==="string"):[];
  const selected=answer ? text(field?(answer.answer as Record<string,unknown>)[field]:answer.answer):"";
  const tooLong=selected.length>maxLength;
  return <Modal title={`${label} · 이전 작업에서 가져오기`} onClose={onClose} footer={<>
    <Button variant="secondary" onClick={onClose}>취소</Button>
    <Button disabled={!answer||!selected.trim()||tooLong} onClick={()=>onApply(selected,`${chosen!.title} · ${sourceLabel(chosen!)} · 답변 v${version}${field?` · ${detail?.schema.properties?.[field]?.description||field}`:""}`)}>{replacing?"현재 입력을 이 내용으로 바꾸기":"이 내용 가져오기"}</Button>
  </>}><div className="answer-picker">
    <p className="muted">개별 실행과 자동화 단계에서 완료된 답변을 가져옵니다. 원본은 바뀌지 않으며, 가져온 뒤 직접 수정할 수 있습니다.</p>
    <Field id={id} label="작업 검색" hint="작업 제목이나 요청·답변 내용으로 검색하세요.">{p=><input {...p} type="search" value={q} maxLength={200} onChange={e=>{setQ(e.target.value);setOffset(0);}}/>}</Field>
    {error&&<div role="alert"><p>{error}</p><Button variant="secondary" onClick={()=>setRetry(v=>v+1)}>다시 불러오기</Button></div>}
    <div className="answer-picker-columns"><div className="answer-picker-list" aria-label="이전 작업 목록">
      {loading?<p role="status">작업을 불러오는 중…</p>:!items.length?<p>가져올 답변이 없습니다. 검색어를 바꾸거나 연결된 에이전트의 작업을 완료해 주세요.</p>:items.map(item=><button type="button" key={itemKey(item)} className="answer-source-card" aria-pressed={!!chosen&&itemKey(chosen)===itemKey(item)} onClick={()=>setChosen(item)}><strong>{item.title}</strong>{item.request_preview&&<span className="answer-source-summary">{item.request_preview}</span>}<span>{new Date(item.created_at).toLocaleString("ko-KR")} · 답변 v{item.version}</span><span className="answer-source-origin">{sourceLabel(item)}</span>{item.is_test&&<StatusBadge>테스트 요청</StatusBadge>}</button>)}
      {(offset>0||more)&&<div className="actions"><Button variant="secondary" disabled={loading||!offset} onClick={()=>setOffset(v=>v-20)}>이전</Button><span>{offset/20+1} 페이지</span><Button variant="secondary" disabled={loading||!more} onClick={()=>setOffset(v=>v+20)}>다음</Button></div>}
    </div><div className="answer-picker-preview">
      {!chosen?<p>작업을 선택하면 가져올 답변을 확인할 수 있습니다.</p>:!detail?<p role="status">답변을 불러오는 중…</p>:<>
        <h3>{chosen.title}</h3>
        <SelectCombobox label="답변 버전" searchable={false} value={version} onChange={v=>{setVersion(v);setField("");}} options={detail.versions.map(v=>({id:String(v.version),label:`v${v.version} · ${v.source==="ai"?"AI 작성":"직접 수정"} · ${new Date(v.created_at).toLocaleString("ko-KR")}`}))}/>
        {!!fields.length&&<SelectCombobox label="가져올 내용" searchable={false} value={field} onChange={setField} options={[{id:"",label:"답변 전체"},...fields.map(([key])=>({id:key,label:detail.schema.properties?.[key]?.description||key}))]}/>}
        <div className="answer-source-text" aria-label="가져올 내용 미리보기">{selected}</div>
        <p className={tooLong?"field-error":"helper-text"} role={tooLong?"alert":undefined}>{selected.length.toLocaleString()}자{tooLong?` · 입력 한도 ${maxLength.toLocaleString()}자를 초과합니다. 더 짧은 답변 항목을 선택하세요. 자동으로 자르지 않습니다.`:" · 선택한 내용을 그대로 가져옵니다."}</p>
      </>}
    </div></div>
  </div></Modal>;
}
