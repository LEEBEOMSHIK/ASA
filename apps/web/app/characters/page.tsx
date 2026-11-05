import { RegistryShell } from "../../components/registry-shell";
import { CharacterLibrary } from "../../components/character-library";
export default async function CharactersPage({searchParams}:{searchParams:Promise<{view?:string}>}) {
  return <RegistryShell><CharacterLibrary scene={(await searchParams).view==="scenes"}/></RegistryShell>;
}
