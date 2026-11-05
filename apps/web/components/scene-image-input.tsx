"use client";
import "./scene-reference-versions.css";
import { useState } from "react";
import { api, message, type SchemaNode } from "../lib/registry";
import { Button, InputRequirement } from "./ui";
import { ImageBrowser, Modal } from "./character-library";

type Scene = {image_id:string;base_image_id?:string;selection?:string;name:string;image_version:number;scene_id:string;shot_id:string;character_count:number};
type Selection = {format:string;scenes:Scene[]};
export function isSceneReference(node:SchemaNode) {return node.type==="object" && node.properties?.format?.enum?.includes("asa_scene_selection_v1");}
export function SceneImageInput({id,label,required,value,onChange}:{id:string;label:string;required:boolean;value:string;onChange:(v:string)=>void}) {
 const [open,setOpen]=useState(false);const [pending,setPending]=useState<string[]>([]);const [busy,setBusy]=useState(false);const [error,setError]=useState("");
 let selected:Selection|null=null;try{const parsed=JSON.parse(value);if(Array.isArray(parsed.scenes))selected=parsed;}catch{}
 function show(){setPending(selected?.scenes.map(s=>s.image_id)||[]);setError("");setOpen(true);}
 async function apply(){setBusy(true);setError("");try{const result=await api<Selection>("/characters/scene-library/selection","POST",{image_ids:pending});onChange(JSON.stringify(result));setOpen(false);}catch(e){setError(message(e));}finally{setBusy(false);}}
 return <fieldset id={id} className="image-reference-input"><legend>{label}<InputRequirement required={required}/></legend>
 <p className="muted">실제 씬 이미지와 장면 번호·최종 설정·캐릭터 설정을 함께 전달합니다. 영상 생성 없이, 이미지의 현재 모습에 맞는 비디오 프롬프트를 작성합니다.</p>
 {!!selected?.scenes.length&&<div className="scene-reference-grid">{selected.scenes.map(s=><section key={s.image_id} className="scene-reference-card"><div className="reference-selection-card"><img src={`/api/v1/characters/images/${s.image_id}/asset`} alt={s.name}/><span><strong>{s.name}</strong><small>장면 {s.scene_id} · v{s.image_version} · 확정 기준</small><small>생성 당시 캐릭터 설정 {s.character_count}명 포함</small></span></div></section>)}</div>}
 <p className="helper-text">씬마다 확정 이미지 한 장을 사용합니다. 다른 버전을 사용하려면 해당 씬에서 기준 이미지를 변경한 뒤 다시 선택하세요.</p>
 {!open&&error&&<p role="alert">{error}</p>}
 <div className="button-row"><Button variant="secondary" onClick={show}>{selected?.scenes.length?`선택 변경 · ${selected.scenes.length}장`:"확정 씬 이미지 선택"}</Button>{value&&<Button variant="secondary" onClick={()=>onChange("")}>선택 해제</Button>}</div>
 <p className="helper-text">대본·장면 구성과 같은 작업의 이미지를 선택하세요. 캐릭터 설정은 생성 당시 기록을 가져오며 다시 입력하지 않아도 됩니다. 선택하지 않은 씬은 이미지 대조 대상에서 제외됩니다.</p>
 {open&&<Modal title="확정 씬 이미지 가져오기" onClose={()=>{if(!busy)setOpen(false);}} footer={<><span role="status">{pending.length} / 32장 선택</span><Button variant="secondary" disabled={busy} onClick={()=>setOpen(false)}>취소</Button><Button disabled={busy||!pending.length} onClick={()=>void apply()}>{busy?"연결 확인 중…":"선택한 씬 연결"}</Button></>}>
 <ImageBrowser scene selection={pending} selectionBusy={busy} onSelectAll={setPending} onClearSelection={()=>setPending([])} onToggle={item=>{if(!busy)setPending(old=>old.includes(item.id)?old.filter(x=>x!==item.id):old.length<32?[...old,item.id]:old);}}/>
 {pending.length===32&&<p className="muted">32장까지 선택할 수 있습니다. 더 많은 장면은 나누어 요청하세요.</p>}{error&&<p role="alert">{error}</p>}
 </Modal>}
 </fieldset>;
}
