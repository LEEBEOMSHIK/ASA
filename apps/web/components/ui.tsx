import type { ButtonHTMLAttributes, ReactNode } from "react";

export function StudioNavigation({ active, includeHome = true }: { active: string; includeHome?: boolean }) {
  const items = [
    { href: "/", label: "작업 공간", icon: "work" },
    { href: "/automations", label: "자동화 빌더", icon: "flow" },
    { href: "/agents", label: "에이전트", icon: "agent" },
    { href: "/tools", label: "도구 라이브러리", icon: "tools" },
  ];
  return <nav className="studio-navigation" aria-label="스튜디오 메뉴">
    <p className="studio-nav-label">스튜디오</p>
    {items.filter(item => includeHome || item.href !== "/").map(item => <a key={item.href} href={item.href} className="studio-nav-item" aria-current={active === item.href ? "page" : undefined}>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        {item.icon === "flow" ? <><rect x="3" y="3" width="7" height="6" rx="2"/><rect x="14" y="15" width="7" height="6" rx="2"/><path d="M6.5 9v9H14M10 6h7v9"/></> : item.icon === "agent" ? <><rect x="4" y="6" width="16" height="14" rx="4"/><path d="M12 3v3M8 11v2M16 11v2M9 16h6"/></> : item.icon === "tools" ? <><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><path d="M17.5 14v7M14 17.5h7"/></> : <><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M8 4v16M12 9h5M12 14h3"/></>}
      </svg><span>{item.label}</span>{active === item.href && <span className="studio-current" aria-hidden="true"/>}
    </a>)}
  </nav>;
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" };
export function Button({ variant = "primary", className = "", type = "button", ...props }: ButtonProps) {
  return <button type={type} className={`button button--${variant} ${className}`} {...props} />;
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`card ${className}`}>{children}</div>;
}

export function StatusBadge({ children, tone = "neutral" }: {
  children: ReactNode; tone?: "neutral" | "success" | "warning" | "danger";
}) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}

export function Field({ id, label, hint, error, children }: {
  id: string; label: string; hint?: string; error?: string;
  children: (props: { id: string; "aria-describedby"?: string; "aria-invalid": boolean }) => ReactNode;
}) {
  const description = [hint ? `${id}-hint` : "", error ? `${id}-error` : ""].filter(Boolean).join(" ");
  return <div className="field">
    <label htmlFor={id}>{label}</label>
    {children({ id, "aria-describedby": description || undefined, "aria-invalid": Boolean(error) })}
    {hint && <p id={`${id}-hint`} className="muted">{hint}</p>}
    {error && <p id={`${id}-error`} className="field-error" role="alert">{error}</p>}
  </div>;
}
