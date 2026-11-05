"use client";
import { useEffect, useState } from "react";
import { api, message } from "../lib/registry";
import { Button, Card, Field } from "./ui";
import { Modal } from "./character-library";
import { workStatus } from "./work-history";

type Counts = {requests:number; answers:number; images:number; videos:number; delete_assets:boolean};
type Entry = {request_id:string; name:string; status:string; created_at:string; actor:string;
  deleted_at:string; summary:Counts; videos:{id:string;label:string}[]};
type Preview = {name:string; summary:Counts; blockers:string[]; references:string[]; token:string};
const base = "/admin/work-history";

function Scope({counts}:{counts:Counts}) {
  return <dl className="deletion-scope">
    <dt>영구 삭제</dt><dd>요청 {counts.requests}건 · 답변 {counts.answers}개</dd>
    <dt>{counts.delete_assets?"함께 삭제":"보존"}</dt>
    <dd>이미지 {counts.images}장 · 영상 {counts.videos}개</dd>
  </dl>;
}

function ConfirmDeletion({entry,close,done}:{entry:Entry;close:()=>void;done:()=>void}) {
  const [assets,setAssets]=useState(false),[plan,setPlan]=useState<Preview|null>(null);
  const [error,setError]=useState(""),[busy,setBusy]=useState(false),[reload,setReload]=useState(0);
  useEffect(()=>{
    let live=true;
    api<Preview>(base+"/"+entry.request_id+"/preview?delete_assets="+assets)
      .then(p=>{if(live)setPlan(p);}).catch(e=>{if(live)setError(message(e));});
    return ()=>{live=false;};
  },[entry.request_id,assets,reload]);
  async function remove(){
    if(!plan||busy||plan.blockers.length)return;
    setBusy(true);
    try {
      await api(base+"/"+entry.request_id+"/delete","POST",{delete_assets:assets,token:plan.token});
      done();
    } catch(e){setPlan(null);setError(message(e));} finally {setBusy(false);}
  }
  return <Modal title="영구 삭제 범위 확인" onClose={()=>{if(!busy)close();}} footer={<>
    <Button variant="secondary" disabled={busy} onClick={close}>취소</Button>
    <Button disabled={busy||!plan||!!plan.blockers.length} onClick={remove}>영구 삭제</Button>
  </>}>
    <div className="work-management"><h3>{entry.name}</h3><p>{new Date(entry.created_at).toLocaleString("ko-KR")}에 접수된 작업입니다.</p>
      <label className="checkbox"><input type="checkbox" checked={assets} disabled={busy}
        onChange={e=>{setPlan(null);setError("");setAssets(e.target.checked);}}/>이 작업에서 생성한 이미지와 영상도 삭제</label>
      {error&&<p role="alert">{error} <Button variant="secondary" onClick={()=>{setError("");setReload(n=>n+1);}}>다시 확인</Button></p>}
      {plan?<><Scope counts={plan.summary}/>{plan.references.length>0&&<details><summary>다른 작업에서 참조하는 결과물 · {plan.references.length}건</summary><ul>{plan.references.map((label,i)=><li key={i}>{label}</li>)}</ul></details>}{plan.blockers.map(s=><p className="notice" role="alert" key={s}>{s}</p>)}</>:!error&&<p role="status">삭제 범위 확인 중…</p>}
      <p className="muted">영구 삭제한 내용은 복원할 수 없습니다. 사용량·비용과 삭제 기록은 보존됩니다.</p>
    </div>
  </Modal>;
}

export function WorkManagement(){
  const [deleted,setDeleted]=useState(false),[q,setQ]=useState(""),[offset,setOffset]=useState(0);
  const [rows,setRows]=useState<Entry[]>([]),[more,setMore]=useState(false),[busy,setBusy]=useState(true);
  const [error,setError]=useState(""),[notice,setNotice]=useState(""),[revision,setRevision]=useState(0);
  const [target,setTarget]=useState<Entry|null>(null);
  useEffect(()=>{
    let live=true;setBusy(true);setError("");
    const timer=setTimeout(()=>{api<{items:Entry[];has_more:boolean}>(base+"?"+new URLSearchParams({q,deleted:String(deleted),offset:String(offset)}))
      .then(r=>{if(live){setRows(r.items);setMore(r.has_more);}}).catch(e=>{if(live)setError(message(e));}).finally(()=>{if(live)setBusy(false);});},150);
    return ()=>{live=false;clearTimeout(timer);};
  },[q,offset,deleted,revision]);
  return <section className="work-management"><h1>작업 관리</h1>
    <div className="button-row">{[false,true].map(v=><Button key={String(v)} variant={deleted===v?"primary":"secondary"} aria-pressed={deleted===v} onClick={()=>{if(v!==deleted){setBusy(true);setRows([]);setDeleted(v);setOffset(0);}}}>{v?"삭제 기록":"작업 목록"}</Button>)}</div>
    <Field id="work-management-search" label="에이전트 이름으로 검색">{p=><input {...p} value={q} maxLength={200} onChange={e=>{setQ(e.target.value);setOffset(0);}}/>}</Field>
    {notice&&<p role="status">{notice}</p>}
    {busy?<p role="status">불러오는 중…</p>:error?<p role="alert">{error}</p>:<>
      {!rows.length&&<p>표시할 작업이 없습니다.</p>}
      {rows.map(r=><Card key={r.request_id}><div className="card-heading"><strong>{r.name}</strong>
        {!deleted&&<Button variant="secondary" onClick={()=>setTarget(r)}>삭제 범위 확인</Button>}</div>
        {deleted?<><p>삭제한 사람 · {r.actor} · {new Date(r.deleted_at).toLocaleString("ko-KR")}</p>
          <Scope counts={r.summary}/>{r.videos.map(v=><a key={v.id} className="button button--secondary" href={"/api/v1/video-clips/asset/"+v.id+"/video"}>보존 영상 · {v.label}</a>)}</>:
          <p>{new Date(r.created_at).toLocaleString("ko-KR")} · {workStatus(r.status)} · <a href={"/?request="+r.request_id}>작업 열기</a></p>}
      </Card>)}
      {(more||offset>0)&&<div className="button-row"><Button variant="secondary" disabled={!offset} onClick={()=>setOffset(offset-20)}>이전</Button><Button variant="secondary" disabled={!more} onClick={()=>setOffset(offset+20)}>다음</Button></div>}
    </>}
    {target&&<ConfirmDeletion entry={target} close={()=>setTarget(null)} done={()=>{setBusy(true);setRows([]);setTarget(null);setQ("");setDeleted(true);setOffset(0);setNotice("작업을 삭제했습니다. 아래에서 처리 결과를 확인하세요.");setRevision(n=>n+1);}}/>}
  </section>;
}
