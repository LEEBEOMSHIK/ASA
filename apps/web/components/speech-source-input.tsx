"use client";

import { useEffect, useState } from "react";
import { api, message } from "../lib/registry";
import { ActionIcon, Button, Field, InputRequirement } from "./ui";
import { Modal } from "./character-library";
import "./previous-answer-input.css";

type SceneSource = { request_id: string; version: number; title: string; cue_count: number };
const sourceValue = (source: SceneSource) => source.request_id + ":" + source.version;

export function SpeechSourceInput({ id, label, value, required, onChange }: {
  id: string; label: string; value: string; required: boolean; onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<SceneSource[]>([]);
  const [chosen, setChosen] = useState<SceneSource>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    let active = true;
    const timer = setTimeout(() => {
      api<SceneSource[]>("/audio/production-sources?" + new URLSearchParams({ q: query.trim() }))
        .then(result => { if (active) setItems(result); })
        .catch(error => { if (active) setError(message(error)); })
        .finally(() => { if (active) setLoading(false); });
    }, 150);
    return () => { active = false; clearTimeout(timer); };
  }, [open, query]);

  function showPicker() {
    setLoading(true);
    setError("");
    setOpen(true);
  }

  return <div className="editing-sources" role="group" aria-labelledby={id}>
    <div className="editing-source-heading">
      <h3 id={id}>{label} <InputRequirement required={required}/></h3>
      <Button variant="secondary" onClick={showPicker}><ActionIcon kind={value ? "edit" : "add"}/>
        {value ? "씬 구성 변경" : "씬 구성 선택"}</Button>
    </div>
    <p className="helper-text" role="status">{value
      ? chosen ? `${chosen.title} · 답변 v${chosen.version} · 발화 ${chosen.cue_count}개`
        : "저장된 씬 구성을 사용합니다."
      : "발화 시간표가 있는 씬 구성에서 대사와 내레이션을 가져옵니다."}</p>
    {open && <Modal title="음성으로 만들 씬 구성 선택" onClose={() => setOpen(false)}
      footer={<Button variant="secondary" onClick={() => setOpen(false)}><ActionIcon kind="close"/>닫기</Button>}>
      <div className="answer-picker">
        <Field id={id + "-search"} label="씬 구성 검색" hint="작품 제목이나 씬 내용으로 최근 답변을 검색합니다.">
          {props => <input {...props} type="search" value={query} maxLength={120} onChange={event => {
            setLoading(true); setError(""); setQuery(event.target.value);
          }}/>}
        </Field>
        {loading ? <p role="status">씬 구성을 불러오는 중…</p> : error ? <p role="alert">{error}</p>
          : items.length === 0 ? <p role="status">발화 시간표가 저장된 씬 구성 답변이 없습니다.</p>
          : <div className="answer-picker-list" aria-label="씬 구성 답변">
            {items.map(item => <button type="button" className="answer-source-card" key={sourceValue(item)}
              aria-pressed={value === sourceValue(item)} onClick={() => {
                setChosen(item); onChange(sourceValue(item)); setOpen(false);
              }}>
              <strong>{item.title}</strong><span>답변 v{item.version} · 발화 {item.cue_count}개</span>
            </button>)}
          </div>}
      </div>
    </Modal>}
  </div>;
}
