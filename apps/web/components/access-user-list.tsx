"use client";
import {useState} from "react";
import {Button,DisclosureIcon,Field} from "./ui";
import type {AccessRole} from "./access-role-list";
type User={id:string;username:string;display_name:string;role_id:string;enabled:boolean;revision:number};
export function AccessUserList({users,roles,selectedId,busy,onSelect}:{users:User[];roles:AccessRole[];selectedId?:string;busy:boolean;onSelect:(user:User)=>void}){
 const [query,setQuery]=useState("");const [role,setRole]=useState("all");const [status,setStatus]=useState("all");const [page,setPage]=useState(1);
 const roleMap=new Map(roles.map(r=>[r.id,r]));
 const filtered=users.filter(u=>`${u.display_name} ${u.username}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())&&(role==="all"||u.role_id===role)&&(status==="all"||u.enabled===(status==="enabled")));
 const pages=Math.max(1,Math.ceil(filtered.length/10));const current=Math.min(page,pages);const visible=filtered.slice((current-1)*10,current*10);
 return <div className="access-role-browser settings-content">
  <div className="access-user-filters compact-filter-fields">
   <Field id="user-search" label="사용자 검색">{props=><input {...props} type="search" placeholder="이름 또는 로그인 아이디" value={query} onChange={e=>{setQuery(e.target.value);setPage(1);}}/>}</Field>
   <Field id="user-role-filter" label="역할">{props=><select {...props} value={role} onChange={e=>{setRole(e.target.value);setPage(1);}}><option value="all">전체 역할</option>{roles.map(r=><option key={r.id} value={r.id}>{r.name}{r.enabled?"":" · 사용 중지"}</option>)}</select>}</Field>
   <Field id="user-status-filter" label="계정 상태">{props=><select {...props} value={status} onChange={e=>{setStatus(e.target.value);setPage(1);}}><option value="all">전체 상태</option><option value="enabled">사용 중</option><option value="disabled">사용 중지</option></select>}</Field>
  </div>
  <p className="helper-text" role="status">검색 결과 {filtered.length}명 · 전체 {users.length}명 · 페이지당 10명</p>
  <div className="access-role-rows access-directory" aria-label="사용자 목록">
   <div className="access-directory-head access-user-columns" aria-hidden="true"><span>사용자</span><span>역할</span><span>계정 상태</span><span/></div>
   {visible.map(u=><button key={u.id} type="button" className="access-role-row access-user-columns" aria-pressed={selectedId===u.id} disabled={busy} onClick={()=>onSelect(u)}><span className="access-user-name"><strong>{u.display_name}</strong><span>{u.username}</span></span><span className="access-directory-cell" data-label="역할">{roleMap.get(u.role_id)?.name||"역할 미확인"}{roleMap.get(u.role_id)?.enabled===false&&" · 역할 사용 중지"}</span><span className="access-directory-cell" data-label="계정 상태">{u.enabled?"사용 중":"사용 중지"}</span><DisclosureIcon/></button>)}
   {!visible.length&&<p className="access-role-empty">{users.length?"조건에 맞는 사용자가 없습니다.":"등록된 사용자가 없습니다. 사용자를 추가해 주세요."}</p>}
  </div>
  <nav className="access-role-pagination" aria-label="사용자 목록 페이지"><Button variant="secondary" disabled={busy||current===1} onClick={()=>setPage(current-1)}><span className="access-previous"><DisclosureIcon/></span>이전</Button><span aria-live="polite">{current} / {pages} 페이지</span><Button variant="secondary" disabled={busy||current===pages} onClick={()=>setPage(current+1)}>다음<DisclosureIcon/></Button></nav>
 </div>;
}
