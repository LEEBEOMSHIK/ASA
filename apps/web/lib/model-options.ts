export type ModelOption = {id:string;label:string};
// Display order, not a benchmark ranking. Unknown families remain searchable at the end.
function rank(id:string):number[] {
 const gpt=id.match(/^gpt-(\d+)(?:\.(\d+))?/);
 const claude=id.match(/^claude-(?:(?:opus|sonnet|haiku)-)?(\d+)(?:[-.](\d{1,2})(?!\d))?/);
 const reasoning=id.match(/^o(\d+)/);
 const version=gpt||claude||reasoning;
 const specialized=/(image|audio|realtime|transcrib|tts|search|codex|instruct)/.test(id);
 const tier=/haiku|nano/.test(id)?3:/mini|luna/.test(id)?2:/sonnet/.test(id)?1:0;
 return [version&&!specialized?0:1,-Number(version?.[1]||0),-Number(version?.[2]||0),tier,/-\d{4}-\d{2}-\d{2}$|-\d{8}$/.test(id)?1:0];
}
export function sortModels<T extends ModelOption>(models:T[]):T[] {
 return [...models].sort((a,b)=>{
  const ar=rank(a.id),br=rank(b.id);
  for(let i=0;i<ar.length;i++) if(ar[i]!==br[i]) return ar[i]-br[i];
  return b.id.localeCompare(a.id,undefined,{numeric:true});
 });
}
