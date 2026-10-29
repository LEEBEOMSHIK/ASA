"use client";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

type Preference = "light" | "dark" | "system";
const key = "asa-theme";
function preference(value: string | null): Preference {
  return value === "dark" || value === "system" ? value : "light";
}
function apply(value: Preference) {
  document.documentElement.dataset.theme = value === "system"
    ? window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
    : value;
}
const ThemeContext = createContext<{ value: Preference | null; change: (value: Preference) => void }>({ value: null, change: () => {} });

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [value, setValue] = useState<Preference | null>(null);
  useEffect(() => {
    let initial: Preference = "light";
    try { initial = preference(localStorage.getItem(key)); } catch { /* Storage may be disabled. */ }
    setValue(initial); apply(initial);
    const sync = (event: StorageEvent) => {
      if (event.key === key || event.key === null) {
        const next = preference(event.newValue); setValue(next); apply(next);
      }
    };
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, []);
  useEffect(() => {
    if (value === null) return;
    apply(value);
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const sync = () => { if (value === "system") apply(value); };
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, [value]);
  function change(next: Preference) {
    setValue(next); apply(next);
    try { localStorage.setItem(key, next); } catch { /* Current page still changes. */ }
  }
  return <ThemeContext.Provider value={{ value, change }}>{children}</ThemeContext.Provider>;
}

export function ThemeSelect() {
  const { value, change } = useContext(ThemeContext);
  return <label className="theme-select"><span>화면 모드</span><select disabled={value === null} value={value || "light"} onChange={event => change(preference(event.target.value))}>
    <option value="light">밝게</option><option value="dark">어둡게</option><option value="system">시스템 설정</option>
  </select></label>;
}
