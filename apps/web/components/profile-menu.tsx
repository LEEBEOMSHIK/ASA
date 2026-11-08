"use client";
import { useEffect, useId, useRef, useState } from "react";
import { api, message, ApiError } from "../lib/registry";
import { prepareAvatar } from "../lib/prepare-avatar";
import { Button, Field } from "./ui";
import { ImageDropzone } from "./image-dropzone";
import { ThemeSelect } from "./theme-provider";
import { useNavigationPreferences } from "./navigation-preferences";

type Profile = {display_name:string; avatar:string|null; revision:number; workspace_id:string; roles:string[]};

function onBackdrop(event: React.MouseEvent<HTMLDialogElement>) {
  if (event.target !== event.currentTarget) return false;
  const rect = event.currentTarget.getBoundingClientRect();
  return event.clientX < rect.left || event.clientX >= rect.right ||
    event.clientY < rect.top || event.clientY >= rect.bottom;
}

export function ProfileMenu({compact=false,onLogout,disabled=false}:{compact?:boolean;onLogout:()=>void|Promise<void>;disabled?:boolean}) {
  const inputId=useId();
  const navigationPreferences=useNavigationPreferences();
  const [profile,setProfile]=useState<Profile|null>(null);
  const [name,setName]=useState(""),[avatar,setAvatar]=useState<string|null>(null);
  const [editing,setEditing]=useState(false),[error,setError]=useState(""),[busy,setBusy]=useState(false);
  const dialog=useRef<HTMLDialogElement>(null),trigger=useRef<HTMLButtonElement>(null);
  const pressedBackdrop = useRef(false);
  useEffect(()=>{
    let live=true;
    const load=()=>{api<Profile>("/profile").then(p=>{if(live)setProfile(p);}).catch(e=>{if(live)setError(message(e));});};
    load();window.addEventListener("asa-profile-saved",load);
    return ()=>{live=false;window.removeEventListener("asa-profile-saved",load);};
  },[]);
  const role=profile?.roles.includes("owner")?"소유자":profile?.roles.includes("admin")?"관리자":"사용자";
  function badge(photo:string|null|undefined,text:string){
    return <span className="profile-avatar" aria-hidden="true">{photo?<img src={photo} alt=""/>:Array.from(text)[0]?.toLocaleUpperCase()||"●"}</span>;
  }
  async function choosePhoto(files: FileList) {
    if (busy || !files.length) return;
    if (files.length !== 1) { setError("사진을 한 장만 선택해 주세요."); return; }
    setBusy(true); setError("");
    try { setAvatar(await prepareAvatar(files[0])); }
    catch (err) { setError(err instanceof Error ? err.message : "사진을 읽지 못했습니다."); }
    finally { setBusy(false); }
  }
  function open(edit: boolean, b: HTMLButtonElement){
    const d=dialog.current;
    trigger.current=b;
    pressedBackdrop.current = false;
    if(!d||!b)return;
    setEditing(edit);
    if (edit && profile) { setName(profile.display_name); setAvatar(profile.avatar); setError(""); }
    const rect=b.getBoundingClientRect();
    d.style.setProperty("--profile-left",Math.max(8,Math.min(rect.left,window.innerWidth-300))+"px");
    d.style.setProperty("--profile-bottom",Math.max(8,Math.min(window.innerHeight-rect.top+4,window.innerHeight-260))+"px");
    d.showModal();
  }
  async function save(){
    if(!profile||busy||!name.trim())return;
    setBusy(true);setError("");
    try {
      const saved=await api<Profile>("/profile","PUT",{display_name:name.trim(),avatar,revision:profile.revision});
      setProfile(saved);window.dispatchEvent(new Event("asa-profile-saved"));dialog.current?.close();
    }catch(e){if(e instanceof ApiError && e.status===409){setProfile(await api<Profile>("/profile"));setError("다른 화면에서 프로필을 변경했습니다. 다시 열어 최신 정보를 확인하세요.");setEditing(false);}else setError(message(e));}
    finally{setBusy(false);}
  }
  return <div className={compact ? "account-footer is-compact" : "account-footer"}>
    <button type="button" className="profile-trigger" title="내 프로필 편집" aria-label="내 프로필 편집" aria-haspopup="dialog" disabled={disabled || !profile} onClick={e=>open(true,e.currentTarget)}>
      {badge(profile?.avatar,profile?.display_name||"")}{!compact&&<span className="profile-identity"><strong>{profile?.display_name||"내 프로필"}</strong><small>{role}</small></span>}
    </button>
    <button type="button" className="profile-trigger profile-settings" title="설정" aria-label="설정" aria-haspopup="dialog"
      disabled={disabled} onClick={e=>open(false,e.currentTarget)}>
      <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"><path d="m10 3-.6 2.2-1.6.9-2.2-.6-2 3.4 1.6 1.6v2.1l-1.6 1.6 2 3.5 2.2-.6 1.6.9.6 2.2h4l.6-2.2 1.6-.9 2.2.6 2-3.5-1.6-1.6v-2.1L20 9l-2-3.5-2.2.6-1.6-.9L13.6 3Z"/><circle cx="11.8" cy="11.7" r="3"/></svg>
    </button>
    <dialog ref={dialog} className={editing?"profile-panel profile-edit":"profile-panel"} aria-label={editing?"내 프로필 편집":"설정"}
      onClose={()=>trigger.current?.focus()} onCancel={e=>{if(busy)e.preventDefault();}}
      onPointerDownCapture={event => {
        pressedBackdrop.current = event.isPrimary && event.button === 0 && onBackdrop(event);
      }}
      onPointerCancel={() => { pressedBackdrop.current = false; }}
      onClick={event => {
        const dismiss = pressedBackdrop.current && !busy && onBackdrop(event);
        pressedBackdrop.current = false;
        if (dismiss) event.currentTarget.close();
      }}>
      <div className="profile-body"><div className="card-heading"><strong>{editing?"내 프로필":"설정"}</strong><Button variant="secondary" disabled={busy} onClick={()=>dialog.current?.close()} aria-label="프로필 닫기">닫기</Button></div>
      {error&&<p role="alert" className="field-error">{error}</p>}
      {editing&&profile?<><Field label="표시 이름" id={inputId}>{p=><input {...p} maxLength={40} value={name} onChange={e=>setName(e.target.value)}/>}</Field>
        <div className="field profile-photo-field"><strong>프로필 사진</strong>
          <ImageDropzone id={inputId+"-photo"} label="프로필 사진" image={avatar} disabled={busy} onFiles={choosePhoto}/>
        </div>
        {avatar&&<Button variant="secondary" onClick={()=>setAvatar(null)} disabled={busy}>기본 아이콘 사용</Button>}
        <small>권한 · {role}</small><small>작업 공간 ID · {profile.workspace_id}</small>
        <Button disabled={busy||!name.trim()} onClick={save}>저장</Button></>:<>
        <ThemeSelect/>
        <Button variant="secondary" disabled={!navigationPreferences.available} onClick={()=>{dialog.current?.close();navigationPreferences.open("home",trigger.current);}}>메뉴 강조색</Button>
        <Button variant="secondary" onClick={()=>{dialog.current?.close();void onLogout();}}>로그아웃</Button></>}
      </div></dialog>
  </div>;
}
