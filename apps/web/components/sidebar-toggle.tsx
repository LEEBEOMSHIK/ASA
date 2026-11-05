"use client";
import { useEffect, useState } from "react";
import { Button } from "./ui";

export function SidebarHome() {
  return <a href="/" className="studio-nav-item sidebar-home" title="홈 · 작업 공간" aria-label="작업 공간 홈으로 이동">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" aria-hidden="true"><path d="m3 10 9-7 9 7v10H15v-7H9v7H3Z"/></svg>
  </a>;
}

export function useSidebarCollapse(key="asa-menu-rail-collapsed", initiallyCollapsed=true) {
  const [collapsed, setCollapsed] = useState(initiallyCollapsed);
  useEffect(() => {
    try { const saved=localStorage.getItem(key); setCollapsed(saved===null ? initiallyCollapsed : saved==="true"); } catch { /* Storage is optional. */ }
  }, [key,initiallyCollapsed]);
  function toggle() {
    setCollapsed(value => {
      try { localStorage.setItem(key, String(!value)); } catch { /* Keep in-memory preference. */ }
      return !value;
    });
  }
  return { collapsed, toggle };
}

export function SidebarToggle({ collapsed, toggle, controls, label }: { collapsed: boolean; toggle: () => void; controls: string; label?: string }) {
  return <Button variant="secondary" className="desktop-sidebar-toggle" aria-label={label ?? (collapsed ? "메뉴 열기" : "메뉴 접기")} title={label ?? (collapsed ? "메뉴 열기" : "메뉴 접기")} aria-expanded={!collapsed} aria-controls={controls} onClick={toggle}>
    <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/><path d={collapsed?"m13 9 3 3-3 3":"m16 9-3 3 3 3"}/></svg>
  </Button>;
}
