import { RegistryShell } from "../../../components/registry-shell";
import { WorkManagement } from "../../../components/work-management";

export default function WorkHistoryPage() {
  return <RegistryShell adminOnly><WorkManagement/></RegistryShell>;
}
