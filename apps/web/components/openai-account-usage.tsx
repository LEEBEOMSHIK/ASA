"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/registry";
import { Button, Card, ExternalLink, StatusBadge } from "./ui";

type Tokens = {input_tokens:number;output_tokens:number;input_cached_tokens:number;num_model_requests:number};
type Snapshot = {configured:boolean;project_id:string|null;error_code:string|null;stale:boolean;last_synced_at:string|null;last_attempt_at:string|null;data:null|{
  start:string;end:string;timezone:string;costs:Record<string,string>;tokens:Tokens;
  daily:{date:string;usd:string}[];models:(Tokens&{model:string})[];
}};
const errors:Record<string,string> = {
  not_configured:"사용량 조회용 Admin API Key가 아직 설정되지 않았습니다. 생성용 API 키와 별도로 연결해야 합니다.",
  invalid_key:"Admin API Key 인증에 실패했습니다. 서버의 키 설정을 확인하세요.",
  permission_denied:"사용량 조회 권한이 없습니다. Admin API Key의 권한을 확인하세요.",
  rate_limited:"OpenAI 조회 한도에 도달했습니다. 잠시 후 다시 시도하세요.",
  provider_unavailable:"OpenAI에서 집계 데이터를 가져오지 못했습니다.",
  connection_failed:"OpenAI 연결이 지연되거나 끊어졌습니다.",
  invalid_response:"집계 응답을 확인할 수 없습니다. 현재 값을 0으로 처리하지 않습니다.",
};
const money=(v:string)=>`$${Number(v).toLocaleString("ko-KR",{maximumFractionDigits:6})}`;
const count=(v:number)=>v.toLocaleString("ko-KR");
export function OpenAIAccountUsage() {
  const [snapshot,setSnapshot]=useState<Snapshot|null>(null);
  const [busy,setBusy]=useState(false);
  const [failure,setFailure]=useState("");
  const [refresh,setRefresh]=useState(0);
  useEffect(()=>{
    let active=true;
    let fetching=false;
    async function load(force=false) {
      if(fetching) return;
      fetching=true; setBusy(true); setFailure("");
      try {
        const result=await api<Snapshot>(`/admin/ai-usage/openai-account?refresh=${force}`);
        if(active) setSnapshot(result);
      } catch {if(active) setFailure("공식 집계를 조회하지 못했습니다. 소유자 권한과 서버 연결을 확인하세요.");}
      finally {fetching=false;if(active)setBusy(false);}
    }
    void load(refresh>0);
    const timer=setInterval(()=>{if(document.visibilityState==="visible")void load(true);},15*60*1000);
    return ()=>{active=false;clearInterval(timer);};
  },[refresh]);
  const data=snapshot?.data;
  return <section className="official-usage" aria-label="OpenAI 공식 집계">
    <Card>
      <div className="usage-heading"><div><h2>OpenAI 공식 집계</h2><p className="muted">공급자가 집계한 사용 비용입니다. 충전 잔액이나 ASA 요청별 예상 비용과는 다릅니다.</p></div>
        <Button variant="secondary" disabled={busy} onClick={()=>setRefresh(v=>v+1)}>공식 집계 새로고침</Button></div>
      <div className="badge-row"><StatusBadge tone={snapshot?.error_code||failure?"warning":"neutral"}>{busy?"조회 중":failure?"연결 확인 필요":snapshot?.error_code==="not_configured"?"연결 필요":snapshot?.error_code?"갱신 실패":snapshot?"연결됨":"조회 전"}</StatusBadge>
        {snapshot?.stale && <StatusBadge tone="warning">이전 정상 데이터</StatusBadge>}</div>
      <p className="muted">조회 범위: {snapshot?.project_id?`프로젝트 ${snapshot.project_id}`:"OpenAI 조직 전체"} · 날짜 기준 UTC · 화면을 보는 동안 15분마다 갱신</p>
      <p className="helper-text">다른 서비스의 API 사용이 포함될 수 있습니다. 기존 ASA 예상 비용과 더하지 마세요. 공급자의 집계 반영은 지연될 수 있습니다.</p>
      {busy && <p role="status">공식 사용량을 확인하고 있습니다…</p>}
      {(failure||snapshot?.error_code) && <p role="alert">{failure||errors[snapshot!.error_code!]||"공식 데이터를 확인할 수 없습니다."}</p>}
      {failure&&data&&<p className="muted">연결 실패로 마지막 조회 데이터를 표시합니다.</p>}
      <div className="official-usage-links"><ExternalLink href="https://platform.openai.com/settings/organization/billing/overview">충전 잔액·결제 확인</ExternalLink><ExternalLink href="https://platform.openai.com/settings/organization/usage">OpenAI 사용량 화면</ExternalLink></div>
      <p className="helper-text">마지막 정상 조회: {snapshot?.last_synced_at?new Date(snapshot.last_synced_at).toLocaleString("ko-KR"):"아직 없음"}</p>
      <details className="official-usage-setup"><summary>연결 설정 안내</summary><p>서버 환경변수 ASA_OPENAI_ADMIN_API_KEY에 별도 Admin API Key를 설정한 뒤 API 서버를 재시작하세요. 이 화면에는 키를 입력하지 않습니다.</p><p>ASA_OPENAI_USAGE_PROJECT_ID를 설정하면 해당 프로젝트만 조회합니다. 생략하면 조직 전체를 조회합니다. 계정 공식 집계는 소유자 전용입니다.</p><p>새로고침은 최소 30초 간격으로 공급자를 조회합니다. 서버 재시작 시 캐시는 초기화됩니다.</p><ExternalLink href="https://platform.openai.com/settings/organization/admin-keys">Admin API Key 관리</ExternalLink></details>
    </Card>
    {data && <>
      <div className="usage-metrics">{[["today","오늘"],["month","이번 달"],["days7","최근 7일"],["days30","최근 30일"]].map(([key,label])=><Card key={key}><span>{label} · 공식 집계 USD</span><strong>{money(data.costs[key])}</strong></Card>)}</div>
      <Card><h3>텍스트 모델 사용량</h3><p className="muted">{data.start.slice(0,10)} ~ {data.end.slice(0,10)} · UTC · 이미지·음성 전용 생성량은 이 토큰 합계에 포함되지 않습니다. 위 비용은 Costs API의 전체 비용 항목입니다.</p><dl className="usage-facts"><div><dt>입력 토큰</dt><dd>{count(data.tokens.input_tokens)}</dd></div><div><dt>출력 토큰</dt><dd>{count(data.tokens.output_tokens)}</dd></div><div><dt>입력 중 캐시 토큰</dt><dd>{count(data.tokens.input_cached_tokens)}</dd></div><div><dt>요청 수</dt><dd>{count(data.tokens.num_model_requests)}</dd></div></dl></Card>
      <Card><details><summary>일별 비용과 모델별 토큰 상세</summary><div className="usage-table-wrap"><table><thead><tr><th>날짜 · UTC</th><th>비용 · USD</th></tr></thead><tbody>{data.daily.map(d=><tr key={d.date}><td>{d.date}</td><td>{money(d.usd)}</td></tr>)}</tbody></table>{data.daily.length===0&&<p>해당 기간에 집계된 비용이 없습니다.</p>}<table><thead><tr><th>모델</th><th>입력</th><th>출력</th><th>입력 중 캐시</th><th>요청</th></tr></thead><tbody>{data.models.map(m=><tr key={m.model}><td>{m.model}</td><td>{count(m.input_tokens)}</td><td>{count(m.output_tokens)}</td><td>{count(m.input_cached_tokens)}</td><td>{count(m.num_model_requests)}</td></tr>)}</tbody></table>{data.models.length===0&&<p>해당 기간에 집계된 텍스트 요청이 없습니다.</p>}</div></details></Card>
    </>}
  </section>;
}
