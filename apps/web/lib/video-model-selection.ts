export const videoProviders:Record<string,string> = {
  runway:"Runway", alibaba:"Alibaba", higgsfield:"Higgsfield",
};
type Model = {key:string; provider:string; label:string; model?:string; resolution?:string};
export type VideoDefaults=Record<string,{model_key:string;duration_seconds:number}>;
export function appliedVideoModel<T extends Model>(models:T[], saved:string, userEnabled:boolean, defaults:VideoDefaults):T|undefined {
  const selected=models.find(m=>m.key===saved);
  if(!selected||userEnabled)return selected;
  const configured=defaults[`${selected.provider}:${selected.model}`];
  return models.find(m=>m.key===configured?.model_key&&sameVideoModel(m,selected))
    ??models.find(m=>sameVideoModel(m,selected)&&m.resolution==='720p')??selected;
}
export function videoModelFamilies<T extends Model>(models:T[]):T[] {
  return models.filter((m,index)=>models.findIndex(other=>
    other.provider===m.provider && (other.model??other.key)===(m.model??m.key))===index);
}
export function sameVideoModel(a:Model,b:Model):boolean {
  return a.provider===b.provider && (a.model??a.key)===(b.model??b.key);
}
const legacy:Record<string,Model> = {
  "hf-seedance25":{key:"hf-seedance25",provider:"higgsfield",label:"Seedance 2.5"},
  "hf-seedance20":{key:"hf-seedance20",provider:"higgsfield",label:"Seedance 2.0"},
  "hf-kling4":{key:"hf-kling4",provider:"higgsfield",label:"Kling 4.0"},
  "runway-gen45":{key:"runway-gen45",provider:"runway",label:"Runway Gen-4.5"},
  wan3:{key:"wan3",provider:"alibaba",label:"WAN 3.0"},
  "hf-wan3":{key:"hf-wan3",provider:"higgsfield",label:"WAN 3.0"},
};
export function videoModelChoices(allowed:unknown[]|undefined, models:Model[], saved:string):Model[] {
  const keys=[...new Set([...(allowed??[]).map(String),...(saved?[saved]:[])])];
  return keys.map(key=>models.find(model=>model.key===key) ?? legacy[key] ??
    {key,provider:"unavailable",label:key});
}
export function videoModelName(model:Model):string {
  const provider=videoProviders[model.provider];
  if(!provider)return model.label;
  // Catalog labels also appear on history cards, where the provider is useful.
  // Remove only an explicit provider suffix inside the provider-scoped selector.
  return model.label.replace(new RegExp(`\\s*[·-]\\s*${provider}$`,"i"),"");
}
