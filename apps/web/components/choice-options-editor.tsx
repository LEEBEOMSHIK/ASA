"use client";
import { useRef, useState } from "react";
import type { SchemaNode } from "../lib/registry";
import { Button, Field } from "./ui";

export function ChoiceOptionsEditor({ id, node, onChange }: { id: string; node: SchemaNode; onChange: (node: SchemaNode) => void }) {
  const inputs = useRef<(HTMLInputElement | null)[]>([]);
  const [notice, setNotice] = useState("");
  const options = node.enum || [];
  function rename(index: number, value: string) {
    const next = { ...node, enum: options.map((old, i) => i === index ? value : old) };
    if (node.default !== undefined && node.default === options[index]) next.default = value;
    onChange(next);
    setNotice("");
  }
  function remove(index: number) {
    const next = { ...node, enum: options.filter((_, i) => i !== index) };
    if (node.default !== undefined && node.default === options[index]) {
      delete next.default;
      setNotice("기본값으로 사용하던 선택지를 삭제했습니다. 필요한 경우 기본값을 다시 선택하세요.");
    } else setNotice("선택지를 삭제했습니다.");
    onChange(next);
    requestAnimationFrame(() => inputs.current[Math.min(index, next.enum.length - 1)]?.focus());
  }
  return <fieldset className="choice-options-editor">
    <legend>선택지</legend>
    <p className="helper-text">각 입력칸이 하나의 선택지입니다. 사용자가 고를 내용을 적어 주세요.</p>
    <div className="choice-options-list">
      {options.map((value, index) => {
        const text = String(value);
        const error = !text.trim() ? "선택지 내용을 입력하거나 이 선택지를 삭제하세요." : options.some((v, i) => i !== index && String(v).trim() === text.trim()) ? "같은 선택지가 있습니다. 서로 다른 내용을 입력하세요." : undefined;
        return <div className="choice-option-row" key={index}>
          <Field id={`${id}-${index}`} label={`선택지 ${index + 1}`} error={error}>{p => <input {...p} ref={el => { inputs.current[index] = el; el?.setCustomValidity(error || ""); }} required value={text} placeholder="선택지 내용" onChange={e => rename(index, e.target.value)} onBlur={e => { if (e.target.value !== e.target.value.trim()) rename(index, e.target.value.trim()); }} />}</Field>
          <Button variant="secondary" disabled={options.length <= 1} aria-label={`선택지 ${index + 1} 삭제${text ? `: ${text}` : ""}`} onClick={() => remove(index)}>삭제</Button>
        </div>;
      })}
    </div>
    <div className="actions"><Button variant="secondary" disabled={options.length >= 100} onClick={() => { onChange({ ...node, enum: [...options, ""] }); setNotice(""); requestAnimationFrame(() => inputs.current[options.length]?.focus()); }}>＋ 선택지 추가</Button><span className="helper-text">{options.length} / 100개 · 최소 1개</span></div>
    {notice && <p className="helper-text" role="status">{notice}</p>}
  </fieldset>;
}
