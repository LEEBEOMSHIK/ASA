import type { ReactNode } from "react";
import { AIComparisonNavigation } from "../../components/ai-comparison-navigation";
import { RegistryShell } from "../../components/registry-shell";

export default function AIComparisonLayout({ children }: { children: ReactNode }) {
  return <RegistryShell>
    <AIComparisonNavigation />
    {children}
  </RegistryShell>;
}
