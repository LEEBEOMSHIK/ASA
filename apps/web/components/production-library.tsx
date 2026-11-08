"use client";

import { useEffect, useId, useRef, useState } from "react";
import { api, message } from "../lib/registry";
import { Button, Field, SelectCombobox, StatusBadge } from "./ui";
import { ImageBrowser, Modal } from "./character-library";
import "./production-library.css";

type Work = {source_label?:string;created_at?:string;context?:string;id:string;name:string;revision:number;count:number;automatic?:boolean;origin?:string|null};
type Item = {is_scene_plan?:boolean;related_count?:number;duplicate_count?:number;excerpt?:string;category:string;agent_name?:string;id:string;kind:string;subtype:string;title:string;version:number;status:string;created_at:string;source_name:string;work_id:string|null;work_name:string|null;subject:string;assignment_revision:number;automatic?:boolean;origin:string|null;media_url:string|null};
type Detail = Item & {content:unknown;versions:Item[];related_items?:Item[];duplicate_items?:Item[];parent_scene?:Item|null};
type Listing = {items:Item[];total:number;has_more:boolean;works:Work[];counts:Record<string,number>;unassigned:number};
const kinds:Record<string,string> = {script:"대본",scene:"씬",character:"캐릭터 설정",character_image:"캐릭터 이미지",scene_image:"씬 이미지",reference_image:"참고 이미지",speech:"음성",music:"배경음악",video:"영상",prompt:"비디오 프롬프트",document:"기타 자료"};
const visibleKinds = Object.entries(kinds).filter(([id])=>!["character","reference_image","prompt","document"].includes(id));
const states:Record<string,string> = {excluded:"사용 안 함",retained:"보관됨",saved:"저장됨",approved:"확정",review:"검토 필요",uploaded:"업로드",queued:"대기",submitting:"접수 중",running:"생성 중",failed:"실패",unknown:"상태 확인 필요"};
const subtypes:Record<string,string> = {video_reference:"참고 영상",automation:"자동화 결과",character:"캐릭터 이미지",scene:"씬 이미지",reference:"참고 이미지",clip:"영상 클립",compose:"최종 합성 영상",speech:"음성",music:"배경음악",답변:"에이전트 답변"};
function workDescription(work:Work,works:Work[]) {
  const describe=(w:Work)=>[w.source_label||(w.automatic?"원본 작업":"직접 만든 작품"),w.created_at?new Date(w.created_at).toLocaleString("ko-KR",{year:"numeric",month:"numeric",day:"numeric",hour:"numeric",minute:"2-digit"}):"",w.context].filter(Boolean).join(" · ");
  const description=describe(work);
  return description+(works.some(w=>w.id!==work.id&&w.name===work.name&&describe(w)===description)?` · 구분 ${work.id.slice(0,8)}`:"");
}
function workOption(work:Work,works:Work[],current?:string|null) {
  const description=workDescription(work,works);
  return {id:work.id,label:work.name,description,badge:work.id===current?"현재 연결":undefined,selectedLabel:works.some(w=>w.id!==work.id&&w.name===work.name)?`${work.name} · ${description}`:work.name};
}
function errorText(e:unknown) { const s = e instanceof Error ? e.message : "";return s==="library_changed"?"다른 곳에서 변경되었습니다. 닫고 새로고침한 뒤 다시 시도해 주세요.":message(e); }

function WorkEditor({work,onClose,onSaved}:{work?:Work;onClose:()=>void;onSaved:()=>void}) {
  const id=useId();const [name,setName]=useState(work?.name||"");const [busy,setBusy]=useState(false);const [error,setError]=useState("");
  async function save(){setBusy(true);setError("");try{await api(work?`/library/works/${work.id}`:"/library/works",work?"PUT":"POST",{name:name.trim(),revision:work?.revision||0});onSaved();onClose();}catch(e){setError(errorText(e));}finally{setBusy(false);}}
  return <Modal title={work?"작품 이름 수정":"작품 만들기"} onClose={onClose} footer={<div className="button-row"><Button variant="secondary" onClick={onClose} disabled={busy}>취소</Button><Button disabled={busy||!name.trim()} onClick={save}>{busy?"저장 중…":"저장"}</Button></div>}>
    <div className="production-library-form"><Field label="작품 이름" id={id}>{props=><input {...props} maxLength={120} value={name} onChange={e=>setName(e.target.value)} autoFocus/>}</Field><p className="muted">같은 작품의 대본·씬·이미지·음성·영상을 모아 볼 수 있습니다. 원래 작업 이름과 내용은 유지됩니다.</p>{error&&<p role="alert">{error}</p>}</div>
  </Modal>;
}

