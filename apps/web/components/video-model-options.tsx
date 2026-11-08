"use client";
import { useEffect, useState } from "react";
import { api, type SchemaNode } from "../lib/registry";
import { Button } from "./ui";

type Model = { key:string; label:string; generation_supported:boolean };

export function VideoModelOptions({node,onChange}:{node:SchemaNode; onChange:(node:SchemaNode)=>void}) {
  const [models,setModels]=useState<Model[]>([]);
  const [failed,setFailed]=useState(false);
  useEffect(()=>{
    let live=true;
    api<{models:Model[]}>("/video-planning/models")
      .then(data=>{if(live)setModels(data.models.filter(model=>model.generation_supported));})
      .catch(()=>{if(live)setFailed(true);});
    return ()=>{live=false;};
  },[]);
  return <div className="stack">
    <p className="helper-text">연결 가능한 모델을 선택지에 추가할 수 있습니다. 에이전트 설정을 저장한 뒤 새 실행에 적용됩니다.</p>
    {failed ? <p role="status" className="helper-text">모델 목록을 불러오지 못했습니다. 설정을 다시 열어 주세요.</p>
      : <div className="script-actions">{models.map(model=>{
        const included=node.enum?.includes(model.key);
        return <Button key={model.key} variant="secondary" disabled={included}
          onClick={()=>onChange({...node,enum:[...(node.enum??[]),model.key]})}>
          {model.label} {included ? "추가됨" : "추가"}
        </Button>;
      })}</div>}
  </div>;
}
