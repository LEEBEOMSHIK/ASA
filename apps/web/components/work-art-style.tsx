"use client";
import {useEffect,useId,useState} from "react";
import Image from "next/image";
import type {ArtCatalog,ArtPreset} from "../lib/art-style-catalog";
import {videoStyles} from "../lib/video-prompt-settings";
import {api,ApiError,message} from "../lib/registry";
import {useWorkDraft} from "../lib/work-draft";
import {Button,DisclosureButton,Field,SelectCombobox,StatusBadge} from "./ui";

type Style={work_id:string|null;prompt:string;revision:number;media_type:string|null};
export function WorkArtStyle({projectId}:{projectId:string}){
  const id=useId(),[saved,setSaved]=useState<Style|null>(null),[text,setText]=useState("");
  const [open,setOpen]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [custom,setCustom]=useState(false);
  const [media,setMedia]=useState("");
  const [catalog,setCatalog]=useState<ArtPreset[]>([]),[catalogReady,setCatalogReady]=useState(false);
  useEffect(()=>{let alive=true;api<ArtCatalog>("/art-style-catalog").then(v=>{if(alive){setCatalog(v.items.filter(p=>p.enabled));setCatalogReady(true);}}).catch(e=>{if(alive)setError(message(e));});return()=>{alive=false;};},[]);
  const examples=catalog.filter(s=>s.media_type===media);
  const choice=custom?"custom":catalog.find(s=>s.description===text&&(!media||s.media_type===media))?.id||(text?"custom":"existing");
  const dirty=!!saved&&(text!==saved.prompt||media!==(saved.media_type||""));
  function choose(value:string){setCustom(value==="custom");setNotice("");if(value==="existing")setText("");else if(value!=="custom")setText(catalog.find(s=>s.id===value)?.description||"");}
  const draft=useWorkDraft(saved?.work_id?`art-style:${saved.work_id}:r${saved.revision}`:undefined,
    {prompt:text,media_type:media},value=>{
      if(typeof value==="string"){setText(value);setOpen(true);}
      else if(value&&typeof value.prompt==="string"){setText(value.prompt);setMedia(value.media_type||"");setOpen(true);}
    },!!saved,dirty);
  const path=`/characters/projects/${projectId}/art-style`;
  function accept(value:Style){setSaved(value);setText(value.prompt);setMedia(value.media_type||"");setCustom(false);}
  useEffect(()=>{let alive=true;api<Style>(path).then(v=>{if(alive)accept(v);})
    .catch(e=>{if(alive)setError(message(e));});return()=>{alive=false;};},[path]);
  async function save(){if(!saved?.work_id||busy)return;setBusy(true);setError("");setNotice("");
    try{const value=await api<Style>(path,"PUT",{work_id:saved.work_id,revision:saved.revision,prompt:text,media_type:media||null});
      draft.clear();accept(value);setOpen(false);setNotice("영상 유형과 화풍을 저장했습니다.");
    }catch(e){setError(e instanceof ApiError&&["art_style_changed","art_style_work_changed"].includes(e.code)
      ?"화풍 또는 작품 연결이 변경됐습니다. 입력을 복사한 뒤 최신 설정을 다시 불러와 주세요.":message(e));}
    finally{setBusy(false);}}
  return <section className="voice-directions work-art-style" aria-label="작품 공통 · 화풍">
    <div className="voice-direction-heading"><div><h3>작품 공통 · 영상 유형과 화풍</h3>
      <p className="muted">{saved?`${videoStyles.find(s=>s.id===media)?.name||"영상 유형 미설정"} · ${choice==="custom"?"직접 입력":catalog.find(s=>s.id===choice)?.label||"기본 화풍"}`:"불러오는 중…"}</p>
      {dirty&&<StatusBadge>저장 전 변경</StatusBadge>}</div>
      <DisclosureButton variant="secondary" aria-expanded={open} aria-controls={id} onClick={()=>setOpen(!open)}>{open?"화풍 접기":"화풍 설정"}</DisclosureButton></div>
    <div id={id} hidden={!open} className="voice-direction-panel">
      {saved&&!saved.work_id?<p role="status">작품 연결을 확인할 수 없습니다. 보관함에서 작품을 연결한 뒤 다시 불러와 주세요.</p>:<>
      <SelectCombobox label="영상 유형" value={media} loading={busy||!saved||!catalogReady} searchable={false} showId={false}
        options={videoStyles.map(s=>({id:s.id,label:s.name}))} onChange={value=>{
          setMedia(value);setNotice("");
          if(catalog.some(s=>s.id===choice&&s.media_type!==value)){setText("");setCustom(false);}
        }}/>
      {!media&&<p className="muted">영상 유형을 먼저 선택하세요. 기존 화풍은 보존됩니다.</p>}
      {media&&<>
      <SelectCombobox label="화풍 선택" value={choice} loading={busy||!saved||!catalogReady} searchable={false} showId={false}
        options={[{id:"existing",label:"유형에 맞는 기본 화풍"},...examples.map(({id,label})=>({id,label})),{id:"custom",label:"직접 입력"}]}
        onChange={choose}/>
      {choice==="custom"?<Field id={id+"prompt"} label="원하는 화풍 직접 입력">{p=><textarea {...p} placeholder="예: 차분한 푸른색 수채화, 종이 질감과 부드러운 연필선" rows={3} maxLength={2000} disabled={busy||!saved} value={text} onChange={e=>{setText(e.target.value);setCustom(true);setNotice("");}}/>}</Field>
        :<div className="art-style-examples" role="group" aria-label="화풍 예시 이미지">
          {examples.map(s=><button type="button" key={s.id} className="art-style-example" aria-label={`${s.label} 선택`} aria-pressed={choice===s.id} disabled={busy||!saved} onClick={()=>choose(s.id)}>
            {s.image?<Image src={s.image} width={768} height={512} sizes="(max-width: 520px) 100vw, (max-width: 900px) 40vw, 24vw" alt={`${s.label} 예시 이미지`}/>:<span className="art-style-placeholder">예시 이미지 없음</span>}
            <span>{s.label}{choice===s.id&&<span aria-hidden="true"> ✓</span>}</span>
          </button>)}
        </div>}</>}
      {draft.notice&&/못|실패|복원/.test(draft.notice)&&<p role="status">{draft.notice}</p>}
      <div className="voice-direction-actions art-style-actions">{dirty&&saved&&<Button variant="secondary" disabled={busy} onClick={()=>{draft.clear();accept(saved);setNotice("");}}>변경 취소</Button>}<Button disabled={busy||!dirty||!saved||!media} onClick={()=>void save()}>{busy?"저장 중…":"공통 설정 저장"}</Button></div></>}
    </div>
    {notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
    {(error||(saved&&!saved.work_id))&&<Button variant="secondary" disabled={busy} onClick={()=>void Promise.all([api<Style>(path),api<ArtCatalog>("/art-style-catalog")]).then(([v,c])=>{draft.clear();accept(v);setCatalog(c.items.filter(p=>p.enabled));setCatalogReady(true);setError("");}).catch(e=>setError(message(e)))}>최신 설정 다시 불러오기</Button>}
  </section>;
}
