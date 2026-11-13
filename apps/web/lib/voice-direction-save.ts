export function retainUnsavedSpeakers<T extends {id:string}>(saved:T[],draft:T[],savedId:string):T[]{
  return saved.map(s=>s.id===savedId?s:(draft.find(d=>d.id===s.id)||s));
}
