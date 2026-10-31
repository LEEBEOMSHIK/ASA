import { agentIcons } from "../lib/agent-icons";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { HelpText } from "./help-text";
export { HelpText } from "./help-text";

export function AgentIcon({icon="bot"}: {icon?: string}) {
  const selected=agentIcons.find(item=>item.id===icon) || agentIcons[0];
  return <span className="agent-avatar" aria-hidden="true" data-agent-icon={selected.id}><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{selected.id==="bot" && <rect x="4" y="6" width="16" height="14" rx="4"/>}<path d={selected.path}/></svg></span>;
}

export function ExternalLink({ href, children }: { href: string; children: ReactNode }) {
  return <a className="external-link" href={href} target="_blank" rel="noreferrer">
    <span>{children}</span><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M14 4h6v6M20 4l-9 9M10 4H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-5"/></svg>
    <span className="sr-only"> (새 탭)</span>
  </a>;
}

export function StudioNavigation({ active, includeHome = true, includeAdmin = false }: { active: string; includeHome?: boolean; includeAdmin?: boolean }) {
  const items = [
    { href: "/", label: "작업 공간", icon: "work" },
    { href: "/automations", label: "자동화 빌더", icon: "flow" },
    { href: "/agents", label: "에이전트", icon: "agent" },
    { href: "/characters", label: "캐릭터 보관함", icon: "agent" },
    { href: "/tools", label: "도구 라이브러리", icon: "tools" },
    ...(includeAdmin ? [{ href: "/models", label: "AI 모델 관리", icon: "tools" }, { href: "/monitoring", label: "AI 사용량·비용", icon: "usage" }] : []),
  ];
  return <nav className="studio-navigation" aria-label="스튜디오 메뉴">
    <p className="studio-nav-label">스튜디오</p>
    {items.filter(item => includeHome || item.href !== "/").map(item => <a key={item.href} href={item.href} className="studio-nav-item" aria-current={active === item.href ? "page" : undefined}>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        {item.icon === "usage" ? <><path d="M4 3v18h17M8 16v-5M13 16V7M18 16V4"/></> : item.icon === "flow" ? <><rect x="3" y="3" width="7" height="6" rx="2"/><rect x="14" y="15" width="7" height="6" rx="2"/><path d="M6.5 9v9H14M10 6h7v9"/></> : item.icon === "agent" ? <><rect x="4" y="6" width="16" height="14" rx="4"/><path d="M12 3v3M8 11v2M16 11v2M9 16h6"/></> : item.icon === "tools" ? <><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><path d="M17.5 14v7M14 17.5h7"/></> : <><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M8 4v16M12 9h5M12 14h3"/></>}
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

export function Field({ id, label, hint, help, annotation, error, children }: {
  id: string; label: string; hint?: string; help?: ReactNode; annotation?: string; error?: string;
  children: (props: { id: string; "aria-describedby"?: string; "aria-invalid": boolean }) => ReactNode;
}) {
  const description = [hint ? `${id}-hint` : "", error ? `${id}-error` : ""].filter(Boolean).join(" ");
  return <div className="field">
    {help || annotation ? <div className="help-row"><label htmlFor={id}>{label}</label>{annotation?.includes("AI") ? <HelpText ai label={`${label} · ${annotation}`}><strong>{annotation}</strong>{help && <div>{help}</div>}</HelpText> : <>{annotation ? <HelpText kind={annotation === "관리용" ? "management" : "settings"} label={`${label} · ${annotation}`}><strong>{annotation}</strong><div>{help || (annotation === "관리용" ? "에이전트를 구분하기 위한 정보입니다. 현재 AI 생성 프롬프트에는 포함되지 않습니다." : "AI 호출에 적용되는 설정입니다.")}</div></HelpText> : help && <HelpText label={label}>{help}</HelpText>}</>}</div> : <label htmlFor={id}>{label}</label>}
    {children({ id, "aria-describedby": description || undefined, "aria-invalid": Boolean(error) })}
    {hint && <p id={`${id}-hint`} className="muted">{hint}</p>}
    {error && <p id={`${id}-error`} className="field-error" role="alert">{error}</p>}
  </div>;
}

export function SettingsSection({ title, description, action, children }: {
  title: string; description?: string; action?: ReactNode; children: ReactNode;
}) {
  return <section className="settings-section card">
    <div className="settings-heading"><div><h2>{title}</h2>{description && <p className="muted">{description}</p>}</div>{action && <div className="settings-heading-action">{action}</div>}</div>
    <div className="settings-content">{children}</div>
  </section>;
}

export { SelectCombobox } from "./select-combobox";
