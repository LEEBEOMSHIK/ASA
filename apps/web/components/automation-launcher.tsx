"use client";
import { CitedAnswer } from "./cited-answer";
import { useEffect, useState } from "react";
import { api, message } from "../lib/registry";
import type { Graph } from "../lib/automation-graph";
import { Button, Card, Field } from "./ui";

type Item = {id: string; revision: number; draft: {name: string; steps: {id: string; label: string}[]; graph?: Graph | null}};
type Run = {next_step: number; id: string; status: string; prompt: string; revision: number; error?: string; created_at: string; definition: Item["draft"]; output?: unknown; steps: {id: string; node_id?: string; label?: string; iteration?: number; status: string; input: unknown; output?: unknown}[]};
type Schedule = {revision: number; enabled: boolean; kind: "once" | "daily"; time: string; next_at: string | null; prompt: string; definition_revision: number; note: string};
const labels: Record<string,string> = {queued:"실행 대기",running:"진행 중",waiting_review:"결과 확인 대기",succeeded:"완료",failed:"실패",needs_attention:"확인 필요",cancelled:"취소됨"};
const display = (v: unknown) => typeof v === "string" ? v : JSON.stringify(v,null,2);
const date = (v: string) => new Date(v).toLocaleString("ko-KR",{timeZone:"Asia/Seoul"});

function Answer({value}: {value: unknown}) {
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    const names: Record<string,string> = {characters:"글자 수",limit:"기준 글자 수",exceeded:"기준 초과",title:"제목",narration:"대본",script:"대본",hashtags:"해시태그"};
    return <dl className="automation-answer">{Object.entries(value).map(([key,v])=><div key={key}><dt>{names[key]||key}</dt><dd>{typeof v==="boolean"?(v?"예":"아니요"):display(v)}</dd></div>)}</dl>;
  }
  return typeof value === "string" ? <CitedAnswer value={value}/> : <pre>{display(value)}</pre>;
}