function Assign({item,works,onClose,onSaved}:{item:Item;works:Work[];onClose:()=>void;onSaved:()=>void}) {
  const [work,setWork]=useState(item.work_id||"");const [busy,setBusy]=useState(false);const [error,setError]=useState("");
  async function save(){setBusy(true);setError("");try{await api("/library/assignment","PUT",{subject:item.subject,work_id:work||null,revision:item.assignment_revision});onSaved();onClose();}catch(e){setError(errorText(e));}finally{setBusy(false);}}
  return <Modal title="작품 연결" onClose={onClose} footer={<div className="button-row"><Button variant="secondary" disabled={busy} onClick={onClose}>취소</Button><Button disabled={busy} onClick={save}>{busy?"저장 중…":"저장"}</Button></div>}>
    <div className="production-library-form"><strong>{item.source_name===item.title?item.title:`${item.source_name} · ${item.title}`}</strong><SelectCombobox label="연결할 작품" showId={false} value={work} options={[{id:"",label:"작품 미지정"},...works.map(w=>workOption(w,works,item.work_id))]} onChange={setWork}/><p className="muted">{item.subject.startsWith("request:")?"이 작업과 원래 요청에서 다시 만든 작업의 모든 결과·버전을 함께 연결합니다. 제작 연결로 확인되는 자료는 자동 분류됩니다. 여기서는 예외 분류만 변경합니다.":"이 업로드 자료의 작품 분류를 변경합니다. 실제 생성 작업에서 사용한 참조는 유지됩니다."}</p>{!works.length&&<p>먼저 ‘작품 만들기’로 작품을 등록해 주세요.</p>}{error&&<p role="alert">{error}</p>}</div>
  </Modal>;
}

