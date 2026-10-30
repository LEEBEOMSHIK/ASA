"use client";
import type { SchemaNode } from "../lib/registry";
import { Button, Field } from "./ui";
import { ChoiceOptionsEditor } from "./choice-options-editor";

const modes = [["text", "짧은 글"], ["textarea", "긴 글"], ["radio", "라디오 버튼"], ["select", "선택 목록"], ["slider", "슬라이더"], ["number", "숫자"]];
const modeHints: Record<string, string> = {
  text: "사용자가 한 줄로 직접 적습니다. 예: 주인공 이름, 이야기 주제",
  textarea: "사용자가 여러 줄로 자세히 적습니다. 예: 상세 요청, 피해야 할 소재",
  radio: "선택지를 모두 보여주고 하나를 고르게 합니다. 예: 아이 나이 — 3~5세 / 6~7세 / 8~9세",
  select: "목록을 펼쳐 하나를 고르게 합니다. 예: 이야기 소재 — 유령, 도깨비 등. 선택지가 많을 때 적합합니다.",
  slider: "사용자가 막대를 움직여 범위 안의 숫자를 고릅니다. 예: 무서운 정도 1~5",
  number: "사용자가 숫자를 직접 입력합니다. 예: 등장인물 수, 목표 시간(분)",
  advanced: "중첩된 항목 등 기존 세부 형식입니다. 아래 ‘중첩 항목 및 세부 형식’에서 확인할 수 있습니다.",
};
export function InputFormEditor({ value, onChange }: { value: SchemaNode; onChange: (value: SchemaNode) => void }) {
  const properties = value.properties || {};
  const required = value.required || [];
  const update = (key: string, node: SchemaNode) => onChange({ ...value, properties: { ...properties, [key]: node } });
  return <div className="stack">
    {Object.entries(properties).map(([key, node], index) => {
      const mode = node["x-widget"] || (node.enum ? "select" : node.type === "string" ? "textarea" : ["number", "integer"].includes(node.type) ? "number" : "advanced");
      const choice = mode === "radio" || mode === "select";
      const numeric = mode === "slider" || mode === "number";
      const changeMode = (next: string) => {
        const n: SchemaNode = { type: next === "slider" ? "integer" : next === "number" ? "number" : "string", description: node.description, "x-widget": next as SchemaNode["x-widget"] };
        if (next === "radio" || next === "select") n.enum = ["선택지 1", "선택지 2"];
        if (next === "slider") { n.minimum = 1; n.maximum = 5; }
        update(key, n);
      };
      return <details className="input-field-card" key={key} open>
        <summary>{index + 1}. {node.description || "새 입력 항목"} <span className="muted">· {required.includes(key) ? "필수" : "선택"}</span></summary>
        <div className="input-field-body">
          <div className="input-form-grid">
            <Field id={`form-name-${key}`} label="항목 이름">{p => <input {...p} maxLength={400} value={node.description || ""} placeholder="예: 무서운 정도" onChange={e => update(key, { ...node, description: e.target.value })} />}</Field>
            <Field id={`form-mode-${key}`} label="사용자가 답하는 방식" hint={modeHints[mode]} help="에이전트를 실행할 때 사용자가 이 항목에 어떻게 답할지 정합니다. AI의 답변 형식이 아니라 사용자 입력 화면의 모양을 설정하는 곳입니다. 라디오 버튼은 보기를 모두 펼쳐 보여주고, 선택 목록은 열어서 확인합니다. 둘 다 하나만 고릅니다.">{p => <select {...p} value={mode} onChange={e => changeMode(e.target.value)}>{mode === "advanced" && <option value="advanced">기존 세부 형식</option>}{modes.map(([v, label]) => <option key={v} value={v}>{label}</option>)}</select>}</Field>
          </div>
          {choice && <ChoiceOptionsEditor id={`form-options-${key}`} node={node} onChange={n => update(key, n)} />}
          {numeric && <div className="input-form-grid">{(["minimum", "maximum"] as const).map((bound, i) => <Field key={bound} id={`form-${bound}-${key}`} label={i ? "최댓값" : "최솟값"}>{p => <input {...p} type="number" step={mode === "slider" ? 1 : "any"} value={node[bound] ?? ""} onChange={e => { const n = { ...node }; if (e.target.value === "") delete n[bound]; else n[bound] = Number(e.target.value); update(key, n); }} />}</Field>)}</div>}
          <div className="input-field-options">
            <label className="checkbox"><input type="checkbox" checked={required.includes(key)} onChange={e => onChange({ ...value, required: e.target.checked ? [...required, key] : required.filter(k => k !== key) })} />필수 입력</label>
            {mode !== "advanced" && <label className="checkbox"><input type="checkbox" checked={node.default !== undefined} onChange={e => { const n = { ...node }; if (!e.target.checked) delete n.default; else n.default = choice ? node.enum?.[0] ?? "" : numeric ? node.minimum ?? 0 : ""; update(key, n); }} />기본값 사용</label>}
          </div>
          {node.default !== undefined && mode !== "advanced" && <Field id={`form-default-${key}`} label="기본값" hint="새 실행 화면을 열 때 미리 채웁니다. 사용자가 바꿀 수 있습니다.">{p => choice ? <select {...p} value={String(node.default)} onChange={e => update(key, { ...node, default: e.target.value })}>{!node.enum?.includes(node.default!) && <option value={String(node.default)}>선택지를 다시 선택하세요</option>}{(node.enum || []).map((v, i) => <option key={i} value={String(v)}>{String(v)}</option>)}</select> : <input {...p} type={numeric ? "number" : "text"} min={node.minimum} max={node.maximum} step={mode === "slider" ? 1 : "any"} value={String(node.default)} onChange={e => update(key, { ...node, default: numeric ? e.target.value === "" ? "" : Number(e.target.value) : e.target.value })} />}</Field>}
          <div className="input-field-footer"><span className="helper-text">연결 이름: {key} · 이름을 바꿔도 기존 연결은 유지됩니다.</span><Button variant="secondary" onClick={() => { const next = { ...properties }; delete next[key]; onChange({ ...value, properties: next, required: required.filter(k => k !== key) }); }}>항목 삭제<span className="sr-only"> {node.description || key}</span></Button></div>
        </div>
      </details>;
    })}
    <Button variant="secondary" disabled={Object.keys(properties).length >= 50} onClick={() => { let n = 1; while (`field_${n}` in properties) n++; onChange({ ...value, properties: { ...properties, [`field_${n}`]: { type: "string", description: "", "x-widget": "text" } } }); }}>＋ 입력 항목 추가</Button>
  </div>;
}
