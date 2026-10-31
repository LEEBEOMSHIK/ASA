"use client";
import { useId, useState } from "react";
import { agentIcons, type AgentIconId } from "../lib/agent-icons";
import { AgentIcon, Button, Field } from "./ui";

export function AgentIconPicker({value="bot",onChange}:{value?:AgentIconId;onChange:(id:AgentIconId)=>void}) {
  const [expanded, setExpanded] = useState(false);
  const id = useId();
  const selected = agentIcons.find(icon => icon.id === value) || agentIcons[0];
  return <div className="agent-icon-picker">
    <Field id={`${id}-change`} label="에이전트 아이콘" annotation="관리용"
      help="목록과 실행 화면에서 에이전트를 구분할 표시입니다. 기본 로봇 아이콘을 그대로 사용해도 됩니다. AI에게 전달되지 않습니다. 초안 저장 시 목록에, 새 버전 등록 후 실행 화면에 반영됩니다.">
      {props => <div className="agent-icon-current">
        <AgentIcon icon={selected.id}/><span>{selected.label}{selected.id === "bot" ? " · 기본 아이콘" : ""}</span>
        <Button {...props} variant="secondary" aria-expanded={expanded} aria-controls={`${id}-options`} onClick={() => setExpanded(!expanded)}>{expanded ? "선택 닫기" : "아이콘 변경"}</Button>
      </div>}
    </Field>
    {expanded && <fieldset id={`${id}-options`} className="agent-icon-choices"><legend className="sr-only">변경할 아이콘 선택</legend>
      <div className="agent-icon-options">{agentIcons.map(icon=><label key={icon.id} className="agent-icon-option">
        <input type="radio" name={`${id}-icon`} value={icon.id} checked={selected.id===icon.id} onChange={()=>onChange(icon.id)}/>
        <AgentIcon icon={icon.id}/><span>{icon.label}</span>
      </label>)}</div>
    </fieldset>}
  </div>;
}
