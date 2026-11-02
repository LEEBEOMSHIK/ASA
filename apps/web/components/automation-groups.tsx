"use client";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, message } from "../lib/registry";
import { Button, Switch } from "./ui";
import { CategoryMoveMenu } from "./agent-groups";
type Catalog={enabled:boolean;revision:number;categories:{id:string;name:string}[];assignments:Record<string,string>;can_manage:boolean};
export function AutomationGroups({items,render}:{items:{id:string;name:string}[];render:(id:string)=>ReactNode}) {
  const [catalog,setCatalog]=useState<Catalog|null>(null);
  const [error,setError]=useState("");const [notice,setNotice]=useState("");const [busy,setBusy]=useState(false);
  const [name,setName]=useState("");const [editing,setEditing]=useState("");const [renamed,setRenamed]=useState("");
  const [search,setSearch]=useState("");const [filter,setFilter]=useState("*");
  const [drag,setDrag]=useState<{kind:"automation"|"category";id:string}|null>(null);const [over,setOver]=useState<string|null>(null);
  async function load(){setCatalog(await api<Catalog>("/automation-categories"));}
  useEffect(()=>{void load().catch(e=>setError(message(e)));},[]);
  const suppressClickUntil=useRef(0);
  const saving=useRef(false);
  const canManage=!!catalog?.can_manage && !!catalog?.enabled;
  async function save(next:Catalog,done:string) {
    if(saving.current)return false;saving.current=true;setBusy(true);setError("");setNotice("");setDrag(null);setOver(null);
    try {setCatalog(await api<Catalog>("/automation-categories","PUT",next));setNotice(done);setEditing("");return true;}
    catch(e){setError(message(e));await load().catch(()=>{});return false;}
    finally{saving.current=false;setBusy(false);}
  }
  function moveAutomation(id:string,target:string){
    if(!catalog || !canManage)return;
    const assignments={...catalog.assignments};if(target)assignments[id]=target;else delete assignments[id];
    void save({...catalog,assignments},"자동화 분류를 저장했습니다.");
  }
  function reorder(id:string,target:string){
    if(!catalog || id===target)return;
    const categories=[...catalog.categories];const item=categories.find(c=>c.id===id);if(!item)return;
    categories.splice(categories.indexOf(item),1);categories.splice(categories.findIndex(c=>c.id===target),0,item);
    void save({...catalog,categories},"카테고리 순서를 저장했습니다.");
  }
  if(!catalog)return <div><p role={error?"alert":"status"}>{error || "카테고리를 불러오는 중입니다…"}</p>{error && <Button variant="secondary" onClick={()=>void load().catch(e=>setError(message(e)))}>다시 불러오기</Button>}<div className="flow-library-grid">{items.map(a=><div key={a.id}>{render(a.id)}</div>)}</div></div>;
  const groups=[{id:"",name:"미분류"},...catalog.categories];
  const matches=items.filter(a=>a.name.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()));
  return <div className="agent-groups automation-groups">
    <div className="automation-category-toggle"><Switch label="카테고리로 정리" checked={!!catalog.enabled} disabled={busy || !catalog.can_manage} onChange={()=>{setFilter("*");void save({...catalog,enabled:!catalog.enabled},catalog.enabled?"분류를 숨겼습니다. 기존 카테고리는 유지됩니다.":"카테고리로 정리를 켰습니다.");}}/></div>
    <div className="category-toolbar"><label>자동화 검색<input value={search} onChange={e=>setSearch(e.target.value)} placeholder="이름으로 검색"/></label>{catalog.enabled && <label>카테고리<select value={filter} onChange={e=>setFilter(e.target.value)}><option value="*">전체</option>{groups.filter(g=>canManage || g.id).map(g=><option key={g.id} value={g.id}>{g.name}</option>)}</select></label>}</div>
    {canManage && <details className="automation-category-manager"><summary>카테고리 관리</summary><form className="category-create" onSubmit={e=>{e.preventDefault();if(name.trim())void save({...catalog,categories:[...catalog.categories,{id:crypto.randomUUID(),name:name.trim()}]},"카테고리를 추가했습니다.").then(ok=>{if(ok)setName("");});}}><label>새 카테고리<input maxLength={60} value={name} onChange={e=>setName(e.target.value)} placeholder="예: 대본 작성"/></label><Button type="submit" disabled={busy || !name.trim()}>카테고리 추가</Button><p className="muted">카드를 잡아 원하는 그룹에 놓으세요. 카드의 ⋯ 메뉴로도 이동할 수 있습니다. 변경하면 바로 저장됩니다.</p></form></details>}
    {error && <p role="alert">{error}</p>}<p className="category-notice" role="status">{busy?"분류를 저장하는 중…":notice}</p>
    {!catalog.enabled ? <div className="flow-library-grid">{matches.map(a=><div className="automation-plain-card" key={a.id}>{render(a.id)}</div>)}{!matches.length && <p className="muted">검색 조건에 맞는 자동화가 없습니다.</p>}</div> : groups.filter(g=>filter==="*" || filter===g.id).map(group=>{
      const index=catalog.categories.findIndex(c=>c.id===group.id);
      const members=items.filter(a=>(catalog.assignments[a.id] || "")===group.id && a.name.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()));

      return <section key={group.id} className={`agent-group ${over===group.id?"is-drop-target":""}`} aria-label={!canManage && !group.id?"자동화":group.name}
        onDragOver={e=>{if(canManage && drag && !busy && (drag.kind==="automation" || group.id)){e.preventDefault();setOver(group.id);e.dataTransfer.dropEffect="move";}}}
        onDragLeave={e=>{if(!e.currentTarget.contains(e.relatedTarget as Node))setOver(null);}}
        onDrop={e=>{e.preventDefault();if(!canManage || !drag || busy)return;if(drag.kind==="automation")moveAutomation(drag.id,group.id);else if(group.id)reorder(drag.id,group.id);setDrag(null);setOver(null);}}>
        {(canManage || group.id) && <div className="category-heading"><h2>{group.name} <span className="muted">{members.length}개</span></h2>
          {canManage && group.id && <div className="category-actions">
            <button type="button" className="category-handle" draggable={!busy} disabled={busy} aria-label={`${group.name} 순서 드래그`} onDragStart={e=>{setDrag({kind:"category",id:group.id});e.dataTransfer.setData("text/plain",group.id);e.dataTransfer.effectAllowed="move";}} onDragEnd={()=>{setDrag(null);setOver(null);}}>⠿ 순서</button>
            <Button variant="secondary" disabled={busy || index===0} onClick={()=>reorder(group.id,catalog.categories[index-1].id)} aria-label={`${group.name} 위로 이동`}>↑</Button>
            <Button variant="secondary" disabled={busy || index>=catalog.categories.length-1} onClick={()=>reorder(catalog.categories[index+1].id,group.id)} aria-label={`${group.name} 아래로 이동`}>↓</Button>
            <Button variant="secondary" disabled={busy} onClick={()=>{setEditing(group.id);setRenamed(group.name);}}>이름 변경</Button>
            <Button variant="secondary" disabled={busy} onClick={()=>{if(!window.confirm("카테고리를 삭제할까요? 포함된 자동화는 미분류로 이동합니다."))return;const assignments=Object.fromEntries(Object.entries(catalog.assignments).filter(([,v])=>v!==group.id));setFilter("*");void save({...catalog,categories:catalog.categories.filter(c=>c.id!==group.id),assignments},"카테고리를 삭제하고 자동화를 미분류로 이동했습니다.");}}>삭제</Button>
          </div>}
        </div>}
        {editing===group.id && group.id && <form className="category-create" onSubmit={e=>{e.preventDefault();void save({...catalog,categories:catalog.categories.map(c=>c.id===group.id?{...c,name:renamed.trim()}:c)},"이름을 저장했습니다.");}}><label>카테고리 이름<input value={renamed} maxLength={60} onChange={e=>setRenamed(e.target.value)}/></label><Button type="submit" disabled={busy || !renamed.trim()}>저장</Button><Button variant="secondary" onClick={()=>setEditing("")}>취소</Button></form>}
        {over===group.id && <p className="category-drop-hint">여기에 놓으면 {drag?.kind==="category"?"이 그룹 앞으로 이동합니다.":"이 그룹으로 분류합니다."}</p>}
        <div className="flow-library-grid">{members.map(a=><div key={a.id}
          className={`grouped-agent ${canManage?"is-draggable":""} ${drag?.kind==="automation" && drag.id===a.id?"is-dragging":""}`}
          draggable={canManage && !busy}
          onDragStartCapture={e=>{
            if(!canManage || busy || (e.target as HTMLElement).closest("select,option,button,input")){e.preventDefault();return;}
            setDrag({kind:"automation",id:a.id});suppressClickUntil.current=Date.now()+1000;
            e.dataTransfer.setData("text/plain",a.id);e.dataTransfer.effectAllowed="move";
            e.dataTransfer.setDragImage(e.currentTarget,24,24);
          }}
          onDragEnd={()=>{setDrag(null);setOver(null);suppressClickUntil.current=Date.now()+300;}}
          onClickCapture={e=>{if(Date.now()<suppressClickUntil.current){e.preventDefault();e.stopPropagation();}}}>
          {canManage && <CategoryMoveMenu name={a.name} current={group.id} groups={groups} disabled={busy} onMove={target=>moveAutomation(a.id,target)}/>}
          {render(a.id)}
        </div>)}</div>
        {!members.length && <p className="category-empty">{search.trim()?"검색 조건에 맞는 자동화가 없습니다.":"카드를 이 그룹으로 끌어 놓거나 ⋯ 메뉴로 이동하세요."}</p>}
      </section>;
    })}
  </div>;
}
