"use client";
import {workHref} from "../lib/work-route";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { api, message, type SchemaNode } from "../lib/registry";
import { Button, Field, InputRequirement, SelectCombobox, StatusBadge } from "./ui";
import "./character-library.css";

type Character = {id:string;name:string;appearance:string;facts:string;proposed:string;image_prompt:string;image_id?:string;image_version?:number;project_id?:string;source_request_id?:string};
export type ImageCard = {created_at:string;source_deleted?:boolean;id:string;project_id:string;request_id:string;source_version:number;character_id:string;character:Character;version:number;project_name:string;agent_id:string;agent_name:string;state:string;confirmed:boolean;is_default:boolean;model:string};
type Facet = Pick<ImageCard,"project_id"|"project_name"|"agent_id"|"agent_name">;
type Listing = {items:ImageCard[];has_more:boolean;facets:Facet[]};
type Selection = {format:string;characters:Character[]};
const labels:Record<string,string> = {approved:"확정",review:"검토 필요",excluded:"사용 안 함",running:"새 이미지 생성 중",queued:"새 이미지 대기",failed:"생성 실패 확인",unknown:"상태 확인 필요"};
const asset = (id:string) => `/api/v1/characters/images/${id}/asset`;
const origin = (item:ImageCard) => workHref(item.request_id,item.source_version);

function CloseIcon() {return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg>;}
export function Modal({title,onClose,children,footer,className=""}:{title:string;onClose:()=>void;children:ReactNode;footer?:ReactNode;className?:string}) {
  const ref=useRef<HTMLDialogElement>(null);const id=useId();
  const backdropStart=useRef(false);
  function outside(dialog:HTMLDialogElement,x:number,y:number){const box=dialog.getBoundingClientRect();return x<box.left||x>box.right||y<box.top||y>box.bottom;}
  useEffect(()=>{const dialog=ref.current;dialog?.showModal();return()=>dialog?.close();},[]);
  return <dialog className={`image-library-dialog ${className}`} ref={ref} aria-labelledby={id} onCancel={e=>{e.preventDefault();onClose();}} onPointerDown={e=>{backdropStart.current=e.target===e.currentTarget&&outside(e.currentTarget,e.clientX,e.clientY);}} onPointerCancel={()=>{backdropStart.current=false;}} onClick={e=>{const dismiss=backdropStart.current&&e.target===e.currentTarget&&outside(e.currentTarget,e.clientX,e.clientY);backdropStart.current=false;if(dismiss)onClose();}}>
    <header className="image-library-dialog-heading"><h2 id={id}>{title}</h2><Button variant="secondary" className="image-library-icon" aria-label="닫기" onClick={onClose}><CloseIcon/></Button></header>
    <div className="image-library-dialog-body">{children}</div>{footer&&<footer className="image-library-dialog-footer">{footer}</footer>}
  </dialog>;
}

