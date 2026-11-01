import { BrandSettings } from "../../../components/brand-settings";
import { RegistryShell } from "../../../components/registry-shell";
export default function BrandingPage() {
  return <RegistryShell adminOnly><BrandSettings/></RegistryShell>;
}
