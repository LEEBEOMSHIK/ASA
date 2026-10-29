"use client";
import { GraphIcon } from "./graph-icon";
import { cardSize, cardPortY, spaceCards, placeCard } from "../lib/graph-card-layout";
import { aiCardInfo } from "../lib/ai-card";
import { CitedAnswer } from "./cited-answer";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, message, type Tool, type SchemaNode, type Issue } from "../lib/registry";
import { type AutomationDraft, type GraphNode, type GraphEdge, type Binding, nodeKinds, ports, portNames } from "../lib/automation-graph";
import { Button, Field, StatusBadge } from "./ui";
import { wirePath, routeConnections, inputSocketOffset, type Point } from "../lib/graph-routing";
const show = (v: unknown): string => typeof v === "string" ? v : v === undefined ? "" : JSON.stringify(v,null,2);
const parse = (s: string): unknown => {try{return JSON.parse(s);}catch{return s;}};
const coordinate = (n: number) => Number.isFinite(n) ? Math.max(16,Math.min(100000,Math.round(n))) : 16;
const fields = (s?: SchemaNode): [string,SchemaNode][] => !s ? [] : s.type === "object" ? Object.entries(s.properties || {}) : [["$",s]];
type ModelCatalog = {models: {id:string;label:string;provider:string;web_search:boolean}[];default_model:string|null;configured:boolean;providers:{id:string;label:string;configured:boolean;web_search_available:boolean}[]};

