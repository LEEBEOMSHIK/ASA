"use client";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, message } from "../lib/registry";
import { Button, Field, SettingsSection } from "./ui";
import { useDirtyGuard } from "./registry-shell";
import { BrandPreview, type Branding } from "./studio-brand";

function CancelIcon({label,disabled,onClick}: {label:string;disabled:boolean;onClick:()=>void}) {
  return <span className="brand-icon-action"><Button variant="secondary" className="brand-cancel-icon" aria-label={label} disabled={disabled} onClick={onClick}><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M3 10h11a6 6 0 0 1 0 12M3 10l6-6M3 10l6 6"/></svg></Button><span className="brand-action-hint" aria-hidden="true">{label}</span></span>;
}

async function prepareLogo(file: File): Promise<string> {
  if(!["image/png","image/jpeg","image/webp"].includes(file.type))throw new Error("PNG, JPG, WebP 이미지를 선택하세요.");
  if(file.size>5*1024*1024)throw new Error("이미지는 5MB 이하로 선택하세요.");
  const url=URL.createObjectURL(file);
  try {
    const image=new Image(); image.src=url; await image.decode();
    if(image.naturalWidth*image.naturalHeight>25000000)throw new Error("이미지 크기가 너무 큽니다. 2,500만 픽셀 이하로 선택하세요.");
    const canvas=document.createElement("canvas");canvas.width=96;canvas.height=96;
    const context=canvas.getContext("2d");if(!context)throw new Error("이미지를 읽을 수 없습니다.");
    const scale=Math.min(96/image.naturalWidth,96/image.naturalHeight);
    const width=image.naturalWidth*scale,height=image.naturalHeight*scale;
    context.drawImage(image,(96-width)/2,(96-height)/2,width,height);
    const data=canvas.toDataURL("image/png");
    if(data.length>50000)throw new Error("로고를 변환할 수 없습니다. 더 단순한 이미지를 선택하세요.");
    return data;
  } catch(error) {throw new Error(error instanceof Error && error.message.includes("세요")?error.message:"이미지를 읽을 수 없습니다. 다른 파일을 선택하세요.");}
  finally {URL.revokeObjectURL(url);}
}

export function BrandSettings() {
  const [saved,setSaved]=useState<Branding|null>(null),[draft,setDraft]=useState<Branding|null>(null);
  const [error,setError]=useState(""),[notice,setNotice]=useState(""),[over,setOver]=useState(false);
  const [busy,setBusy]=useState(false),[reading,setReading]=useState(false);
  const input=useRef<HTMLInputElement>(null),sequence=useRef(0);
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
    try{const logo=await prepareLogo(files[0]);if(id===sequence.current)setDraft(old=>old?{...old,logo}:old);}
    catch(e){if(id===sequence.current)setError(e instanceof Error?e.message:"이미지를 읽을 수 없습니다.");}
    finally{if(id===sequence.current){setReading(false);if(input.current)input.current.value="";}}
  }
  function cancel(imageOnly: boolean){
    if(!saved || busy)return;
    sequence.current+=1;setReading(false);setOver(false);setError("");
    if(input.current)input.current.value="";
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
          <div className={`brand-dropzone ${over?"is-over":""}`} onDragOver={e=>{e.preventDefault();if(!busy)setOver(true);}} onDragLeave={e=>{if(!e.currentTarget.contains(e.relatedTarget as Node))setOver(false);}} onDrop={e=>{e.preventDefault();setOver(false);void choose(e.dataTransfer.files);}}>
            {draft.logo && <div className="brand-upload-preview"><img src={draft.logo} alt="선택한 로고 이미지"/><div><strong>선택한 로고</strong><p className="muted">저장하면 메뉴에 적용됩니다.</p></div></div>}
            <strong role="status">{reading?"이미지를 준비하는 중…":draft.logo?"다른 이미지를 끌어 놓으면 교체됩니다.":"로고 이미지를 여기에 끌어 놓으세요"}</strong>
            <p id="brand-logo-help" className="muted">PNG · JPG · WebP, 최대 5MB. 비율을 유지해 로고용으로 축소합니다.</p>
            <input ref={input} id="brand-logo" type="file" hidden accept="image/png,image/jpeg,image/webp" aria-describedby="brand-logo-help" disabled={busy || reading} onChange={e=>void choose(e.target.files)}/>
            <Button variant="secondary" disabled={busy || reading} aria-describedby="brand-logo-help" onClick={()=>input.current?.click()}>{draft.logo?"이미지 변경":"이미지 선택"}</Button>
          </div>
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