function ImageDetails({item,scene,onClose}:{item:ImageCard;scene:boolean;onClose:()=>void}) {
  const [versions,setVersions]=useState<ImageCard[]>([item]); const [chosen,setChosen]=useState(item.id);const [error,setError]=useState("");
  useEffect(()=>{let alive=true;api<ImageCard[]>(`/characters/library/${item.id}/versions?kind=${scene?"scene":"character"}`).then(v=>{if(alive)setVersions(v);}).catch(e=>{if(alive)setError(message(e));});return()=>{alive=false;};},[item.id,scene]);
  const shown=versions.find(v=>v.id===chosen)||item;
  return <Modal title={`${item.character.name} · 이미지 확인`} onClose={onClose} footer={item.source_deleted?<p className="muted">삭제된 작업 · 보관된 이미지입니다.</p>:item.request_id?<a className="button button--secondary" href={origin(item)}>원래 작업에서 수정·확정 →</a>:<p className="muted">직접 업로드한 참고 이미지입니다. 실행 화면에서 선택해 연결할 수 있습니다.</p>}>
    {error&&<p role="alert">{error}</p>}
    <div className="image-library-detail"><img src={asset(shown.id)} alt={`${shown.character.name} v${shown.version} 크게 보기`}/><div className="image-library-info">
      <StatusBadge tone={shown.confirmed?"success":"warning"}>{!item.request_id?"사용자 업로드":shown.confirmed?(shown.is_default?"기본 이미지":"확정 이미지"):"검토본"}</StatusBadge>
      <SelectCombobox label="이미지 버전" searchable={false} value={chosen} options={versions.map(v=>({id:v.id,label:`v${v.version}${v.confirmed?(v.is_default?" · 기본 이미지":" · 확정"):" · 검토본"}`}))} onChange={setChosen}/>
      <dl><dt>작업</dt><dd>{item.project_name}</dd><dt>에이전트</dt><dd>{item.agent_name}</dd><dt>이미지 모델</dt><dd>{shown.model}</dd><dt>{scene?"장면 구도·배경·행동":"외형·의상"}</dt><dd>{shown.character.appearance}</dd></dl>
      <details><summary>{scene?"씬 설정 더 보기":"캐릭터 설정 더 보기"}</summary><dl><dt>{scene?"대본 대응 구간":"대본에서 확인한 정보"}</dt><dd>{shown.character.facts||"없음"}</dd><dt>{scene?"장면 연속성":"AI가 제안한 설정"}</dt><dd>{shown.character.proposed||"없음"}</dd><dt>이미지 제작 지침</dt><dd>{shown.character.image_prompt}</dd></dl></details>
    </div></div>
  </Modal>;
}

