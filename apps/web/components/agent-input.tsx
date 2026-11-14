import { ExpandableTextarea } from "./expandable-textarea";
import { SceneImageInput, isSceneReference } from "./scene-image-input";
import { VideoModelInput } from "./video-model-input";
import { videoStyles } from "../lib/video-prompt-settings";
import {WorkVideoStyleInput} from "./work-video-style-input";
import { VideoInput, isVideoReference } from "./video-input";
import type { ReactNode } from "react";
import { PreviousAnswerInput } from "./previous-answer-input";
import type { SchemaNode } from "../lib/registry";
import { Button, Field, InputRequirement } from "./ui";
import { CharacterImageInput, isCharacterReference } from "./character-library";

export function AgentInput({ node, id, label, required, value, onChange, videoStyle = "", inputs, onDetailChange, defaultsReady=true }: { node: SchemaNode; id: string; label: string; required: boolean; value: string; onChange: (v: string) => void; videoStyle?:string;inputs?:Record<string,string>;onDetailChange?:(v:string)=>void;defaultsReady?:boolean }) {
  if (node["x-video-model"]) return <VideoModelInput {...{node,id,label,required,value,onChange,videoStyle}} />;
  if (isVideoReference(node)) return <VideoInput multiple={node.type === "array"} id={id} label={label} required={required} value={value} onChange={onChange}/>;
  if (isSceneReference(node)) return <SceneImageInput id={id} label={label} required={required} value={value} onChange={onChange}/>;
  if (isCharacterReference(node)) return <CharacterImageInput id={id} label={label} required={required} value={value} onChange={onChange}/>;
  const widget = node["x-widget"];
  if (node.type === "string" && JSON.stringify(node.enum) === JSON.stringify(videoStyles.map(s=>s.id))) {
    return <WorkVideoStyleInput {...{id,label,required,value,onChange,inputs,onDetailChange,defaultsReady}}/>;
  }
  const ratioLabels: Record<string, string> = {
    "9:16": "9:16 · 세로형 — 쇼츠·릴스",
    "16:9": "16:9 · 가로형 — 일반 영상",
    "1:1": "1:1 · 정사각형 — 피드 이미지",
  };
  const isRatio = node.type === "string" && !!node.enum?.length && node.enum.every(v => typeof v === "string" && v in ratioLabels);
  const hint = isRatio
    ? `가로:세로 비율입니다. 쇼츠용 장면은 9:16 세로형을 선택하세요. 장면의 구도와 제작 지침에 적용되며, 기존 캐릭터 기준 이미지는 변경되지 않습니다.`
    : label.trim() === "이야기 길이"
      ? "선택한 길이는 완성 영상의 목표 시간입니다. 실제 길이는 대사 속도·행동·편집에 따라 짧거나 길어질 수 있으며, 씬 구성과 음성 측정 후 확인합니다. 목표와 차이가 크면 대본이나 구성을 보완해야 합니다."
      : undefined;
  if (widget === "radio") return <fieldset className="input-radio-group"><legend>{label}<InputRequirement required={required}/></legend>{hint && <p className="helper-text">{hint}</p>}<div className="input-radio-options">{(node.enum || []).map((option, i) => <label key={i} className="input-radio-option"><input type="radio" name={id} required={required} checked={value === String(option)} value={String(option)} onChange={e => onChange(e.target.value)} /><span>{String(option)}</span></label>)}</div>{!required && value !== "" && <Button variant="secondary" onClick={() => onChange("")}>선택 해제</Button>}</fieldset>;
  if (node.type === "string" && !node.enum && widget !== "text") {
    const renderLongText = (importAction?: ReactNode, receipt?: ReactNode) => <div>
      <ExpandableTextarea id={id} label={label} viewOnly required={required} rows={4}
        value={value} maxLength={node.maxLength || 65536} placeholder="이번 작업의 내용을 입력하세요"
        onChange={e => onChange(e.target.value)}
        renderField={(input, expandAction) => <Field id={id} label={label} required={required}
          labelAction={<>{importAction}{expandAction}</>}>{() => input}</Field>}/>
      {receipt}
    </div>;
    return node["x-previous-answer"] === true
      ? <PreviousAnswerInput agentId={node["x-answer-agent"]} label={label} value={value}
          maxLength={node.maxLength || 65536} onChange={onChange}>{renderLongText}</PreviousAnswerInput>
      : renderLongText();
  }
  const renderInput = (action?:ReactNode, receipt?:ReactNode) => <div><Field id={id} label={label} required={required} hint={hint} labelAction={action}>{p => widget === "slider" ? <div className="input-slider">
    <output htmlFor={id} aria-live="polite">{value === "" ? "아직 선택하지 않았습니다" : `${value}단계`}</output>
    <input {...p} type="range" min={node.minimum} max={node.maximum} step={1} value={value || node.minimum || 0} onChange={e => onChange(e.target.value)} />
    <div className="input-range-labels"><span>최소 {node.minimum}</span><span>최대 {node.maximum}</span></div>
    {value === "" ? <Button variant="secondary" onClick={() => onChange(String(node.minimum ?? 0))}>최솟값 선택</Button> : !required && <Button variant="secondary" onClick={() => onChange("")}>선택 해제</Button>}
  </div> : node.enum || node.type === "boolean" ? <select {...p} required={required} value={value} onChange={e => onChange(e.target.value)}><option value="">선택하세요</option>{(node.enum || [true, false]).map((v, i) => <option key={i} value={String(v)}>{isRatio ? ratioLabels[String(v)] : typeof v === "boolean" ? v ? "예" : "아니오" : String(v)}</option>)}</select> : ["number", "integer"].includes(node.type) ? <input {...p} type="number" required={required} min={node.minimum} max={node.maximum} step={node.type === "integer" ? 1 : "any"} value={value} onChange={e => onChange(e.target.value)} /> : widget === "text" ? <input {...p} required={required} maxLength={node.maxLength || 65536} value={value} onChange={e => onChange(e.target.value)} /> : <textarea {...p} required={required} rows={4} maxLength={node.maxLength || 65536} value={value} placeholder={node.type === "array" ? '["항목"]' : node.type === "object" ? '{"항목": "내용"}' : "이번 작업의 내용을 입력하세요"} onChange={e => onChange(e.target.value)} />}</Field>{receipt}</div>;
  return node.type === "string" && !node.enum && node["x-previous-answer"] === true ? <PreviousAnswerInput agentId={node["x-answer-agent"]} label={label} value={value} maxLength={node.maxLength || 65536} onChange={onChange}>{renderInput}</PreviousAnswerInput> : renderInput();
}
