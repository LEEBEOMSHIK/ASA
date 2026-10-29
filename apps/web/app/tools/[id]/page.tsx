import { ToolDetail } from "../../../components/tool-detail";
import { RegistryShell } from "../../../components/registry-shell";
export default async function ToolPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <RegistryShell><ToolDetail id={id} /></RegistryShell>;
}