export function ImageBrowser({selection,onToggle,scene=false,onSelectAll,onClearSelection,selectionBusy=false}:{selection?:string[];onToggle?:(item:ImageCard)=>void;scene?:boolean;onSelectAll?:(ids:string[])=>void;onClearSelection?:()=>void;selectionBusy?:boolean}) {
  const [q,setQ]=useState(""); const [state,setState]=useState(selection&&scene?"approved":"");
  const [project,setProject]=useState("");const [agent,setAgent]=useState("");
  const [data,setData]=useState<Listing>({items:[],has_more:false,facets:[]});
  const [offset,setOffset]=useState(0);const [loading,setLoading]=useState(true);const [error,setError]=useState("");const [refresh,setRefresh]=useState(0);
  const [detail,setDetail]=useState<ImageCard|null>(null);const searchId=useId();
  useEffect(()=>{
    let alive=true;setLoading(true);setError("");
    const timer=setTimeout(()=>{const params=new URLSearchParams({q,state,project,agent,kind:scene?"scene":"character",offset:String(offset)});if(selection&&!scene)params.set("confirmed_versions","true");
      api<Listing>(`/characters/${scene&&selection?"scene-library":"library"}?${params}`).then(result=>{if(alive)setData(result);}).catch(e=>{if(alive)setError(message(e));}).finally(()=>{if(alive)setLoading(false);});},200);
    return()=>{alive=false;clearTimeout(timer);};
  },[q,state,project,agent,offset,refresh,scene,!!selection]);
  const projects=Array.from(new Map(data.facets.map(f=>[f.project_id,{id:f.project_id,label:f.project_name}])).values());
  const agents=Array.from(new Map(data.facets.filter(f=>f.agent_id).map(f=>[f.agent_id,{id:f.agent_id,label:f.agent_name}])).values());
  const limit=scene?32:12;
  const mergedIds=[...new Set([...(selection||[]),...data.items.map(item=>item.id)])];
  const allShownSelected=data.items.length>0&&data.items.every(item=>selection?.includes(item.id));
  return <div className="image-library-browser">
    <div className="image-library-filters">
      <div className="image-library-search"><label htmlFor={searchId}>검색</label><input id={searchId} type="search" placeholder={scene?"씬·작업·에이전트 이름":"캐릭터·작업·에이전트 이름"} maxLength={200} value={q} onChange={e=>{setQ(e.target.value);setOffset(0);}}/></div>
      <SelectCombobox label="작업" value={project} options={[{id:"",label:"모든 작업"},...projects]} onChange={v=>{setProject(v);setOffset(0);}} searchable={false}/>
      <SelectCombobox label="에이전트" value={agent} options={[{id:"",label:"모든 에이전트"},...agents]} onChange={v=>{setAgent(v);setOffset(0);}} searchable={false}/>
      {!selection&&<SelectCombobox label="상태" value={state} options={[{id:"",label:"모든 상태"},...Object.entries(labels).map(([id,label])=>({id,label}))]} onChange={v=>{setState(v);setOffset(0);}} searchable={false}/>}
    </div>
    <div className="image-library-toolbar"><p className="muted">{scene&&!selection?"씬별로 확정 이미지 또는 최근 생성한 이미지를 표시합니다. 카드를 눌러 버전과 장면 내용을 확인하세요.":scene?"확정된 씬 이미지를 선택하세요. 장면 번호와 생성 당시 캐릭터 설정이 함께 연결됩니다. 최대 32장입니다.":selection?"확정 이미지와 사용자가 연결한 업로드 이미지를 선택할 수 있습니다. 최대 12장까지 함께 전달합니다.":"캐릭터별 확정 이미지 또는 최신 이미지를 표시합니다. 이전 버전은 카드를 눌러 확인하세요."}</p><Button variant="secondary" disabled={loading} onClick={()=>setRefresh(v=>v+1)}>새로고침</Button></div>
    {onSelectAll&&selection&&<div className="image-library-toolbar"><div className="button-row"><Button variant="secondary" disabled={loading||selectionBusy||!!error||!data.items.length||allShownSelected||mergedIds.length>limit} onClick={()=>onSelectAll(mergedIds)}>현재 목록 모두 선택</Button><Button variant="secondary" disabled={selectionBusy||!selection.length} onClick={onClearSelection}>전체 선택 해제</Button></div><p className="helper-text" role="status">{mergedIds.length>limit?`최대 ${limit}장까지 선택할 수 있습니다. 검색·필터로 범위를 줄이거나 기존 선택을 해제하세요.`:data.has_more||offset>0?"검색·필터가 적용된 현재 페이지의 이미지를 선택합니다. 다른 페이지의 선택은 유지됩니다.":"검색·필터가 적용된 현재 목록을 모두 선택합니다."}</p></div>}
    {error&&<p role="alert">{error}</p>}
    {loading?<p role="status">이미지를 불러오는 중…</p>:!error&&!data.items.length?<div className="image-library-empty"><strong>표시할 이미지가 없습니다.</strong><p>{selection?"원래 작업에서 이미지를 확정하거나 검색·필터를 변경해 주세요.":"검색·필터를 변경해 보세요. 아직 생성하지 않은 이미지는 원래 작업에서 확인할 수 있습니다."}</p></div>:!error&&<div className="image-library-grid">{data.items.map(item=>{
      const selected=selection?.includes(item.id);const stateLabel=selection&&item.confirmed?(item.is_default?"기본 이미지":"확정"):!item.request_id?"사용자 업로드":labels[item.state]||item.state;return <button type="button" key={item.id} className="image-library-card" aria-pressed={selection?!!selected:undefined} aria-label={`${item.character.name} · ${stateLabel}${selection?" 선택":" 이미지 확인"}`} onClick={()=>onToggle?onToggle(item):setDetail(item)}>
        <div className="image-library-thumbnail"><img src={asset(item.id)} alt={`${item.character.name} 기준 이미지`} loading="lazy"/>{selection&&<span className="image-library-check" aria-hidden="true">{selected?"✓":"+"}</span>}</div>
        <div className="image-library-card-content"><div className="image-library-card-title"><strong>{item.character.name}</strong><StatusBadge tone={!item.request_id?"neutral":item.state==="approved"?"success":item.state==="excluded"?"neutral":"warning"}>{stateLabel}</StatusBadge></div>
          <span className="image-library-version">v{item.version}{item.is_default?" · 기본 이미지":item.confirmed?" · 확정":""}</span>
          <div className="image-library-source"><span>생성 시각</span><span>{new Date(item.created_at).toLocaleString("ko-KR")}</span><span>작업</span><span>{item.project_name}{item.source_deleted && " · 삭제된 작업"}</span><span>에이전트</span><span>{item.agent_name}</span></div>
        </div></button>;
    })}</div>}
    {(offset>0||data.has_more)&&<div className="image-library-pages"><Button variant="secondary" disabled={loading||offset===0} onClick={()=>setOffset(v=>Math.max(0,v-24))}>이전 이미지</Button><span>{offset/24+1} 페이지</span><Button variant="secondary" disabled={loading||!data.has_more} onClick={()=>setOffset(v=>v+24)}>다음 이미지</Button></div>}
    {detail&&<ImageDetails scene={scene} item={detail} onClose={()=>setDetail(null)}/>}
  </div>;
}

