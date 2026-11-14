"use client";
import {useEffect,useRef,useState} from "react";
import Image from "next/image";
import {api} from "../lib/registry";
import {videoStyles} from "../lib/video-prompt-settings";
import type {ArtCatalog,ArtPreset} from "../lib/art-style-catalog";
import {Field} from "./ui";

export function WorkVideoStyleInput({id,label,required,value,onChange,inputs={},onDetailChange,defaultsReady=true}:{
  id:string;label:string;required:boolean;value:string;onChange:(value:string)=>void;
  inputs?:Record<string,string>;onDetailChange?:(value:string)=>void;defaultsReady?:boolean;
}){
  const change=useRef(onChange);change.current=onChange;
  useEffect(()=>{if(defaultsReady&&!value)change.current("auto");},[defaultsReady,value]);
  const [catalog,setCatalog]=useState<ArtPreset[]>([]),[catalogError,setCatalogError]=useState("");
  const [custom,setCustom]=useState(false);
  const detail=inputs.video_art_style||"";
  const examples=catalog.filter(s=>s.media_type===value);
  const choice=custom?"custom":examples.find(s=>s.description===detail)?.id||(detail?"custom":"default");
  function choose(key:string){setCustom(key==="custom");if(key!=="custom")onDetailChange?.(examples.find(s=>s.id===key)?.description||"");}
  useEffect(()=>{let alive=true;api<ArtCatalog>("/art-style-catalog").then(c=>{if(alive)setCatalog(c.items.filter(s=>s.enabled));}).catch(()=>{if(alive)setCatalogError("화풍 목록을 불러오지 못했습니다. 직접 입력은 사용할 수 있습니다.");});return()=>{alive=false;};},[]);
  return <div className="video-art-style-input">
    <Field id={id} label={label} required={required} hint="이번 비디오 프롬프트·영상 생성에만 적용합니다. 작품 공통 설정과 기존 이미지는 바뀌지 않습니다.">{p=><select {...p} required={required} disabled={!defaultsReady} value={value||"auto"} onChange={e=>{onChange(e.target.value);onDetailChange?.("");setCustom(false);}}>
      <option value="auto">자동 · 기준 이미지에 맞춤</option>
      {videoStyles.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}
    </select>}</Field>
    {(!value||value==="auto")&&<p className="helper-text">확정 기준 이미지의 화풍을 따르고, 이미지가 없으면 대본·씬 구성으로 판단합니다.</p>}
    {value&&value!=="auto"&&onDetailChange&&<>
      <Field id={id+"-detail"} label="상세 화풍">{p=><select {...p} value={choice} onChange={e=>choose(e.target.value)}><option value="default">유형에 맞는 기본 화풍</option>{examples.map(s=><option key={s.id} value={s.id}>{s.label}</option>)}<option value="custom">직접 입력</option></select>}</Field>
      {catalogError&&<p role="alert">{catalogError}</p>}
      {choice==="custom"?<Field id={id+"-custom"} label="원하는 화풍 직접 입력" hint="최대 2,000자 · 선택한 영상 유형 안에서 색감·질감·표현을 지정하세요.">{p=><textarea {...p} rows={3} maxLength={2000} value={detail} placeholder="예: 따뜻한 파스텔 색감, 종이 질감과 부드러운 수채화 번짐" onChange={e=>onDetailChange(e.target.value)}/>}</Field>:<>
        {detail&&<p className="helper-text">{detail}</p>}
        <div className="art-style-examples" role="group" aria-label="영상 상세 화풍 예시 이미지">{examples.map(s=><button key={s.id} type="button" className="art-style-example" aria-pressed={choice===s.id} aria-label={`${s.label} 화풍 선택`} onClick={()=>choose(s.id)}>{s.image?<Image src={s.image} width={768} height={512} sizes="(max-width:520px) 100vw, (max-width:900px) 40vw, 24vw" alt={`${s.label} 예시 이미지`}/>:<span className="art-style-placeholder">예시 이미지 없음</span>}<span>{s.label}{choice===s.id&&" ✓"}</span></button>)}</div>
      </>}
    </>}
  </div>;
}
