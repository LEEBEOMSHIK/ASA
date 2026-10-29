"use client";
import { useState } from "react";
import { type Definition, type SchemaNode, type Tool } from "../lib/registry";
import { Field } from "./ui";
import { SchemaEditor } from "./schema-editor";

const executionExamples = [
  { name: "대본 작가", inputLabel: "영상 주제", input: "처음 화분을 키우는 사람을 위한 물 주기 팁",
    outputLabel: "완성된 대본", output: "[도입] 화분에 물, 매일 주고 있나요?\n[본문] 먼저 흙의 상태를 확인해 보세요. 식물 종류와 환경에 따라 필요한 물의 양은 달라요.\n[마무리] 오늘은 내 화분에 맞는 관리법부터 찾아보세요.", note: "주제를 입력하면 대본을 받는 구조예요." },
  { name: "아이디어 기획자", inputLabel: "채널 관심사", input: "작은 집에서 식물을 키우는 일상",
    outputLabel: "영상 아이디어 목록", output: "1. 첫 화분을 고르기 전에 확인할 세 가지\n2. 작은 창가를 식물 공간으로 꾸미기\n3. 물 주기 기록을 시작하는 방법", note: "관심사를 입력하면 여러 아이디어를 받는 구조예요." },
  { name: "대본 검수자", inputLabel: "검토할 대본", input: "모든 식물에는 매일 물을 줘야 합니다. 물을 많이 줄수록 잘 자랍니다.",
    outputLabel: "검토 의견과 수정안", output: "검토 의견: 모든 식물에 같은 방법을 적용한다는 표현은 수정이 필요해요.\n수정안: 식물 종류와 흙의 상태에 맞춰 물 주기를 조절하세요.", note: "대본을 입력하면 개선 의견과 수정안을 받는 구조예요." },
];

export function ExecutionExample() {
  const [index, setIndex] = useState(0);
  const example = executionExamples[index];
  return <section className="execution-example" aria-labelledby="execution-example-title">
    <div className="section-heading"><div><h3 id="execution-example-title">실행할 때는 이렇게 사용해요</h3>
      <p className="muted">이해를 돕기 위한 고정 예시입니다. 현재 설정의 실행 결과가 아니며, 선택해도 설정은 바뀌지 않아요.</p></div></div>
    <div className="example-switch" role="group" aria-label="실행 예시 종류">{executionExamples.map((item, i) =>
      <button key={item.name} className="button button--secondary" type="button" aria-pressed={index === i} onClick={() => setIndex(i)}>{item.name}</button>)}</div>
    <div className="example-flow" aria-live="polite"><div className="example-pane"><span className="eyebrow">내가 입력하는 값 · 예시</span><h4>{example.inputLabel}</h4><p>{example.input}</p></div>
      <span className="example-arrow" aria-hidden="true">→</span>
      <div className="example-pane"><span className="eyebrow">받게 될 결과 · 예시</span><h4>{example.outputLabel}</h4><p>{example.output}</p></div></div>
    <p className="helper-text">{example.note} 아래에서는 실제 내용을 입력하지 않고, 어떤 정보를 받을지와 결과 형식을 설정해요.</p>
  </section>;
}

export function GroupedTools({ tools, selected, agentId, onChange }: {
  tools: Tool[]; selected: string[]; agentId?: string; onChange: (ids: string[]) => void;
}) {
  return <>
    <p className="muted">두 종류를 함께 선택할 수 있어요. 선택은 사용 권한을 주는 것이며, 실행 순서를 정하거나 모든 도구를 반드시 호출한다는 뜻은 아니에요.</p>
    {(["asa", "agent"] as const).map(kind => {
      const group = tools.filter(tool => tool.kind === kind);
      return <details className="tool-group tool-category" key={kind}><summary>{kind === "asa" ? "ASA 기본 도구" : "내가 만든 에이전트"}
        <span className="muted"> · {group.filter(t => selected.includes(t.id)).length}개 선택</span></summary>
        <p className="muted">{kind === "asa" ? "길이 검사처럼 ASA가 제공하는 기능이에요." : "‘도구로 등록’한 버전을 다른 에이전트의 도우미로 사용할 수 있어요."}</p>
        {group.length === 0 ? <p className="tool-empty">{kind === "asa" ? "아직 제공된 도구가 없어요." : "아직 도구로 등록한 에이전트가 없어요. 에이전트 초안을 저장한 뒤 ‘도구로 등록’을 눌러 주세요."}</p> :
          <div className="tool-choices">{group.map(tool => {
            const self = Boolean(agentId && tool.agent_id === agentId);
            const unavailable = self || !tool.available;
            return <label key={tool.id} className={`tool-choice${unavailable ? " tool-choice--unavailable" : ""}`}>
              <input type="checkbox" disabled={unavailable && !selected.includes(tool.id)} checked={selected.includes(tool.id)}
                onChange={e => onChange(e.target.checked ? [...selected, tool.id] : selected.filter(t => t !== tool.id))} />
              <span><strong>{tool.name}</strong><span className="muted">{tool.description}</span>
                {unavailable && <span className="helper-text">{self ? "자기 자신은 선택할 수 없어요." : tool.unavailable_reason}</span>}</span><small>v{tool.version}</small>
            </label>;
          })}</div>}
      </details>;
    })}
    <p className="helper-text">지금은 연결 설정을 저장하는 단계예요. 실제 AI 도구 호출은 아직 제공되지 않아요.</p>
  </>;
}

