"use client";
import type { SchemaNode } from "../lib/registry";
import { conditionChoices, conditionValueLabel } from "../lib/input-requirements";
import { Field } from "./ui";

export function InputRequirementEditor({ field, schema, onChange }: {
  field: string; schema: SchemaNode; onChange: (schema: SchemaNode) => void;
}) {
  const properties = schema.properties || {};
  const node = properties[field];
  const required = schema.required || [];
  const rule = node["x-required-when"];
  const mode = rule ? "conditional" : required.includes(field) ? "always" : "optional";
  const sources = Object.entries(properties).filter(([key, value]) =>
    key !== field && conditionChoices(value).length > 0);
  const choices = conditionChoices(properties[rule?.field || ""]);
  const valid = rule && sources.some(([key]) => key === rule.field) &&
    choices.some(value => value === rule.equals && value !== "");
  const id = `requirement-${field}`;

  function updateRule(next: NonNullable<SchemaNode["x-required-when"]>) {
    onChange({ ...schema, required: required.filter(key => key !== field),
      properties: { ...properties, [field]: { ...node, "x-required-when": next } } });
  }
  function changeMode(next: string) {
    const updated = { ...node };
    delete updated["x-required-when"];
    if (next === "conditional") updated["x-required-when"] = { field: "", equals: "" };
    onChange({ ...schema, properties: { ...properties, [field]: updated },
      required: next === "always" ? [...required.filter(key => key !== field), field]
        : required.filter(key => key !== field) });
  }

  return <div className="input-requirement-editor">
    <Field id={id} label="입력 조건" hint={mode === "conditional"
      ? "예: 작업 방식에서 ‘이미지 기반’을 선택한 경우에만 이 항목을 필수로 요청합니다."
      : mode === "always" ? "실행할 때마다 입력합니다." : "비워 두어도 실행할 수 있습니다."}>
      {p => <select {...p} value={mode} onChange={e => changeMode(e.target.value)}>
        <option value="always">항상 필수</option>
        <option value="conditional">조건부 필수</option>
        <option value="optional">선택</option>
      </select>}
    </Field>
    {rule && <div className="input-condition-panel">
      <div className="input-form-grid">
        <Field id={id+"-field"} label="조건을 확인할 항목">
          {p => <select {...p} value={rule.field} onChange={e => updateRule({ field: e.target.value, equals: "" })}>
            <option value="">항목 선택</option>
            {sources.map(([key, source]) => <option key={key} value={key}>{source.description || key}</option>)}
            {rule.field && !sources.some(([key]) => key === rule.field) &&
              <option value={rule.field}>기존 조건 항목 · 다시 선택하세요</option>}
          </select>}
        </Field>
        <Field id={id+"-value"} label="이 값을 선택하면 필수" error={!valid ? "조건 항목과 값을 선택해 주세요." : undefined}>
          {p => <select {...p} disabled={!choices.length} value={choices.findIndex(value => value === rule.equals)}
            onChange={e => updateRule({ ...rule, equals: choices[Number(e.target.value)] ?? "" })}>
            <option value={-1}>선택값 지정</option>
            {choices.map((value, i) => <option key={i} value={i}>{conditionValueLabel(value)}</option>)}
          </select>}
        </Field>
      </div>
      {!sources.length && <p className="helper-text">먼저 다른 입력 항목에 라디오 버튼이나 선택 목록을 추가해 주세요.</p>}
      <p className="helper-text">그 외에는 선택 입력입니다. 조건이 바뀌어도 사용자가 입력한 내용은 유지됩니다.</p>
    </div>}
  </div>;
}
