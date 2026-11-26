import { DesignSystemPreview } from "../../../components/design-system-preview";
import { RegistryShell } from "../../../components/registry-shell";

export default function DesignSystemPage() {
  return <RegistryShell adminOnly><DesignSystemPreview /></RegistryShell>;
}