function Preview({item,onClose,onAssign}:{item:Item;onClose:()=>void;onAssign:(item:Item)=>void}) {
  const [detail,setDetail]=useState<Detail|null>(null);const [chosen,setChosen]=useState(item.id);const [error,setError]=useState("");
  useEffect(()=>{let alive=true;setDetail(null);setError("");api<Detail>(`/library/items/${encodeURIComponent(chosen)}`).then(d=>{if(alive)setDetail(d);}).catch(e=>{if(alive)setError(errorText(e));});return()=>{alive=false;};},[chosen]);
  const text=detail?.content==null?"":typeof detail.content==="string"?detail.content:JSON.stringify(detail.content,null,2);
  function download(){const url=URL.createObjectURL(new Blob([text],{type:"text/plain;charset=utf-8"}));const a=document.createElement("a");a.href=url;a.download=`${(detail?.title||"자료").replace(/[<>:"/\\|?*]/g,"_")}.txt`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  return <Modal title={`${detail?.title||item.title} · 자료 확인`} onClose={onClose} className="production-library-preview" footer={<div className="button-row">{detail&&<Button variant="secondary" onClick={()=>onAssign(detail)}>작품 연결 관리</Button>}{detail?.origin&&<a className="button button--secondary" href={detail.origin}>원래 작업에서 수정·확정 →</a>}{detail?.media_url&&<a className="button button--secondary" href={detail.media_url} download>파일 다운로드</a>}{text&&<Button variant="secondary" onClick={download}>내용 다운로드</Button>}</div>}>
    {error?<p role="alert">{error}</p>:!detail?<p role="status">자료를 불러오는 중…</p>:<div className="production-library-detail">
      <div className="production-library-meta"><StatusBadge tone={detail.status==="approved"?"success":"neutral"}>{states[detail.status]||detail.status}</StatusBadge><span>{detail.is_scene_plan?"씬 이미지 제작 계획":subtypes[detail.subtype]||kinds[detail.kind]}</span><span>{detail.work_name||"작품 미지정"}</span></div>
      <p className="muted">{detail.source_name} · {new Date(detail.created_at).toLocaleString("ko-KR")}</p>
      {detail.parent_scene&&<div className="library-related-section"><strong>연결된 원래 씬</strong><Button variant="secondary" onClick={()=>setChosen(detail.parent_scene!.id)}>{detail.parent_scene.title} →</Button></div>}
      {!!detail.related_items?.length&&<section className="library-related-section" aria-label="씬 연결 자료"><h3>연결 자료</h3><p className="muted">이 씬을 바탕으로 만든 이미지 제작 계획입니다.</p>{detail.related_items.map(related=><Button key={related.id} variant="secondary" onClick={()=>setChosen(related.id)}>씬 이미지 제작 계획 · v{related.version} · {new Date(related.created_at).toLocaleDateString("ko-KR")} →</Button>)}</section>}
      {(detail.duplicate_items?.length||0)>1&&<details className="library-related-section"><summary>같은 결과의 저장 위치 {detail.duplicate_items!.length}곳</summary><p className="muted">같은 자동화에서 동일하게 저장된 결과를 하나로 표시합니다. 각 단계의 원본은 유지됩니다.</p><div className="library-related-links">{detail.duplicate_items!.map(source=><Button key={source.id} variant="secondary" aria-pressed={chosen===source.id} onClick={()=>setChosen(source.id)}>{source.title}{chosen===source.id?" · 현재 보기":""}</Button>)}</div></details>}
      {detail.versions.length>1&&<SelectCombobox label="같은 작업의 자료·버전" value={chosen} options={detail.versions.map(v=>({id:v.id,label:`${v.title} · v${v.version} · ${new Date(v.created_at).toLocaleString("ko-KR")}`}))} onChange={setChosen}/>}
      {detail.media_url?(detail.kind==="image"?<img src={detail.media_url} alt={detail.title}/>:detail.kind==="audio"?<audio controls preload="metadata" src={detail.media_url}/>:<video controls preload="metadata" src={detail.media_url}/>):text?<pre tabIndex={0}>{text}</pre>:<p>아직 재생할 파일이 없습니다. 원래 작업에서 진행 상태를 확인해 주세요.</p>}
      {!detail.origin&&<p className="muted">{detail.subject.startsWith("request:")?"원래 작업이 삭제되었지만 보관된 파일은 확인할 수 있습니다.":detail.subtype==="automation"?"자동화 실행에서 저장된 결과입니다.":"직접 업로드한 자료입니다."}</p>}
    </div>}
  </Modal>;
}

function LibraryGlyph({kind}:{kind:string}) {return <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">{kind==="speech"?<><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8"/></>:kind==="character_image"?<><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="12" cy="9" r="3"/><path d="M6 20v-2a6 6 0 0 1 12 0v2"/></>:kind==="image"||kind==="scene_image"?<><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8" cy="8" r="2"/><path d="m3 18 6-6 4 4 4-6 4 6"/></>:kind==="audio"||kind==="music"?<><path d="M9 18V5l11-2v13M9 8l11-2"/><ellipse cx="6" cy="18" rx="3" ry="2"/><ellipse cx="17" cy="16" rx="3" ry="2"/></>:kind==="video"?<><rect x="3" y="4" width="18" height="16" rx="2"/><path d="m10 8 6 4-6 4Z"/></>:kind==="character"?<><circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/></>:kind==="work"?<><path d="M3 6h7l2 3h9v11H3Z"/><path d="M3 6V4h7l2 2h9v3"/></>:kind==="scene"?<><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><path d="M7 10v8h7M14 6h7"/></>:<><path d="M5 3h10l4 4v14H5ZM14 3v5h5M8 12h8M8 16h6"/></>}</svg>;}

function LibraryAssetCard({item,expanded,onOpen}:{item:Item;expanded:boolean;onOpen:()=>void}) {
  const playable=expanded&&["audio","video"].includes(item.kind);
  return <article className={`production-library-card library-asset-${item.kind}`}>
    {playable&&item.media_url&&item.kind==="video"&&<div className="library-card-player"><video controls preload="none" playsInline src={item.media_url} aria-label={`${item.title} 영상 미리보기`}/></div>}
    <button type="button" className="production-library-open" onClick={onOpen} aria-label={`${item.title} 자료 확인`}>
      {item.kind==="image"&&item.media_url&&<div className="library-asset-thumbnail"><img src={item.media_url} alt={item.title} loading="lazy"/></div>}
      <span className="library-card-type muted">{expanded&&<LibraryGlyph kind={item.category}/>}<span>{item.is_scene_plan?"씬 이미지 제작 계획":kinds[item.category]||item.category}</span></span>
      <h2 title={item.title}>{item.title}</h2>
      {expanded&&item.excerpt&&<p className="library-card-excerpt">{item.excerpt}</p>}
      {expanded&&!item.excerpt&&!item.media_url&&<p className="library-card-excerpt muted">{playable?"아직 재생할 파일이 없습니다. 상세에서 진행 상태를 확인하세요.":"자료를 열어 저장된 내용을 확인하세요."}</p>}
      {(item.agent_name||item.source_name)!==item.title&&<span className="library-card-source muted">{item.agent_name||item.source_name}</span>}
      <div className="production-library-meta library-card-footer"><span className="muted">{new Date(item.created_at).toLocaleString("ko-KR",{month:"numeric",day:"numeric",hour:"numeric",minute:"2-digit"})} · v{item.version}</span><StatusBadge tone={item.status==="approved"?"success":item.status==="failed"?"danger":"neutral"}>{states[item.status]||item.status}</StatusBadge></div>
      {!!item.related_count&&<span className="library-card-related">연결 자료 · 이미지 제작 계획 {item.related_count}개</span>}
      {(item.duplicate_count||0)>1&&<span className="library-card-source muted">동일 결과 {item.duplicate_count}곳 · 묶어서 표시</span>}
      {expanded&&<span className="library-card-detail-link">상세 보기 →</span>}
    </button>
    {playable&&item.media_url&&item.kind==="audio"&&<div className="library-card-player"><audio controls preload="none" src={item.media_url} aria-label={`${item.title} 오디오 미리듣기`}/></div>}
  </article>;
}

export function ProductionLibrary({legacyView}:{legacyView?:string}) {
  const [view,setView]=useState<"type"|"work"|"images">(legacyView?"images":"type");const [scene,setScene]=useState(legacyView==="scenes");
  const [kind,setKind]=useState("script");const [work,setWork]=useState("");const [q,setQ]=useState("");const [state,setState]=useState("");const [offset,setOffset]=useState(0);const [tick,setTick]=useState(0);
  const [pageSize,setPageSize]=useState(24);
  const workNavigation=useRef<Record<string,{kind:string;q:string;state:string;offset:number;pageSize:number}>>({});
  const initialWork=useRef<string|null>(null);
  const [data,setData]=useState<Listing>({items:[],total:0,has_more:false,works:[],counts:{},unassigned:0});const [loading,setLoading]=useState(true);const [error,setError]=useState("");
  const [preview,setPreview]=useState<Item|null>(null);const [assign,setAssign]=useState<Item|null>(null);const [editing,setEditing]=useState<Work|"new"|null>(null);const searchId=useId();
  const overview=view==="work"&&!work;
  const activeWork=data.works.find(w=>w.id===work);
  const location=view==="type"?kinds[kind]:work==="unassigned"?"작품 미지정":activeWork?.name||"작품 자료";
  useEffect(()=>{
    let alive=true;let redirect=false;setLoading(true);setError("");
    const timer=setTimeout(()=>api<Listing>(`/library?${new URLSearchParams({kind,work,q,state,offset:String(offset),limit:String(pageSize)})}`).then(d=>{
      if(!alive)return;
      if(initialWork.current===work){
        initialWork.current=null;
        const first=visibleKinds.find(([id])=>d.counts[id]>0)?.[0]||"";
        if(first!==kind){redirect=true;setKind(first);return;}
      }
      if(offset>0&&offset>=d.total){redirect=true;setOffset(d.total?Math.floor((d.total-1)/pageSize)*pageSize:0);return;}
      setData(d);
    }).catch(e=>{if(alive)setError(errorText(e));}).finally(()=>{if(alive&&!redirect)setLoading(false);}),150);
    return()=>{alive=false;clearTimeout(timer);};
  },[kind,work,q,state,offset,pageSize,tick]);
  useEffect(()=>{if(view==="work"&&work&&!initialWork.current&&!loading)workNavigation.current[work]={kind,q,state,offset,pageSize};},[view,work,kind,q,state,offset,pageSize,loading]);
  function refresh(){setTick(v=>v+1);}
  function switchView(value:typeof view){setTick(v=>v+1);initialWork.current=null;setLoading(true);setView(value);setKind(value==="type"?"script":"");setWork("");setQ("");setState("");setOffset(0);}
  function openKind(value:string){setKind(value);setOffset(0);setQ("");setState("");}
  function openWork(value:string){const saved=workNavigation.current[value];initialWork.current=saved?null:value;setLoading(true);setWork(value);setKind(saved?.kind||"");setOffset(saved?.offset||0);setQ(saved?.q||"");setState(saved?.state||"");setPageSize(saved?.pageSize||24);}
  return <section className="production-library">
    <header className="production-library-heading">{view==="work"&&work?<><div><p className="eyebrow">작품별 보관함</p><h1>{location}</h1><p className="muted">유형을 선택해 이 작품의 제작 자료를 확인하세요.</p></div><Button variant="secondary" onClick={()=>switchView("work")}>← 작품 목록</Button></>:<><div><p className="eyebrow">LIBRARY</p><h1>보관함</h1><p className="muted">자료 종류로 찾거나, 한 작품의 제작 자료를 모아 보세요.</p></div>{view==="work"&&<Button onClick={()=>setEditing("new")}>＋ 작품 만들기</Button>}</>}</header>
    {!(view==="work"&&work)&&<nav className="library-view-switch" aria-label="보관함 보기">{([["type","유형별","자료 종류로 찾기"],["work","작품별","작품 단위로 모아보기"]] as const).map(([value,label,help])=><button key={value} type="button" aria-pressed={view===value||(value==="type"&&view==="images")} onClick={()=>switchView(value)}><LibraryGlyph kind={value==="type"?"scene":"work"}/><span><strong>{label}</strong><small>{help}</small></span></button>)}</nav>}
    {view==="type"&&<nav className="library-type-tabs" aria-label="자료 유형">{visibleKinds.map(([id,label])=><button key={id} type="button" aria-pressed={kind===id} onClick={()=>openKind(id)}><LibraryGlyph kind={id}/>{label}<span>{data.counts[id]||0}</span></button>)}</nav>}
    {view==="images"?<div className="production-library-detail"><Button variant="secondary" onClick={()=>switchView("type")}>← 자료 유형</Button><div className="button-row"><Button variant={!scene?"primary":"secondary"} aria-pressed={!scene} onClick={()=>setScene(false)}>캐릭터 이미지</Button><Button variant={scene?"primary":"secondary"} aria-pressed={scene} onClick={()=>setScene(true)}>씬 이미지</Button></div><ImageBrowser key={String(scene)} scene={scene}/></div>:overview?<>
      <div className="production-library-toolbar"><div><h2>내 작품</h2><p className="muted">작품을 선택하면 연결된 제작 자료를 볼 수 있습니다.</p></div><Button variant="secondary" disabled={loading} onClick={refresh}>새로고침</Button></div>
      {error?<p role="alert">{error}</p>:loading?<p role="status">보관함을 불러오는 중…</p>:<>
        {!data.works.length&&<div className="production-library-empty"><strong>아직 표시할 작품이 없습니다.</strong><p>대본과 이어서 만든 자료는 제작 연결을 따라 자동으로 모입니다. 출처를 확인할 수 없는 자료만 작품 미지정에 남습니다.</p><Button onClick={()=>setEditing("new")}>첫 작품 만들기</Button></div>}
        {data.works.length>0&&<div className="library-project-grid">{data.works.map(w=><article key={w.id} className="library-project"><button type="button" className="library-project-open" onClick={()=>openWork(w.id)}><LibraryGlyph kind="work"/><h3>{w.name}</h3><span className="library-work-description muted">{workDescription(w,data.works)}</span><span className="muted">{w.automatic?"제작 연결로 자동 분류":"직접 묶은 작품"}</span><strong>{w.count}개</strong><span>작품 열기 →</span></button>{w.automatic?(w.origin&&<a className="button button--secondary" href={w.origin}>원본 작업 →</a>):<Button variant="secondary" onClick={()=>setEditing(w)} aria-label={`${w.name} 작품 이름 수정`}>이름 수정</Button>}</article>)}</div>}
        <button className="library-unassigned" type="button" onClick={()=>openWork("unassigned")}><span><strong>작품 미지정 자료</strong><small>아직 작품에 연결하지 않은 기존 자료와 업로드 파일</small></span><strong>{data.unassigned}개 →</strong></button>
      </>}
    </>:<>
      {view==="type"&&["character_image","scene_image"].includes(kind)&&<div className="library-location"><Button variant="secondary" onClick={()=>{setScene(kind==="scene_image");setView("images");}}>대표 이미지·버전 모아보기</Button></div>}
      {view==="work"&&<nav className="library-type-tabs library-work-tabs" aria-label="작품 자료 유형">{visibleKinds.map(([id,label])=><button key={id} type="button" aria-pressed={kind===id} disabled={!!initialWork.current} onClick={()=>openKind(id)}><LibraryGlyph kind={id}/>{label}<span>{loading?"…":data.counts[id]||0}</span></button>)}<button type="button" aria-pressed={kind===""} disabled={!!initialWork.current} onClick={()=>openKind("")}><LibraryGlyph kind="work"/>전체 자료<span>{work==="unassigned"?data.unassigned:activeWork?.count||0}</span></button></nav>}
      {work==="unassigned"&&<p className="muted">자료를 열고 ‘작품 연결 관리’에서 분류하세요. 같은 요청의 결과와 모든 버전이 함께 연결됩니다.</p>}
      <div className={`production-library-filters aligned-control-grid${view==="work"?" library-work-filters":""}`}><Field label="자료 검색" id={searchId}>{props=><input {...props} type="search" maxLength={200} placeholder="자료 이름 검색" value={q} onChange={e=>{setQ(e.target.value);setOffset(0);}}/>}</Field>{view!=="work"&&<SelectCombobox label="작품" value={work} options={[{id:"",label:"전체 작품"},{id:"unassigned",label:"작품 미지정"},...data.works.map(w=>workOption(w,data.works))]} onChange={v=>{setWork(v);setOffset(0);}}/>}<SelectCombobox label="상태" value={state} options={[{id:"",label:"전체 상태"},...Object.entries(states).map(([id,label])=>({id,label}))]} onChange={v=>{setState(v);setOffset(0);}} searchable={false}/><SelectCombobox label="페이지당 표시" value={String(pageSize)} options={[12,24,48].map(n=>({id:String(n),label:`${n}개씩`}))} onChange={v=>{setPageSize(Number(v));setOffset(0);}} searchable={false} showId={false}/></div>
      <div className="production-library-toolbar"><p className="muted" role="status">{loading?"자료를 불러오는 중…":`${data.total}개 자료 · 저장 버전 포함`}</p><Button variant="secondary" disabled={loading} onClick={refresh}>새로고침</Button></div>
      {error?<p role="alert">{error}</p>:loading?null:!data.items.length?<div className="production-library-empty"><strong>{view==="work"&&!q&&!state?`이 작품에는 아직 ${kinds[kind]||"표시할"} 자료가 없습니다.`:"표시할 자료가 없습니다."}</strong><p>{q||state?"검색어나 상태 필터를 변경해 주세요.":"다른 유형을 선택해 보세요. 이어서 만든 자료는 기존 제작 연결에 따라 모입니다."}</p></div>:<div className={`production-library-grid${view==="work"?" library-work-assets":""}`}>{data.items.map(item=><LibraryAssetCard key={item.id} item={item} expanded={view==="work"} onOpen={()=>setPreview(item)}/>)}</div>}
      {(offset>0||data.has_more)&&<div className="production-library-pages"><Button variant="secondary" disabled={loading||offset===0} aria-label="이전 페이지" title="이전 페이지" className="library-page-arrow" onClick={()=>setOffset(v=>Math.max(0,v-pageSize))}><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="m15 6-6 6 6 6"/></svg></Button><span>{offset/pageSize+1} / {Math.max(1,Math.ceil(data.total/pageSize))} 페이지</span><Button variant="secondary" disabled={loading||!data.has_more} aria-label="다음 페이지" title="다음 페이지" className="library-page-arrow" onClick={()=>setOffset(v=>v+pageSize)}><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg></Button></div>}
    </>}
    {preview&&<Preview item={preview} onClose={()=>setPreview(null)} onAssign={item=>{setPreview(null);setAssign(item);}}/>}{assign&&<Assign item={assign} works={data.works} onClose={()=>setAssign(null)} onSaved={refresh}/>}{editing&&<WorkEditor work={editing==="new"?undefined:editing} onClose={()=>setEditing(null)} onSaved={refresh}/>}
  </section>;
}
