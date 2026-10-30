"use client";
import { useEffect, useId, useRef, useState } from "react";
type SelectOption = {id:string;label:string};

export function SelectCombobox({options,value,onChange,loading=false,label,searchable=true,hint,caption}: {options:SelectOption[];value:string;onChange:(id:string)=>void;loading?:boolean;label:string;searchable?:boolean;hint?:string;caption?:string}) {
 const id=useId(); const [open,setOpen]=useState(false); const [query,setQuery]=useState(""); const [active,setActive]=useState(0);
 const list=useRef<HTMLDivElement>(null);
 const filtered=options.filter(m=>`${m.id} ${m.label}`.toLowerCase().includes(searchable?query.toLowerCase():""));
 const selected=options.find(m=>m.id===value);
 useEffect(()=>{list.current?.querySelector('[data-active="true"]')?.scrollIntoView({block:"nearest"});},[active]);
 function choose(model:SelectOption){onChange(model.id);setQuery("");setOpen(false);}
 return <div className="select-combobox" onBlur={e=>{if(!e.currentTarget.contains(e.relatedTarget)){setOpen(false);setQuery("");}}}>
  <label htmlFor={id}>{label}</label>
  <div className="select-combobox-control"><input id={id} role="combobox" aria-autocomplete={searchable?"list":"none"} readOnly={!searchable} aria-expanded={open} aria-controls={`${id}-list`} aria-activedescendant={open&&filtered[active]?`${id}-option-${active}`:undefined} aria-describedby={hint?`${id}-hint`:undefined} autoComplete="off" disabled={loading} placeholder={loading?"목록 확인 중…":`${label} 또는 검색`} value={open&&searchable?query:(selected?.label||"")} onClick={()=>{setOpen(searchable?true:!open);setQuery("");setActive(0);}} onFocus={()=>{if(searchable)setOpen(true);setQuery("");setActive(0);}} onChange={e=>{setQuery(e.target.value);setActive(0);setOpen(true);onChange("");}} onKeyDown={e=>{
   if(e.nativeEvent.isComposing)return;
   if(e.key==="ArrowDown"||e.key==="ArrowUp"){e.preventDefault();setOpen(true);setActive(n=>Math.max(0,Math.min(filtered.length-1,n+(e.key==="ArrowDown"?1:-1))));}
   else if(e.key==="Enter"||(!searchable&&e.key===" ")){e.preventDefault();if(open&&filtered[active])choose(filtered[active]);else setOpen(true);}
   else if(e.key==="Escape"){e.preventDefault();setOpen(false);setQuery("");}
  }}/><span aria-hidden="true"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m6 9 6 6 6-6"/></svg></span></div>
  {open&&<div className="select-combobox-popup"><div className="select-combobox-caption">{caption||label} <span>{filtered.length}개</span></div><div ref={list} id={`${id}-list`} role="listbox" aria-label={`${label} 목록`} className="select-combobox-options">{filtered.map((m,i)=><div key={m.id} id={`${id}-option-${i}`} role="option" aria-selected={value===m.id} data-active={active===i} onMouseDown={e=>e.preventDefault()} onMouseEnter={()=>setActive(i)} onClick={()=>choose(m)}><span><strong>{m.label}</strong>{searchable&&m.label!==m.id&&<small>{m.id}</small>}</span>{value===m.id&&<span aria-hidden="true">✓</span>}</div>)}</div>{!filtered.length&&<p role="status">일치하는 항목이 없습니다.</p>}</div>}
  {hint&&<p id={`${id}-hint`} className="muted">{hint}</p>}
 </div>;
}
