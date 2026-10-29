export type Binding = { source: string; field?: string; value?: unknown };
export type GraphNode = {
  id: string; label: string; kind: "start" | "tool" | "ai" | "condition" | "repeat" | "end" | "map";
  x: number; y: number; tool_id?: string; bindings?: Record<string, Binding>;
  instructions?: string; model?: string; provider?: "openai" | "anthropic"; web_search?: boolean; output_type?: "text" | "list"; review_after?: boolean;
  condition?: {left: Binding; operator: "equals" | "not_equals" | "contains" | "greater_than" | "less_than" | "is_true"; right: unknown};
  output_fields?: Record<string,"text"|"number"|"boolean"|"text-list">;
  items?: Binding; max_items?: number;
};
export type GraphEdge = {id: string; source: string; target: string; port: "next" | "yes" | "no" | "item" | "done"};
export type Graph = {nodes: GraphNode[]; edges: GraphEdge[]};
export type Step = {id: string; label: string; tool_id: string; review_after?: boolean; bindings: Record<string, Binding>};
export type AutomationDraft = {name: string; description: string; steps: Step[]; graph?: Graph | null};
export const nodeKinds = {start:"시작 요청",tool:"등록된 작업",ai:"AI에게 요청",condition:"조건 분기",repeat:"목록 반복",end:"최종 결과",map:"결과 항목 선택"};
export const portNames = {next:"다음",yes:"맞으면",no:"아니면",item:"각 항목",done:"반복 완료"};
export const ports = (n: GraphNode): GraphEdge["port"][] => n.kind === "end" ? [] : n.kind === "condition" ? ["yes","no"] : n.kind === "repeat" ? ["item","done"] : ["next"];
export function newGraph(): Graph { return {nodes:[{id:"start",kind:"start",label:"시작 요청",x:48,y:100},{id:"end",kind:"end",label:"최종 결과",x:420,y:100}],edges:[{id:"initial",source:"start",target:"end",port:"next"}]}; }
export function convertGraph(draft: AutomationDraft): AutomationDraft {
 const startId="start_"+crypto.randomUUID().replaceAll("-","");
 const endId="end_"+crypto.randomUUID().replaceAll("-","");
 const nodes: GraphNode[] = [{id:startId,label:"시작 요청",kind:"start",x:48,y:100},...draft.steps.map((s,i): GraphNode=>({...s,kind:"tool",x:48+(i+1)*300,y:100})),{id:endId,label:"최종 결과",kind:"end",x:48+(draft.steps.length+1)*300,y:100}];
 return {...draft,steps:[],graph:{nodes,edges:nodes.slice(0,-1).map((n,i)=>({id:`edge_${i}`,source:n.id,target:nodes[i+1].id,port:"next"}))}};
}
