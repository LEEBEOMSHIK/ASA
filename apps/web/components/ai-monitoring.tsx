"use client";
import { useEffect, useRef, useState } from "react";
import { api, message } from "../lib/registry";
import { Button, Card, Field, StatusBadge } from "./ui";
import { OpenAIAccountUsage } from "./openai-account-usage";

type Usage = { input_tokens: number; output_tokens: number; cache_read: number; cache_creation: number };
type Call = { id: string; run_id: string; request_id: string; source: string; requested_by: string | null;
  automation_id: string | null; name: string; revision: number | null; step_id: string; step_name: string;
  provider: string; model: string; status: string; created_at: string; finished_at: string | null;
  duration_ms: number | null; usage: Usage | null; estimated_usd: number | string | null; cost_state: string };
type Totals = { calls: number; runs: number; failed: number; incomplete: number; input_tokens: number | null;
  output_tokens: number | null; usage_unknown: number; estimated_usd: number | string | null;
  cost_unknown: number; partial_cost: number; average_ms: number | null };
type Overview = { summary: Totals; items: Call[]; has_more: boolean;
  models: (Totals & {provider: string; model: string})[];
  automations: (Totals & {automation_id: string | null; name: string})[] };
type Detail = Call & { workspace_id: string; requested_at: string | null; original_request: unknown; messages: unknown; response: unknown;
  pricing: unknown; related: Call[]; run: {status: string; created_at: string; updated_at: string; elapsed_ms: number; queue_ms: number | null} | null };
const sources: Record<string,string> = {automation:"직접 실행", schedule:"예약 실행", customer:"고객 대본 요청", cli:"운영자 CLI", character:"캐릭터 이미지"};
const statuses: Record<string,string> = {succeeded:"응답 완료", failed:"호출·처리 실패", incomplete:"완료 미확인"};
const costs: Record<string,string> = {estimated:"예상 비용", tokens_only:"토큰 비용만 · 검색 비용 미포함", rate_missing:"모델 요율 미등록", usage_unknown:"사용량 미확인", cache_rate_missing:"캐시 요율 미등록", unknown:"미확인"};
const number = (n: number | null | undefined) => n == null ? "—" : n.toLocaleString("ko-KR");
const money = (n: number | string | null) => n == null ? "미확인" : `$${Number(n).toLocaleString("en-US", {minimumFractionDigits: 4, maximumFractionDigits: 8})}`;
const seconds = (n: number | null) => n == null ? "미확인" : `${(Number(n)/1000).toFixed(2)}초`;
const date = (value: string) => new Date(value).toLocaleString("ko-KR");
const day = (offset = 0) => {const d = new Date(); d.setDate(d.getDate()+offset); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;};
function JsonContent({value}: {value: unknown}) {return <pre className="usage-payload">{value == null ? "기록되지 않았습니다." : typeof value === "string" ? value : JSON.stringify(value,null,2)}</pre>;}

