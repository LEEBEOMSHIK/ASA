"use client";
import { useState } from "react";
import type { Definition } from "../lib/registry";
import { videoStyles } from "../lib/video-prompt-settings";
import { ExpandableTextarea } from "./expandable-textarea";
import { Field } from "./ui";

type Style = typeof videoStyles[number]["id"];
export function VideoPromptEditor({definition,onChange}: {
  definition:Definition; onChange:(value:Definition)=>void;
}) {
  const [editingStyle,setEditingStyle]=useState<Style>("animation_2d");
  const config=definition.video_prompt_modules;
  if (!config?.editor_managed) return null;
  const body=config.style_instructions?.[editingStyle]??"";
  const label=`${videoStyles.find(s=>s.id===editingStyle)!.name} 추가 지침`;
  return <div className="video-prompt-editor" role="group" aria-labelledby="video-prompts-title">
    <div><h3 id="video-prompts-title">영상 스타일별 추가 지침</h3>
      <p className="muted">실행할 때 사용자가 영상 스타일을 선택하면, 위 공통 지침에 해당 스타일의 지침이 자동으로 추가됩니다.</p></div>
    <Field id="video-edit-style" label="편집할 영상 스타일" hint="지침을 편집할 대상을 선택합니다. 이번 영상의 스타일은 실행 화면에서 선택합니다.">{p=><select {...p}
      value={editingStyle} onChange={e=>setEditingStyle(e.target.value as Style)}>
      {videoStyles.map(s=><option key={s.id} value={s.id}>{s.name}{config.style_instructions?.[s.id]?.trim()?" · 지침 있음":" · 미작성"}</option>)}
    </select>}</Field>
    <ExpandableTextarea id="video-style-instructions" label={label} rows={7} characterLimit={65536}
      value={body} onChange={e=>onChange({...definition,video_prompt_modules:{...config,
        style_instructions:{...config.style_instructions,[editingStyle]:e.target.value}}})}
      renderField={(input,action)=><Field id="video-style-instructions" label={label} labelAction={action}
        hint={`${Array.from(body).length.toLocaleString("ko-KR")} / 65,536자 · 저장하면 새 작업부터 적용됩니다.`}>{()=>input}</Field>}/>
    {!body.trim()&&<p className="notice">이 스타일의 지침이 아직 없습니다. 지침을 작성하고 저장해야 이 스타일로 실행할 수 있습니다.</p>}
    <p className="helper-text">적용 순서: 에이전트 지침(공통) → 실행 화면에서 선택한 스타일의 추가 지침. 사용 여부를 별도로 켜거나 끄지 않습니다.</p>
  </div>;
}
