"use client";
import { useId } from "react";
import { type SchemaNode } from "../lib/registry";
import { Button } from "./ui";

export function SchemaEditor({ value, onChange, depth = 1 }: {
  value: SchemaNode; onChange: (node: SchemaNode) => void; depth?: number;
}) {
  const prefix = useId();
  const properties = value.properties || {};
  const required = value.required || [];
  function add() {
    let i = 1; while (`field${i}` in properties) i++;
    onChange({ ...value, properties: { ...properties, [`field${i}`]: { type: "string" } } });
  }
  function rename(oldName: string, name: string, control: HTMLInputElement) {
    if (!/^[A-Za-z][A-Za-z0-9_]{0,63}$/.test(name) || (name !== oldName && name in properties)) {
      control.setCustomValidity("영문자로 시작하는 고유한 영문·숫자·밑줄 이름을 입력하세요."); control.reportValidity(); return;
    }
    control.setCustomValidity("");
    if (name === oldName) return;
    onChange({ ...value,
      properties: Object.fromEntries(Object.entries(properties).map(([k, v]) => [k === oldName ? name : k, v])),
      required: required.map(k => k === oldName ? name : k) });
  }
  return <div className="schema-editor">
    {Object.entries(properties).map(([name, node], index) => <fieldset key={name} className="schema-field">
      <legend>필드 {index + 1}</legend><div className="field-row">
        <label htmlFor={`${prefix}-${name}`}>연결용 이름 (영문)<input id={`${prefix}-${name}`} defaultValue={name}
          onChange={e => { e.target.setCustomValidity(""); onChange({ ...value }); }}
          onBlur={e => rename(name, e.target.value, e.target)} /></label>
        <label htmlFor={`${prefix}-${name}-type`}>정보 형식<select id={`${prefix}-${name}-type`} value={node.type}
          onChange={e => { const type = e.target.value; onChange({ ...value, properties: { ...properties,
            [name]: type === "object" ? { type, description: node.description, properties: {}, required: [] } : type === "array" ?
              { type, description: node.description, items: { type: "string" }, maxItems: 100 } : { type, description: node.description } } }); }}>
          {[['string', '텍스트'], ['number', '숫자'], ['integer', '정수'], ['boolean', '예/아니오'], ['object', '정보 묶음'], ['array', '목록']].map(([type, label]) =>
            <option key={type} value={type} disabled={depth >= 3 && (type === "object" || type === "array")}>{label}</option>)}
        </select></label>
        <label className="checkbox"><input type="checkbox" checked={required.includes(name)}
          onChange={e => onChange({ ...value, required: e.target.checked ? [...required, name] : required.filter(k => k !== name) })} />필수</label>
        <Button variant="secondary" onClick={() => { const next = { ...properties }; delete next[name];
          onChange({ ...value, properties: next, required: required.filter(k => k !== name) }); }}>삭제<span className="sr-only"> {name}</span></Button>
      </div>
      {node.type === "object" && <SchemaEditor value={node} depth={depth + 1}
        onChange={next => onChange({ ...value, properties: { ...properties, [name]: next } })} />}
      {node.type === "array" && <div className="field-row"><label>목록 항목 유형<select value={node.items?.type || "string"}
        onChange={e => onChange({ ...value, properties: { ...properties, [name]: { ...node, items: { type: e.target.value } } } })}>
        <option value="string">문자열</option><option value="number">숫자</option><option value="integer">정수</option><option value="boolean">예/아니오</option>
      </select></label><label>최대 항목 수<input type="number" min={1} max={100} value={node.maxItems ?? 100}
        onChange={e => onChange({ ...value, properties: { ...properties, [name]: { ...node, maxItems: e.target.valueAsNumber } } })} /></label></div>}
    </fieldset>)}
    <Button variant="secondary" disabled={Object.keys(properties).length >= 50} onClick={add}>필드 추가</Button>
  </div>;
}
