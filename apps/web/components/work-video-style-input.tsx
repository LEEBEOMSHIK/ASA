"use client";
import {useEffect,useRef,useState} from "react";
import {api,message} from "../lib/registry";
import {videoStyles} from "../lib/video-prompt-settings";
import {Field} from "./ui";

export function WorkVideoStyleInput({id,label,required,value,onChange,inputs={}}:{
  id:string;label:string;required:boolean;value:string;onChange:(value:string)=>void;inputs?:Record<string,string>;
}){
  const [style,setStyle]=useState<{media_type:string|null;prompt:string}|null>(null);
  const [loading,setLoading]=useState(true),[error,setError]=useState("");
  const change=useRef(onChange);change.current=onChange;
  const sources=JSON.stringify(Object.fromEntries(Object.entries(inputs).filter(([,value])=>/asa_(scene_selection|character_handoff|character_selection)_v1/.test(value))));
  useEffect(()=>{let alive=true;setLoading(true);setError("");
    api<{style:{media_type:string|null;prompt:string}|null}>("/characters/art-style/resolve","POST",{inputs:JSON.parse(sources)})
      .then(result=>{if(alive){setStyle(result.style);if(result.style?.media_type)change.current(result.style.media_type);}})
      .catch(e=>{if(alive){setStyle(null);setError(message(e));}})
      .finally(()=>{if(alive)setLoading(false);});return()=>{alive=false;};
  },[sources]);
  return <Field id={id} label={label} required={required} hint={style?.media_type?"작품 공통 설정 적용 · 변경은 캐릭터·씬의 작품 공통 영역에서 합니다.":undefined}>
    {p=><>{style?.media_type?<input {...p} readOnly value={videoStyles.find(s=>s.id===style.media_type)?.name||style.media_type}/>
      :<select {...p} disabled={loading||!!error} required={required} value={value} onChange={e=>onChange(e.target.value)}>
        <option value="">{loading?"작품 설정 확인 중…":"영상 스타일을 선택하세요"}</option>
        {videoStyles.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}
      </select>}{error&&<p role="alert">{error}</p>}</>}
  </Field>;
}
