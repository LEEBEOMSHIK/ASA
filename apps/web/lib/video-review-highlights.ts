/** AI review hints only. Never use these spans in stored/provider prompts. */
export const reviewKinds = [
  {id:'camera',label:'구도·카메라'}, {id:'expression',label:'표정'},
  {id:'gaze',label:'시선'}, {id:'action',label:'동작'},
  {id:'voice',label:'목소리'}, {id:'music',label:'배경음악'},
] as const;
export type ReviewKind = typeof reviewKinds[number]['id'];
export type ReviewPhrase = {text:string;kind?:ReviewKind};
export type ReviewAnnotation = {key:string;quote:string;kind:ReviewKind;source:string;start?:number;end?:number};

export function reviewPhrases(text:string, annotations:ReviewAnnotation[]=[], key=''):ReviewPhrase[] {
  const spans:{start:number;end:number;kind:ReviewKind}[]=[];
  for(const item of annotations) {
    if(item.key!==key||item.source!==text||!item.quote||!reviewKinds.some(k=>k.id===item.kind))continue;
    const indexed=Number.isInteger(item.start)&&Number.isInteger(item.end)&&item.start!>=0&&item.end!>item.start!;
    const chars=Array.from(text);
    const start=indexed?chars.slice(0,item.start).join('').length:text.indexOf(item.quote);
    const end=indexed?chars.slice(0,item.end).join('').length:start+item.quote.length;
    if(start<0||text.slice(start,end)!==item.quote||(!indexed&&text.indexOf(item.quote,start+1)>=0)||spans.some(s=>start<s.end&&end>s.start))continue;
    spans.push({start,end,kind:item.kind});
  }
  const parts:ReviewPhrase[]=[];
  let cursor=0;
  for(const span of spans.sort((a,b)=>a.start-b.start)) {
    if(span.start>cursor)parts.push({text:text.slice(cursor,span.start)});
    parts.push({text:text.slice(span.start,span.end),kind:span.kind});cursor=span.end;
  }
  if(cursor<text.length)parts.push({text:text.slice(cursor)});
  return parts;
}