export function CharacterLibrary({scene=false}:{scene?:boolean}) {
 return <section className="image-library">
   <header><p className="eyebrow">IMAGE LIBRARY</p><h1>이미지 보관함</h1>
     <p className="muted">캐릭터와 씬 이미지를 확인하고, 원래 작업에서 수정하거나 확정하세요.</p></header>
   <nav aria-label="이미지 종류" className="button-row">
     <a href="/characters" aria-current={!scene?"page":undefined} className={`button button--${scene?"secondary":"primary"}`}>캐릭터 이미지</a>
     <a href="/characters?view=scenes" aria-current={scene?"page":undefined} className={`button button--${scene?"primary":"secondary"}`}>씬 이미지</a>
   </nav>
   <ImageBrowser key={scene?"scene":"character"} scene={scene}/>
 </section>;
}

export function isCharacterReference(node:SchemaNode) {
 return node.type==="object" && node.properties?.format?.enum?.some(v=>v==="asa_character_selection_v1");
}
function readSelection(value:string):Selection|null {try{const parsed=JSON.parse(value) as Selection;return Array.isArray(parsed.characters)?parsed:null;}catch{return null;}}
function UploadImage({existing,onClose,onApply}:{existing?:Character;onClose:()=>void;onApply:(value:Selection)=>Promise<void>}) {
 const uid=useId();const fileRef=useRef<HTMLInputElement>(null);const formRef=useRef<HTMLDivElement>(null);
 const [file,setFile]=useState<File|null>(null);const [preview,setPreview]=useState("");
 const [name,setName]=useState(existing?.name||"");const [appearance,setAppearance]=useState(existing?.appearance||"");
 const [prompt,setPrompt]=useState(existing?.image_prompt||"");const [linked,setLinked]=useState(existing?.image_id||"");
 const [choosing,setChoosing]=useState(false);const [dragging,setDragging]=useState(false);const [busy,setBusy]=useState(false);const [error,setError]=useState("");
 useEffect(()=>{formRef.current?.closest('.image-library-dialog-body')?.scrollTo(0,0);},[choosing]);
 useEffect(()=>{if(!file)return;const url=URL.createObjectURL(file);setPreview(url);return()=>URL.revokeObjectURL(url);},[file]);
 function choose(files:FileList|null){if(busy||!files?.length)return;setError("");if(files.length!==1){setError("이미지를 한 장씩 연결해 주세요.");return;}const f=files[0];if(!["image/png","image/jpeg","image/webp"].includes(f.type)||f.size>5*1024*1024){setError("PNG·JPG·WebP, 5MB 이하 이미지를 선택해 주세요.");return;}setFile(f);}
 async function save(){setBusy(true);setError("");try{
   const data=file?await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(",")[1]);reader.onerror=()=>reject(new Error());reader.readAsDataURL(file);}):undefined;
   const result=await api<Selection>("/characters/library/uploads","POST",{data,existing_upload:file?undefined:existing?.image_id,filename:file?.name||"참고 이미지",character_image:linked||undefined,name:name.trim(),appearance:appearance.trim(),image_prompt:prompt.trim()});
   await onApply(result);onClose();
 }catch(e){setError(message(e));}finally{setBusy(false);}}
 return <Modal title={existing?"업로드 이미지 연결 수정":"캐릭터 참고 이미지 업로드"} onClose={()=>{if(!busy)onClose();}} footer={<><Button variant="secondary" disabled={busy} onClick={onClose}>취소</Button><Button disabled={busy||choosing||(!file&&!existing)||!name.trim()||!appearance.trim()} onClick={()=>void save()}>{busy?"저장·연결 중…":"이미지 저장하고 연결"}</Button></>}>
 {choosing?<><p className="muted">연결할 캐릭터를 선택하세요. 이름과 저장된 설정을 가져옵니다.</p><Button variant="secondary" onClick={()=>setChoosing(false)}>연결 설정으로 돌아가기</Button><ImageBrowser selection={[]} onToggle={item=>{setLinked(item.id);setName(item.character.name);setAppearance(item.character.appearance);setPrompt(item.character.image_prompt);setChoosing(false);}}/></>:<div ref={formRef} className="reference-upload-layout">
  <div className="reference-upload-media"><div className="reference-dropzone" data-dragging={dragging} onDragOver={e=>{e.preventDefault();if(!busy)setDragging(true);}} onDragLeave={()=>setDragging(false)} onDrop={e=>{e.preventDefault();setDragging(false);choose(e.dataTransfer.files);}}>
    {(preview||existing)&&<img src={preview||asset(existing?.image_id||"")} alt="업로드할 캐릭터 참고 이미지 미리보기"/>}
    <strong>{file?file.name:existing?"저장된 업로드 이미지":"이미지를 여기로 끌어 놓으세요"}</strong><p className="muted">PNG·JPG·WebP · 5MB 이하 · 한 장씩 연결</p>
    <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={e=>{choose(e.target.files);e.target.value="";}}/>
    <Button variant="secondary" disabled={busy} onClick={()=>fileRef.current?.click()}>{file||existing?"이미지 변경":"이미지 선택"}</Button>
  </div><p className="muted">원본 비율을 유지하며 최대 2048px로 저장합니다. 업로드만으로 AI가 실행되지는 않습니다.</p></div>
  <div className="reference-upload-fields"><h3>어떤 캐릭터의 이미지인가요?</h3><p className="muted">장면 구성의 캐릭터 이름과 동일하게 연결하세요. 이름·외형·의상·제작 지침이 이미지와 함께 AI에 전달됩니다.</p>
    <div className="button-row"><Button variant="secondary" disabled={busy} onClick={()=>setChoosing(true)}>보관함 캐릭터 설정 가져오기</Button>{linked&&<Button variant="secondary" disabled={busy} onClick={()=>{setLinked("");setName("");setAppearance("");setPrompt("");}}>새 캐릭터로 연결</Button>}</div>
    <Field id={`${uid}-name`} label="캐릭터 이름" hint="필수 · 예: 장면 구성에 등장하는 ‘몽실이’">{p=><input {...p} disabled={busy} maxLength={100} value={name} onChange={e=>setName(e.target.value)}/>}</Field>
    <Field id={`${uid}-appearance`} label="외형·의상" hint="필수 · 이미지에서 유지할 모습을 알려 주세요.">{p=><textarea {...p} disabled={busy} rows={4} maxLength={3000} value={appearance} onChange={e=>setAppearance(e.target.value)}/>}</Field>
    <Field id={`${uid}-prompt`} label="이미지 활용 시 유지할 특징" hint="선택 · 비워 두면 첨부 이미지의 외형·의상·화풍을 기준으로 삼습니다. 변경을 원할 때만 적어 주세요.">{p=><textarea {...p} disabled={busy} rows={3} maxLength={4000} value={prompt} onChange={e=>setPrompt(e.target.value)}/>}</Field>
    <p className="muted">저장하면 보관함에도 남습니다. 기존 캐릭터 설정과 대본·장면 원문은 변경하지 않습니다.</p>
  </div></div>}{error&&<p role="alert" className="field-error">{error}</p>}
 </Modal>;
}
export function CharacterImageInput({id,label,required,value,onChange}:{id:string;label:string;required:boolean;value:string;onChange:(value:string)=>void}) {
 const [open,setOpen]=useState(false);const [pending,setPending]=useState<string[]>([]);const [busy,setBusy]=useState(false);const [error,setError]=useState("");
 const selected=readSelection(value);
 const [upload,setUpload]=useState<Character|true|null>(null);
 async function attach(data:Selection){const ids=(selected?.characters||[]).filter(c=>upload===true||c.image_id!==(upload as Character)?.image_id).map(c=>c.image_id);const merged=await api<Selection>("/characters/library/selection","POST",{image_ids:[...ids,...data.characters.map(c=>c.image_id)]});onChange(JSON.stringify(merged));}
 function remove(imageId:string){const remaining=selected?.characters.filter(c=>c.image_id!==imageId)||[];onChange(remaining.length?JSON.stringify({...selected,characters:remaining}):"");}
 function show(){setPending(selected?.characters.map(c=>c.image_id||"").filter(Boolean)||[]);setError("");setOpen(true);}
 async function toggleVersion(item:ImageCard){
   if(busy)return;
   if(pending.includes(item.id)){setPending(old=>old.filter(id=>id!==item.id));return;}
   setBusy(true);setError("");
   try{const family=await api<ImageCard[]>(`/characters/library/${item.id}/versions`);const ids=new Set(family.map(v=>v.id));const next=pending.filter(id=>!ids.has(id));if(next.length>=12){setError("캐릭터 이미지는 최대 12장까지 선택할 수 있습니다.");return;}setPending([...next,item.id]);}
   catch(e){setError(message(e));}finally{setBusy(false);}
 }
 async function apply(){setBusy(true);setError("");try{const data=await api<Selection>("/characters/library/selection","POST",{image_ids:pending});onChange(JSON.stringify(data));setOpen(false);}catch(e){setError(message(e));}finally{setBusy(false);}}
 return <fieldset className="image-reference-input" id={id}><legend>캐릭터 참고 이미지와 설정<InputRequirement required={required}/></legend>
   <p className="muted">보관함에서 선택하거나 직접 업로드하세요. 캐릭터 이름·설정과 실제 이미지가 함께 전달됩니다. 최대 12장입니다.</p>
   {!!selected?.characters.length&&<div className="image-reference-selected">{selected.characters.map(c=><div key={c.image_id} className="reference-selection-card"><img src={asset(c.image_id||"")} alt={`${c.name} 선택된 기준 이미지`}/><span><strong>{c.name}</strong><small>{c.source_request_id===""?"사용자 업로드":"보관함"} · v{c.image_version}</small></span><div className="reference-selection-actions">{c.source_request_id===""&&<Button variant="secondary" onClick={()=>setUpload(c)}>연결 수정</Button>}<Button variant="secondary" aria-label={`${c.name} 연결 해제`} onClick={()=>remove(c.image_id||"")}>연결 해제</Button></div></div>)}</div>}
   <div className="button-row"><Button variant="secondary" onClick={show}>{selected?.characters.length?`보관함 선택 변경 · ${selected.characters.length}장`:"보관함에서 선택"}</Button><Button variant="secondary" disabled={(selected?.characters.length||0)>=12} onClick={()=>setUpload(true)}>이미지 업로드</Button>{value&&<Button variant="secondary" onClick={()=>onChange("")}>전체 선택 해제</Button>}</div>
   {upload&&<UploadImage existing={upload===true?undefined:upload} onClose={()=>setUpload(null)} onApply={attach}/>}
   {open&&<Modal title="전달할 캐릭터 이미지 선택" onClose={()=>{if(!busy)setOpen(false);}} footer={<><span role="status">{pending.length} / 12장 선택</span><Button variant="secondary" disabled={busy} onClick={()=>setOpen(false)}>취소</Button><Button disabled={busy||!pending.length} onClick={()=>void apply()}>{busy?"확인 중…":"선택한 이미지 연결"}</Button></>}>
     <ImageBrowser selection={pending} selectionBusy={busy} onToggle={item=>void toggleVersion(item)}/>
     {pending.length===12&&<p className="muted">12장을 선택했습니다. 다른 이미지를 선택하려면 먼저 선택을 해제하세요.</p>}
     {error&&<p role="alert">{error}</p>}
   </Modal>}
 </fieldset>;
}
