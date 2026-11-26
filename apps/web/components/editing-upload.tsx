"use client";

import { useId, useRef, useState } from "react";
import { message } from "../lib/registry";
import { ActionIcon, Button } from "./ui";
export type EditSource = {
  id: string;
  title: string;
  kind: string;
  duration?: number | null;
  media_url?: string;
  work_name?: string;
  source_name?: string;
};

export function EditingUpload({ selectedCount, remaining, onAdd, onBusy, onBrowse, uploadFile }: {
  selectedCount: number;
  remaining: number;
  onAdd: (item: EditSource) => void;
  onBusy: (busy: boolean) => void;
  onBrowse: () => void;
  uploadFile: (file: File) => Promise<EditSource>;
}) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const locked = useRef(false);
  const dragDepth = useRef(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [over, setOver] = useState(false);

  async function uploadFiles(files: File[]) {
    if (locked.current || input.current?.closest("fieldset:disabled") || files.length === 0) return;
    if (files.length > remaining) {
      setError(remaining
        ? `파일 ${files.length}개를 놓았습니다. 이번 요청에는 ${remaining}개까지 더 추가할 수 있습니다.`
        : "이번 요청의 자료 한도에 도달했습니다. 선택한 자료를 제외하면 추가할 수 있습니다.");
      return;
    }
    if (files.some(file => !file.size || file.size > 20 * 1024 * 1024 || !/\.(mp4|mov|webm)$/i.test(file.name))) {
      setError("MP4·MOV·WebM 파일을 하나당 20MB 이하로 선택해 주세요.");
      return;
    }

    locked.current = true;
    setBusy(true);
    onBusy(true);
    setError("");
    const failures: string[] = [];
    try {
      for (const file of files) {
        try {
          onAdd(await uploadFile(file));
        } catch (error) {
          const reason = error instanceof Error && error.message === "editing_upload_invalid"
            ? "영상을 읽지 못했거나 길이가 10분을 넘습니다."
            : message(error);
          failures.push(file.name + ": " + reason);
        }
      }
    } finally {
      locked.current = false;
      setBusy(false);
      onBusy(false);
      setError(failures.join(" / "));
    }
  }

  return <div className="editing-upload" role="group" aria-labelledby={id + "-title"}>
    <div className="editing-source-heading">
      <div className="editing-source-heading">
        <h4 id={id + "-title"}>외부 영상</h4>
        <span className="muted editing-source-count">{selectedCount}개 선택</span>
      </div>
      <Button variant="secondary" disabled={busy} onClick={onBrowse}>
        <ActionIcon kind="camera" />이전에 올린 영상
      </Button>
    </div>
    <div className={"video-dropzone editing-dropzone" + (over ? " is-over" : "")}
      tabIndex={0} role="group" aria-label="영상 파일 끌어 놓기" aria-describedby={id + "-formats"}
      onDragEnter={event => {
        if (!event.dataTransfer.types.includes("Files")) return;
        event.preventDefault();
        dragDepth.current += 1;
        if (!input.current?.matches(":disabled")) setOver(true);
      }}
      onDragOver={event => {
        if (!event.dataTransfer.types.includes("Files")) return;
        event.preventDefault();
        const canDrop = !input.current?.matches(":disabled");
        event.dataTransfer.dropEffect = canDrop ? "copy" : "none";
        setOver(canDrop);
      }}
      onDragLeave={() => {
        dragDepth.current = Math.max(0, dragDepth.current - 1);
        if (dragDepth.current === 0) setOver(false);
      }}
      onDrop={event => {
        event.preventDefault();
        dragDepth.current = 0;
        setOver(false);
        void uploadFiles(Array.from(event.dataTransfer.files));
      }}
      onPaste={event => {
        const files = Array.from(event.clipboardData.files);
        if (files.length) {
          event.preventDefault();
          void uploadFiles(files);
        } else if (event.clipboardData.getData("text")) {
          setError("영상 파일을 선택하거나 끌어 놓아 주세요.");
        }
      }}>
      <div className="editing-dropzone-copy">
        <strong>{over ? "여기에 놓아 추가하세요" : "영상 파일을 끌어 놓으세요"}</strong>
        <p className="helper-text" id={id + "-formats"}>MP4·MOV·WebM · 파일당 최대 20MB, 10분 · 파일 붙여넣기 가능</p>
      </div>
      <input ref={input} type="file" hidden multiple accept=".mp4,.mov,.webm" disabled={busy || !remaining}
        onChange={event => {
          void uploadFiles(Array.from(event.target.files ?? []));
          event.target.value = "";
        }} />
      <Button variant="secondary" disabled={busy || !remaining} onClick={() => input.current?.click()}>
        <ActionIcon kind="add" />영상 파일 선택
      </Button>
    </div>
    {busy && <p className="helper-text" role="status">영상을 확인하고 업로드 중입니다.</p>}
    {error && <p className="field-error" role="alert">{error}</p>}
  </div>;
}
