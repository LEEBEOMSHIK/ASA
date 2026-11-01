"use client";
import { useState } from "react";
import { ReviewAnswer } from "./review-answer";
import { Button, StatusBadge } from "./ui";

type Issue = {title:string;location:string;evidence:string;correction:string;severity:string;scope:string};
type Report = {summary:string;requirements:{label:string;status:string;evidence:string}[];issues:Issue[];edit_instruction:string;human_checks:string[]};
const record = (v:unknown): v is Record<string,unknown> => !!v && typeof v==='object' && !Array.isArray(v);
export function reviewReport(value:unknown): {report:Report;legacy:boolean} | null {
  if(record(value) && value.format==='image_review_v1' && record(value.report)) {
    const r=value.report;
    if(typeof r.summary==='string' && typeof r.edit_instruction==='string' && Array.isArray(r.requirements) && r.requirements.every(x=>record(x)&&typeof x.label==='string'&&typeof x.evidence==='string'&&['met','unmet','unknown'].includes(String(x.status))) && Array.isArray(r.issues) && r.issues.every(x=>record(x)&&['title','location','evidence','correction','severity','scope'].every(k=>typeof x[k]==='string')) && Array.isArray(r.human_checks) && r.human_checks.every(x=>typeof x==='string')) return {report:r as Report,legacy:false};
  }
  if(typeof value!=='string') return null;
  const sections:Record<string,string[]>={}; let heading='';
  for(const line of value.split(/\r?\n/)) { const h=/^#{1,6}\s+(.+)$/.exec(line.trim()); if(h) {heading=h[1]; sections[heading]??=[];} else if(heading) sections[heading].push(line); }
  if(!sections['확인된 문제와 위치']) return null;
  const bullets=(name:string)=>(sections[name]||[]).join('\n').split(/(?:^|\n)\s*[-*+]\s+/).map(x=>x.trim()).filter(Boolean);
  return {legacy:true,report:{summary:(sections['검토 요약']||[]).join('\n').trim(),requirements:[],issues:bullets('확인된 문제와 위치').map((text,i)=>{const colon=text.indexOf(':');return {title:colon>0?text.slice(0,colon):`확인 의견 ${i+1}`,location:'',evidence:colon>0?text.slice(colon+1).trim():text,correction:'',severity:'unknown',scope:'unknown'};}),edit_instruction:bullets('수정 요청 제안').join('\n'),human_checks:bullets('사람이 확인할 부분')}};
}

export function ReviewDashboard({value}:{value:unknown}) {
  const [copyState,setCopyState]=useState('');
  const parsed=reviewReport(value);
  if(!parsed) return <ReviewAnswer value={value}/>;
  const {report:r,legacy}=parsed;
  const met=r.requirements.filter(x=>x.status==='met').length;
  const unknown=r.requirements.filter(x=>x.status==='unknown').length;
  const needsReview=legacy || r.requirements.length===0 || met<r.requirements.length || r.human_checks.length>0;
  async function copy() {try {await navigator.clipboard.writeText(r.edit_instruction);setCopyState('수정 지시를 복사했습니다.');}catch {setCopyState('복사하지 못했습니다. 아래 문구를 선택해 복사해 주세요.');}}
  return <div className="review-dashboard">
    <div className="character-heading"><h4>이미지 검수 결과</h4><StatusBadge tone={r.issues.length || needsReview?'warning':'success'}>{legacy?'의견 확인 필요':r.issues.length?'수정 필요':needsReview?'사람 확인 필요':'확인된 문제 없음'}</StatusBadge></div>
    <div className="review-metrics"><div><span>요구사항 충족</span><strong>{r.requirements.length?`${met} / ${r.requirements.length}`:'미집계'}</strong><small>{legacy?'이전 검수에는 항목별 판정이 없습니다.':unknown?`${unknown}개는 확인이 필요합니다.`:'검수한 요구사항 기준'}</small></div><div className={r.issues.length ? "review-metric-attention" : undefined}><span>{legacy?'검토할 의견':'수정 필요 문제'}</span><strong>{r.issues.length}개</strong><small>{legacy?'기존 의견을 항목별로 나눴습니다.':'AI가 발견한 문제 · 최종 판단은 사용자'}</small></div></div>
    {r.summary && <p className="review-summary">{r.summary}</p>}
    <div className="review-issues">{r.issues.map((issue,i)=><article className="review-issue" key={i}><span className="review-issue-icon" aria-hidden="true">!</span><div><h5>{legacy?'확인 의견':'문제'} {i+1}. {issue.title}</h5>{!legacy && <p className="muted">심각도: {({major:'높음',minor:'낮음'} as Record<string,string>)[issue.severity]||'미판정'} · 범위: {({local:'부분',global:'전체'} as Record<string,string>)[issue.scope]||'미판정'}{issue.location && ` · 위치: ${issue.location}`}</p>}<p>{issue.evidence}</p>{issue.correction && <p><strong>수정 방향: </strong>{issue.correction}</p>}</div></article>)}</div>
    {!!r.requirements.length && <details className="character-edit"><summary>요구사항별 판정 확인</summary><ul className="review-checks">{r.requirements.map((q,i)=><li key={i}><strong>{q.label} · {q.status==='met'?'충족':q.status==='unmet'?'미충족':'확인 필요'}</strong><p>{q.evidence}</p></li>)}</ul></details>}
    {r.edit_instruction && <section className="review-edit-instruction"><h5>이미지 수정 지시</h5><div><p>{r.edit_instruction}</p><Button variant="secondary" onClick={()=>void copy()}>수정 지시 복사</Button><span role="status">{copyState}</span></div><p className="helper-text">복사한 내용을 이미지의 ‘바꿀 부분’에 붙여 넣고 확인한 뒤 수정 요청을 보내세요. 자동으로 실행되지 않습니다.</p></section>}
    {!!r.human_checks.length && <details className="character-edit"><summary>사람이 확인할 부분 · {r.human_checks.length}개</summary><ul className="review-checks">{r.human_checks.map((text,i)=><li key={i}>{text}</li>)}</ul></details>}
  </div>;
}
