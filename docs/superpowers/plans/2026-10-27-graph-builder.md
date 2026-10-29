# Graph Automation Builder Implementation Plan

**Goal:** User-approved freely placed/connected blocks, conditions, list repetition and inline AI requests, with real persisted execution.
**Architecture:** Preserve v1 steps. Add optional graph to same Automation envelope. Native SVG/HTML canvas, draggable cards, explicit output-port connections and keyboard-accessible connection controls. Existing API/auth/schedule/run snapshots retained. LangGraph runs bounded graph transitions; DB persists continuation and per-invocation results.
**Tech Stack:** Existing Next.js/React, FastAPI, PostgreSQL, LangGraph/LangChain. No new packages or local models.

## Design and shared wire contract
User approved graph expansion in chat; further implementation choices below are ours. Alternatives: replace old builder (risks existing drafts) or additive graph format (chosen); arbitrary executable code (outside ASA-tools scope) versus fixed safe control blocks (chosen).

Automation = {name,description,steps:[],graph?:{nodes:GraphNode[],edges:GraphEdge[]}}. Legacy with graph absent/null remains unchanged. Both nonempty steps and graph invalid.
GraphNode = {id,label,kind, x,y, tool_id?:string, bindings?:Record<string,Binding>, instructions?:string, output_type?:'text'|'list', condition?:{left:Binding,operator:'equals'|'not_equals'|'contains'|'greater_than'|'less_than'|'is_true',right:any}, items?:Binding,max_items?:number, review_after?:boolean}.
kind = start | tool | ai | condition | repeat | end.
Binding = existing {source,field?,value?}; sources: literal, input, node ID. field supports safe dot-separated dictionary keys/indexes, no eval. For repeat body current item use source repeat node ID, field 'item'; index is 'index'; after loop source repeat node ID, field 'results'.
GraphEdge = {id,source,target,port:'next'|'yes'|'no'|'item'|'done'}.
Start one outgoing next. Tool/AI one next. Condition exactly yes/no. Repeat item body entry and done next. End no outgoing. One start, at least one end. Edges to start invalid. Branch fan-in is alternative path merge, not parallel execution. No arbitrary cycles; only repeat-body return to owning repeat allowed. No nested repeat in first version; expose limitation in UI/validation. Every repeat body path must return to its loop; may branch within body. Bound nodes50, edges100, loop items20 and total executed invocations200.
AI node bindings['$'] is input; instructions plain system instructions; output_type text → string, list → array of strings. Server model profile default only, key server-only. AI result list can feed repeat. Tool bindings from catalog schema. End bindings['$'] chooses final output (optional; preceding result if absent).
Repeat resolves array once, emits {item,index} during iteration, appends last body output into results at return; done emits {results:[...]}. Empty list exits done without body. Oversize lists fail explicitly, never truncate silently. Each call gets unique invocation ID, deduped and counted against existing rolling24h limit; also total per-run AI cap20. No paid calls in tests.
Run graph continuation is DB JSON state; run.next_step remains monotonic completed invocation count for stale approval checks. steps[] graph result events include id unique invocation, node_id,label,status,input,output?,iteration?; legacy unchanged. Graph waiting review resumes at next transition without recalling completed blocks. Unselected branches shown as not executed; no fake results. Actual visited route and iteration outputs available.
Preview endpoint supports graph using sample outputs keyed node ID for AI/agent; paid_calls0, supports conditions and repeat with same evaluator. Samples list output must parse JSON string array in UI. Invalid paths/missing executed values fail with readable issue, never trigger downstream API. Validate before queueing/scheduling.

## Ownership and tasks
- [ ] Backend: graph schemas/validation/evaluator; hook Automation/check_flow/preview; frozen manifest for inline AI/catalog tools; runtime graph branch with durable continuation; tests branch, list0/2/oversize, stale approval resume, cycle/type/scope rejection, no duplicate calls.
- [ ] Frontend: graph editor/types, palette, drag canvas/zoom, visible port connections, inspector and easy examples; controlled conditions/bindings/repeat fields; save/validate/preview; new automation graph default and explicit legacy conversion with unsaved state retained; launcher graph stage/events/final output.
- [ ] Integration: existing tests, ruff/mypy/frontend typecheck/build; review; browser local graph demo save/reopen/branch/repeat/approval/history; screenshots at desktop/mobile and light/dark.
- [ ] Docs/WORKBOARD: record actual versus mock verification, limitations, no paid API claims.

No commit/push. Existing untracked checkout retained. Schedule snapshots remain fixed and must be re-saved to include edits. Arbitrary HTTP/code, parallel branches, nested repeats, media APIs, editing past results are not part of this increment.