export function AutomationLauncher({item, initial, onClose}: {item: Item; initial: "run" | "schedule" | "history"; onClose: () => void}) {
  const [tab,setTab] = useState(initial);
  const [prompt,setPrompt] = useState("");
  const [run,setRun] = useState<Run | null>(null);
  const [history,setHistory] = useState<Run[]>([]);
  const [schedule,setSchedule] = useState<Schedule | null>(null);
  const [kind,setKind] = useState<"once" | "daily">("daily");
  const [time,setTime] = useState("09:00");
  const [at,setAt] = useState("");
  const [schedulePrompt,setSchedulePrompt] = useState("");
  const [runtime,setRuntime] = useState<{worker_online: boolean; ai_ready: boolean} | null>(null);
  const [busy,setBusy] = useState(false);
  const [ready,setReady] = useState(false);
  const [error,setError] = useState("");
  const [notice,setNotice] = useState("");
  const [attempt,setAttempt] = useState<{id: string; prompt: string} | null>(null);
  useEffect(() => { let alive = true;
    Promise.all([api<Schedule | null>(`/automations/${item.id}/schedule`),api<Run[]>(`/automations/${item.id}/runs`),api<{worker_online:boolean;ai_ready:boolean}>("/automation-runtime")]).then(([s,h,r]) => {
      if (!alive) return;
      setSchedule(s);setHistory(h);setRuntime(r);setReady(true);
      if (s) {setKind(s.kind);setTime(s.time);setSchedulePrompt(s.prompt);if(s.next_at)setAt(new Date(new Date(s.next_at).getTime()+9*3600000).toISOString().slice(0,16));}
    }).catch(e => {if(alive)setError(message(e));});
    return () => {alive=false;};
  },[item.id]);
  useEffect(() => {
    if (!run || !["queued","running"].includes(run.status)) return;
    let alive = true;
    const timer = window.setInterval(() => {api<Run>(`/automation-runs/${run.id}`).then(r => {if(alive)setRun(r);}).catch(e => {if(alive)setError(message(e));});},2000);
    return () => {alive=false;clearInterval(timer);};
  },[run?.id,run?.status]);
  async function perform(action: () => Promise<void>) {setBusy(true);setError("");setNotice("");try {await action();} catch(e){setError(message(e));} finally{setBusy(false);}}
  async function refreshHistory() {setHistory(await api<Run[]>(`/automations/${item.id}/runs`));}
  async function start() {
    const request = attempt?.prompt === prompt ? attempt : {id:crypto.randomUUID(),prompt};setAttempt(request);
    const response = await api<{id:string}>(`/automations/${item.id}/runs`,"POST",{...request,revision:item.revision});
    setRun(await api<Run>(`/automation-runs/${response.id}`));await refreshHistory();
  }
  return <section className="automation-launcher">
    <header className="flow-library-heading"><div><Button variant="secondary" onClick={onClose}>← 내 자동화</Button><h1>{item.draft.name}</h1><p className="muted">저장된 구성 v{item.revision} · {item.draft.graph?.nodes.length ?? item.draft.steps.length}개 블록</p></div></header>
    <nav className="badge-row" aria-label="자동화 사용"><Button variant={tab==="run"?"primary":"secondary"} onClick={()=>setTab("run")}>실행</Button><Button variant={tab==="schedule"?"primary":"secondary"} onClick={()=>setTab("schedule")}>시간 예약</Button><Button variant={tab==="history"?"primary":"secondary"} onClick={()=>{setTab("history");void perform(refreshHistory);}}>실행 기록</Button></nav>
    {error && <p role="alert" className="field-error">{error}</p>}{notice && <p role="status">{notice}</p>}
    {runtime && <p className="muted">{runtime.worker_online ? "실행 서비스가 최근 응답했습니다." : "실행 서비스가 응답하지 않습니다. 요청은 대기 상태로 보관됩니다."} {!runtime.ai_ready && "AI 연결 설정이 필요합니다. ASA 길이 검사는 실행할 수 있습니다."}</p>}
    {tab==="run" && <div className="automation-run-layout"><Card><h2>어떤 작업을 할까요?</h2><p className="muted">입력한 내용이 첫 단계의 ‘시작 요청’으로 전달됩니다.</p><Field id="run-prompt" label="작업 내용">{p=><textarea {...p} rows={6} maxLength={6000} value={prompt} onChange={e=>{setPrompt(e.target.value);setAttempt(null);}} placeholder="예: 상자를 좋아하는 고양이를 주제로 30초 쇼츠 대본을 만들어 줘."/>}</Field><Button disabled={busy||!ready||!prompt.trim()} onClick={()=>void perform(start)}>자동화 실행</Button><p className="muted">AI 단계는 연결된 API를 호출하며 비용이 발생할 수 있습니다.</p></Card>
      <Card><h2>단계별 결과</h2>{!run ? <p className="muted">실행하면 각 단계의 진행 상태와 실제 결과가 여기에 표시됩니다.</p> : <><p role="status"><strong>{labels[run.status] || run.status}</strong> · 구성 v{run.revision}</p><p>{run.prompt}</p>{run.error && <p role="alert">{run.status==="needs_attention"?"호출 결과가 불확실하여 자동 재실행을 멈췄습니다. 공급자 사용량과 결과를 확인하세요.":"이 단계의 입력 형식과 AI 설정·호출 한도를 확인하세요."}</p>}
      <ol className="automation-run-steps">{run.definition.graph ? <>{run.steps.map((result,i)=><li key={result.id+"-"+i}><strong>{result.label || run.definition.graph?.nodes.find(n=>n.id===result.node_id)?.label || "실행 단계"}</strong><span className="muted">{labels[result.status] || result.status}{result.iteration!==undefined ? ` · ${result.iteration+1}번째 반복` : ""}</span>{result.output!==undefined&&<Answer value={result.output}/>}<details><summary>전달된 입력 보기</summary><pre>{display(result.input)}</pre></details></li>)}{run.definition.graph.nodes.filter(n=>!run.steps.some(r=>r.node_id===n.id)).map(n=><li key={n.id}><strong>{n.label}</strong><span className="muted">{["succeeded","failed","cancelled","needs_attention"].includes(run.status)?"실행하지 않음":"아직 실행하지 않음"}</span></li>)}</> : run.definition.steps.map(s=>{const result=run.steps.find(r=>r.id===s.id);return <li key={s.id}><strong>{s.label}</strong><span className="muted">{result?labels[result.status]:"대기"}</span>{result?.output!==undefined && <Answer value={result.output}/>}{result && <details><summary>전달된 입력 보기</summary><pre>{display(result.input)}</pre></details>}</li>;})}</ol>{run.status==="succeeded" && run.definition.graph && <div><h3>최종 결과</h3><Answer value={run.output !== undefined ? run.output : [...run.steps].reverse().find(r=>run.definition.graph?.nodes.some(n=>n.id===r.node_id&&n.kind==="end"))?.output}/></div>}
      {run.status==="waiting_review" && <Button disabled={busy} onClick={()=>void perform(async()=>setRun(await api<Run>(`/automation-runs/${run.id}/approve`,"POST",{next_step:run.next_step})))}>결과 확인 완료 · 이어서 진행</Button>}
      {["queued","waiting_review"].includes(run.status) && <Button variant="secondary" disabled={busy} onClick={()=>void perform(async()=>setRun(await api<Run>(`/automation-runs/${run.id}/cancel`,"POST")))}>이 실행 취소</Button>}
      {!["queued","running","waiting_review"].includes(run.status) && <Button variant="secondary" onClick={()=>{setPrompt(run.prompt);setAttempt(null);setRun(null);}}>이 요청으로 새 작업 준비</Button>}</>}</Card></div>}
    {tab==="schedule" && <Card><h2>정해진 시간에 자동 실행</h2><p className="muted">한국 시간 기준입니다. 예약할 때 저장된 구성과 아래 요청을 사용합니다.</p>{schedule && <p>{schedule.enabled?"예약 켜짐":"예약 꺼짐"} · 구성 v{schedule.definition_revision}{schedule.enabled && schedule.next_at && ` · 다음 실행 ${date(schedule.next_at)}`}</p>}{schedule?.note && <p>{schedule.note}</p>}
      <Field id="schedule-kind" label="반복">{p=><select {...p} value={kind} onChange={e=>setKind(e.target.value as "once"|"daily")}><option value="daily">매일</option><option value="once">한 번만</option></select>}</Field>
      {kind==="daily" ? <Field id="schedule-time" label="실행 시간 (한국 시간)">{p=><input {...p} type="time" value={time} onChange={e=>setTime(e.target.value)}/>}</Field> : <Field id="schedule-at" label="실행 날짜와 시간 (한국 시간)">{p=><input {...p} type="datetime-local" value={at} onChange={e=>setAt(e.target.value)}/>}</Field>}
      <Field id="schedule-prompt" label="예약 실행에 사용할 작업 내용">{p=><textarea {...p} rows={4} value={schedulePrompt} maxLength={6000} onChange={e=>setSchedulePrompt(e.target.value)}/>}</Field><div className="badge-row"><Button disabled={busy||!ready||!schedulePrompt.trim()||(kind==="once"?!at:!time)} onClick={()=>void perform(async()=>{const s=await api<Schedule>(`/automations/${item.id}/schedule`,"PUT",{revision:item.revision,schedule_revision:schedule?.revision||0,enabled:true,kind,time,at:kind==="once"?new Date(at+"+09:00").toISOString():null,prompt:schedulePrompt});setSchedule(s);setNotice("시간 예약을 저장했습니다.");})}>예약 저장 · 켜기</Button>{schedule?.enabled && <Button variant="secondary" disabled={busy} onClick={()=>void perform(async()=>{await api(`/automations/${item.id}/schedule`,"DELETE");setSchedule(await api<Schedule>(`/automations/${item.id}/schedule`));setNotice("예약을 껐습니다. 이미 시작된 작업은 유지됩니다.");})}>예약 끄기</Button>}</div><p className="muted">로컬 PC와 실행 서비스가 켜져 있어야 합니다. 꺼져 있는 동안 놓친 예약은 재시작 시 한 번만 실행합니다. 이전 실행이 진행 중이면 다음 예약은 건너뜁니다.</p></Card>}
    {tab==="history" && <Card><h2>최근 실행 기록</h2><p className="muted">최근 50개 실행 · 한국 시간</p>{!history.length && <p>아직 실행한 작업이 없습니다.</p>}{history.map(h=><button className="automation-history-row" key={h.id} disabled={busy} onClick={()=>void perform(async()=>{setRun(await api<Run>(`/automation-runs/${h.id}`));setTab("run");})}><span>{date(h.created_at)}</span><strong>{labels[h.status]||h.status}</strong><span>구성 v{h.revision} →</span></button>)}</Card>}
  </section>;
}
