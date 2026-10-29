"use client";
import { useEffect, useState } from "react";
import { Button } from "./ui";

export function useSidebarCollapse() {
  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => {
    try { setCollapsed(localStorage.getItem("asa-sidebar-collapsed") === "true"); } catch { /* Storage is optional. */ }
  }, []);
  function toggle() {
    setCollapsed(value => {
      try { localStorage.setItem("asa-sidebar-collapsed", String(!value)); } catch { /* Keep in-memory preference. */ }
      return !value;
    });
  }
  return { collapsed, toggle };
}

export function SidebarToggle({ collapsed, toggle, controls }: { collapsed: boolean; toggle: () => void; controls: string }) {
  return <Button variant="secondary" className="desktop-sidebar-toggle" aria-label={collapsed ? "메뉴 열기" : "메뉴 접기"} title={collapsed ? "메뉴 열기" : "메뉴 접기"} aria-expanded={!collapsed} aria-controls={controls} onClick={toggle}>
    <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/><path d={collapsed?"m13 9 3 3-3 3":"m16 9-3 3 3 3"}/></svg>
  </Button>;
}
