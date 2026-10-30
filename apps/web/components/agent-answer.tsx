import type { SchemaNode } from "../lib/registry";
import { Button, Field } from "./ui";

export function answerText(value: unknown, schema?: SchemaNode): string {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.map((item, i) => `${i + 1}. ${answerText(item, schema?.items)}`).join("\n");
  if (typeof value === "object") return Object.entries(value).map(([key, item]) => `${schema?.properties?.[key]?.description || key}\n${answerText(item, schema?.properties?.[key])}`).join("\n\n");
  return typeof value === "boolean" ? value ? "예" : "아니오" : String(value);
}
export function AnswerView({ value, schema }: { value: unknown; schema?: SchemaNode }) {
  if (Array.isArray(value)) return <ol>{value.map((item, i) => <li key={i}><AnswerView value={item} schema={schema?.items} /></li>)}</ol>;
  if (value !== null && typeof value === "object") return <div className="stack">{Object.entries(value).map(([key, item]) => <section key={key}><h3>{schema?.properties?.[key]?.description || key}</h3><AnswerView value={item} schema={schema?.properties?.[key]} /></section>)}</div>;
  return <p className="agent-answer-text">{answerText(value, schema)}</p>;
}
function emptyValue(schema: SchemaNode): unknown {
  if (schema.type === "object") return Object.fromEntries(Object.entries(schema.properties || {}).filter(([key]) => schema.required?.includes(key)).map(([key, node]) => [key, emptyValue(node)]));
  if (schema.type === "array") return [];
  if (schema.type === "boolean") return false;
  if (["number", "integer"].includes(schema.type)) return schema.minimum ?? 0;
  return "";
}
export function AnswerEditor({ value, schema, onChange, id = "agent-answer-edit", label = "답변" }: { value: unknown; schema: SchemaNode; onChange: (value: unknown) => void; id?: string; label?: string }) {
  if (schema.type === "object") {
    const record = (value && typeof value === "object" ? value : {}) as Record<string, unknown>;
    return <div className="stack">{Object.entries(schema.properties || {}).map(([key, node], i) => <div key={key}>{key in record ? <><AnswerEditor value={record[key]} schema={node} onChange={next => onChange({ ...record, [key]: next })} id={`${id}-${i}`} label={node.description || key} />{!schema.required?.includes(key) && <Button variant="secondary" onClick={() => { const next = { ...record }; delete next[key]; onChange(next); }}>{node.description || key} 제거</Button>}</> : <Button variant="secondary" onClick={() => onChange({ ...record, [key]: emptyValue(node) })}>{node.description || key} 추가</Button>}</div>)}</div>;
  }
  if (schema.type === "array") {
    const items = Array.isArray(value) ? value : [];
    const child = schema.items || { type: "string" };
    return <div className="stack"><strong>{label}</strong>{items.map((item, i) => <div key={i}><AnswerEditor value={item} schema={child} onChange={next => onChange(items.map((v, index) => index === i ? next : v))} id={`${id}-${i}`} label={`${label} ${i + 1}`} /><Button variant="secondary" onClick={() => onChange(items.filter((_, index) => index !== i))}>항목 {i + 1} 제거</Button></div>)}<Button variant="secondary" disabled={items.length >= (schema.maxItems ?? 100)} onClick={() => onChange([...items, emptyValue(child)])}>항목 추가</Button></div>;
  }
  return <Field id={id} label={label}>{props => schema.type === "boolean" ? <select {...props} value={String(value)} onChange={e => onChange(e.target.value === "true")}><option value="true">예</option><option value="false">아니오</option></select> : ["number", "integer"].includes(schema.type) ? <input {...props} type="number" required min={schema.minimum} max={schema.maximum} step={schema.type === "integer" ? 1 : "any"} value={String(value)} onChange={e => onChange(e.target.value === "" ? "" : Number(e.target.value))} /> : <textarea {...props} rows={10} maxLength={schema.maxLength ?? 65536} value={String(value ?? "")} onChange={e => onChange(e.target.value)} />}</Field>;
}
