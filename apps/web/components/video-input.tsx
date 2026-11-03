"use client";
import { useRef, useState } from "react";
import { api, message, type SchemaNode } from "../lib/registry";
import { Button, Field } from "./ui";
import { pendingVideoUrl, videoLinkLabel } from "../lib/video-link";

export function isVideoReference(node: SchemaNode): boolean { return node.type === "array" ? Boolean(node.items && isVideoReference(node.items)) : Boolean(node.type === "object" && node.properties?.format?.enum?.includes("asa_video_reference_v1")); }
type Props = {id:string;label:string;required:boolean;value:string;onChange:(value:string)=>void};
export function VideoInput({multiple = false, ...props}: Props & {multiple?:boolean}) {
  const latest = useRef(props); latest.current = props;
  const nextKey = useRef(1);
  const [keys, setKeys] = useState<string[]>(() => videoRows(props.value).map((_, i) => `video-${i}`));
  function rows() { return videoRows(latest.current.value); }
  function update(index:number, patch:Record<string,unknown>, replace = false) {
    const list = rows(); if (index >= list.length) return;
    list[index] = replace ? {...patch, ...(list[index].note ? {note:list[index].note} : {})} : {...list[index], ...patch};
    latest.current.onChange(JSON.stringify(list));
  }
  if (!multiple) return <SingleVideoInput {...props}/>;
  const list = rows();
  return <fieldset className="video-reference-input"><legend>{props.label} <span className="helper-text">{props.required ? "필수 입력" : "선택 입력"}</span></legend>
    <p className="helper-text">파일과 링크를 섞어 최대 4개를 함께 분석합니다. 영상별 특징과 공통 스타일을 정리합니다. 각 영상은 5분·20MB 이하이며 음성·음악은 분석하지 않습니다.</p>
    {list.map((item, index) => <div className="video-reference-card" key={keys[index] || `video-${index}`}>
      <header className="video-reference-card-heading"><strong>참고 영상 {index + 1}</strong><Button variant="secondary" disabled={item.format === "asa_video_upload_pending"} aria-label={`참고 영상 ${index + 1} 삭제`} onClick={() => {props.onChange(JSON.stringify(list.filter((_, i) => i !== index)));setKeys(current => current.filter((_, i) => i !== index));}}>삭제</Button></header>
      <SingleVideoInput id={`${props.id}-${index}`} label="영상 자료" required value={item.format ? JSON.stringify(item) : ""} onChange={v => update(index, v ? JSON.parse(v) : {}, true)}/>
      <Field id={`${props.id}-${index}-note`} label="이 영상에서 참고할 점" hint="선택 · 예: 색감은 이 영상처럼, 카메라 움직임은 두 번째 영상처럼">{p => <input {...p} maxLength={1000} value={String(item.note || "")} onChange={e => update(index, {note:e.target.value})}/>}</Field>
    </div>)}
    <div className="button-row"><Button variant="secondary" disabled={list.length >= 4} onClick={() => {props.onChange(JSON.stringify([...list, {}]));setKeys(current => [...current, `added-${nextKey.current++}`]);}}>+ 참고 영상 추가</Button><span className="helper-text">{list.length} / 4개</span></div>
  </fieldset>;
}
function videoRows(value:string): Record<string,unknown>[] { try {const parsed = JSON.parse(value); return Array.isArray(parsed) ? parsed : [parsed];} catch {return [{}];} }
function SingleVideoInput({id,label,required,value,onChange}:Props) {
  const change = useRef(onChange); change.current = onChange;
  const url = pendingVideoUrl(value) ?? "";
  const linkLabel = videoLinkLabel(url);
  const [busy,setBusy]=useState(false); const [error,setError]=useState("");
  const [name,setName]=useState(""); const [over,setOver]=useState(false); const file=useRef<HTMLInputElement>(null);
  async function save(body:object, title:string) {
    setBusy(true);setError("");
    try { const result=await api<object>("/video-references","POST",body);change.current(JSON.stringify(result));setName(title); }
    catch(e){change.current(value);setError(message(e));}finally{setBusy(false);}
  }
  async function upload(selected?:File) {
    if(!selected||busy)return;
    if(selected.size>20*1024*1024 || !/\.(mp4|mov|webm)$/i.test(selected.name)){setError("MP4·MOV·WebM 파일을 20MB 이하로 올려 주세요.");return;}
    setBusy(true);setError("");
    change.current(JSON.stringify({format:"asa_video_upload_pending"}));
    try { const data=await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(",")[1]);reader.onerror=()=>reject(new Error("파일을 읽지 못했습니다."));reader.readAsDataURL(selected);});await save({data,filename:selected.name},selected.name); }
    catch{change.current(value);setError("파일을 읽지 못했습니다. 다시 선택해 주세요.");}finally{setBusy(false);}
  }
  return <fieldset className="video-reference-input"><legend>{label} <span className="helper-text">{required?"필수 입력":"선택 입력"}</span></legend>
    <p className="helper-text">파일 또는 링크 중 하나를 선택하세요. 시간순 화면 표본을 분석하므로 빠른 동작·전환은 추정으로 구분합니다.</p>
    <div className={`video-dropzone${over?" is-over":""}`} onDragOver={e=>{e.preventDefault();if(!busy)setOver(true);}} onDragLeave={()=>setOver(false)} onDrop={e=>{e.preventDefault();setOver(false);void upload(e.dataTransfer.files[0]);}}>
      <strong>영상 파일을 끌어 놓으세요</strong><span className="helper-text">MP4 · MOV · WebM / 최대 20MB</span>
      <input ref={file} type="file" hidden accept=".mp4,.mov,.webm" onChange={e=>{void upload(e.target.files?.[0]);e.target.value="";}}/>
      <Button variant="secondary" disabled={busy} onClick={()=>file.current?.click()}>영상 파일 선택</Button>
    </div>
    <Field id={`${id}-url`} label="또는 공개 영상 링크" hint="링크를 붙여 넣고 분석을 시작하세요. 영상 접근 여부는 실행 시 확인하며, 비공개·로그인 제한 영상은 파일로 올려 주세요.">{p=><input {...p} type="url" value={url} disabled={busy} placeholder="YouTube·Shorts·Instagram Reels 링크" aria-invalid={Boolean(url && !linkLabel)} onChange={e=>{setError("");setName("");onChange(e.target.value ? JSON.stringify({format:"asa_video_link_pending",url:e.target.value}) : "");}}/>}</Field>
    {value&&<div className="button-row"><Button variant="secondary" disabled={busy} onClick={()=>{onChange("");setName("");setError("");}}>선택 해제</Button></div>}
    <p role="status">{busy?"영상 자료를 저장하고 있습니다…":url?linkLabel?`${linkLabel} · 주소 형식 확인됨. 분석 시작 시 영상을 가져옵니다.`:"YouTube·Shorts 또는 Instagram Reels의 HTTPS 링크를 입력하세요.":value?`영상 연결됨 · ${name||"이전에 선택한 영상"}`:"영상 파일을 선택하거나 링크를 입력하세요."}</p>
    {error&&<p role="alert" className="field-error">{error}</p>}
  </fieldset>;
}
