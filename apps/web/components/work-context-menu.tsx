"use client";
import { useLayoutEffect, useRef } from "react";

export function WorkContextMenu({ anchor, busy, hidden, onClose, onRename, onVisibility }: {
  anchor: HTMLButtonElement; busy: boolean; hidden: boolean;
  onClose: () => void; onRename: () => void; onVisibility: () => void;
}) {
  const menu = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const element = menu.current;
    if (!element) return;
    element.showPopover();
    const rect = anchor.getBoundingClientRect();
    const bounds = element.getBoundingClientRect();
    const gap = parseFloat(getComputedStyle(element).getPropertyValue("--space-2")) || 8;
    element.style.left = `${Math.max(gap, Math.min(rect.right - bounds.width, innerWidth - bounds.width - gap))}px`;
    element.style.top = `${Math.max(gap, Math.min(rect.bottom + gap, innerHeight - bounds.height - gap))}px`;
    element.querySelector<HTMLButtonElement>("button")?.focus({preventScroll:true});
    const dismiss = () => element.hidePopover();
    window.addEventListener("resize", dismiss);
    window.addEventListener("scroll", dismiss, true);
    return () => {
      window.removeEventListener("resize", dismiss);
      window.removeEventListener("scroll", dismiss, true);
    };
  }, [anchor]);
  return <div ref={menu} popover="auto" role="menu" aria-label="작업 옵션" className="work-context-menu"
    onToggle={event=>{if(event.newState==="closed")onClose();}}
    onKeyDown={event=>{
      if(event.key==="Escape") {event.preventDefault();menu.current?.hidePopover();anchor.focus({preventScroll:true});}
      if(["ArrowDown","ArrowUp","Home","End"].includes(event.key)) {
        event.preventDefault();
        const buttons=Array.from(menu.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)")??[]);
        if(!buttons.length)return;
        const index=buttons.indexOf(document.activeElement as HTMLButtonElement);
        const next=event.key==="Home"?0:event.key==="End"?buttons.length-1:(index+(event.key==="ArrowDown"?1:-1)+buttons.length)%buttons.length;
        buttons[next].focus();
      }
      if(event.key==="Tab") {menu.current?.hidePopover();anchor.focus({preventScroll:true});}
    }}>
    <button type="button" role="menuitem" disabled={busy} onClick={onRename}>작업 이름 수정</button>
    <button type="button" role="menuitem" disabled={busy} onClick={onVisibility}>{hidden?"최근 작업에 복원":"내 목록에서 숨기기"}</button>
  </div>;
}
