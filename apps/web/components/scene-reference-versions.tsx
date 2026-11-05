"use client";
import "./scene-reference-versions.css";
import { useState } from "react";
import { api, message } from "../lib/registry";

export type SceneReference = {id:string;name:string;image_id:string|null;role?:string};
type Version = {id:string;version:number;confirmed:boolean;created_at:string;character:{name:string;appearance:string;image_prompt:string};image_change?:string};
export type UsedReference = {id:string;name:string;image_id:string;image_version:number;selection?:string};

export function SceneReferenceVersions({references,value,onChange,disabled,used=[]}:{references:SceneReference[];value:Record<string,string>;onChange:(value:Record<string,string>)=>void;disabled:boolean;used?:UsedReference[]}) {
  const [versions,setVersions]=useState<Record<string,Version[]>>({});
  const [error,setError]=useState("");const [loading,setLoading]=useState(false);
  async function load(){
    if(loading)return;setLoading(true);setError("");
    try {
      const rows=await Promise.all(references.filter(c=>c.image_id).map(async c=>[c.id,await api<Version[]>(`/characters/library/${c.image_id}/versions`)] as const));
      setVersions(Object.fromEntries(rows));
    }catch(e){setError(message(e));}finally{setLoading(false);}
  }
  return <details className="scene-cast" onToggle={e=>{if(e.currentTarget.open)void load();}}>
    <summary>이 씬에 연결된 캐릭터 · {references.length}명</summary>
    <div className="character-form">
      <p className="helper-text">기본은 이 작업에 연결한 기준 이미지입니다. 다른 확정 버전도 선택할 수 있습니다. 다른 버전을 선택하면 이 씬의 다음 생성·수정 요청에만 적용됩니다. 해당 버전의 외형·의상과 제작 지침도 함께 전달하며, 다른 씬과 확정 기준은 바뀌지 않습니다.</p>
      {loading&&<p role="status">이미지 버전을 확인하고 있습니다.</p>}
      {error&&<p role="alert">{error}</p>}
      <div className="scene-reference-grid">{references.map(c=>{
        const choices=(versions[c.id]||[]).filter(v=>v.confirmed);
        const selected=value[c.id]?choices.find(v=>v.id===value[c.id]):choices.find(v=>v.id===c.image_id);
        const recorded=used.find(v=>v.id===c.id);
        return <section className="scene-reference-card" key={c.id}>
          <div className="scene-cast-item">
            {(selected?.id||c.image_id)&&<img src={`/api/v1/characters/images/${selected?.id||c.image_id}/asset`} alt={`${c.name} ${selected?`v${selected.version}`:"기준"} 이미지`}/>}
            <div><strong>{c.name}</strong><p className="helper-text">{c.role==="reference_only"?"소품·스타일 참고용":"씬 등장인물"}</p></div>
          </div>
          <label className="character-field">다음 요청에 사용할 버전
            <select disabled={disabled||loading||!choices.length} value={value[c.id]||""} onChange={e=>{const next={...value};if(e.target.value)next[c.id]=e.target.value;else delete next[c.id];onChange(next);}}>
              <option value="">선택한 기준 이미지 사용{choices.find(v=>v.id===c.image_id)?` · v${choices.find(v=>v.id===c.image_id)!.version}`:""}</option>
              {choices.map(v=><option value={v.id} key={v.id}>v{v.version} · {v.confirmed?"확정":"미확정"} · 이 씬에서 사용</option>)}
            </select>
          </label>
          {value[c.id]&&<p className="helper-text">이 씬에서만 지정한 버전입니다. ‘선택한 기준 이미지 사용’을 선택하면 기본값으로 돌아갑니다.</p>}
          {selected&&<details><summary>선택한 버전의 설정 확인</summary><div className="character-form"><p className="helper-text">생성 시각 · {new Date(selected.created_at).toLocaleString("ko-KR")}</p><p>{selected.character.appearance}</p><p>{selected.character.image_prompt}</p>{selected.image_change&&<p>당시 수정 요청 · {selected.image_change}</p>}</div></details>}
          {recorded&&<p className="helper-text">현재 씬 이미지 생성에 사용: {recorded.name} v{recorded.image_version}{recorded.selection==="scene_override"?" · 씬별 지정":" · 생성 당시 기준"}</p>}
        </section>;
      })}</div>
    </div>
  </details>;
}
