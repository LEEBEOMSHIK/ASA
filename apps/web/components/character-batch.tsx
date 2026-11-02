"use client";
import { useRef, useState } from "react";
import { api, message } from "../lib/registry";
import { Button } from "./ui";
import { ImageModelSelect } from "./image-model-select";

type Character = {id:string;name:string;facts:string;appearance:string;proposed:string;scene_ids:string;image_prompt:string};
type Props = {
  projectId:string; characters:Character[]; excluded:string[];
  jobs:{character_id:string;status:string}[]; models:string[]; enabled:boolean;
  getDraft:(character:Character)=>Character; refresh:()=>Promise<void>;
};
export function CharacterBatch({projectId,characters,excluded,jobs,models,enabled,getDraft,refresh}:Props) {
  const [open,setOpen]=useState(false);
  const [selected,setSelected]=useState<string[]>([]);
  const [model,setModel]=useState(models[0] || "");
  const [busy,setBusy]=useState(false);
  const [feedback,setFeedback]=useState("");
  const dispatch=useRef<{signature:string;ids:string[]}|null>(null);
  const eligible=characters.filter(c=>!excluded.includes(c.id) && !jobs.some(j=>j.character_id===c.id && ["succeeded","queued","running","unknown"].includes(j.status)));
  const picked=eligible.filter(c=>selected.includes(c.id));
  async function generate() {
    if(busy || !picked.length)return;
    setBusy(true);setFeedback("");
    const payload=picked.map(c=>({character:getDraft(c),model,change:"",base_id:null}));
    const signature=JSON.stringify(payload);
    if(dispatch.current?.signature!==signature)dispatch.current={signature,ids:payload.map(()=>crypto.randomUUID())};
    try {
      await api(`/characters/projects/${projectId}/images/batch`,"POST",{items:payload.map((item,i)=>({...item,id:dispatch.current!.ids[i]}))});
      dispatch.current=null;setSelected([]);setFeedback(`${payload.length}명의 이미지 요청을 접수했습니다. 대기 중인 요청은 각 캐릭터에서 취소할 수 있습니다.`);
      await refresh();
    } catch(e){setFeedback(message(e));await refresh().catch(()=>{});} finally{setBusy(false);}
  }
  return <section className="character-batch" aria-label="여러 캐릭터 이미지 생성">
    <div className="character-heading"><Button variant="secondary" aria-expanded={open} onClick={()=>setOpen(v=>!v)}>여러 캐릭터 생성 {open?"접기":"열기"}</Button><span className="muted">새 이미지 생성 가능 · {eligible.length}명</span></div>
    {open && <div className="character-form">
      <p className="muted">아직 이미지가 없는 캐릭터를 선택하세요. 현재 수정한 설정으로 인물당 1장을 생성합니다. 기존 이미지·확정 이미지는 바꾸지 않습니다.</p>
      {eligible.length ? <><div className="character-heading"><strong>생성할 캐릭터</strong><Button variant="secondary" disabled={busy} onClick={()=>setSelected(picked.length===eligible.length?[]:eligible.map(c=>c.id))}>{picked.length===eligible.length?"선택 해제":"전체 선택"}</Button></div>
        <div className="character-batch-options">{eligible.map(c=><label key={c.id}><input type="checkbox" checked={selected.includes(c.id)} disabled={busy} onChange={e=>setSelected(v=>e.target.checked?[...v,c.id]:v.filter(id=>id!==c.id))}/><span>{c.name}</span></label>)}</div>
        <ImageModelSelect label="선택한 캐릭터의 이미지 모델" value={model} options={models} onChange={setModel} disabled={busy}/>
        <div className="character-heading"><Button disabled={busy || !picked.length || !model || !enabled} onClick={()=>void generate()}>{busy?"접수 중…":`선택한 ${picked.length}명 생성`}</Button><span className="muted">인물당 유료 API 호출 · 백그라운드에서 순서대로 처리</span></div>
      </>:<p>새로 생성할 캐릭터가 없습니다. 기존 이미지 수정은 각 캐릭터에서 요청하세요.</p>}
    </div>}
    {feedback && <p role="status">{feedback}</p>}
  </section>;
}