export function AiMonitoring() {
  const [view,setView]=useState<"requests"|"official">("requests");
  const [start,setStart] = useState(day(-6)); const [end,setEnd] = useState(day());
  const [provider,setProvider] = useState(""); const [source,setSource] = useState("");
  const [status,setStatus] = useState(""); const [query,setQuery] = useState("");
  const [filter,setFilter] = useState(()=>new URLSearchParams({start:new Date(`${day(-6)}T00:00:00`).toISOString(),end:new Date(`${day(1)}T00:00:00`).toISOString()}).toString()); const [offset,setOffset] = useState(0); const [refresh,setRefresh] = useState(0);
  const [data,setData] = useState<Overview | null>(null); const [error,setError] = useState("");
  const [busy,setBusy] = useState(true); const [selected,setSelected] = useState("");
  const [detail,setDetail] = useState<Detail | null>(null); const [detailError,setDetailError] = useState("");
  const detailRef = useRef<HTMLElement>(null);
  const [advanced,setAdvanced] = useState(false);
  const applied = new URLSearchParams(filter);
  const appliedLabels = [applied.get("provider") === "openai" ? "OpenAI" : applied.get("provider") === "anthropic" ? "Claude" : "", sources[applied.get("source") || ""], statuses[applied.get("status") || ""]].filter(Boolean);
  const advancedChanged = provider !== (applied.get("provider") || "") || source !== (applied.get("source") || "") || status !== (applied.get("status") || "");
  useEffect(() => {
    let active = true; setBusy(true); setError(""); setData(null);
    api<Overview>(`/admin/ai-usage?${filter}&offset=${offset}`).then(result=>{if(active)setData(result);})
      .catch(e=>{if(active)setError(message(e));}).finally(()=>{if(active)setBusy(false);});
    return ()=>{active=false;};
  },[filter,offset,refresh]);
  useEffect(()=>{
    if (!selected) return;
    let active=true; setDetail(null); setDetailError("");
    api<Detail>(`/admin/ai-usage/${selected}`).then(result=>{if(active){setDetail(result);}})
      .catch(e=>{if(active)setDetailError(message(e));});
    detailRef.current?.focus(); detailRef.current?.scrollIntoView({behavior:"smooth",block:"start"});
    return ()=>{active=false;};
  },[selected,refresh]);
  function apply() {
    if (!start || !end || start>end) {setError("시작일과 종료일을 확인하세요.");return;}
    const until=new Date(`${end}T00:00:00`); until.setDate(until.getDate()+1);
    const from=new Date(`${start}T00:00:00`);
    if (until.getTime()-from.getTime()>366*86400000) {setError("조회 기간은 최대 366일입니다.");return;}
    setFilter(new URLSearchParams({start:from.toISOString(),end:until.toISOString(),provider,source,status,q:query}).toString());
    setOffset(0); setSelected(""); setRefresh(v=>v+1);
  }
  return <div className="usage-page">
    <header className="usage-heading"><div><p className="eyebrow">AI OBSERVABILITY</p><h1>AI 사용량·비용</h1><p className="muted">어떤 요청에서 얼마나 사용했는지, 호출 하나까지 확인하세요.</p></div><div className="badge-row"><StatusBadge>관리자 전용</StatusBadge>{view === "requests" && <Button variant="secondary" disabled={busy} onClick={()=>setRefresh(v=>v+1)}>새로고침</Button>}</div></header>
    <nav className="usage-view-switch" aria-label="사용량 조회 종류"><Button variant="secondary" aria-pressed={view==="requests"} onClick={()=>setView("requests")}>ASA 요청별 사용량</Button><Button variant="secondary" aria-pressed={view==="official"} onClick={()=>setView("official")}>OpenAI 공식 집계</Button></nav>
    {view==="official" && <OpenAIAccountUsage/>}
    <div className="usage-request-view" hidden={view!=="requests"}>
    <form className="usage-filters" onSubmit={e=>{e.preventDefault();apply();}}>
      <Field id="usage-start" label="시작일">{p=><input {...p} type="date" value={start} onChange={e=>setStart(e.target.value)}/>}</Field>
      <Field id="usage-end" label="종료일">{p=><input {...p} type="date" value={end} onChange={e=>setEnd(e.target.value)}/>}</Field>
      <Field id="usage-query" label="검색">{p=><input {...p} maxLength={200} value={query} onChange={e=>setQuery(e.target.value)} placeholder="요청·자동화·모델 검색"/>}</Field>
      <Button type="submit" disabled={busy}>조회</Button>
      <Button variant="secondary" className="usage-filter-toggle" aria-expanded={advanced} aria-controls="usage-advanced" onClick={()=>setAdvanced(v=>!v)}>
        상세 조건{appliedLabels.length > 0 && <span className="usage-filter-count">{appliedLabels.length}</span>}
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" style={{transform:advanced?"rotate(180deg)":undefined}}><path d="m6 9 6 6 6-6"/></svg>
      </Button>
      {(appliedLabels.length > 0 || advancedChanged) && <div className="usage-filter-summary" aria-live="polite">
        {appliedLabels.length > 0 && <><span>적용 중</span>{appliedLabels.map(label=><span className="usage-filter-chip" key={label}>{label}</span>)}</>}
        {advancedChanged && <span>상세 조건 변경됨 · 조회를 눌러 적용하세요.</span>}
      </div>}
      <div id="usage-advanced" className="usage-filter-advanced" hidden={!advanced}>
      <Field id="usage-provider" label="AI 서비스">{p=><select {...p} value={provider} onChange={e=>setProvider(e.target.value)}><option value="">전체 서비스</option><option value="openai">OpenAI</option><option value="anthropic">Claude</option></select>}</Field>
      <Field id="usage-source" label="요청 출처">{p=><select {...p} value={source} onChange={e=>setSource(e.target.value)}><option value="">전체 출처</option>{Object.entries(sources).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select>}</Field>
      <Field id="usage-status" label="호출 상태">{p=><select {...p} value={status} onChange={e=>setStatus(e.target.value)}><option value="">전체 상태</option>{Object.entries(statuses).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select>}</Field>
        <button type="button" className="usage-filter-reset" onClick={()=>{setProvider("");setSource("");setStatus("");}}>상세 조건 초기화</button>
      </div>
    </form>
    {error && <p role="alert" className="notice">{error}</p>}
    {busy && <p role="status">사용량을 불러오는 중입니다…</p>}
    {data && <>
      <div className="usage-metrics">
        <Card><span>AI 호출</span><strong>{number(data.summary.calls)}<small>회</small></strong><p>{number(data.summary.runs)}개 실행에서 발생</p></Card>
        <Card><span>입력 / 출력 토큰</span><strong>{number(data.summary.input_tokens)} <small>/ {number(data.summary.output_tokens)}</small></strong><p>사용량 미확인 {data.summary.usage_unknown}회</p></Card>
        <Card><span>집계 가능한 예상 비용 · USD</span><strong>{money(data.summary.estimated_usd)}</strong><p>미산정 {data.summary.cost_unknown}회 · 검색 비용 미포함 {data.summary.partial_cost}회</p></Card>
        <Card><span>평균 호출 소요 시간</span><strong>{seconds(data.summary.average_ms)}</strong><p>실패 {data.summary.failed}회 ({data.summary.calls ? (data.summary.failed/data.summary.calls*100).toFixed(1) : "0"}%) · 완료 미확인 {data.summary.incomplete}회</p></Card>
      </div>
      <p className="usage-disclaimer">공급자가 반환한 토큰과 호출 당시 등록된 요율로 계산합니다. 최종 청구액과 다를 수 있으며 미확인 항목은 0원으로 간주하지 않습니다. 과거 기록은 소급 수집되지 않습니다.</p>
      {data.summary.calls===0 ? <Card className="usage-empty"><h2>아직 기록된 AI 호출이 없습니다</h2><p>선택한 기간과 조건에 해당하는 호출이 없습니다. 실제 AI 작업을 실행하면 사용량과 요청 흐름이 여기에 표시됩니다.</p><a href="/automations" className="button button--secondary">자동화 열기</a></Card> : <>
        <div className="usage-breakdowns"><Card><h2>모델별 사용량</h2><div className="usage-table-wrap"><table><thead><tr><th>모델</th><th>호출</th><th>입력 / 출력</th><th>예상 비용</th></tr></thead><tbody>{data.models.map(m=><tr key={`${m.provider}:${m.model}`}><td>{m.provider === "anthropic" ? "Claude" : m.provider}<strong>{m.model}</strong></td><td>{m.calls}<small>평균 {seconds(m.average_ms)}</small></td><td>{number(m.input_tokens)} / {number(m.output_tokens)}</td><td>{money(m.estimated_usd)}{(m.cost_unknown>0||m.partial_cost>0)&&<small>일부 비용 미포함</small>}</td></tr>)}</tbody></table></div></Card>
        <Card><h2>자동화·작업별 사용량</h2><div className="usage-table-wrap"><table><thead><tr><th>작업</th><th>실행 / 호출</th><th>예상 비용</th></tr></thead><tbody>{data.automations.map((a,i)=><tr key={`${a.automation_id}:${a.name}:${i}`}><td>{a.name}</td><td>{a.runs} / {a.calls}</td><td>{money(a.estimated_usd)}{(a.cost_unknown>0||a.partial_cost>0)&&<small>일부 비용 미포함</small>}</td></tr>)}</tbody></table></div></Card></div>
        <Card><div className="usage-heading"><h2>호출 기록</h2><span className="muted">최신순 · {offset+1}–{offset+data.items.length}</span></div><div className="usage-table-wrap"><table><thead><tr><th>요청·블록</th><th>모델</th><th>토큰 입력 / 출력</th><th>예상 비용</th><th>시간·상태</th><th>상세</th></tr></thead><tbody>{data.items.map(item=><tr key={item.id}><td><strong>{item.name}</strong><span>{item.step_name}</span><small>{sources[item.source]} · {date(item.created_at)}</small></td><td>{item.model}<small>{item.provider}</small></td><td>{item.usage ? `${number(item.usage.input_tokens)} / ${number(item.usage.output_tokens)}` : "사용량 미확인"}</td><td>{money(item.estimated_usd)}<small>{costs[item.cost_state]}</small></td><td>{seconds(item.duration_ms)}<small>{statuses[item.status]}</small></td><td><Button variant="secondary" onClick={()=>setSelected(item.id)} aria-label={`${item.step_name} 요청 추적 ${item.id}`}>요청 추적</Button></td></tr>)}</tbody></table></div>
          <div className="usage-pagination"><Button variant="secondary" disabled={offset===0} onClick={()=>{setOffset(v=>Math.max(0,v-25));setSelected("");}}>이전 25개</Button><Button variant="secondary" disabled={!data.has_more} onClick={()=>{setOffset(v=>v+25);setSelected("");}}>다음 25개</Button></div>
        </Card>
      </>}
    </>}
    {selected && <section ref={detailRef} tabIndex={-1} className="usage-detail" aria-label="AI 호출 요청 추적">
      <div className="usage-heading"><div><p className="eyebrow">REQUEST TRACE</p><h2>요청부터 응답까지</h2></div><Button variant="secondary" onClick={()=>setSelected("")}>닫기</Button></div>
      {detailError ? <p role="alert">{detailError}</p> : !detail ? <p role="status">상세 기록을 불러오는 중입니다…</p> : <>
        <div className="usage-trace-path"><span>{sources[detail.source]}</span><span aria-hidden="true">→</span><strong>{detail.name}{detail.revision ? ` · v${detail.revision}` : ""}</strong><span aria-hidden="true">→</span><span>{detail.step_name}</span><span aria-hidden="true">→</span><span>{detail.provider} · {detail.model}</span></div>
        <dl className="usage-facts"><div><dt>요청자</dt><dd>{detail.requested_by || "기존 기록 · 요청자 미확인"}</dd></div><div><dt>호출 상태</dt><dd>{statuses[detail.status]}</dd></div><div><dt>요청 ID</dt><dd>{detail.request_id}</dd></div><div><dt>실행 ID</dt><dd>{detail.run_id}</dd></div><div><dt>작업 공간 ID</dt><dd>{detail.workspace_id}</dd></div><div><dt>블록 실행 ID</dt><dd>{detail.step_id}</dd></div><div><dt>원래 요청 접수</dt><dd>{detail.requested_at ? date(detail.requested_at) : "미확인"}</dd></div><div><dt>호출 시작</dt><dd>{date(detail.created_at)}</dd></div><div><dt>호출 종료</dt><dd>{detail.finished_at ? date(detail.finished_at) : "미확인"}</dd></div><div><dt>호출 처리 시간</dt><dd>{seconds(detail.duration_ms)}</dd></div><div><dt>예상 비용</dt><dd>{money(detail.estimated_usd)} · {costs[detail.cost_state]}</dd></div><div><dt>캐시 읽기 / 생성 토큰</dt><dd>{detail.usage ? `${number(detail.usage.cache_read)} / ${number(detail.usage.cache_creation)}` : "미확인"}</dd></div></dl>
        {detail.run && <p className="muted">자동화 상태: {({queued:"실행 대기",running:"진행 중",waiting_review:"확인 대기",succeeded:"완료",failed:"실패",needs_attention:"확인 필요",cancelled:"취소됨"} as Record<string,string>)[detail.run.status] || detail.run.status} · 요청 접수 {date(detail.run.created_at)} · 최초 대기 {seconds(detail.run.queue_ms)} · 마지막 상태 변경까지 {seconds(detail.run.elapsed_ms)} (대기·승인 시간 포함). AI 호출 처리 시간과 별개입니다.</p>}
        <details open><summary>사용자가 처음 맡긴 요청</summary><JsonContent value={detail.original_request}/></details>
        <details><summary>이 호출에 실제 전달한 지시문·입력</summary><p className="muted">모델에 전달한 시스템·사용자 메시지입니다. 비밀값은 마스킹하며 긴 내용은 잘라 표시합니다.</p><JsonContent value={detail.messages}/></details>
        <details><summary>AI 응답</summary><JsonContent value={detail.response}/></details>
        <details><summary>호출 당시 요율 · USD / 백만 토큰</summary><JsonContent value={detail.pricing}/></details>
        <h3>같은 실행의 AI 호출</h3><div className="usage-related">{detail.related.map(item=><button key={item.id} className={item.id===selected?"is-active":""} onClick={()=>setSelected(item.id)} aria-current={item.id===selected?"true":undefined}><strong>{item.step_name}</strong><span>{statuses[item.status]} · {seconds(item.duration_ms)} · {money(item.estimated_usd)}</span></button>)}</div>
      </>}
    </section>}
    </div>
  </div>;
}
