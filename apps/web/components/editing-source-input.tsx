"use client";

import { useEffect, useRef, useState } from "react";
import { api, message, type Tool } from "../lib/registry";
import { isSpeechProductionOutput } from "../lib/work-layout";
import { ActionIcon, Button, Field } from "./ui";
import { Modal } from "./character-library";
import { EditingUpload } from "./editing-upload";
import "./editing.css";

export type EditSource = {
  id: string;
  title: string;
  kind: string;
  duration?: number | null;
  media_url?: string;
  work_name?: string;
  source_name?: string;
};

const categories = [
  { kind: "image", origin: "studio", label: "이미지", icon: "composition" },
  { kind: "video", origin: "studio", label: "영상", icon: "camera" },
  { kind: "audio", origin: "studio", label: "음원", icon: "music" },
  { kind: "video", origin: "upload", label: "이전에 올린 영상", icon: "camera" },
] as const;

type Category = (typeof categories)[number];
const sourceLimit = 32;

function belongsTo(source: EditSource, category: Category) {
  const uploaded = source.id.startsWith("reference:");
  const matchesKind = source.kind === category.kind || (category.kind === "audio" && source.kind === "music");
  return matchesKind && uploaded === (category.origin === "upload");
}

function sourceType(source: EditSource) {
  if (source.id.startsWith("reference:")) return "외부 영상";
  if (source.kind === "image") return "이미지";
  if (source.kind === "video") return "보관함 영상";
  return "음원";
}

function sourceDetails(source: EditSource) {
  return [sourceType(source), source.duration ? source.duration + "초" : ""].filter(Boolean).join(" · ");
}

