import { AgentList } from "../../../components/registry-lists";
import { RegistryShell } from "../../../components/registry-shell";
export default function AgentManagementPage() {
  return <RegistryShell adminOnly><AgentList manage /></RegistryShell>;
}