export const starters = [
  { name: "쇼츠 대본 작가", mark: "01", description: "주제를 짧고 매력적인 대본으로 바꿔요.",
    instructions: "주어진 주제로 30초 분량의 한국어 쇼츠 대본을 작성하세요. 첫 문장은 호기심을 끄는 질문으로 시작하고, 핵심 내용을 쉽게 설명한 뒤 짧은 마무리로 끝내세요. 확인되지 않은 사실은 단정하지 마세요.",
    input: "영상으로 만들 주제 (예: 고양이가 상자를 좋아하는 이유)", output: "도입, 본문, 마무리가 있는 30초 대본" },
  { name: "아이디어 기획자", mark: "02", description: "막연한 관심사에서 영상 아이디어를 찾아요.",
    instructions: "주어진 관심사에서 쇼츠 아이디어 5개를 제안하세요. 각각 제목, 시청자가 궁금해할 질문, 전달할 핵심 메시지를 포함하세요. 서로 겹치지 않는 관점으로 제안하세요.",
    input: "채널의 관심사나 분야 (예: 일상 속 과학)", output: "제목과 핵심 메시지를 포함한 아이디어 5개" },
  { name: "대본 검수자", mark: "03", description: "대본의 어색한 표현과 개선점을 찾아요.",
    instructions: "입력된 대본을 읽고 이해하기 어려운 표현, 흐름이 끊기는 부분, 사실 확인이 필요한 주장을 짚어주세요. 개선 이유와 수정안을 함께 제시하세요. 사실 여부를 확인할 수 없으면 확인이 필요하다고 표시하세요.",
    input: "검토할 대본 전체", output: "개선할 부분과 이유, 수정한 대본" },
];

export function starterDefinition(index: number): Definition {
  const s = starters[index];
  return { name: s.name, description: s.description, instructions: s.instructions, model_profile: "default", tools: [],
    input_schema: { type: "object", properties: { topic: { type: "string", description: s.input } }, required: ["topic"] },
    output_schema: { type: "string" },
    limits: { model_calls: 10, tool_calls: 20, depth: 2, seconds: 300 } };
}

export function FriendlyFields({ value, onChange, kind }: {
  value: SchemaNode; onChange: (node: SchemaNode) => void; kind: "input" | "output";
}) {
  const incoming = kind === "input";
  return <>
    {Object.entries(value.properties || {}).map(([key, node], i) => <Field key={key} id={`${kind}-description-${key}`}
      label={`${incoming ? "실행할 때 물어볼 항목" : "AI가 채울 답변 항목"} ${i + 1}`}
      hint={incoming ? `${(value.required || []).includes(key) ? "필수 항목" : "선택 항목"} · ${node.type === "string" ? "텍스트" : node.type === "object" ? "정보 묶음" : node.type === "array" ? "목록" : "값"}` : "예: 제목 · 대본 · 해시태그. AI가 이 항목에 어떤 내용을 작성하면 될지 적어 주세요."}>
      {p => <input {...p} maxLength={400} value={node.description || ""}
        placeholder={incoming ? `어떤 정보인가요? 예: 영상 주제 (${key})` : "예: 영상 제목, 30초 분량의 대본, 관련 해시태그"}
        onChange={e => onChange({ ...value, properties: { ...value.properties, [key]: { ...node, description: e.target.value } } })} />}
    </Field>)}
    {Object.keys(value.properties || {}).length === 0 && <p className="muted">세부 형식이 지정된 항목입니다. 아래에서 구성할 수 있어요.</p>}
    <details className="advanced"><summary>항목 추가 및 세부 형식 설정</summary>
      <p className="muted">다른 블록과 연결할 때 쓰는 이름과 형식입니다. 처음에는 기본 설정을 그대로 사용해도 됩니다.</p>
      <SchemaEditor value={value} onChange={onChange} />
    </details>
  </>;
}
