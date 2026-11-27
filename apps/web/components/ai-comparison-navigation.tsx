"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ActionIcon } from "./ui";
import styles from "./audio-comparison.module.css";

const tabs = [
  { href: "/video-comparison", label: "영상 AI", icon: "camera" },
  { href: "/video-comparison/audio", label: "음성 AI", icon: "voice" },
] as const;

export function AIComparisonNavigation() {
  const pathname = usePathname();
  return <nav className={styles.tabs} aria-label="AI 비교 유형">
    {tabs.map(({ href, label, icon }) =>
      <Link key={href} href={href}
        className="button button--secondary"
        aria-current={pathname === href ? "page" : undefined}>
        <ActionIcon kind={icon} />{label}
      </Link>
    )}
  </nav>;
}
