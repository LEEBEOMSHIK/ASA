"use client";
import {useState} from "react";
import {Button, DisclosureIcon, Field} from "./ui";

export type AccessRole={id:string;name:string;enabled:boolean;permissions:string[];revision:number};
export function AccessRoleList({roles,selectedId,busy,onSelect,pageSize=10}:{roles:AccessRole[];selectedId?:string;busy:boolean;onSelect:(role:AccessRole)=>void;pageSize?:number}){
  const [query,setQuery]=useState("");
  const [status,setStatus]=useState("all");
  const [page,setPage]=useState(1);
  const filtered=roles.filter(role=>role.name.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())&&(status==="all"||role.enabled===(status==="enabled")));
  const pages=Math.max(1,Math.ceil(filtered.length/pageSize));
  const current=Math.min(page,pages);
  const visible=filtered.slice((current-1)*pageSize,current*pageSize);
  return <div className="access-role-browser settings-content">
    <div className="access-role-filters compact-filter-fields">
      <Field id="role-search" label="역할 검색">{props=><input {...props} type="search" placeholder="역할 이름 검색" value={query} onChange={e=>{setQuery(e.target.value);setPage(1);}}/>}</Field>
      <Field id="role-status" label="사용 상태">{props=><select {...props} value={status} onChange={e=>{setStatus(e.target.value);setPage(1);}}><option value="all">전체 상태</option><option value="enabled">사용 중</option><option value="disabled">사용 중지</option></select>}</Field>
    </div>
    <p className="helper-text" role="status">검색 결과 {filtered.length}개 · 전체 {roles.length}개 · 페이지당 {pageSize}개</p>
    <div className="access-role-rows access-directory" aria-label="역할 목록">
      <div className="access-directory-head access-role-columns" aria-hidden="true"><span>역할 이름</span><span>사용 상태</span><span>접근 메뉴</span><span/></div>
      {visible.map(role=><button type="button" key={role.id} className="access-role-row access-role-columns" aria-pressed={selectedId===role.id} disabled={busy} onClick={()=>onSelect(role)}>
        <strong>{role.name}</strong><span className="access-directory-cell" data-label="사용 상태">{role.enabled?"사용 중":"사용 중지"}</span><span className="access-directory-cell" data-label="접근 메뉴">{role.permissions.filter(p=>p.endsWith(".view")).length}개 메뉴</span><DisclosureIcon/>
      </button>)}
      {!visible.length&&<p className="access-role-empty">{roles.length?"조건에 맞는 역할이 없습니다.":"등록된 역할이 없습니다. 역할을 추가해 주세요."}</p>}
    </div>
    <nav className="access-role-pagination" aria-label="역할 목록 페이지">
      <Button variant="secondary" disabled={busy||current===1} onClick={()=>setPage(current-1)}><span className="access-previous"><DisclosureIcon/></span>이전</Button>
      <span aria-live="polite">{current} / {pages} 페이지</span>
      <Button variant="secondary" disabled={busy||current===pages} onClick={()=>setPage(current+1)}>다음<DisclosureIcon/></Button>
    </nav>
  </div>;
}
