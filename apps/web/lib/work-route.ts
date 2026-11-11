const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export function workHref(id:string,answer?:number){return `/works/${encodeURIComponent(id)}${answer&&Number.isSafeInteger(answer)&&answer>0?`/answers/${answer}`:""}`;}
export function workRoute(url:URL):{id:string;answer?:number}|null {
 const parts=url.pathname.split('/').filter(Boolean);
 if(parts[0]==='works'&&uuid.test(parts[1]||'')){
  if(parts.length===2)return {id:parts[1]};
  if(parts.length===4&&parts[2]==='answers'&&/^[1-9]\d*$/.test(parts[3])&&Number.isSafeInteger(Number(parts[3])))return {id:parts[1],answer:Number(parts[3])};
 }
 const id=url.pathname==='/'?url.searchParams.get('request'):null;
 if(id&&uuid.test(id)){const answer=Number(url.searchParams.get('answer'));return {id,...(Number.isSafeInteger(answer)&&answer>0?{answer}:{})};}
 return null;
}
