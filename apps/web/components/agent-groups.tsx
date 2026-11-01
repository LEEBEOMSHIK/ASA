"use client";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, message } from "../lib/registry";
import { Button } from "./ui";

type Catalog={revision:number;categories:{id:string;name:string}[];assignments:Record<string,string>;can_manage:boolean};
function CategoryMoveMenu({name,current,groups,disabled,onMove}:{name:string;current:string;groups:{id:string;name:string}[];disabled:boolean;onMove:(id:string)=>void}) {
  const [open,setOpen]=useState(false);
  const root=useRef<HTMLDivElement>(null);
  const trigger=useRef<HTMLButtonElement>(null);
  useEffect(()=>{
    if(!open)return;
    const close=(event:PointerEvent)=>{if(!root.current?.contains(event.target as Node))setOpen(false);};
    document.addEventListener("pointerdown",close);
    return ()=>document.removeEventListener("pointerdown",close);
  },[open]);
  return <div ref={root} className="agent-move-menu" onPointerDown={e=>e.stopPropagation()} onDragStart={e=>e.preventDefault()} onKeyDown={e=>{if(e.key==="Escape"){e.stopPropagation();setOpen(false);trigger.current?.focus();}}}>
    <button ref={trigger} type="button" className="agent-move-trigger" aria-label={`${name} 카테고리 이동`} aria-expanded={open} disabled={disabled} onClick={()=>setOpen(!open)}><svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/></svg></button>
    {open && <div className="agent-move-popover" role="group" aria-label="카테고리 이동"><strong>카테고리 이동</strong><div className="agent-move-options">{groups.map(g=><button type="button" key={g.id} aria-pressed={g.id===current} disabled={disabled} onClick={()=>{setOpen(false);trigger.current?.focus();if(g.id!==current)onMove(g.id);}}><span>{g.name}</span>{g.id===current && <span aria-label="현재 카테고리">✓</span>}</button>)}</div></div>}
  </div>;
}

