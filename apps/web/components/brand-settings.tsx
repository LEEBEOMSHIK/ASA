"use client";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, message } from "../lib/registry";
import { Button, Field, SettingsSection } from "./ui";
import { ImageDropzone } from "./image-dropzone";
import { prepareAvatar } from "../lib/prepare-avatar";
import { useDirtyGuard } from "./registry-shell";
import { BrandPreview, type Branding } from "./studio-brand";

function CancelIcon({label,disabled,onClick}: {label:string;disabled:boolean;onClick:()=>void}) {
  return <span className="brand-icon-action"><Button variant="secondary" className="brand-cancel-icon" aria-label={label} disabled={disabled} onClick={onClick}><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M3 10h11a6 6 0 0 1 0 12M3 10l6-6M3 10l6 6"/></svg></Button><span className="brand-action-hint" aria-hidden="true">{label}</span></span>;
}

export function BrandSettings() {
  const [saved,setSaved]=useState<Branding|null>(null),[draft,setDraft]=useState<Branding|null>(null);
  const [error,setError]=useState(""),[notice,setNotice]=useState("");
  const [busy,setBusy]=useState(false),[reading,setReading]=useState(false);
  const sequence=useRef(0);
  const dirty=!!draft && !!saved && (draft.name!==saved.name || draft.logo!==saved.logo);
  const setDirty=useDirtyGuard();
  useEffect(()=>{setDirty(dirty);return ()=>setDirty(false);},[dirty,setDirty]);
  useEffect(()=>{if(!dirty)return;const warn=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue="";};window.addEventListener("beforeunload",warn);return ()=>window.removeEventListener("beforeunload",warn);},[dirty]);
  async function load(){try{const value=await api<Branding>("/branding");setSaved(value);setDraft(value);setError("");}catch(e){setError(message(e));}}
  useEffect(()=>{void load();},[]);
  async function choose(files: FileList|null){
    if(!files?.length || busy)return;
    if(files.length!==1){setError("로고 이미지를 한 장만 선택하세요.");return;}
    const id=++sequence.current;setReading(true);setError("");setNotice("");
    try{const logo=await prepareAvatar(files[0]);if(id===sequence.current)setDraft(old=>old?{...old,logo}:old);}
    catch(e){if(id===sequence.current)setError(e instanceof Error?e.message:"이미지를 읽을 수 없습니다.");}
    finally{if(id===sequence.current){setReading(false);}}
  }
  function cancel(imageOnly: boolean){
    if(!saved || busy)return;
    sequence.current+=1;setReading(false);setError("");
    setDraft(old=>imageOnly && old?{...old,logo:saved.logo}:saved);
    setNotice(imageOnly?"이미지 변경을 취소했습니다.":"변경을 취소하고 저장된 설정으로 되돌렸습니다.");
  }
  async function save(){
    if(!draft || busy || reading)return;setBusy(true);setError("");setNotice("");
    try{const value=await api<Branding>("/branding","PUT",draft);setSaved(value);setDraft(value);setNotice("브랜드 설정을 저장했습니다. 메뉴에 반영되었습니다.");window.dispatchEvent(new Event("asa-branding-saved"));}
    catch(e){setError(e instanceof ApiError && e.status===409?"다른 관리자가 설정을 변경했습니다. 최신 설정을 다시 불러온 후 수정하세요.":message(e));}
    finally{setBusy(false);}
  }
  return <div className="brand-settings"><header><h1>브랜드 설정</h1><p className="muted">이 작업 공간의 메뉴에 표시할 이름과 로고를 관리합니다. 저장하면 사용자 화면에도 적용됩니다.</p></header>
    {error && <div role="alert" className="notice"><p>{error}</p><Button variant="secondary" disabled={busy || reading} onClick={()=>{if(!dirty || window.confirm("저장하지 않은 변경을 버리고 최신 설정을 불러올까요?"))void load();}}>최신 설정 불러오기</Button></div>}
    {!draft?<p role="status">설정을 불러오는 중입니다…</p>:<>
      <SettingsSection title="이름과 로고" description="저장한 로고는 메뉴와 브라우저 탭 아이콘에 적용됩니다. 로그인 전 화면과 탭 제목에는 기본 서비스 이름이 표시됩니다.">
        <Field id="brand-name" label="서비스 이름" hint="메뉴 공간에 맞춰 긴 이름은 줄여 표시합니다.">{props=><input {...props} maxLength={40} value={draft.name} disabled={busy} onChange={e=>{setDraft({...draft,name:e.target.value});setNotice("");}}/>}</Field>
        <div className="field"><label htmlFor="brand-logo">로고 이미지</label>
          <ImageDropzone id="brand-logo" label="로고 이미지" image={draft.logo} disabled={busy || reading} onFiles={choose}/>
          <div className="brand-actions">
            {draft.logo && <Button variant="secondary" disabled={busy || reading} onClick={()=>{setDraft({...draft,logo:null});setNotice("");}}>기본 문자 로고 사용</Button>}
            {saved && (draft.logo!==saved.logo || reading) && <CancelIcon label="이미지 변경 취소" disabled={busy} onClick={()=>cancel(true)}/>}
          </div>
        </div>
      </SettingsSection>
      <SettingsSection title="미리보기" description="저장하면 현재 메뉴에 적용됩니다. 다른 열린 화면은 새로고침하면 반영됩니다."><div className="brand-preview brand"><BrandPreview name={draft.name || "서비스 이름"} logo={draft.logo}/></div></SettingsSection>
      <div className="brand-save"><p role="status">{notice || (dirty?"저장하지 않은 변경이 있습니다.":"저장된 설정입니다.")}</p><div className="brand-actions"><CancelIcon label="전체 변경 취소" disabled={(!dirty && !reading) || busy} onClick={()=>cancel(false)}/><Button disabled={!dirty || !draft.name.trim() || busy || reading} onClick={()=>void save()}>{busy?"저장 중…":"저장"}</Button></div></div>
    </>}
  </div>;
}
