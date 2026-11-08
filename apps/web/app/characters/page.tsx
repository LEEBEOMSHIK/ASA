import { RegistryShell } from "../../components/registry-shell";
import { ProductionLibrary } from "../../components/production-library";
export default async function CharactersPage({searchParams}:{searchParams:Promise<{view?:string}>}) {
  return <RegistryShell><ProductionLibrary legacyView={(await searchParams).view}/></RegistryShell>;
}
