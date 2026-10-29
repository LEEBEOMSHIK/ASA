import { AgentEditor } from "../../../components/agent-editor";
import { RegistryShell } from "../../../components/registry-shell";
export default async function AgentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <RegistryShell><AgentEditor id={id} /></RegistryShell>;
}
