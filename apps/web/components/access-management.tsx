"use client";
import {useEffect,useState,useRef} from "react";
import {api,message} from "../lib/registry";
import {ActionIcon,Button,Field,Switch} from "./ui";
import "./access-management.css";
import {AccessAuditList} from "./access-audit-list";
import {AccessUserList} from "./access-user-list";
import {AccessRoleList} from "./access-role-list";
import {AccessPermissionMatrix,toggleAccessPermission,type AccessMenu} from "./access-permission-matrix";

type Role={id:string;name:string;enabled:boolean;permissions:string[];revision:number};
type User={id:string;username:string;display_name:string;role_id:string;enabled:boolean;revision:number};
type Data={roles:Role[];users:User[];catalog:AccessMenu[];can_edit:boolean;user_id:string;audit:{actor:string;event:string;target:string;created_at:string}[]};
export function AccessManagement(){
  const userHeading=useRef<HTMLHeadingElement>(null);
  const [data,setData]=useState<Data|null>(null);
  const [tab,setTab]=useState("roles");
  const [role,setRole]=useState<Role|null>(null);
  const roleHeading=useRef<HTMLHeadingElement>(null);
  useEffect(()=>{if(role){roleHeading.current?.focus({preventScroll:true});roleHeading.current?.scrollIntoView({block:"start"});}},[role?.id]);
  const [user,setUser]=useState<User|null>(null);
  const [password,setPassword]=useState("");
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  async function load(){setData(await api<Data>("/admin/access"));}
  useEffect(()=>{load().catch(e=>setError(message(e)));},[]);
  async function save(kind:"roles"|"users"){
    const value=kind==="roles"?role:user;if(!value)return;
    setBusy(true);setError("");setNotice("");
    try{
      const {id,...body}=value;
      await api(`/admin/access/${kind}/${id}`,"PUT",{...body,...(kind==="users"&&password?{password}: {})});
      setPassword("");setRole(null);setUser(null);await load();setNotice("저장했습니다. 변경된 권한은 다음 요청부터 적용됩니다.");
    }catch(e){setError(message(e));}finally{setBusy(false);}
  }
  function toggle(menu:string,action:string){
    setRole(current=>current&&{...current,permissions:toggleAccessPermission(current.permissions,menu,action)});
  }
  useEffect(()=>{if(user){userHeading.current?.focus({preventScroll:true});userHeading.current?.scrollIntoView({block:"start"});}},[user?.id]);
  const editable=!!data?.can_edit&&!busy;
  return <div className="access-management"><header><h1>사용자·권한 관리</h1><p className="muted">역할별 메뉴와 실행 권한을 설정하고 사용자에게 부여합니다. 자료는 같은 작업 공간에서 공유됩니다.</p></header>
    <div className="access-tabs" role="tablist" aria-label="권한 관리 구분">{[["roles","역할·메뉴"],["users","사용자"],["audit","변경 이력"]].map(([id,label])=><Button key={id} variant="secondary" role="tab" id={`access-tab-${id}`} aria-controls="access-panel" aria-selected={tab===id} disabled={busy} onClick={()=>{setTab(id);setRole(null);setUser(null);setPassword("");setError("");}}><ActionIcon kind={id==="roles"?"settings":id==="users"?"edit":"document"}/>{label}</Button>)}</div>
    {error&&<p role="alert" className="field-error">{error}</p>}{notice&&<p role="status">{notice}</p>}
    {!data?<p role="status">권한 정보를 불러오는 중입니다…</p>:<section id="access-panel" role="tabpanel" aria-labelledby={`access-tab-${tab}`}>
      {tab==="roles"&&<><div className="access-heading"><h2>역할</h2><Button disabled={!editable} onClick={()=>{setRole({id:crypto.randomUUID(),name:"",enabled:true,permissions:[],revision:0});setNotice("");}}><ActionIcon kind="add"/>역할 추가</Button></div>
        <p className="access-owner-note"><ActionIcon kind="confirm"/><span><strong>소유자 · 보호됨</strong> 전체 권한을 유지하며 변경·중지할 수 없습니다.</span></p>
        <AccessRoleList roles={data.roles} selectedId={role?.id} busy={busy} onSelect={r=>{setRole({...r,permissions:[...r.permissions]});setNotice("");}}/>
        {role&&<form onSubmit={e=>{e.preventDefault();void save("roles");}} className="card card--content settings-content access-editor"><h2 ref={roleHeading} tabIndex={-1}>{role.revision?"역할 수정":"새 역할"}</h2><Field id="role-name" label="역할 이름" required>{props=><input {...props} required maxLength={60} value={role.name} disabled={!editable} onChange={e=>setRole({...role,name:e.target.value})}/>}</Field><Switch checked={role.enabled} disabled={!editable} label="이 역할 사용" onChange={()=>setRole({...role,enabled:!role.enabled})}/><p className="helper-text">메뉴 접근을 끄면 해당 메뉴의 기능 권한도 해제됩니다. 역할을 중지하면 이 역할의 사용자는 접근할 수 없습니다.</p>
          <div className="access-role-context"><div><span className="helper-text">편집 중인 역할</span><strong>{role.name||"새 역할"}</strong></div><span>{role.permissions.filter(p=>p.endsWith(".view")).length} / {data.catalog.length}개 메뉴 접근</span></div>
          <AccessPermissionMatrix catalog={data.catalog} permissions={role.permissions} editable={editable} onToggle={toggle}/>
          <div className="actions"><Button type="submit" disabled={!editable}><ActionIcon kind="save"/>역할 저장</Button><Button variant="secondary" disabled={busy} onClick={()=>setRole(null)}><ActionIcon kind="close"/>닫기</Button></div></form>}
      </>}
      {tab==="users"&&<><div className="access-heading"><h2>사용자</h2><Button disabled={!editable||!data.roles.some(r=>r.enabled)} onClick={()=>{setPassword("");setUser({id:crypto.randomUUID(),username:"",display_name:"",role_id:data.roles.find(r=>r.enabled&&r.name==="제작자")?.id||data.roles.find(r=>r.enabled)!.id,enabled:true,revision:0});}}><ActionIcon kind="add"/>사용자 추가</Button></div>
        <p className="helper-text">소유자 접근 키는 공유하지 않고 각 사용자에게 별도 계정을 만드세요. 계정 중지 또는 비밀번호 변경 시 기존 로그인이 해제됩니다.</p>
        <AccessUserList users={data.users} roles={data.roles} selectedId={user?.id} busy={busy} onSelect={u=>{setUser({...u});setPassword("");setNotice("");}}/>
        {user&&<form className="card card--content settings-content access-editor" onSubmit={e=>{e.preventDefault();void save("users");}}><h2 ref={userHeading} tabIndex={-1}>{user.revision?"사용자 수정":"새 사용자"}</h2>{user.id===data.user_id&&<p className="notice">자신의 역할·계정 상태는 다른 관리자 또는 소유자에게 변경을 요청하세요.</p>}
          <Field id="access-username" label="로그인 아이디" hint="영문·숫자·마침표·밑줄·하이픈, 3~64자" required>{props=><input {...props} required autoComplete="off" pattern="[a-zA-Z0-9][a-zA-Z0-9._\-]{2,63}" maxLength={64} disabled={!editable} value={user.username} onChange={e=>setUser({...user,username:e.target.value})}/>}</Field>
          <Field id="access-display-name" label="표시 이름" required>{props=><input {...props} required maxLength={80} disabled={!editable} value={user.display_name} onChange={e=>setUser({...user,display_name:e.target.value})}/>}</Field>
          <Field id="access-role" label="역할" required>{props=><select {...props} value={user.role_id} disabled={!editable} onChange={e=>setUser({...user,role_id:e.target.value})}>{data.roles.map(r=><option key={r.id} value={r.id} disabled={!r.enabled}>{r.name}{r.enabled?"":" · 사용 중지"}</option>)}</select>}</Field>
          <Field id="access-password" label={user.revision?"새 비밀번호":"비밀번호"} hint={user.revision?"변경할 때만 12~128자로 입력하세요.":"12~128자로 입력하세요."} required={!user.revision}>{props=><input {...props} type="password" autoComplete="new-password" required={!user.revision} minLength={12} maxLength={128} disabled={!editable} value={password} onChange={e=>setPassword(e.target.value)}/>}</Field>
          <Switch checked={user.enabled} disabled={!editable} label="이 계정 사용" onChange={()=>setUser({...user,enabled:!user.enabled})}/><div className="actions"><Button type="submit" disabled={!editable||user.id===data.user_id}><ActionIcon kind="save"/>사용자 저장</Button><Button variant="secondary" disabled={busy} onClick={()=>{setUser(null);setPassword("");}}><ActionIcon kind="close"/>닫기</Button></div>
        </form>}
      </>}
      {tab==="audit"&&<AccessAuditList/>}
    </section>}
  </div>;
}
