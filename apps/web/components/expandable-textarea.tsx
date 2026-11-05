"use client";
import { useId, useRef, useState, type ReactNode, type TextareaHTMLAttributes } from "react";
import { createPortal } from "react-dom";
import { Modal } from "./character-library";
import { Button } from "./ui";
import "./expandable-textarea.css";

type Props = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label: string;
  value: string;
  characterLimit?: number;
  viewOnly?: boolean;
  renderField?: (input: ReactNode, action: ReactNode) => ReactNode;
};

/** One controlled value: closing the enlarged editor never discards unsaved edits. */
export function ExpandableTextarea({ label, characterLimit, renderField, viewOnly = false, ...props }: Props) {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const id = useId();
  const count = Array.from(props.value).length;
  const exceeded = characterLimit !== undefined && count > characterLimit;
  function close() { setOpen(false); trigger.current?.focus(); }
  const actionLabel = viewOnly ? "크게 보기" : "크게 편집";
  const action = <button ref={trigger} type="button" className="button button--secondary expanded-editor-trigger"
      disabled={props.disabled} aria-label={`${label} ${actionLabel}`} title={actionLabel} onClick={() => setOpen(true)}>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5M3 3l6 6m12-6-6 6M3 21l6-6m12 6-6-6"/></svg>
      <span>{actionLabel}</span>
    </button>;
  const input = <textarea {...props}/>;
  return <div className="expandable-textarea">
    {renderField ? renderField(input, action) : <><div className="expanded-editor-trigger-row">{action}</div>{input}</>}
    {open && createPortal(<Modal title={`${label} · ${actionLabel}`} className="expanded-editor-dialog" onClose={close}
      footer={<><span className={exceeded ? "field-error" : "muted"}>{count.toLocaleString("ko-KR")}자{characterLimit !== undefined && ` / ${characterLimit.toLocaleString("ko-KR")}자`}</span><Button onClick={close}>{viewOnly ? "입력 화면으로 돌아가기" : "편집 화면으로 돌아가기"}</Button></>}>
      {viewOnly ? <div className="expanded-reading" role="region" aria-label={label} tabIndex={0}>{props.value || "아직 입력한 내용이 없습니다."}</div> : <>
      <p id={`${id}-hint`} className="helper-text">수정 내용은 원래 입력란에 바로 반영됩니다. 닫아도 유지되며, 돌아간 뒤 ‘저장’을 눌러야 저장됩니다.</p>
      <label className="sr-only" htmlFor={id}>{label}</label>
      <textarea {...props} id={id} autoFocus aria-describedby={`${id}-hint${exceeded ? ` ${id}-error` : ""}`} aria-invalid={exceeded || props["aria-invalid"]} className="expanded-editor-input"/>
      {exceeded && <p id={`${id}-error`} className="field-error" role="alert">저장 가능한 길이를 초과했습니다. 내용은 유지됩니다. 길이를 줄인 뒤 저장해 주세요.</p>}
      </>}
    </Modal>, document.body)}
  </div>;
}
