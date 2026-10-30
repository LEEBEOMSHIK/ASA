import type { SchemaNode } from "../lib/registry";
import { Button, Field } from "./ui";

export function AgentInput({ node, id, label, required, value, onChange }: { node: SchemaNode; id: string; label: string; required: boolean; value: string; onChange: (v: string) => void }) {
  const widget = node["x-widget"];
  const hint = required ? "필수 입력" : "선택 입력";
  if (widget === "radio") return <fieldset className="input-radio-group"><legend>{label} <span className="helper-text">{hint}</span></legend><div className="input-radio-options">{(node.enum || []).map((option, i) => <label key={i} className="input-radio-option"><input type="radio" name={id} required={required} checked={value === String(option)} value={String(option)} onChange={e => onChange(e.target.value)} /><span>{String(option)}</span></label>)}</div>{!required && value !== "" && <Button variant="secondary" onClick={() => onChange("")}>선택 해제</Button>}</fieldset>;
  return <Field id={id} label={label} hint={hint}>{p => widget === "slider" ? <div className="input-slider">
    <output htmlFor={id} aria-live="polite">{value === "" ? "아직 선택하지 않았습니다" : `${value}단계`}</output>
    <input {...p} type="range" min={node.minimum} max={node.maximum} step={1} value={value || node.minimum || 0} onChange={e => onChange(e.target.value)} />
    <div className="input-range-labels"><span>최소 {node.minimum}</span><span>최대 {node.maximum}</span></div>
    {value === "" ? <Button variant="secondary" onClick={() => onChange(String(node.minimum ?? 0))}>최솟값 선택</Button> : !required && <Button variant="secondary" onClick={() => onChange("")}>선택 해제</Button>}
  </div> : node.enum || node.type === "boolean" ? <select {...p} required={required} value={value} onChange={e => onChange(e.target.value)}><option value="">선택하세요</option>{(node.enum || [true, false]).map((v, i) => <option key={i} value={String(v)}>{typeof v === "boolean" ? v ? "예" : "아니오" : String(v)}</option>)}</select> : ["number", "integer"].includes(node.type) ? <input {...p} type="number" required={required} min={node.minimum} max={node.maximum} step={node.type === "integer" ? 1 : "any"} value={value} onChange={e => onChange(e.target.value)} /> : widget === "text" ? <input {...p} required={required} maxLength={node.maxLength || 65536} value={value} onChange={e => onChange(e.target.value)} /> : <textarea {...p} required={required} rows={4} maxLength={node.maxLength || 65536} value={value} placeholder={node.type === "array" ? '["항목"]' : node.type === "object" ? '{"항목": "내용"}' : "이번 작업의 내용을 입력하세요"} onChange={e => onChange(e.target.value)} />}</Field>;
}
