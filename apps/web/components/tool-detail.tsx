"use client";
import { useEffect, useState } from "react";
import { api, message, type SchemaNode, type Tool } from "../lib/registry";
import { Card, StatusBadge } from "./ui";

function example(schema: SchemaNode, output: boolean): unknown {
  switch (schema.type) {
    case "object": return Object.fromEntries(Object.entries(schema.properties || {}).map(([key, value]) => [key, example(value, output)]));
    case "array": return schema.items ? [example(schema.items, output)] : [];
    case "integer": case "number": return schema.minimum ?? 0;
    case "boolean": return false;
    default: return output ? "AI가 작성할 답변" : "사용자가 입력할 내용";
  }
}

function SchemaExample({ title, schema, sample, output = false }: {
  title: string; schema?: SchemaNode; sample?: unknown; output?: boolean;
}) {
  const types: Record<string, string> = { string: "글", object: "항목별 답변", array: "목록", integer: "정수", number: "숫자", boolean: "예 / 아니요" };
  return <Card><h2>{title}</h2>{!schema?.type ? <p className="muted">준비 중인 도구입니다. 입력·결과 형식은 아직 정해지지 않았습니다.</p> : <>
    {schema.type === "object" ? <dl className="tool-fields">{Object.entries(schema.properties || {}).map(([key, value]) => <div key={key}>
      <dt>{value.description || key} <span className="muted">({key})</span></dt>
      <dd>{types[value.type] || value.type}{!output && (schema.required?.includes(key) ? " · 필수 입력" : " · 선택 입력")}
        {value.maxLength !== undefined && ` · 최대 ${value.maxLength}자`}
        {value.minimum !== undefined && ` · 최소 ${value.minimum}`}{value.maximum !== undefined && ` · 최대 ${value.maximum}`}</dd>
    </div>)}</dl> : <p>{schema.type === "string" && output ? "AI가 자유로운 글로 답변합니다." : types[schema.type] || schema.type}</p>}
    <h3>{sample === undefined ? "형식을 이해하기 위한 예시" : "사용 예시"}</h3>
    <pre className="tool-example">{JSON.stringify(sample === undefined ? example(schema, output) : sample, null, 2)}</pre>
    <p className="muted">{sample === undefined ? "내용과 값은 자리 표시용입니다. 실제 입력이나 AI 실행 결과가 아닙니다." : "사용 방법을 설명하는 고정 예시입니다. 이 화면에서 실행한 결과가 아닙니다."}</p>
    <details><summary>전체 항목 설정 보기</summary><pre className="tool-example">{JSON.stringify(schema, null, 2)}</pre></details>
  </>}</Card>;
}

export function ToolDetail({ id }: { id: string }) {
  const [tool, setTool] = useState<Tool | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    // Colons are valid path characters; keep them literal through the API rewrite.
    const pathId = encodeURIComponent(id.replace(/%3A/gi, ":")).replace(/%3A/gi, ":");
    api<Tool>(`/tools/${pathId}`).then(data => { if (active) setTool(data); }).catch(e => { if (active) setError(message(e)); });
    return () => { active = false; };
  }, [id]);
  return <><a href="/tools">← 도구 목록</a>{error ? <p role="alert">{error}</p> : !tool ? <p role="status">도구를 불러오는 중입니다…</p> : <>
    <div className="page-heading"><div><p className="eyebrow">TOOL DETAILS</p><h1>{tool.name}</h1><p className="muted">{tool.description}</p></div>
      <div className="badge-row"><StatusBadge>{tool.kind === "asa" ? "ASA 기본 도구" : "내가 만든 에이전트"}</StatusBadge><StatusBadge>버전 {tool.version}</StatusBadge></div></div>
    <div className="tool-detail-stack"><Card><h2>어떻게 사용하나요?</h2>
      <p>{tool.usage || (tool.kind === "agent" ? "다른 에이전트의 ‘함께 쓸 도구’에서 이 에이전트를 선택하세요. 실행 연결이 제공되면 AI가 필요한 때 아래 입력을 전달하고 답변을 받아 활용합니다." : "에이전트의 ‘함께 쓸 도구’에서 선택할 수 있는 ASA 제공 기능입니다.")}</p>
      <p role="status"><StatusBadge tone={tool.execution_available ? "success" : "warning"}>{tool.execution_available ? "실행 가능" : "실행 연결 준비 중"}</StatusBadge> {tool.unavailable_reason}</p>
      {tool.agent_id ? <><p className="muted">등록된 버전 {tool.version}의 설정입니다. 원본 초안을 수정해도 이 버전은 바뀌지 않습니다. 변경 내용을 사용하려면 새 버전으로 도구에 등록하세요.</p><a href={`/agents/${tool.agent_id}`}>원본 에이전트 편집 →</a></> : <p className="muted">ASA 기본 도구는 개발자가 기능과 버전을 관리합니다.</p>}
    </Card>
    <div className="tool-example-grid"><SchemaExample title="어떤 정보를 전달하나요?" schema={tool.input_schema} sample={tool.example_input} /><SchemaExample title="어떤 답을 받나요?" schema={tool.output_schema} sample={tool.example_output} output /></div>
    {!!tool.dependencies?.length && <Card><h2>이 도구가 함께 쓰는 도구</h2><ul>{tool.dependencies.map(dependency => <li key={dependency}><a href={`/tools/${encodeURIComponent(dependency)}`}>{dependency}</a></li>)}</ul></Card>}
    </div>
  </>}</>;
}
