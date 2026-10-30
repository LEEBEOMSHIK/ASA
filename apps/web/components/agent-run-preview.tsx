"use client";
import { useEffect, useRef, useState } from "react";
import { message, type Definition, type SchemaNode } from "../lib/registry";
import { Button, Card, StatusBadge } from "./ui";

import { AgentInput } from "./agent-input";

function entries(schema: SchemaNode): [string, SchemaNode][] {
  return schema.type === "object" ? Object.entries(schema.properties || {}) : [["value", schema]];
}

export function AgentRunPreview({ definition, onBack, customer = false, initialInput, onSave }: {
  definition: Pick<Definition, "name" | "description" | "input_schema"> & Partial<Pick<Definition, "instructions">>;
  onBack: () => void; customer?: boolean; initialInput?: unknown; onSave?: (input: unknown) => Promise<void>;
}) {
  const [values, setValues] = useState<Record<string, string>>(() => {
    if (initialInput === undefined) return Object.fromEntries(entries(definition.input_schema).filter(([, n]) => n.default !== undefined).map(([key, n]) => [key, String(n.default)]));
    const source = definition.input_schema.type === "object" ? initialInput as Record<string, unknown> : { value: initialInput };
    return Object.fromEntries(Object.entries(source).map(([key, value]) => [key, typeof value === "string" ? value : JSON.stringify(value)]));
  });
  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);
  const [checked, setChecked] = useState(false);
  const [error, setError] = useState("");
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus(); }, []);
  const input = entries(definition.input_schema);
  async function checkInput(event: React.FormEvent) {
    event.preventDefault(); setError("");
    if (savingRef.current) return;
    for (const [key, node] of input) {
      const required = definition.input_schema.type !== "object" || definition.input_schema.required?.includes(key);
      if (required && (values[key] === undefined || values[key] === "")) { setError(`${node.description || key}: 값을 입력하거나 선택해 주세요.`); return; }
      if (values[key] && node.enum && !node.enum.some(v => String(v) === values[key])) { setError(`${node.description || key}: 선택지에서 골라 주세요.`); return; }
      if (values[key] && ["number", "integer"].includes(node.type)) {
        const n = Number(values[key]);
        if (!Number.isFinite(n) || (node.type === "integer" && !Number.isInteger(n)) || n < (node.minimum ?? -Infinity) || n > (node.maximum ?? Infinity)) { setError(`${node.description || key}: 설정된 숫자 범위에 맞춰 입력해 주세요.`); return; }
      }
      if (!values[key] || !["object", "array"].includes(node.type)) continue;
      try {
        const parsed: unknown = JSON.parse(values[key]);
        if (node.type === "array" ? !Array.isArray(parsed) : parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error();
      } catch { setError(`${node.description || key}: ${node.type === "array" ? "목록 []" : "정보 묶음 {}"} 형태의 JSON을 입력해 주세요.`); return; }
    }
    if (onSave) {
      const payload: Record<string, unknown> = {};
      for (const [key, node] of input) {
        const value = values[key];
        if (value === undefined || value === "") continue;
        payload[key] = node.type === "string" ? value : ["integer", "number"].includes(node.type) ? Number(value) : JSON.parse(value);
      }
      savingRef.current = true; setSaving(true);
      try { await onSave(definition.input_schema.type === "object" ? payload : payload.value); }
      catch (e) { setError(message(e)); }
      finally { savingRef.current = false; setSaving(false); }
    } else setChecked(true);
  }
  return <section className="run-preview-screen">
    <Button variant="secondary" disabled={saving} onClick={onBack}>{customer ? "← 다른 에이전트 선택" : "← 설정 편집으로 돌아가기"}</Button>
    <div className="page-heading"><div><p className="eyebrow">AGENT RUN</p><h1 ref={heading} tabIndex={-1}>{definition.name || "새 에이전트"} 실행</h1><p className="muted">{definition.description || "정보를 입력하고 이 에이전트에게 작업을 맡기는 화면입니다."}</p></div><StatusBadge tone="warning">{customer ? "답변 생성" : "미리보기 · 실제 AI 호출 없음"}</StatusBadge></div>
    <p className="preview-banner">{customer ? "실행하면 답변 생성 요청이 접수됩니다. 대기·작성 상태와 결과는 최근 작업에서 확인할 수 있습니다. 현재는 등록된 답변 형식으로 생성하며, 실제 AI 호출에 비용이 발생합니다." : "현재 초안으로 만든 실행 화면 미리보기입니다. 입력한 내용은 서버에 보내거나 저장하지 않으며, 편집 화면으로 돌아가면 지워집니다."}</p>
    <div className="run-input-layout"><Card><h2>이번에는 어떤 작업을 맡길까요?</h2><p className="muted">{customer ? "주제와 원하는 방향을 구체적으로 알려 주세요." : "설정 설명을 쓰는 곳이 아닙니다. 이번 작업에 쓸 실제 내용을 입력해 보세요."}</p>
      <form onSubmit={checkInput}>
        <fieldset disabled={saving} className="request-fields">
        {input.map(([key, node], i) => {
          const required = definition.input_schema.type !== "object" || (definition.input_schema.required || []).includes(key);
          const label = node.description || `입력 항목 ${i + 1}`;
          return <AgentInput key={key} node={node} id={`run-input-${key}`} label={label} required={required} value={values[key] ?? ""} onChange={v => { setValues({ ...values, [key]: v }); setChecked(false); }} />;
        })}
        {input.length === 0 && <p>입력 없이 실행하도록 설정된 에이전트입니다.</p>}
        {error && <p role="alert" className="field-error">{error}</p>}
        <div className="actions"><Button type="submit">{saving ? "요청 접수 중…" : onSave ? "답변 생성 실행" : "입력 확인하기"}</Button>{!customer && <Button disabled aria-describedby="run-preview-unavailable">미리보기 · 실제 실행 없음</Button>}</div>
        <p id="run-preview-unavailable" className="helper-text">{onSave ? "등록된 에이전트 지침과 모델로 실행합니다. 도구를 연결한 에이전트의 실행은 아직 지원하지 않습니다." : "입력 확인은 이 화면에서만 수행합니다. 세부 형식 검증과 실제 AI 실행은 이 미리보기에서 제공하지 않습니다."}</p>
        </fieldset>
      </form>
      {checked && <div role="status" className="notice"><strong>입력 내용을 확인했어요.</strong><p>실제 실행은 하지 않았습니다. 아래에서 입력한 내용을 확인할 수 있어요.</p>
        <dl>{input.map(([key, node], i) => <div key={key}><dt>{node.description || `입력 항목 ${i + 1}`}</dt><dd className="run-entered-value">{values[key] || "입력 없음"}</dd></div>)}</dl></div>}
    </Card>{!customer && <details className="advanced"><summary>에이전트 지침</summary><p className="run-entered-value">{definition.instructions || "아직 지침을 작성하지 않았어요."}</p></details>}</div>
  </section>;
}
