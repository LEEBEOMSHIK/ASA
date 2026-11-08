"use client";

import { useEffect, useId, useLayoutEffect, useRef, useState, type MouseEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { navigationItems } from "../lib/navigation";
import { navigationAccent } from "../lib/navigation-color";
import { useNavigationPreferences } from "./navigation-preferences";

/** Render names outside the scrollable icon rail without changing its width. */
export function NavigationLink({ href, label, current, className = "", iconOnly = false, children }: {
  href: string; label: string; current?: boolean; className?: string; iconOnly?: boolean; children: ReactNode;
}) {
  const id = useId();
  const preferences = useNavigationPreferences();
  const menu = navigationItems.find(item=>item.href===href)?.id;
  const accent = menu ? preferences.items[menu]?.color : null;
  const link = useRef<HTMLAnchorElement>(null);
  const text = useRef<HTMLSpanElement>(null);
  const hint = useRef<HTMLDivElement>(null);
  const [anchor, setAnchor] = useState<DOMRect | null>(null);
  const [position, setPosition] = useState({ left: 0, top: 0 });
  function close() { setAnchor(null); }
  function blur() {
    if (!link.current?.matches(":hover") && !hint.current?.matches(":hover")) close();
  }
  function show() {
    if (iconOnly || text.current?.getBoundingClientRect().width === 0) {
      setAnchor(link.current!.getBoundingClientRect());
    }
  }
  function leave(event: MouseEvent<HTMLElement>) {
    const next = event.relatedTarget;
    // The portal includes the visual gap, so crossing to the name needs no grace timer.
    if (next instanceof Node && (link.current?.contains(next) || hint.current?.contains(next))) return;
    if (document.activeElement !== link.current) close();
  }
  useLayoutEffect(() => {
    if (!anchor || !hint.current) return;
    const box = hint.current.getBoundingClientRect();
    const gap = parseFloat(getComputedStyle(hint.current).getPropertyValue("--space-2")) || 8;
    setPosition({
      left: Math.max(gap, Math.min(anchor.right, window.innerWidth - box.width - gap)),
      top: Math.max(gap, Math.min(anchor.top + (anchor.height - box.height) / 2, window.innerHeight - box.height - gap)),
    });
  }, [anchor]);
  useEffect(() => {
    if (!anchor) return;
    const dismiss = () => setAnchor(null);
    const scroll = () => {
      const rect = link.current?.getBoundingClientRect();
      if (document.activeElement === link.current && rect && rect.bottom > 0 && rect.top < window.innerHeight) {
        setAnchor(rect);
      } else dismiss();
    };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") dismiss(); };
    window.addEventListener("resize", dismiss);
    window.addEventListener("scroll", scroll, true);
    window.addEventListener("keydown", escape);
    return () => {
      window.removeEventListener("resize", dismiss);
      window.removeEventListener("scroll", scroll, true);
      window.removeEventListener("keydown", escape);
    };
  }, [anchor]);
  return <>
    <a ref={link} href={href} aria-label={label} aria-current={current ? "page" : undefined}
      {...navigationAccent(accent)} aria-keyshortcuts={preferences.available ? "Shift+F10" : undefined}
      className={`studio-nav-item ${className}`} aria-describedby={anchor ? id : undefined}
      onContextMenu={event=>{if(preferences.available&&menu){event.preventDefault();close();link.current?.focus();preferences.open(menu);}}}
      onKeyDown={event=>{if(preferences.available&&menu&&(event.key==="ContextMenu"||(event.shiftKey&&event.key==="F10"))){event.preventDefault();close();preferences.open(menu);}}}
      onMouseEnter={show} onMouseLeave={leave} onFocus={show} onBlur={blur} onClick={close}>
      {children}{!iconOnly && <span ref={text}>{label}</span>}
      {current && <span className="studio-current" aria-hidden="true"/>}
    </a>
    {anchor && createPortal(<div ref={hint} id={id} role="tooltip" className="studio-nav-tooltip"
      style={position} onMouseLeave={leave}><span className="studio-nav-tooltip-content">{label}</span></div>, document.body)}
  </>;
}