const connectionLabel = (port:GraphEdge["port"]) => ({next:"출력",yes:"조건 충족",no:"그 외",item:"각 항목",done:"반복 완료"})[port];
const nodeWidth=(n:GraphNode)=>cardSize(n.kind).width;
const nodeHeight=(n:GraphNode)=>cardSize(n.kind).height;
const portY=(n:GraphNode,port:GraphEdge["port"])=>cardPortY(n.kind,ports(n).indexOf(port));
function BindingEditor({tools=[],label,binding,onChange,nodes,id,literalType}: {tools?:Tool[];literalType?:string;label:string;binding?:Binding;onChange:(b:Binding|undefined)=>void;nodes:GraphNode[];id:string}) {
 const sourceNode=nodes.find(n=>n.id===binding?.source);
 const schema=tools.find(t=>t.id===sourceNode?.tool_id)?.output_schema;
 const paths:string[]=[];
 const collect=(s:SchemaNode|undefined,prefix:string,depth:number)=>{if(!s||depth>4)return;if(s.type==="object")for(const [key,child] of Object.entries(s.properties||{})){const path=prefix?`${prefix}.${key}`:key;paths.push(path);collect(child,path,depth+1);}else if(s.type==="array"&&s.items){const path=prefix?`${prefix}.0`:"0";paths.push(path);collect(s.items,path,depth+1);}};
 collect(schema,"",0);
 if(sourceNode?.kind==="map")paths.push(...Object.keys(sourceNode.output_fields||{}));
 return <div className="graph-binding"><Field id={id} label={label}>{p=><select {...p} value={binding?.source || ""} onChange={e=>onChange(e.target.value ? {source:e.target.value,...(e.target.value==="literal"?{value:""}:{})}:undefined)}><option value="">입력 출처 선택</option><option value="input">시작 · 사용자의 요청</option>{nodes.filter(n=>n.kind!=="start" && n.kind!=="end").map(n=><option key={n.id} value={n.id}>{n.label} · 결과</option>)}<option value="literal">직접 입력</option></select>}</Field>
 {binding&&paths.length>0&&<Field id={id+"-known-field"} label="가져올 결과 항목" hint="0은 첫 번째 결과입니다. 전체 목록은 results를 선택하세요.">{p=><select {...p} value={binding.field||""} onChange={e=>onChange({...binding,field:e.target.value||undefined})}><option value="">전체 결과</option>{binding.field&&!paths.includes(binding.field)&&<option value={binding.field}>{binding.field}</option>}{paths.map(path=><option key={path} value={path}>{path}</option>)}</select>}</Field>}
 {binding?.source==="literal" ? <Field id={id+"-value"} label="직접 전달할 값" hint={literalType==="text-list"?"한 줄에 하나씩 항목을 입력하세요.":"문장이나 숫자를 입력하세요."}>{p=><textarea {...p} rows={2} value={literalType==="text-list" && Array.isArray(binding.value)?binding.value.map(show).join("\n"):show(binding.value)} onChange={e=>onChange({...binding,value:literalType==="string"?e.target.value:literalType==="text-list"?(e.target.value?e.target.value.split("\n"):[]):parse(e.target.value)})}/>}</Field> : binding && binding.source!=="input" && (nodes.find(n=>n.id===binding.source)?.kind==="repeat" ? <Field id={id+"-repeat-field"} label="반복 블록에서 가져올 내용">{p=><select {...p} value={binding.field||""} onChange={e=>onChange({...binding,field:e.target.value})}><option value="">전체 결과</option><option value="item">현재 항목 · 반복 중</option><option value="index">현재 순서 · 0부터</option><option value="results">모은 결과 목록 · 반복 완료 후</option></select>}</Field> : <Field id={id+"-field"} label="결과에서 가져올 항목" hint="비우면 전체 결과. 반복 중 item, 반복 후 results, 도구 결과 characters 등을 선택할 수 있어요.">{p=><input {...p} value={binding.field || ""} onChange={e=>onChange({...binding,field:e.target.value})} placeholder="예: item 또는 results" list={id+"-paths"}/>}</Field>)}
 <datalist id={id+"-paths"}><option value="item"/><option value="index"/><option value="results"/><option value="characters"/><option value="exceeded"/></datalist>
 </div>;
}
type PreviewResult = {id:string;node_id?:string;label?:string;kind:string;status?:string;input:unknown;output?:unknown;message?:string;iteration?:number};
export function GraphEditor({draft,change,tools,busy,testOpen,closeTest}: {draft:AutomationDraft;change:(d:AutomationDraft)=>void;tools:Tool[];busy:boolean;testOpen:boolean;closeTest:()=>void}) {
 const graph=draft.graph!;
 const [deleted,setDeleted]=useState<{graph:typeof graph;label:string}|null>(null);
 const inspector=useRef<HTMLElement>(null);
 const [selected,setSelected]=useState(""); const [zoom,setZoom]=useState(1); const [search,setSearch]=useState("");
 const [tracedEdge,setTracedEdge]=useState("");
 const [isolate,setIsolate]=useState(false);
 const [traceSearch,setTraceSearch]=useState("");
 const [pending,setPending]=useState<{source:string;port:GraphEdge["port"]}|null>(null);
 const drag=useRef<{id:string;x:number;y:number;px:number;py:number;moved:boolean}|null>(null);
 const suppressClick=useRef(false);
 const [dragRoutingNodes,setDragRoutingNodes]=useState<GraphNode[]|null>(null);
 const [moving,setMoving]=useState(false);
 const plane=useRef<HTMLDivElement>(null);
 const connectionTrigger=useRef<HTMLButtonElement|null>(null);
 const connectionDrag=useRef<{source:string;port:GraphEdge["port"];x:number;y:number;moved:boolean}|null>(null);
 const skipPortClick=useRef(false);
 const [quickAdd,setQuickAdd]=useState<{point:Point;left:number;top:number}|null>(null);
 const picker=useRef<HTMLDivElement>(null);
 const [connectionHint,setConnectionHint]=useState("");
 useEffect(()=>{if(quickAdd)picker.current?.focus();},[quickAdd]);
 const cancelConnection=()=>{if(connectionDrag.current)skipPortClick.current=true;setPending(null);setPointer(null);setQuickAdd(null);connectionDrag.current=null;setConnectionHint("");connectionTrigger.current?.focus();};
 const [pointer,setPointer]=useState<Point|null>(null);
 const [catalog,setCatalog]=useState<ModelCatalog|null>(null);
 const [modelError,setModelError]=useState("");
 const [modelLoading,setModelLoading]=useState(true);
 async function loadModels() {
  setModelLoading(true);setModelError("");
  try {setCatalog(await api<ModelCatalog>("/ai-models"));} catch(e) {setModelError(message(e));} finally {setModelLoading(false);}
 }
 useEffect(()=>{void loadModels();},[]);
 useEffect(()=>{
  if(!pending)return;
  const cancel=(event:KeyboardEvent)=>{if(event.key==="Escape"){cancelConnection();}};
  window.addEventListener("keydown",cancel);
  return ()=>window.removeEventListener("keydown",cancel);
 },[pending]);
 const [prompt,setPrompt]=useState(""); const [samples,setSamples]=useState<Record<string,unknown>>({}); const [results,setResults]=useState<PreviewResult[]>([]);
 const [issues,setIssues]=useState<Issue[]>([]); const [error,setError]=useState(""); const [notice,setNotice]=useState(""); const [testing,setTesting]=useState(false);
 const node=graph.nodes.find(n=>n.id===selected);
 const selectedTool=tools.find(t=>t.id===node?.tool_id);
 const inspectorTitle=node?.kind==="ai"?"직접 AI 구성":node?.kind==="tool"?(selectedTool?.kind==="agent"?"내 에이전트 설정":"ASA 기본 도구 설정"):"블록 설정";
 const pendingEdge=pending&&graph.edges.find(e=>e.source===pending.source&&e.port===pending.port);
 const validTarget=(n:GraphNode)=>Boolean(pending&&n.kind!=="start"&&n.id!==pending.source);
 const outputPoint=(n:GraphNode,port:GraphEdge["port"]):Point=>({x:n.x+nodeWidth(n),y:n.y+portY(n,port)});
 const beginConnection=(source:string,port:GraphEdge["port"])=>{
  setTracedEdge("");setQuickAdd(null);setConnectionHint("");setPending({source,port});
  const sourceNode=graph.nodes.find(n=>n.id===source)!;
  const start=outputPoint(sourceNode,port);setPointer({x:start.x+80,y:start.y});
 };
 const mutate=(g:typeof graph)=>{setDeleted(null);change({...draft,steps:[],graph:g});setResults([]);setIssues([]);setNotice("");};
 const update=(n:GraphNode)=>mutate({...graph,nodes:graph.nodes.map(v=>v.id===n.id?n:v)});
 function connect(source:string,port:GraphEdge["port"],target:string) {if(busy)return;if(target&&(target===source||graph.nodes.find(n=>n.id===target)?.kind==="start")){setConnectionHint("자기 자신이나 시작 블록에는 연결할 수 없습니다.");return;}if(target&&graph.edges.length>=100&&!graph.edges.some(e=>e.source===source&&e.port===port)){setConnectionHint("연결은 최대 100개까지 만들 수 있습니다.");return;}mutate({...graph,edges:[...graph.edges.filter(e=>e.source!==source||e.port!==port),...(target?[{id:crypto.randomUUID(),source,target,port}]:[])]});setPending(null);setPointer(null);setQuickAdd(null);setConnectionHint("");connectionTrigger.current?.focus();}
 function add(kind:GraphNode["kind"],tool?:Tool) {if(busy||graph.nodes.length>=50)return;if(kind==="end"&&graph.nodes.some(n=>n.kind==="end"))return;const id="node_"+crypto.randomUUID().replaceAll("-","");const n:GraphNode={id,kind,label:tool?.name||nodeKinds[kind],x:quickAdd?coordinate(quickAdd.point.x):120+(graph.nodes.length%3)*440,y:quickAdd?coordinate(quickAdd.point.y):280+Math.floor((graph.nodes.length-2)/3)*320,...(tool?{tool_id:tool.id,bindings:tool.id==="asa.web.search:1"?{query:{source:"input"},count:{source:"literal",value:3}}:{}}:{}),...(kind==="ai"?{instructions:"",output_type:"text",bindings:{$:{source:"input"}}}:{}),...(kind==="condition"?{condition:{left:{source:"input"},operator:"contains",right:""}}:{}),...(kind==="map"?{output_fields:{title:"text" as const},bindings:{}}:{}),...(kind==="repeat"?{items:{source:"literal",value:[]},max_items:20}:{})};const link=quickAdd&&pending;
 if(link&&graph.edges.length>=100&&!graph.edges.some(e=>e.source===link.source&&e.port===link.port)){setConnectionHint("연결은 최대 100개까지 만들 수 있습니다.");return;}
 mutate({...graph,nodes:[...graph.nodes,placeCard(n,graph.nodes)],edges:link?[...graph.edges.filter(e=>e.source!==link.source||e.port!==link.port),{id:crypto.randomUUID(),source:link.source,target:id,port:link.port}]:graph.edges});setPending(null);setPointer(null);setQuickAdd(null);setSelected(id);closeTest();}
 async function test(kind:"validate"|"preview") {setTesting(true);setError("");setIssues([]);setResults([]);setNotice("");try{if(kind==="validate"){const r=await api<{issues:Issue[]}>("/automations/validate","POST",draft);setIssues(r.issues);if(!r.issues.length)setNotice("연결 구성이 올바릅니다. 실제 AI 실행 검증은 아닙니다.");}else{const r=await api<{results:PreviewResult[]}>("/automations/preview","POST",{draft,prompt,samples});setResults(r.results);setNotice("AI 호출 0회 · 샘플로 지나간 경로만 표시합니다.");}}catch(e){setError(message(e));if(e instanceof ApiError)setIssues(e.issues);}finally{setTesting(false);}}
 const routingNodes=dragRoutingNodes??graph.nodes;
 const routes=useMemo(()=>{
  const rectangles=routingNodes.map(n=>({id:n.id,x:n.x,y:n.y,...cardSize(n.kind)}));
  return routeConnections(rectangles,graph.edges,(n,e)=>outputPoint(routingNodes.find(v=>v.id===n.id)!,e.port as GraphEdge["port"])).map(route=>({...route,edge:route.edge as GraphEdge,source:routingNodes.find(n=>n.id===route.edge.source)!,target:routingNodes.find(n=>n.id===route.edge.target)!}));
 },[routingNodes,graph.edges]);
 const displayedRoutes=moving?routes.map(route=>{
  if(route.edge.source!==drag.current?.id&&route.edge.target!==drag.current?.id)return route;
  const source=graph.nodes.find(n=>n.id===route.edge.source)!,target=graph.nodes.find(n=>n.id===route.edge.target)!;
  return {...route,path:wirePath(outputPoint(source,route.edge.port),{x:target.x,y:target.y+inputSocketOffset(route)},Math.max(source.y+nodeHeight(source),target.y+nodeHeight(target))),blocked:false};
 }):routes;
 const traced=displayedRoutes.find(r=>r.edge.id===tracedEdge);
 const traceLabel=(r:typeof routes[number])=>`${r.source.label} · ${portNames[r.edge.port]} → ${r.target.label}`;
 const visibleRoutes=displayedRoutes.filter(r=>!traced||!isolate||r.edge.id===traced.edge.id).sort((a,b)=>Number(a.edge.id===traced?.edge.id)-Number(b.edge.id===traced?.edge.id));
 const chooseTrace=(id:string)=>{setTracedEdge(id);setPending(null);setPointer(null);};
 const canRemove=(n:GraphNode)=>n.kind!=="start"&&(n.kind!=="end"||graph.nodes.filter(v=>v.kind==="end").length>1);
 function removeNode(n:GraphNode) {
  if(busy||!canRemove(n))return;
  const previous=graph;
  mutate({nodes:graph.nodes.filter(v=>v.id!==n.id),edges:graph.edges.filter(e=>e.source!==n.id&&e.target!==n.id)});
  setDeleted({graph:previous,label:n.label});setSelected("");setTracedEdge("");setPending(null);setPointer(null);
 }
 useEffect(()=>{if(node&&!testOpen)inspector.current?.focus({preventScroll:true});},[selected,testOpen]);
 const routePoints=routes.flatMap(r=>r.points||[]);
 const originX=Math.max(32,32-Math.min(0,...graph.nodes.map(n=>n.x),...routePoints.map(p=>p.x)));
 const originY=Math.max(32,32-Math.min(0,...graph.nodes.map(n=>n.y),...routePoints.map(p=>p.y)));
 const width=Math.max(1000,originX+32+Math.max(0,...graph.nodes.map(n=>n.x+nodeWidth(n)+48),...routePoints.map(p=>p.x)));
 const height=Math.max(640,originY+32+Math.max(0,...graph.nodes.map(n=>n.y+nodeHeight(n)+32),...routePoints.map(p=>p.y)));
 const blockedRoutes=moving?[]:routes.filter(r=>r.blocked);
 return <div className="graph-editor">
 <details className="graph-node-list"><summary>전체 블록 · {graph.nodes.length}개</summary><div>{graph.nodes.map(n=><button key={n.id} onClick={()=>{setSelected(n.id);closeTest();}} aria-pressed={selected===n.id}>{n.label}</button>)}</div></details><div className="graph-topline"><div><strong>자유롭게 연결하는 작업 흐름</strong><p className="muted">출력점을 입력점으로 끌어 연결하세요. 점을 하나씩 눌러도 연결할 수 있습니다.</p></div><div className="badge-row"><Button variant="secondary" disabled={busy||moving||!!pending} onClick={()=>mutate({...graph,nodes:spaceCards(graph.nodes)})}>카드 간격 정리</Button><Button variant="secondary" onClick={()=>setZoom(z=>Math.max(.4,Math.round((z-.1)*10)/10))} aria-label="캔버스 축소">−</Button><button className="graph-zoom" onClick={()=>setZoom(1)} aria-label="확대 비율 초기화">{Math.round(zoom*100)}%</button><Button variant="secondary" onClick={()=>setZoom(z=>Math.min(1.5,Math.round((z+.1)*10)/10))} aria-label="캔버스 확대">＋</Button></div></div>
 <details className="graph-trace-controls" onKeyDown={e=>{if(e.key==="Escape"){setTracedEdge("");setIsolate(false);}}}>
  <summary>연결 흐름 확인 · {routes.length}개{traced?" · 선택한 연결 강조 중":""}</summary>
  <div className="graph-trace-fields">
   <Field id="graph-trace-search" label="연결 검색">{p=><input {...p} value={traceSearch} onChange={e=>setTraceSearch(e.target.value)} placeholder="출발 또는 도착 블록 이름"/>}</Field>
   <Field id="graph-trace-edge" label="확인할 연결" hint="선이 겹치면 목록에서 선택하세요. 실제 실행 순서는 바뀌지 않습니다.">{p=><select {...p} value={traced?.edge.id||""} onChange={e=>chooseTrace(e.target.value)}><option value="">전체 연결 보기</option>{routes.filter(r=>r.edge.id===traced?.edge.id||traceLabel(r).toLocaleLowerCase().includes(traceSearch.toLocaleLowerCase())).map(r=><option key={r.edge.id} value={r.edge.id}>{traceLabel(r)}</option>)}</select>}</Field>
   <label><input type="checkbox" checked={isolate} onChange={e=>setIsolate(e.target.checked)} disabled={!traced}/> 선택한 연결만 보기</label>
   <Button variant="secondary" onClick={()=>{setTracedEdge("");setIsolate(false);setTraceSearch("");}}>강조 해제</Button>
  </div>
 </details>
 {traced&&<div className="graph-trace-summary" role="status"><strong>출발: {traced.source.label}</strong><span>{portNames[traced.edge.port]} →</span><strong>도착: {traced.target.label}</strong><Button variant="secondary" disabled={busy} onClick={()=>beginConnection(traced.edge.source,traced.edge.port)}>연결 변경</Button><Button variant="secondary" disabled={busy} onClick={()=>{connect(traced.edge.source,traced.edge.port,"");setTracedEdge("");setIsolate(false);}}>연결 삭제</Button><Button variant="secondary" onClick={()=>{setTracedEdge("");setIsolate(false);}}>닫기</Button></div>}
 <div className="graph-connect-notice" role="status" aria-live="polite">
  {pending ? <><div className="graph-connection-copy"><strong>{graph.nodes.find(n=>n.id===pending.source)?.label} · {connectionLabel(pending.port)}</strong><span>왼쪽 입력점을 선택하거나 빈 공간에 놓으세요. Esc로 취소{pendingEdge?` · 기존 ‘${graph.nodes.find(n=>n.id===pendingEdge.target)?.label}’ 연결은 확정 후 교체`:""}</span></div><Button variant="secondary" onClick={cancelConnection}>연결 취소</Button></>
   : <span>{moving?"블록 이동 중 · 놓으면 연결선을 정리합니다.":"블록 제목으로 이동 · 가장자리 점으로 연결"}</span>}
 </div>
 {connectionHint&&<p role="alert" className="graph-repair-notice">{connectionHint}</p>}
 {graph.nodes.filter(n=>n.kind==="end").length!==1&&<div role="alert" className="graph-repair-notice"><p className="field-error">최종 결과 블록은 하나여야 합니다. 기존 블록은 보존했습니다. 이 구성은 저장/실행 전 정리가 필요합니다.</p>{!graph.nodes.some(n=>n.kind==="end")&&<Button variant="secondary" disabled={busy||graph.nodes.length>=50} onClick={()=>add("end")}>최종 결과 복원</Button>}{graph.nodes.length>=50&&!graph.nodes.some(n=>n.kind==="end")&&<p className="muted">블록이 50개입니다. 불필요한 작업 블록을 제거한 뒤 최종 결과를 복원하세요.</p>}</div>}
 {!moving&&routes.some(r=>r.crowded&&!r.blocked)&&<p className="graph-repair-notice" role="status">일부 연결은 블록 사이 공간이 부족해 간격을 확보하지 못했습니다. 블록을 더 띄우면 경로를 다시 나눕니다.</p>}
 {blockedRoutes.length>0&&<div className="graph-repair-notice" role="status"><p>블록이 겹쳐 연결선을 안전하게 표시할 수 없는 경로가 있습니다. 블록 사이를 띄워 주세요. 연결 관계는 유지됩니다.</p>{blockedRoutes.map(r=><p key={r.edge.id}>{r.source.label} → {r.target.label} · 배치 확인 필요</p>)}</div>}
 {deleted&&<div className="graph-delete-notice" role="status"><span>‘{deleted.label}’ 블록과 연결선을 삭제했습니다. 이 결과를 참조한 입력은 확인해 주세요.</span><Button variant="secondary" disabled={busy} onClick={()=>mutate(deleted.graph)}>삭제 취소</Button><small>다음 편집 전까지 되돌릴 수 있습니다.</small></div>}
 <div className={`graph-layout ${node||testOpen?"graph-has-panel":""}`}>
 <aside className="graph-palette" aria-label="블록 추가">
  <h2>직접 AI 구성</h2>
  <button className="graph-palette-item" disabled={busy||graph.nodes.length>=50} onClick={()=>add("ai")}><span aria-hidden="true">✦</span>AI에게 요청<span aria-hidden="true">＋</span></button>
  <Field id="graph-tool-search" label="등록된 작업 찾기">{p=><input {...p} value={search} onChange={e=>setSearch(e.target.value)} placeholder="이름 검색"/>}</Field>
  {(["asa","agent"] as const).map(kind=>{
   const matches=tools.filter(t=>t.kind===kind&&t.name.toLocaleLowerCase().includes(search.toLocaleLowerCase()));
   return <details key={kind} className="graph-tool-picker"><summary>{kind==="asa"?"ASA 기본 도구":"내 에이전트"}</summary>
    {matches.length?matches.map(t=><div key={t.id}><button className="graph-palette-item" disabled={busy||!t.available||graph.nodes.length>=50} onClick={()=>add("tool",t)}>{t.name}<span aria-hidden="true">＋</span></button>{!t.available&&<p className="muted graph-small">{t.unavailable_reason||"현재 사용할 수 없습니다."}</p>}</div>):<p className="muted graph-small">{search?"일치하는 작업이 없습니다.":kind==="agent"?"등록된 에이전트가 없습니다.":"등록된 도구가 없습니다."}</p>}
   </details>;
  })}
  <h2>흐름 제어</h2>
  {(["condition","repeat","map"] as const).map(kind=><button key={kind} className="graph-palette-item" disabled={busy||graph.nodes.length>=50} onClick={()=>add(kind)}>{nodeKinds[kind]}<span aria-hidden="true">＋</span></button>)}
  <p className="muted graph-small">최종 결과는 기본 블록 하나를 사용합니다. 분기는 한 경로만 실행하며 중첩 반복과 병렬 실행은 지원하지 않습니다.</p>
 </aside>
 <section className="graph-viewport" aria-label="자유 배치 그래프 캔버스" onPointerMove={e=>{
  if(!pending||!plane.current)return;const rect=plane.current.getBoundingClientRect();setPointer({x:(e.clientX-rect.left)/zoom-originX,y:(e.clientY-rect.top)/zoom-originY});
 }} onClick={e=>{if(skipPortClick.current){skipPortClick.current=false;return;}if(!(e.target as HTMLElement).closest(".graph-node")&&!quickAdd){setPending(null);setPointer(null);}}}>
 <div style={{width:width*zoom,height:height*zoom}}><div ref={plane} className="graph-plane" style={{width,height,transform:`scale(${zoom})`}}>
  <svg className="graph-wires" role="group" width={width} height={height} aria-label="블록 연결선">
   <defs><marker id="graph-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="var(--primary)"/></marker></defs>
   <g transform={`translate(${originX} ${originY})`}>
   {visibleRoutes.map(route=><g key={route.edge.id} className="graph-wire" opacity={traced&&traced.edge.id!==route.edge.id?0.14:pendingEdge?.id===route.edge.id?0.35:1}>
    <path d={route.path} fill="none" stroke="var(--surface-subtle)" strokeWidth={traced?.edge.id===route.edge.id?10:7} vectorEffect="non-scaling-stroke"/>
    <path d={route.path} fill="none" stroke={route.blocked?"var(--warning-fg)":"var(--primary)"} strokeWidth={traced?.edge.id===route.edge.id?3.5:2} vectorEffect="non-scaling-stroke" strokeDasharray={route.blocked?"6 4":undefined} markerEnd="url(#graph-arrow)"/>
    <path className="graph-wire-hit" d={route.path} fill="none" stroke="transparent" strokeWidth="16" vectorEffect="non-scaling-stroke" role="button" tabIndex={pending||moving?-1:0} aria-label={`연결 확인: ${traceLabel(route)}`} aria-pressed={traced?.edge.id===route.edge.id} onClick={e=>{e.stopPropagation();if(!pending&&!moving)chooseTrace(route.edge.id);}} onKeyDown={e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();chooseTrace(route.edge.id);}if(e.key==="Escape"){setTracedEdge("");setIsolate(false);}}}/>
    <title>{traceLabel(route)}{route.blocked?" · 블록 배치 확인 필요":""}</title></g>)}
   {pending&&pointer&&graph.nodes.some(n=>n.id===pending.source)&&<path className="graph-pending-wire" d={wirePath(outputPoint(graph.nodes.find(n=>n.id===pending.source)!,pending.port),pointer,Math.max(pointer.y,graph.nodes.find(n=>n.id===pending.source)!.y+190))} fill="none" stroke="var(--primary)" strokeWidth="3" strokeDasharray="8 6" markerEnd="url(#graph-arrow)"/>}
   </g>
  </svg>
  {graph.nodes.map(n=><article key={n.id} className={`graph-node graph-node-${n.kind} ${selected===n.id?"is-selected":""} ${traced?(traced.edge.source===n.id||traced.edge.target===n.id?"is-trace-endpoint":"is-trace-muted"):""} ${validTarget(n)?"is-connect-target":""} ${pending?.source===n.id?"is-connect-source":""}`} style={{left:n.x+originX,top:n.y+originY,height:nodeHeight(n),width:nodeWidth(n),zIndex:selected===n.id||drag.current?.id===n.id?5:1}}>
   <button className="graph-node-settings" disabled={busy||!!pending} aria-label={`${n.label} 설정 열기`} onClick={()=>{setSelected(n.id);closeTest();}} title="블록 설정"><GraphIcon kind="settings"/></button>
   <button className="graph-node-heading" disabled={busy} aria-pressed={selected===n.id} onClick={()=>{
    if(suppressClick.current){suppressClick.current=false;return;}
    if(pending)return;setSelected(n.id);closeTest();
   }} onPointerDown={e=>{
    if(pending||busy||e.button!==0)return;setDragRoutingNodes(graph.nodes);suppressClick.current=false;drag.current={id:n.id,x:n.x,y:n.y,px:e.clientX,py:e.clientY,moved:false};e.currentTarget.setPointerCapture(e.pointerId);
   }} onPointerMove={e=>{
    const d=drag.current;if(!d||d.id!==n.id)return;
    if(!d.moved&&Math.hypot(e.clientX-d.px,e.clientY-d.py)<5)return;
    d.moved=true;setMoving(true);suppressClick.current=true;
    update({...n,x:coordinate(d.x+(e.clientX-d.px)/zoom),y:coordinate(d.y+(e.clientY-d.py)/zoom)});
   }} onPointerUp={e=>{
    const d=drag.current;if(d?.moved){update(placeCard({...n,x:coordinate(Math.round((d.x+(e.clientX-d.px)/zoom)/8)*8),y:coordinate(Math.round((d.y+(e.clientY-d.py)/zoom)/8)*8)},graph.nodes));}
    drag.current=null;setDragRoutingNodes(null);setMoving(false);if(e.currentTarget.hasPointerCapture(e.pointerId))e.currentTarget.releasePointerCapture(e.pointerId);
   }} onPointerCancel={()=>{drag.current=null;setDragRoutingNodes(null);setMoving(false);suppressClick.current=true;}} onLostPointerCapture={()=>{drag.current=null;setDragRoutingNodes(null);setMoving(false);}}>
    <span className="graph-kind-icon"><GraphIcon kind={n.kind==="tool"&&tools.find(t=>t.id===n.tool_id)?.kind==="agent"?"agent":n.kind}/></span><span className="graph-heading-copy"><small>{n.kind==="tool"?(tools.find(t=>t.id===n.tool_id)?.kind==="agent"?"내 에이전트":"ASA 기본 도구"):n.kind==="ai"?"직접 AI 구성":nodeKinds[n.kind]}</small><strong>{n.label}</strong></span>
   </button>
   {n.kind==="ai"&&<div className="graph-ai-info">
    <p className="graph-ai-summary" title={aiCardInfo(n,catalog?.default_model??null).summary}>{aiCardInfo(n,catalog?.default_model??null).summary}</p>
    <div className="graph-ai-chips"><span title={aiCardInfo(n,catalog?.default_model??null).model}><span aria-hidden="true" className={`provider-logo provider-${n.provider||"openai"}`}/>{aiCardInfo(n,catalog?.default_model??null).model}</span>{n.web_search&&<span><GraphIcon kind="search"/>웹 검색 켜짐</span>}</div>
    {aiCardInfo(n,catalog?.default_model??null).warning&&<p className="graph-ai-warning"><span aria-hidden="true">!</span>{aiCardInfo(n,catalog?.default_model??null).warning}</p>}
   </div>}
   {n.kind!=="start"&&(routes.filter(r=>r.edge.target===n.id).length?routes.filter(r=>r.edge.target===n.id).map(r=>({id:r.edge.id,y:inputSocketOffset(r)})):[{id:"input",y:nodeHeight(n)/2}]).map((entry,i)=><button key={entry.id} data-input-node={n.id} className={`graph-socket graph-input ${validTarget(n)?"is-ready":""}`} style={{top:entry.y}} disabled={busy} aria-label={`${n.label} · 입력 연결점${i?` ${i+1}`:""}`} aria-disabled={!!pending&&!validTarget(n)} title={pending&&!validTarget(n)?"자기 자신에는 연결할 수 없습니다.":"입력 · 출력점을 여기에 연결"} onClick={e=>{e.stopPropagation();if(pending)connect(pending.source,pending.port,n.id);else{setSelected(n.id);closeTest();}}}><span/></button>)}
   {ports(n).map(port=><div key={port}>{ports(n).length>1&&<span className="graph-port-label" style={{top:portY(n,port)}}>{connectionLabel(port)}</span>}<button disabled={busy} className="graph-socket graph-output" style={{top:portY(n,port)}} aria-pressed={pending?.source===n.id&&pending.port===port} aria-label={`${n.label} · ${connectionLabel(port)} 연결점`} title={`${connectionLabel(port)} · 드래그하거나 눌러 연결`} onPointerDown={e=>{
    if(e.button!==0||busy)return;e.stopPropagation();connectionTrigger.current=e.currentTarget;skipPortClick.current=false;connectionDrag.current={source:n.id,port,x:e.clientX,y:e.clientY,moved:false};beginConnection(n.id,port);e.currentTarget.setPointerCapture(e.pointerId);
   }} onPointerMove={e=>{const d=connectionDrag.current;if(d&&Math.hypot(e.clientX-d.x,e.clientY-d.y)>5)d.moved=true;}} onPointerUp={e=>{
    const d=connectionDrag.current;connectionDrag.current=null;if(e.currentTarget.hasPointerCapture(e.pointerId))e.currentTarget.releasePointerCapture(e.pointerId);
    if(!d?.moved)return;skipPortClick.current=true;
    const hit=document.elementFromPoint(e.clientX,e.clientY) as HTMLElement|null;
    const input=hit?.closest<HTMLElement>("[data-input-node]");
    if(input?.dataset.inputNode){connect(d.source,d.port,input.dataset.inputNode);return;}
    if(hit?.closest(".graph-node")){setConnectionHint("블록 왼쪽의 입력점에 놓아 주세요. 시작 블록에는 연결할 수 없습니다.");return;}
    if(hit?.closest(".graph-viewport")&&plane.current){const rect=plane.current.getBoundingClientRect();setQuickAdd({point:{x:(e.clientX-rect.left)/zoom-originX,y:(e.clientY-rect.top)/zoom-originY},left:Math.max(8,Math.min(e.clientX,window.innerWidth-320)),top:Math.max(8,Math.min(e.clientY,window.innerHeight-420))});setSelected("");closeTest();}
    else setConnectionHint("입력점이나 캔버스 빈 공간에 놓아 주세요. Esc로 취소할 수 있습니다.");
   }} onPointerCancel={cancelConnection} onClick={e=>{e.stopPropagation();if(skipPortClick.current){skipPortClick.current=false;return;}connectionTrigger.current=e.currentTarget;beginConnection(n.id,port);}}><span/></button></div>)}

  </article>)}
 </div></div></section>
 {quickAdd&&<div ref={picker} tabIndex={-1} className="graph-quick-add" role="dialog" aria-label="연결할 새 블록" style={{left:quickAdd.left,top:quickAdd.top}} onKeyDown={e=>{if(e.key==="Escape"){e.stopPropagation();cancelConnection();}}}><header><strong>연결할 새 블록</strong><Button variant="secondary" onClick={cancelConnection} aria-label="블록 추가 취소">×</Button></header><p className="muted">선택하면 이 위치에 추가하고 연결합니다.</p>{graph.nodes.length>=50?<p role="alert">블록은 최대 50개입니다.</p>:<><Button variant="secondary" onClick={()=>add("ai")}>✦ AI에게 요청</Button>{(["condition","repeat","map"] as const).map(kind=><Button key={kind} variant="secondary" onClick={()=>add(kind)}>{nodeKinds[kind]}</Button>)}<details><summary>ASA 도구 · 내 에이전트</summary>{tools.filter(t=>t.available).map(t=><Button key={t.id} variant="secondary" onClick={()=>add("tool",t)}>{t.name}</Button>)}</details></>}</div>}
 {(node||testOpen)&&<aside ref={inspector} tabIndex={-1} className="graph-inspector" aria-label={testOpen?"연결 테스트":inspectorTitle}><header><div><strong>{testOpen?"연결 테스트":node?.label}</strong><small className="muted">{testOpen?"샘플로 실행 경로 확인":inspectorTitle}</small></div><Button variant="secondary" aria-label="설정 패널 닫기" onClick={()=>{setSelected("");closeTest();}}>×</Button></header>
 {!testOpen&&node&&<div className="graph-block-actions"><span>입력 연결 {graph.edges.filter(e=>e.target===node.id).length}개 · 출력 연결 {graph.edges.filter(e=>e.source===node.id).length}개</span>{canRemove(node)?<Button variant="secondary" disabled={busy} onClick={()=>removeNode(node)}>블록 삭제</Button>:<small>시작과 최종 결과는 필수 블록입니다.</small>}</div>}
 {testOpen?<div className="graph-inspector-body"><p className="muted">샘플 결과로 연결·분기·반복을 확인합니다. AI와 검색 API를 호출하지 않습니다.</p><Button variant="secondary" disabled={testing||busy} onClick={()=>void test("validate")}>연결 상태 확인</Button><Field id="graph-preview-prompt" label="테스트할 요청">{p=><textarea {...p} rows={3} value={prompt} onChange={e=>{setPrompt(e.target.value);setResults([]);}}/>}</Field>{graph.nodes.some(n=>n.tool_id==="asa.web.search:1")&&<Button variant="secondary" onClick={()=>{setSamples({...samples,...Object.fromEntries(graph.nodes.filter(n=>n.tool_id==="asa.web.search:1").map(n=>[n.id,tools.find(t=>t.id===n.tool_id)?.example_output]))});setResults([]);}}>검색 샘플 채우기</Button>}{graph.nodes.filter(n=>n.kind==="ai"||n.tool_id==="asa.web.search:1"||tools.find(t=>t.id===n.tool_id)?.kind==="agent").map(n=>{const schema=n.kind==="ai"?{type:n.output_type==="list"?"array":"string"}:tools.find(t=>t.id===n.tool_id)?.output_schema;return <Field key={n.id} id={n.id+"-sample"} label={`${n.label} · 샘플 답변`} hint={schema?.type==="string"?"테스트용 문장을 넣으세요.":n.kind==="ai"?"한 줄에 하나씩 샘플 항목을 입력하세요.":"지정된 결과 형식의 JSON을 입력하세요."}>{p=><textarea {...p} rows={3} value={n.kind==="ai"&&n.output_type==="list"&&Array.isArray(samples[n.id])?(samples[n.id] as unknown[]).map(show).join("\n"):show(samples[n.id])} onChange={e=>{setSamples({...samples,[n.id]:schema?.type==="string"?e.target.value:n.kind==="ai"?(e.target.value?e.target.value.split("\n"):[]):parse(e.target.value)});setResults([]);}}/>}</Field>;})}<Button disabled={testing||busy} onClick={()=>void test("preview")}>{testing?"확인 중…":"샘플로 흐름 테스트"}</Button>{error&&<p role="alert" className="field-error">{error}</p>}{notice&&<p role="status">{notice}</p>}{issues.map((i,k)=><p className="field-error" key={k}>{i.message}</p>)}{results.map((r,i)=><div className="graph-preview-result" key={r.id+"-"+i}><strong>{r.label||graph.nodes.find(n=>n.id===(r.node_id||r.id))?.label||"단계"}</strong><StatusBadge>{r.kind==="sample"?"샘플 사용":r.kind==="local_tool"?"로컬 계산":({control:"흐름 확인",condition:"조건 평가",repeat:"반복",start:"시작",end:"최종 결과",needs_sample:"샘플 필요",invalid_sample:"샘플 형식 확인",invalid_input:"입력 확인"} as Record<string,string>)[r.kind]||r.status||r.kind}</StatusBadge>{r.iteration!==undefined&&<p>{r.iteration+1}번째 반복</p>}<details><summary>전달된 입력</summary><pre>{show(r.input)}</pre></details>{r.output!==undefined&&(typeof r.output==="string"?<CitedAnswer value={r.output}/>:<pre>{show(r.output)}</pre>)}{r.message&&<p className="field-error">{r.message}</p>}</div>)}</div>:node&&<fieldset disabled={busy} className="graph-inspector-body"><Field id="graph-node-label" label="블록 이름">{p=><input {...p} maxLength={80} value={node.label} onChange={e=>update({...node,label:e.target.value})}/>}</Field>
 {node.kind==="ai"&&<><Field id="graph-instructions" label="AI에게 맡길 일" hint="예: 입력한 주제로 쇼츠 아이디어 3개를 작성해 줘.">{p=><textarea {...p} rows={5} value={node.instructions||""} onChange={e=>update({...node,instructions:e.target.value})}/>}</Field><Field id="graph-output-type" label="답변 받는 방식">{p=><select {...p} disabled={node.web_search} value={node.output_type||"text"} onChange={e=>update({...node,output_type:e.target.value as "text"|"list"})}><option value="text">하나의 글</option><option value="list">글 목록 · 반복에 연결 가능</option></select>}</Field><Field id="graph-ai-provider" label="AI 서비스">{p=><select {...p} value={node.provider||"openai"} onChange={e=>update({...node,provider:e.target.value as "openai"|"anthropic",model:undefined,web_search:false})}><option value="openai">OpenAI</option><option value="anthropic">Claude · Anthropic</option></select>}</Field>
 <Field id="graph-ai-model" label="사용할 AI 모델" hint="선택한 서비스에 서버가 등록한 모델입니다. API 사용료는 공급자에게 별도 청구됩니다.">{p=><select {...p} disabled={modelLoading} value={node.model||""} onChange={e=>update({...node,model:e.target.value||undefined})}><option value="">{(node.provider||"openai")==="openai"?`서버 기본 모델${catalog?.default_model?` · ${catalog.default_model}`:""}`:"Claude 모델을 선택하세요"}</option>{node.model&&!catalog?.models.some(m=>m.id===node.model&&m.provider===(node.provider||"openai"))&&<option value={node.model}>{node.model} · 등록 여부 확인 필요</option>}{catalog?.models.filter(m=>m.provider===(node.provider||"openai")).map(model=><option key={model.id} value={model.id}>{model.label}{model.web_search?" · 웹 검색 지원":""}</option>)}</select>}</Field>
 {catalog&&!catalog.models.some(m=>m.provider===(node.provider||"openai"))&&<p role="status" className="muted graph-small">등록된 모델이 없습니다. 서버의 {(node.provider||"openai")==="openai"?"ASA_AI_MODEL / ASA_AI_MODELS":"ASA_ANTHROPIC_MODELS"} 설정 후 API와 워커를 다시 시작하세요.</p>}
 {catalog&&!catalog.providers.find(p=>p.id===(node.provider||"openai"))?.configured&&<p role="status" className="muted graph-small">이 서비스의 API 키가 설정되지 않았습니다. 샘플 테스트는 가능하지만 실제 AI 실행은 할 수 없습니다.</p>}
 <label><input type="checkbox" checked={!!node.web_search} onChange={e=>update({...node,web_search:e.target.checked,...(e.target.checked?{output_type:"text" as const}:{})})}/> 웹 검색 사용</label>
 <p className="muted graph-small">선택한 AI 서비스가 필요한 경우 웹을 검색하고 답변에 출처를 표시합니다. 검색료와 모델 사용료가 발생할 수 있습니다. 응답당 검색 도구 호출은 최대 1회로 요청합니다.</p>
 {node.web_search&&<p className="muted graph-small">검색 답변은 하나의 글로 받습니다. 다음 블록에 출처와 함께 전달됩니다.</p>}
 {node.web_search&&catalog&&!catalog.models.some(m=>m.provider===(node.provider||"openai")&&m.id===(node.model||catalog.default_model)&&m.web_search)&&<p role="alert" className="field-error">이 모델의 검색 사용이 서버에서 허용되지 않았습니다. 검색 지원 모델을 등록한 뒤 선택하세요.</p>}
 {modelLoading&&<p role="status" className="muted graph-small">등록된 모델을 불러오는 중…</p>}
 {modelError&&<div role="alert"><p className="field-error">모델 목록을 불러오지 못했습니다. {modelError}</p><Button variant="secondary" onClick={()=>void loadModels()}>모델 목록 다시 불러오기</Button></div>}
 {node.model&&catalog&&!catalog.models.some(m=>m.id===node.model&&m.provider===(node.provider||"openai"))&&<p role="alert" className="field-error">저장된 모델이 현재 허용 목록에 없습니다. 사용할 모델을 다시 선택하세요.</p>}</>}
 {(node.kind==="ai"||node.kind==="end")&&<BindingEditor tools={tools} literalType={node.kind==="ai"?"string":undefined} id={node.id+"-input"} label={node.kind==="end"?"최종 결과로 받을 내용 (비우면 직전 결과)":"AI에 전달할 내용"} nodes={graph.nodes.filter(n=>n.id!==node.id)} binding={node.bindings?.$} onChange={b=>{const bindings={...node.bindings};if(b)bindings.$=b;else delete bindings.$;update({...node,bindings});}}/>}
 {node.tool_id==="asa.web.search:1"&&<p className="muted">실제 검색은 서버 API 설정 후 실행됩니다. 연결 테스트에서는 results 배열에 title·url·snippet을 담은 샘플 JSON을 입력하세요. 빈 결과에서 첫 항목을 선택하면 오류가 나므로 목록 반복으로 처리할 수 있습니다.</p>}
 {node.kind==="tool"&&<><p className="muted">{selectedTool?.description||"등록된 작업 정보를 불러올 수 없습니다."}</p><p className="muted graph-small">{selectedTool?.kind==="agent"?"등록된 에이전트의 지시문·모델·결과 형식을 사용합니다. 여기에서는 전달할 입력을 연결하세요.":"이 도구의 정해진 기능을 실행합니다. 아래 입력을 연결하세요."}</p><h3>전달할 입력</h3>{fields(tools.find(t=>t.id===node.tool_id)?.input_schema).map(([k,s])=><BindingEditor tools={tools} key={k} literalType={s.type} id={node.id+k} label={s.description||(k==="$"?"전달할 내용":k)} binding={node.bindings?.[k]} nodes={graph.nodes.filter(n=>n.id!==node.id)} onChange={b=>{const bindings={...node.bindings};if(b)bindings[k]=b;else delete bindings[k];update({...node,bindings});}}/>)}</>}
 {node.kind==="tool"&&<><h3>받을 결과</h3>{fields(selectedTool?.output_schema).map(([key,schema])=><p className="muted graph-small" key={key}>{schema.description||(key==="$"?"전체 결과":key)} · {({string:"글",number:"숫자",integer:"정수",boolean:"참/거짓",array:"목록",object:"항목별 결과"} as Record<string,string>)[schema.type]||schema.type}</p>)}{!selectedTool?.output_schema&&<p className="muted graph-small">등록된 결과 형식을 확인할 수 없습니다.</p>}</>}
 {node.kind==="map"&&<><p className="muted">받은 결과에서 필요한 값을 골라 이름을 붙이세요. AI가 새로 작성하는 답변이 아니라 원본 값입니다.</p>
 <Button variant="secondary" onClick={()=>{const searchNode=graph.nodes.find(n=>n.tool_id==="asa.web.search:1");update({...node,output_fields:{title:"text",url:"text",snippet:"text"},bindings:searchNode?Object.fromEntries(["title","url","snippet"].map(k=>[k,{source:searchNode.id,field:`results.0.${k}`}])):{}});}}>첫 검색 결과의 제목·URL·요약 설정</Button>
 {Object.entries(node.output_fields||{}).map(([key,type],i)=><div className="graph-mapping-row" key={i}><Field id={`mapping-name-${i}`} label="결과 항목 이름">{p=><input {...p} value={key} maxLength={80} onChange={e=>{const name=e.target.value;if(name!==key&&Object.hasOwn(node.output_fields||{},name))return;const entries=Object.entries(node.output_fields||{}).map(([k,v])=>[k===key?name:k,v]);const bindings={...node.bindings};if(bindings[key]){bindings[name]=bindings[key];if(name!==key)delete bindings[key];}update({...node,output_fields:Object.fromEntries(entries),bindings});}}/>}</Field>
 <Field id={`mapping-type-${i}`} label="값의 종류">{p=><select {...p} value={type} onChange={e=>update({...node,output_fields:{...node.output_fields,[key]:e.target.value as typeof type}})}><option value="text">글</option><option value="number">숫자</option><option value="boolean">참/거짓</option><option value="text-list">글 목록</option></select>}</Field>
 <BindingEditor tools={tools} id={`mapping-value-${i}`} label="어디에서 가져올까요?" literalType={type==="text"?"string":type==="text-list"?"text-list":undefined} nodes={graph.nodes.filter(n=>n.id!==node.id)} binding={node.bindings?.[key]} onChange={b=>{const bindings={...node.bindings};if(b)bindings[key]=b;else delete bindings[key];update({...node,bindings});}}/>
 <Button variant="secondary" onClick={()=>{const output_fields={...node.output_fields},bindings={...node.bindings};delete output_fields[key];delete bindings[key];update({...node,output_fields,bindings});}}>이 항목 제거</Button></div>)}
 <Button variant="secondary" disabled={Object.keys(node.output_fields||{}).length>=20} onClick={()=>{let i=1;while(Object.hasOwn(node.output_fields||{},`항목${i}`))i++;update({...node,output_fields:{...node.output_fields,[`항목${i}`]:"text"}});}}>＋ 결과 항목 추가</Button></>}
 {node.kind==="condition"&&node.condition&&<><BindingEditor tools={tools} id={node.id+"-left"} label="비교할 내용" nodes={graph.nodes.filter(n=>n.id!==node.id)} binding={node.condition.left} onChange={b=>update({...node,condition:{...node.condition!,left:b||{source:"input"}}})}/><Field id="graph-operator" label="조건">{p=><select {...p} value={node.condition!.operator} onChange={e=>update({...node,condition:{...node.condition!,operator:e.target.value as NonNullable<GraphNode["condition"]>["operator"]}})}>{Object.entries({equals:"같음",not_equals:"같지 않음",contains:"포함함",greater_than:"보다 큼",less_than:"보다 작음",is_true:"참인지 확인"}).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select>}</Field>{node.condition.operator!=="is_true"&&<Field id="graph-right" label="비교 기준" hint="숫자와 true/false는 해당 값으로 해석합니다.">{p=><input {...p} value={show(node.condition!.right)} onChange={e=>update({...node,condition:{...node.condition!,right:parse(e.target.value)}})}/>}</Field>}</>}
 {node.kind==="repeat"&&<><BindingEditor tools={tools} literalType="text-list" id={node.id+"-items"} label="반복할 목록" nodes={graph.nodes.filter(n=>n.id!==node.id)} binding={node.items} onChange={b=>update({...node,items:b})}/><Field id="graph-max-items" label="최대 항목 수" hint="최대 20개. 초과하면 중단하며 목록을 자르지 않습니다.">{p=><input {...p} type="number" min={1} max={20} value={node.max_items||20} onChange={e=>update({...node,max_items:Math.max(1,Math.min(20,Math.floor(Number(e.target.value))||1))})}/>}</Field><p className="muted graph-small">‘각 항목’에 작업을 연결하고 마지막 작업을 이 반복 블록으로 돌려보내세요. 작업 입력은 이 블록 결과의 item, 완료 후 결과는 results입니다.</p></>}
 {(node.kind==="tool"||node.kind==="ai")&&<label className="automation-review-toggle"><input type="checkbox" checked={node.review_after||false} onChange={e=>update({...node,review_after:e.target.checked})}/>결과 확인 후 이어서 진행</label>}
 {ports(node).length>0&&<details><summary>연결 관리 · {ports(node).filter(p=>graph.edges.some(e=>e.source===node.id&&e.port===p)).length}개 연결</summary>{ports(node).map(port=><Field key={port} id={node.id+port} label={portNames[port]} hint="선택을 비우면 연결이 제거됩니다.">{p=><select {...p} value={graph.edges.find(e=>e.source===node.id&&e.port===port)?.target||""} onChange={e=>connect(node.id,port,e.target.value)}><option value="">연결하지 않음</option>{graph.nodes.filter(n=>n.kind!=="start"&&n.id!==node.id).map(n=><option key={n.id} value={n.id}>{n.label}</option>)}</select>}</Field>)}</details>}
 <details><summary>블록 위치 · 키보드로 조정</summary><div className="graph-position">{(["x","y"] as const).map(axis=><Field key={axis} id={"node-"+axis} label={axis==="x"?"가로 위치":"세로 위치"}>{p=><input {...p} type="number" min={16} max={100000} value={node[axis]} onChange={e=>update({...node,[axis]:coordinate(Number(e.target.value))})}/>}</Field>)}</div></details></fieldset>}
 </aside>}
 </div></div>;
}
