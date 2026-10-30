"use client";

import { useId, useState, type ReactNode } from "react";

/** Inline disclosure: touch and keyboard users get the same help as mouse users. */
export function HelpText({ label, children, ai = false, kind }: { label: string; children: ReactNode; ai?: boolean; kind?: "management" | "settings" }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return <>
    <button type="button" className={`help-trigger${ai ? " help-trigger--ai" : kind ? " help-trigger--annotation" : ""}`} aria-label={`${label} 도움말`} title={label}
      aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}
      onKeyDown={event => { if (event.key === "Escape") { event.preventDefault(); setOpen(false); } }}>
      {ai ? <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m10 3 2.2 6.8L19 12l-6.8 2.2L10 21l-2.2-6.8L1 12l6.8-2.2L10 3Z"/><path d="M20 2v6M17 5h6"/></svg> : kind ? <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{kind === "management" ? <><rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6M9 12h6M9 16h4"/></> : <><path d="M4 7h6M14 7h6M4 17h10M18 17h2"/><circle cx="12" cy="7" r="2"/><circle cx="16" cy="17" r="2"/></>}</svg> : <span aria-hidden="true">?</span>}
    </button>
    <div id={id} className="help-content" hidden={!open}>{children}</div>
  </>;
}
