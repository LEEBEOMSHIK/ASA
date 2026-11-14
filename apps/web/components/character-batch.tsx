"use client";
import { useRef, useState, type ReactNode } from "react";
import { api, message } from "../lib/registry";
import { Button } from "./ui";
import { GraphIcon } from "./graph-icon";
import { ImageModelSelect } from "./image-model-select";

type Character = {id:string;name:string;facts:string;appearance:string;proposed:string;scene_ids:string;image_prompt:string};
type Props = {
  renderPicker?:(eligible:string[],selected:string[],toggle:(id:string)=>void,busy:boolean)=>ReactNode;
  controlledOpen?:boolean; onToggle?:()=>void; onComplete?:()=>void; unit?:string; blocked?:Record<string,string[]>; projectId:string; characters:Character[]; excluded:string[];
  jobs:{character_id:string;status:string}[]; models:string[]; enabled:boolean;
  getReferenceOverrides?:(character:Character)=>Record<string,string>;
  getDraft:(character:Character)=>Character; refresh:()=>Promise<void>;
};
export function CharacterBatch({projectId,characters,excluded,jobs,models,enabled,getDraft,getReferenceOverrides,refresh,unit="캐릭터",blocked={},controlledOpen,onToggle,onComplete,renderPicker}:Props) {
  const [localOpen,setOpen]=useState(false);
  const open=controlledOpen ?? localOpen;
  const [selected,setSelected]=useState<string[]>([]);
  const [model,setModel]=useState(models[0] || "");
  const [busy,setBusy]=useState(false);
  const [feedback,setFeedback]=useState("");
  const dispatch=useRef<{signature:string;ids:string[]}|null>(null);
  const eligible=characters.filter(c=>!excluded.includes(c.id) && !blocked[c.id]?.length && !jobs.some(j=>j.character_id===c.id && ["succeeded","queued","running","unknown"].includes(j.status)));
  const allGenerated=characters.filter(c=>!excluded.includes(c.id)).length>0 && characters.filter(c=>!excluded.includes(c.id)).every(c=>jobs.some(j=>j.character_id===c.id && j.status==="succeeded"));
  const unavailable=allGenerated?`모든 사용 중인 ${unit}에 이미지가 있습니다. 수정은 각 항목에서 요청하세요.`:`지금 생성 가능한 ${unit}이 없습니다. 각 항목의 상태와 자료 확인 안내를 확인하세요.`;
  const picked=eligible.filter(c=>selected.includes(c.id));
  async function generate() {
    if(busy || !picked.length)return;
    setBusy(true);setFeedback("");
    const payload=picked.map(c=>({character:getDraft(c),model,change:"",base_id:null,reference_overrides:getReferenceOverrides?.(c) || {}}));
    const signature=JSON.stringify(payload);
    if(dispatch.current?.signature!==signature)dispatch.current={signature,ids:payload.map(()=>crypto.randomUUID())};
    try {
      await api(`/characters/projects/${projectId}/images/batch`,"POST",{items:payload.map((item,i)=>({...item,id:dispatch.current!.ids[i]}))});
      dispatch.current=null;setSelected([]);setFeedback(`${payload.length}개의 이미지 요청을 접수했습니다. 대기 중인 요청은 각 항목에서 취소할 수 있습니다.`);
      setOpen(false);onComplete?.();
      await refresh().catch(()=>setFeedback(v=>v+" 최신 상태를 불러오지 못했습니다. 새로고침해 주세요."));
    } catch(e){setFeedback(message(e));await refresh().catch(()=>{});} finally{setBusy(false);}
  }
  return <section className="character-batch" aria-label={`여러 ${unit} 이미지 생성`}>
    <div className="character-heading batch-generate-heading"><span title={!eligible.length?unavailable:undefined} tabIndex={!eligible.length?0:undefined} aria-label={!eligible.length?unavailable:undefined}><Button variant="secondary" aria-expanded={open} disabled={busy || (!open && !eligible.length)} onClick={()=>onToggle?onToggle():setOpen(v=>!v)}><GraphIcon kind="image"/>선택 생성</Button></span></div>
    {open && <div className="character-form">
      <p className="muted">생성 가능한 {unit} {eligible.length}개 · 아직 이미지가 없는 {unit}을 선택하세요. 한 번에 최대 12개를 접수합니다. 현재 수정한 설정으로 항목당 1장을 생성합니다. 기존 이미지·확정 이미지는 바꾸지 않습니다.</p>
      {renderPicker?.(eligible.map(c=>c.id),picked.map(c=>c.id),id=>setSelected(v=>v.includes(id)?v.filter(x=>x!==id):v.length<12?[...v,id]:v),busy)}
      {eligible.length ? <><div className="character-heading"><strong>생성할 {unit}</strong><Button variant="secondary" disabled={busy} onClick={()=>setSelected(picked.length===Math.min(eligible.length,12)?[]:eligible.slice(0,12).map(c=>c.id))}>{picked.length===Math.min(eligible.length,12)?"선택 해제":"전체 선택"}</Button></div>
        {!renderPicker && <div className="character-batch-options">{eligible.map(c=><button type="button" key={c.id} className="batch-select-card" aria-pressed={selected.includes(c.id)} disabled={busy || (!selected.includes(c.id) && picked.length>=12)} onClick={()=>setSelected(v=>v.includes(c.id)?v.filter(id=>id!==c.id):[...v,c.id])}><span>{c.name}</span><span className="batch-selection-mark" aria-hidden="true">{selected.includes(c.id)?"✓":"＋"}</span></button>)}</div>}
        <ImageModelSelect label={`선택한 ${unit}의 이미지 모델`} value={model} options={models} onChange={setModel} disabled={busy}/>
        <div className="character-heading"><Button disabled={busy || !picked.length || !model || !enabled} onClick={()=>void generate()}>{busy?"접수 중…":`선택한 ${picked.length}개 생성`}</Button><span className="muted">항목당 유료 API 호출 · 백그라운드에서 순서대로 처리</span></div>
      </>:<p>{Object.values(blocked).some(notes=>notes.length) ? "지금 생성할 수 있는 항목이 없습니다. 각 항목의 자료 확인 안내를 먼저 확인하세요." : "새로 생성할 항목이 없습니다. 기존 이미지 수정은 각 항목에서 요청하세요."}</p>}
    </div>}
    {feedback && <p role="status">{feedback}</p>}
  </section>;
}
