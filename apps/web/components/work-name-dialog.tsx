"use client";
import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api, type WorkItem } from "../lib/registry";
import { Button, Field } from "./ui";

export function WorkNameDialog({item,onClose,onSaved}:{item:WorkItem;onClose:()=>void;onSaved:(item:WorkItem)=>void}) {
  const dialog=useRef<HTMLDialogElement>(null), id=useId();
  const [mounted,setMounted]=useState(false);
  const [name,setName]=useState(item.custom_name??item.display_title??item.name);
  const [revision,setRevision]=useState(item.name_revision??0);
  const [busy,setBusy]=useState(false),[error,setError]=useState("");
  useEffect(()=>{setMounted(true);},[]);
  useEffect(()=>{if(mounted)dialog.current?.showModal();},[mounted]);
  async function save(reset=false){
    if(busy)return;
    setBusy(true);setError("");
    try {
      const saved=await api<WorkItem>(`/work-requests/${item.id}/name`,"PUT",{name:reset?null:name.trim(),revision});
      onSaved(saved);dialog.current?.close();
    } catch {setError("저장하지 못했습니다. 다른 기기에서 이름이 변경됐거나 연결에 문제가 있을 수 있습니다. 최신 이름을 불러온 뒤 다시 시도해 주세요.");}
    finally {setBusy(false);}
  }
  async function reload(){
    setBusy(true);setError("");
    try {const latest=await api<WorkItem>(`/work-requests/${item.id}`);setName(latest.custom_name??latest.display_title??item.name);setRevision(latest.name_revision??0);}
    catch {setError("최신 이름을 불러오지 못했습니다. 연결 상태를 확인해 주세요.");}
    finally {setBusy(false);}
  }
  if(!mounted)return null;
  return createPortal(<dialog ref={dialog} className="work-name-dialog" aria-labelledby={`${id}-title`}
    onCancel={event=>{if(busy)event.preventDefault();}} onClose={onClose}>
    <form onSubmit={event=>{event.preventDefault();void save();}}>
      <div className="work-name-heading"><h2 id={`${id}-title`}>작업 이름 수정</h2><Button variant="secondary" disabled={busy} onClick={()=>dialog.current?.close()}>닫기</Button></div>
      <p className="muted">내 작업 목록에 표시할 이름입니다. 원본 입력과 답변은 바뀌지 않으며 같은 계정의 다른 기기에도 적용됩니다.</p>
      <Field id={`${id}-name`} label="작업 이름" hint="최대 120자 · 자동 이름으로 되돌릴 수 있습니다.">{props=><input {...props} autoFocus maxLength={120} value={name} disabled={busy} onChange={event=>setName(event.target.value)}/>}</Field>
      {error&&<div className="work-name-error" role="alert"><p>{error}</p><Button variant="secondary" disabled={busy} onClick={()=>void reload()}>최신 이름 불러오기</Button></div>}
      <div className="work-name-actions"><Button variant="secondary" disabled={busy} onClick={()=>void save(true)}>자동 이름으로 되돌리기</Button><Button type="submit" disabled={busy||!name.trim()}>{busy?"저장 중…":"저장"}</Button></div>
    </form>
  </dialog>,document.body);
}
