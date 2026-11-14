"use client";
import { useRef, useState, type ReactNode } from "react";
import { api, message } from "../lib/registry";
import { type WorkProgress } from "../lib/work-progress";
import { type AssetReview } from "./image-review-panel";
import { ReviewDashboard } from "./review-dashboard";
import { Button } from "./ui";
import { GraphIcon } from "./graph-icon";

type Job = {id:string;character_id:string;version:number;status:string};
type Candidate = {job:Job;name:string;expected:string|null;latest:number};
type Props = {renderPicker?:(candidates:Candidate[],selected:string[],toggle:(id:string)=>void,busy:boolean)=>ReactNode;controlledOpen?:boolean;onToggle?:()=>void;onComplete?:()=>void;characters:{id:string;name:string}[];jobs:Job[];approved:Record<string,string>;excluded:string[];progress:WorkProgress;reviews:AssetReview[];refresh:()=>Promise<void>};
export function ImageBatchApproval({characters,jobs,approved,excluded,progress,reviews,refresh,controlledOpen,onToggle,onComplete,renderPicker}:Props) {
  const [localOpen,setOpen]=useState(false),[candidates,setCandidates]=useState<Candidate[]>([]);
  const [selected,setSelected]=useState<string[]>([]),[busy,setBusy]=useState(false),[feedback,setFeedback]=useState("");
  const submitting=useRef(false);
  const open=controlledOpen ?? localOpen;
  const eligible=characters.flatMap(c=>{
    if(excluded.includes(c.id) || progress.items.find(i=>i.id===c.id)?.state!=="review")return [];
    const history=jobs.filter(j=>j.character_id===c.id).sort((a,b)=>b.version-a.version);
    if(history.some(j=>["queued","running","unknown"].includes(j.status)))return [];
    const job=history.find(j=>j.status==="succeeded");
    return job?[{job,name:c.name,expected:approved[c.id] || null,latest:history[0].version}]:[];
  });
  function toggle(){if(!open){setCandidates(eligible);setSelected([]);setFeedback("");}if(onToggle)onToggle();else setOpen(!open);}
  async function confirm(){
    if(submitting.current || !selected.length)return;
    submitting.current=true;setBusy(true);setFeedback("");
    const done:string[]=[],failures:string[]=[];
    for(const c of candidates.filter(c=>selected.includes(c.job.id))){
      try {await api(`/characters/images/${c.job.id}/approve`,"POST",{expected:c.expected,expected_latest_version:c.latest});done.push(c.job.id);}
      catch(e){failures.push(`${c.name}: ${message(e)}`);}
    }
    setCandidates(v=>v.filter(c=>!done.includes(c.job.id)));setSelected(v=>v.filter(id=>!done.includes(id)));
    if(done.length && !failures.length){setOpen(false);onComplete?.();}
    setFeedback(`${done.length}개 이미지를 확정했습니다.${failures.length?` ${failures.length}개는 확정하지 못했습니다. 목록을 닫았다 다시 열어 최신 상태를 확인하세요. ${failures.join(" / ")}`:""}`);
    try {await refresh();}catch{setFeedback(v=>`${v} 최신 상태를 불러오지 못했습니다. 새로고침해 주세요.`);}
    submitting.current=false;setBusy(false);
  }
  return <section className="character-batch" aria-label="여러 이미지 확정">
    <div className="character-heading batch-approve-heading"><Button variant="secondary" aria-expanded={open} disabled={busy || (!open && !eligible.length)} onClick={toggle}><GraphIcon kind="approve"/>선택 확정</Button></div>
    {open && <div className="batch-approval-content"><p className="muted">이미지와 검수 의견을 확인한 뒤 확정할 이미지만 선택하세요. 표시된 버전을 기준 이미지로 확정합니다. AI 검수를 실행하거나 이미지를 새로 생성하지 않습니다.</p>
      {renderPicker?.(candidates,selected,id=>setSelected(v=>v.includes(id)?v.filter(x=>x!==id):[...v,id]),busy)}
      {candidates.length ? <>{!renderPicker && <div className="batch-approval-grid">{candidates.map(c=>{
        const review=reviews.find(r=>r.image_id===c.job.id && r.status==="succeeded");
        return <article key={c.job.id} className={`batch-approval-card${selected.includes(c.job.id)?" is-selected":""}`}>
          <button type="button" className="batch-image-select" aria-pressed={selected.includes(c.job.id)} aria-label={`${c.name} v${c.job.version} 선택`} disabled={busy} onClick={()=>setSelected(v=>v.includes(c.job.id)?v.filter(id=>id!==c.job.id):[...v,c.job.id])}>
          <img src={`/api/v1/characters/images/${c.job.id}/asset`} alt={`${c.name} 확정 검토 이미지 v${c.job.version}`} loading="lazy"/>
          <span className="batch-card-caption"><span><strong>{c.name}</strong><small>v{c.job.version} · 검토 필요</small></span><span className="batch-selection-mark" aria-hidden="true">{selected.includes(c.job.id)?"✓":"＋"}</span></span>
          </button>
          {review && <details><summary>AI 검수 의견 보기</summary><ReviewDashboard value={review.result}/></details>}
        </article>;
      })}</div>}<div className="batch-approval-actions"><span>선택한 이미지 · {selected.length}개</span><Button disabled={busy || !selected.length} onClick={()=>void confirm()}>{busy?"확정 중…":`선택한 ${selected.length}개 이미지 확정`}</Button></div></>:<p>확정할 검토 이미지가 없습니다.</p>}
    </div>}
    {feedback && <p role="status">{feedback}</p>}
  </section>;
}