function EditingSourcePicker({ category, selected, onToggle, onClose }: {
  category: Category;
  selected: EditSource[];
  onToggle: (source: EditSource) => void;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<EditSource[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const pages = Math.max(1, Math.ceil(total / 12));

  useEffect(() => {
    let active = true;
    const params = new URLSearchParams({ q: query.trim(), kind: category.kind, origin: category.origin, page: String(page) });
    const timer = setTimeout(() => {
      api<{ items: EditSource[]; total: number }>("/editing/sources?" + params)
        .then(result => {
          if (!active) return;
          setItems(result.items);
          setTotal(result.total);
          setError("");
        })
        .catch(error => { if (active) setError(message(error)); })
        .finally(() => { if (active) setLoading(false); });
    }, 150);
    return () => { active = false; clearTimeout(timer); };
  }, [category, page, query]);

  function changePage(next: number) {
    setLoading(true);
    setPage(next);
  }

  return <Modal title={category.label + " 선택"} onClose={onClose}
    footer={<>
      <span>이번 요청 {selected.length}개 선택 · 합산 최대 {sourceLimit}개</span>
      <Button onClick={onClose}><ActionIcon kind="confirm" />선택 완료</Button>
    </>}>
    <div className="editing-browser">
      <Field id="editing-source-search" label="자료 검색">
        {props => <input {...props} type="search" value={query} maxLength={120}
          placeholder="작품·작업·자료 이름" onChange={event => {
            setLoading(true);
            setQuery(event.target.value);
            setPage(1);
          }} />}
      </Field>
      <p className="helper-text" role="status">
        {loading ? "자료를 불러오는 중…" : !error && ("검색 결과 " + total + "개 · 이 종류에서 " + selected.filter(item => belongsTo(item, category)).length + "개 선택")}
      </p>
      {!loading && error && <p className="field-error" role="alert">{error}</p>}
      {!loading && !error && items.length === 0 && <p className="helper-text">조건에 맞는 자료가 없습니다.</p>}
      {!loading && !error && items.length > 0 && <div className="editing-source-grid">
        {items.map(item => {
          const checked = selected.some(source => source.id === item.id);
          return <button type="button" className="editing-source" key={item.id}
            aria-pressed={checked} disabled={!checked && selected.length >= sourceLimit} onClick={() => onToggle(item)}>
            {item.kind === "image" && item.media_url ? <img src={item.media_url} alt="" /> : <ActionIcon kind={category.icon} />}
            <strong>{item.title}</strong>
            <span>{[item.work_name || "작품 미지정", item.source_name].filter(Boolean).join(" · ")}</span>
            <span>{sourceDetails(item)}</span>
            <span>{checked ? "선택됨" : "선택"}</span>
          </button>;
        })}
      </div>}
      {!error && pages > 1 && <nav className="editing-actions" aria-label="편집 자료 페이지">
        <Button variant="secondary" disabled={loading || page === 1} onClick={() => changePage(page - 1)}><ActionIcon kind="undo" />이전</Button>
        <span>{page} / {pages}</span>
        <Button variant="secondary" disabled={loading || page >= pages} onClick={() => changePage(page + 1)}><ActionIcon kind="play" />다음</Button>
      </nav>}
    </div>
  </Modal>;
}

export function EditingSourceInput({ id, label, value, onChange }: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const [uploadBusy, setUploadBusy] = useState(false);
  const [category, setCategory] = useState<Category | null>(null);
  const [speechAgent, setSpeechAgent] = useState<string>();
  useEffect(() => {
    let active = true;
    api<Tool[]>("/tools").then(tools => {
      const agent = tools.find(tool => tool.kind === "agent" && tool.available
        && isSpeechProductionOutput(tool.output_schema));
      if (active) setSpeechAgent(agent?.agent_id);
    }).catch(() => {});
    return () => { active = false; };
  }, []);
  let selected: EditSource[] = [];
  try {
    const parsed = JSON.parse(value || "[]");
    if (Array.isArray(parsed)) selected = parsed.filter(item => item?.id && item.id !== "upload:pending");
  } catch {
    // The value may be incomplete when restoring an older draft.
  }
  const selectedRef = useRef(selected);
  const busyRef = useRef(false);
  selectedRef.current = selected;
  const externalCount = selected.filter(item => belongsTo(item, categories[3])).length;
  const remaining = Math.max(0, sourceLimit - selected.length);

  function publish(next: EditSource[]) {
    selectedRef.current = next;
    const items = busyRef.current ? [...next, { id: "upload:pending", title: "영상 업로드 중", kind: "video" }] : next;
    onChange(items.length ? JSON.stringify(items) : "");
  }

  function toggle(item: EditSource) {
    const current = selectedRef.current;
    if (current.some(source => source.id === item.id)) {
      publish(current.filter(source => source.id !== item.id));
    } else if (current.length < sourceLimit) {
      const { id, title, kind, duration, media_url, work_name, source_name } = item;
      publish([...current, { id, title, kind, duration, media_url, work_name, source_name }]);
    }
  }

  function moveEarlier(index: number) {
    const next = [...selectedRef.current];
    [next[index - 1], next[index]] = [next[index], next[index - 1]];
    publish(next);
  }

  return <section className="editing-sources" aria-labelledby={id}>
    <h3 id={id}>{label}</h3>
    <div className="editing-library" role="group" aria-labelledby={id + "-library"}>
      <div className="editing-source-heading">
        <h4 id={id + "-library"}>보관함 자료</h4>
        <span className="muted editing-source-count">{selected.length - externalCount}개 선택</span>
      </div>
      <div className="editing-library-options">
        {categories.slice(0, 3).map(option => <Button key={option.kind} className="editing-library-option"
          variant="secondary" disabled={uploadBusy} onClick={() => setCategory(option)}>
          <ActionIcon kind={option.icon} />
          <span>{option.kind === "image" ? "씬·캐릭터 이미지" : option.label} 추가</span>
          <span className="muted editing-library-count">{selected.filter(item => belongsTo(item, option)).length}개 선택</span>
        </Button>)}
      </div>
      {speechAgent && <div className="editing-actions">
        <a className="button button--secondary" href={"/?agent=" + encodeURIComponent(speechAgent)}
          target="_blank" rel="noopener">
          <ActionIcon kind="ai"/>대사·내레이션 만들기
        </a>
        <span className="helper-text">음성 제작에서 확정한 발화는 ‘음원 추가’에서 선택할 수 있습니다.</span>
      </div>}
    </div>
    <EditingUpload selectedCount={externalCount} remaining={remaining} onBrowse={() => setCategory(categories[3])}
      onAdd={item => publish([...selectedRef.current, item])}
      onBusy={busy => {
        busyRef.current = busy;
        setUploadBusy(busy);
        publish(selectedRef.current);
      }} />
    <div className="editing-selection">
      <h4>선택한 자료 {selected.length}개</h4>
      <p className="helper-text" role="status">
        보관함과 외부 영상 합산 최대 {sourceLimit}개 · {remaining ? `${remaining}개 더 추가 가능` : "한도에 도달했습니다"}
      </p>
      {selected.length > 0 && <p className="helper-text">목록 순서대로 영상과 이미지를 이어 붙입니다.</p>}
      {selected.length > 0 && <ol className="editing-selected">
        {selected.map((item, index) => <li key={item.id}>
          <div className="editing-selection-item">
            <strong>{index + 1}. {item.title}</strong>
            <span className="muted editing-selection-details">{sourceDetails(item)}</span>
          </div>
          <div className="editing-actions">
            <Button variant="secondary" disabled={uploadBusy || index === 0} onClick={() => moveEarlier(index)}
              aria-label={item.title + " 앞으로 이동"}><ActionIcon kind="undo" />앞으로</Button>
            <Button variant="secondary" disabled={uploadBusy} onClick={() => toggle(item)}
              aria-label={item.title + " 제외"}><ActionIcon kind="close" />제외</Button>
          </div>
        </li>)}
      </ol>}
    </div>
    {category && <EditingSourcePicker category={category} selected={selected} onToggle={toggle} onClose={() => setCategory(null)} />}
  </section>;
}