export function AgentGroups({items,render,manage=false}:{items:{id:string;name:string}[];render:(id:string)=>ReactNode;manage?:boolean}) {
  const [catalog,setCatalog]=useState<Catalog|null>(null);
  const [error,setError]=useState("");const [notice,setNotice]=useState("");const [busy,setBusy]=useState(false);
  const [name,setName]=useState("");const [editing,setEditing]=useState("");const [renamed,setRenamed]=useState("");
  const [search,setSearch]=useState("");const [filter,setFilter]=useState("*");
  const [drag,setDrag]=useState<{kind:"agent"|"category";id:string}|null>(null);const [over,setOver]=useState<string|null>(null);
  async function load(){setCatalog(await api<Catalog>("/agent-categories"));}
  useEffect(()=>{void load().catch(e=>setError(message(e)));},[]);
  const suppressClickUntil=useRef(0);
  const admin=manage && !!catalog?.can_manage;
  async function save(next:Catalog,done:string) {
    if(busy)return;setBusy(true);setError("");setNotice("");setDrag(null);setOver(null);
    try {setCatalog(await api<Catalog>("/agent-categories","PUT",next));setNotice(done);setEditing("");}
    catch(e){setError(message(e));await load().catch(()=>{});}
    finally{setBusy(false);}
  }
  function moveAgent(id:string,target:string){
    if(!catalog || !admin)return;
    const assignments={...catalog.assignments};if(target)assignments[id]=target;else delete assignments[id];
    void save({...catalog,assignments},"에이전트 분류를 저장했습니다.");
  }
  function reorder(id:string,target:string){
    if(!catalog || id===target)return;
    const categories=[...catalog.categories];const item=categories.find(c=>c.id===id);if(!item)return;
    categories.splice(categories.indexOf(item),1);categories.splice(categories.findIndex(c=>c.id===target),0,item);
    void save({...catalog,categories},"카테고리 순서를 저장했습니다.");
  }
  if(!catalog)return <p role={error?"alert":"status"}>{error || "카테고리를 불러오는 중입니다…"}</p>;
  const groups=[{id:"",name:"미분류"},...catalog.categories];
  return <div className="agent-groups">
    <div className="category-toolbar"><label>에이전트 검색<input value={search} onChange={e=>setSearch(e.target.value)} placeholder="이름으로 검색"/></label><label>카테고리<select value={filter} onChange={e=>setFilter(e.target.value)}><option value="*">전체</option>{groups.filter(g=>admin || g.id).map(g=><option key={g.id} value={g.id}>{g.name}</option>)}</select></label></div>
    {admin && <form className="category-create" onSubmit={e=>{e.preventDefault();if(name.trim())void save({...catalog,categories:[...catalog.categories,{id:crypto.randomUUID(),name:name.trim()}]},"카테고리를 추가했습니다.").then(()=>setName(""));}}><label>새 카테고리<input maxLength={60} value={name} onChange={e=>setName(e.target.value)} placeholder="예: 대본 작성"/></label><Button type="submit" disabled={busy || !name.trim()}>카테고리 추가</Button><p className="muted">카드를 잡아 원하는 그룹에 놓으세요. 카드의 ⋯ 메뉴로도 이동할 수 있습니다. 변경하면 바로 저장됩니다.</p></form>}
    {error && <p role="alert">{error}</p>}<p className="category-notice" role="status">{busy?"분류를 저장하는 중…":notice}</p>
    {groups.filter(g=>filter==="*" || filter===g.id).map(group=>{
      const index=catalog.categories.findIndex(c=>c.id===group.id);
      const members=items.filter(a=>(catalog.assignments[a.id] || "")===group.id && a.name.toLocaleLowerCase().includes(search.toLocaleLowerCase()));
      if(!admin && !group.id && !members.length)return null;
      return <section key={group.id} className={`agent-group ${over===group.id?"is-drop-target":""}`} aria-label={!admin && !group.id?"에이전트":group.name}
        onDragOver={e=>{if(admin && drag && !busy && (drag.kind==="agent" || group.id)){e.preventDefault();setOver(group.id);e.dataTransfer.dropEffect="move";}}}
        onDragLeave={e=>{if(!e.currentTarget.contains(e.relatedTarget as Node))setOver(null);}}
        onDrop={e=>{e.preventDefault();if(!admin || !drag || busy)return;if(drag.kind==="agent")moveAgent(drag.id,group.id);else if(group.id)reorder(drag.id,group.id);setDrag(null);setOver(null);}}>
        {(admin || group.id) && <div className="category-heading"><h2>{group.name} <span className="muted">{members.length}개</span></h2>
          {admin && group.id && <div className="category-actions">
            <button type="button" className="category-handle" draggable={!busy} disabled={busy} aria-label={`${group.name} 순서 드래그`} onDragStart={e=>{setDrag({kind:"category",id:group.id});e.dataTransfer.setData("text/plain",group.id);e.dataTransfer.effectAllowed="move";}} onDragEnd={()=>{setDrag(null);setOver(null);}}>⠿ 순서</button>
            <Button variant="secondary" disabled={busy || index===0} onClick={()=>reorder(group.id,catalog.categories[index-1].id)} aria-label={`${group.name} 위로 이동`}>↑</Button>
            <Button variant="secondary" disabled={busy || index>=catalog.categories.length-1} onClick={()=>reorder(catalog.categories[index+1].id,group.id)} aria-label={`${group.name} 아래로 이동`}>↓</Button>
            <Button variant="secondary" disabled={busy} onClick={()=>{setEditing(group.id);setRenamed(group.name);}}>이름 변경</Button>
            <Button variant="secondary" disabled={busy} onClick={()=>{if(!window.confirm("카테고리를 삭제할까요? 포함된 에이전트는 미분류로 이동합니다."))return;const assignments=Object.fromEntries(Object.entries(catalog.assignments).filter(([,v])=>v!==group.id));setFilter("*");void save({...catalog,categories:catalog.categories.filter(c=>c.id!==group.id),assignments},"카테고리를 삭제하고 에이전트를 미분류로 이동했습니다.");}}>삭제</Button>
          </div>}
        </div>}
        {editing===group.id && group.id && <form className="category-create" onSubmit={e=>{e.preventDefault();void save({...catalog,categories:catalog.categories.map(c=>c.id===group.id?{...c,name:renamed.trim()}:c)},"이름을 저장했습니다.");}}><label>카테고리 이름<input value={renamed} maxLength={60} onChange={e=>setRenamed(e.target.value)}/></label><Button type="submit" disabled={busy || !renamed.trim()}>저장</Button><Button variant="secondary" onClick={()=>setEditing("")}>취소</Button></form>}
        {over===group.id && <p className="category-drop-hint">여기에 놓으면 {drag?.kind==="category"?"이 그룹 앞으로 이동합니다.":"이 그룹으로 분류합니다."}</p>}
        <div className="catalog-grid">{members.map(a=><div key={a.id}
          className={`grouped-agent ${admin?"is-draggable":""} ${drag?.kind==="agent" && drag.id===a.id?"is-dragging":""}`}
          draggable={admin && !busy}
          onDragStartCapture={e=>{
            if(!admin || busy || (e.target as HTMLElement).closest("select,option,button,input")){e.preventDefault();return;}
            setDrag({kind:"agent",id:a.id});suppressClickUntil.current=Date.now()+1000;
            e.dataTransfer.setData("text/plain",a.id);e.dataTransfer.effectAllowed="move";
            e.dataTransfer.setDragImage(e.currentTarget,24,24);
          }}
          onDragEnd={()=>{setDrag(null);setOver(null);suppressClickUntil.current=Date.now()+300;}}
          onClickCapture={e=>{if(Date.now()<suppressClickUntil.current){e.preventDefault();e.stopPropagation();}}}>
          {admin && <CategoryMoveMenu name={a.name} current={group.id} groups={groups} disabled={busy} onMove={target=>moveAgent(a.id,target)}/>}
          {render(a.id)}
        </div>)}</div>
        {!members.length && <p className="category-empty">{admin?"이 그룹으로 에이전트를 옮겨 보세요.":"표시할 에이전트가 없습니다."}</p>}
      </section>;
    })}
  </div>;
}
