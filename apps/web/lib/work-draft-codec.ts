export function decodeWorkDraft(raw:string, now=Date.now()):unknown {
  const record=JSON.parse(raw);
  if(record?.format!==1||!Number.isFinite(record.time)||record.time>now||now-record.time>=30*86400000)return undefined;
  const value=record.value;
  if(!value||typeof value!=="object"||Array.isArray(value))return undefined;
  return value;
}
