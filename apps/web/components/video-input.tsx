"use client";
import { useRef, useState } from "react";
import { api, message, type SchemaNode } from "../lib/registry";
import { Button, ExternalLink, Field, InputRequirement } from "./ui";
import { videoLinkLabel } from "../lib/video-link";

export function isVideoReference(node: SchemaNode): boolean {
  return node.type === "array" ? Boolean(node.items && isVideoReference(node.items))
    : Boolean(node.type === "object" && node.properties?.format?.enum?.includes("asa_video_reference_v1"));
}
type Props = {id:string; label:string; required:boolean; value:string; onChange:(value:string)=>void; multiple?:boolean};
type Reference = {format:string; source_id?:string; url?:string; note?:string};
function parse(value:string):Reference[] {
  try {
    const data=JSON.parse(value);
    return (Array.isArray(data)?data:[data]).filter(item=>item && typeof item.format==="string");
  } catch {return [];}
}
async function upload(file:File) {
  const data=await new Promise<string>((resolve,reject)=>{
    const reader=new FileReader();
    reader.onload=()=>resolve(String(reader.result).split(",")[1]);
    reader.onerror=()=>reject(new Error("file_read_failed"));
    reader.readAsDataURL(file);
  });
  return api<Reference>("/video-references","POST",{data,filename:file.name});
}
export function VideoInput({multiple=false,id,label,required,value,onChange}:Props) {
  const limit=multiple?5:1;
  const list=parse(value);
  const input=useRef<HTMLInputElement>(null);
  const uploading=useRef(false);
  const [busy,setBusy]=useState(false);
  const [over,setOver]=useState(false);
  const [url,setUrl]=useState("");
  const [error,setError]=useState("");
  const [names,setNames]=useState<Record<string,string>>({});
  function write(items:Reference[]) {
    onChange(items.length?JSON.stringify(multiple?items:items[0]):"");
  }
  function addLink() {
    if(uploading.current || list.length>=limit)return;
    const link=url.trim();
    if(!videoLinkLabel(link)){setError("YouTube·Shorts 또는 Instagram Reels의 HTTPS 링크를 입력해 주세요.");return;}
    if(list.some(item=>item.url===link)){setError("이미 추가한 링크입니다.");return;}
    write([...list,{format:"asa_video_link_pending",url:link}]);
    setUrl("");setError("");
  }
  async function addFiles(files:File[]) {
    if(uploading.current || !files.length)return;
    if(files.length>limit-list.length){setError(`파일과 링크를 합해 최대 ${limit}개입니다. 현재 ${limit-list.length}개를 더 추가할 수 있습니다.`);return;}
    const invalid=files.find(f=>!f.size || f.size>20*1024*1024 || !/\.(mp4|mov|webm)$/i.test(f.name));
    if(invalid){setError(`${invalid.name}: MP4·MOV·WebM 파일을 20MB 이하로 올려 주세요.`);return;}
    uploading.current=true;setBusy(true);setError("");
    const complete=[...list];
    const errors:string[]=[];
    try {
      for(const file of files){
        write([...complete,{format:"asa_video_upload_pending"}]);
        try {
          const item=await upload(file);
          complete.push(item);
          if(item.source_id)setNames(old=>({...old,[item.source_id!]:file.name}));
        } catch(e){errors.push(file.name+" · "+message(e));}
      }
    } finally {
      write(complete);setError(errors.join(" / "));uploading.current=false;setBusy(false);
    }
  }
  const full=list.length>=limit;
  return <fieldset className="video-reference-input" aria-describedby={id+"-source-rule"}>
    <legend><span className="video-input-heading">{label}<InputRequirement required={required}/><small>{multiple?(required?"총 1~5개":"최대 5개"):"1개"}</small></span></legend>
    <p id={id+"-source-rule"} className="video-input-guide">{multiple
      ? "파일만 올려도, 공개 링크만 추가해도 됩니다. 두 방식을 섞어도 됩니다."
      : "파일을 올리거나 공개 링크를 추가하세요. 한 가지 방법이면 충분합니다."}</p>
    <div className="video-source-methods">
    <div className={`video-dropzone${over?" is-over":""}`} onDragOver={e=>{e.preventDefault();setOver(!busy && !full);}} onDragLeave={()=>setOver(false)}
      onDrop={e=>{e.preventDefault();setOver(false);if(!input.current?.closest("fieldset:disabled"))void addFiles(Array.from(e.dataTransfer.files));}}>
      <strong>영상 파일</strong><span className="helper-text">여기에 끌어 놓거나 파일을 선택하세요. MP4 · MOV · WebM, 파일당 최대 20MB</span>
      <input ref={input} hidden type="file" multiple={multiple} accept=".mp4,.mov,.webm" disabled={busy||full} onChange={e=>{void addFiles(Array.from(e.target.files??[]));e.target.value="";}}/>
      <Button variant="secondary" disabled={busy||full} onClick={()=>input.current?.click()}>영상 파일 선택</Button>
    </div>
    <div className="video-link-method"><label htmlFor={id+"-url"}>공개 영상 링크</label><span className="helper-text">공개 영상 주소를 붙여 넣고 링크 추가를 누르세요.</span><div className="field video-link-entry">
      <input id={id+"-url"} type="url" placeholder="YouTube·Shorts·Instagram Reels 링크" value={url} disabled={busy||full}
        onChange={e=>{setUrl(e.target.value);setError("");}} onKeyDown={e=>{if(e.key==="Enter"){e.preventDefault();addLink();}}}/>
      <Button variant="secondary" disabled={busy||full||!url.trim()} onClick={addLink}>링크 추가</Button>
    </div></div></div>
    <p className="helper-text">영상당 최대 5분 · 화면 분석만 지원</p>
    <strong role="status">추가한 영상 · {list.length} / {limit}개{busy?" · 업로드 중":""}</strong>
    {list.map((item,index)=>{
      const link=item.url && videoLinkLabel(item.url) ? new URL(item.url) : null;
      const name=link ? link.pathname.startsWith("/shorts/") ? "YouTube Shorts"
        : link.hostname.endsWith("instagram.com") ? "Instagram Reels" : "YouTube 영상"
        : names[item.source_id??""] || (item.source_id?"이전에 연결한 영상":"파일 업로드 중…");
      return <div className="video-reference-card" key={item.source_id||item.url||index}>
        <div className="video-reference-card-heading"><div className="video-reference-identity">
          <span className="video-reference-number" aria-label={`참고 영상 ${index+1}`}>{String(index+1).padStart(2,"0")}</span>
          <div><strong className="video-source-name">{name}</strong>
            {link && <span className="video-reference-address" title={link.href}>{link.host}{link.pathname}{link.search}</span>}</div></div>
          <Button className="video-reference-remove" variant="secondary" disabled={busy} title="목록에서 삭제" aria-label={`참고 영상 ${index+1} 삭제`} onClick={()=>{write(list.filter((_,i)=>i!==index));setError("");}}>
            <svg width="18" height="18" viewBox="0 0 24 24" stroke="currentColor" fill="none" strokeWidth="1.7" strokeLinecap="round" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg>
          </Button></div>
        {link && <ExternalLink href={link.href}>원본 영상 열기</ExternalLink>}
        {multiple && item.format!=="asa_video_upload_pending" && <details className="video-reference-note"><summary>{item.note?"참고 메모 보기·수정":"참고 메모 추가 (선택)"}</summary>
          <Field id={id+"-note-"+index} label="이 영상에서 참고할 점">{p=><input {...p} disabled={busy} maxLength={1000} value={item.note??""} placeholder="예: 첫 장면의 색감과 카메라 움직임"
          onChange={e=>write(list.map((entry,i)=>i===index?{...entry,note:e.target.value}:entry))}/>}</Field></details>}
      </div>;
    })}
    {error && <p role="alert" className="field-error">{error}</p>}
  </fieldset>;
}
