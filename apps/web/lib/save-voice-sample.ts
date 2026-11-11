export async function saveThenGenerateSample<T extends {revision:number}>({current,needsSave,save,generate,phase}:{current:T;needsSave:boolean;save:()=>Promise<T>;generate:(revision:number)=>Promise<unknown>;phase:(value:"saving"|"requesting")=>void}):Promise<T>{
  let saved=current;
  if(needsSave){phase("saving");saved=await save();}
  phase("requesting");
  await generate(saved.revision);
  return saved;
}
