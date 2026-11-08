"use client";
import { useEffect, useState } from "react";
import { api, message, setCsrf } from "../lib/registry";
import { Button, Card, StatusBadge } from "./ui";
import { SceneTimingReview, type Timing } from "./scene-timing-review";

type Speech = {purpose:"production"|"timing";id:string;cue_id:string;speaker_name:string;voice:string;text:string;start:number;end:number;duration:number|null;transcript:string|null;status:string;has_media:boolean;excluded_reason:string|null;timing_ok:boolean;can_approve:boolean};
type Review = {answer_version:number;source_version:number|null;jobs:Speech[];timing?:Timing|null};
const reasons:Record<string,string> = {
  audio_transcript_mismatch:"원문과 다른 말이 생성되어 제외했습니다.",
  audio_source_changed:"현재 대사·목소리 설정과 달라 이전 결과로 분리했습니다.",
  audio_unknown:"호출 결과가 불확실합니다. 자동으로 다시 생성하지 않습니다.",
  audio_failed:"생성에 실패한 결과입니다.",
};

export function WorkSpeechReview({requestId,version,disabled=false}:{requestId:string;version:number;disabled?:boolean}) {
  const [data,setData]=useState<Review|null>(null);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const [notice,setNotice]=useState("");
  const path=`/audio/work/${requestId}/${version}/review`;
  useEffect(()=>{let live=true;api<Review>(path).then(value=>{if(live)setData(value);}).catch(e=>{if(live)setError(message(e));});return()=>{live=false;};},[path]);
  const pending=Boolean(data?.timing && (data.timing.queued||data.timing.running));
  useEffect(()=>{if(!pending)return;let live=true;const timer=setInterval(()=>{api<Review>(path).then(value=>{if(live){setData(value);setError("");}}).catch(e=>{if(live)setError(message(e));});},3000);return()=>{live=false;clearInterval(timer);};},[path,pending]);
  async function refresh(){setBusy(true);setError("");try{setData(await api<Review>(path));}catch(e){setError(message(e));}finally{setBusy(false);}}
  async function approve(job:Speech){
    if(busy||disabled||!job.can_approve)return;
    setBusy(true);setError("");setNotice("");
    try{
      const session=await api<{csrf_token:string}>("/session");setCsrf(session.csrf_token);
      await api(`/audio/jobs/${job.id}/approve`,"POST",{});
      setData(await api<Review>(path));setNotice(`${job.speaker_name}의 음성을 확인했습니다. 원본 음성의 확인 상태도 함께 반영됩니다.`);
    }catch(e){setError(message(e));}finally{setBusy(false);}
  }
  if(!data&&!error)return null;
  if(data?.timing)return <SceneTimingReview timing={data.timing} requestId={requestId} version={version} sourceVersion={data.source_version} busy={busy} error={error} refresh={()=>void refresh()}/>;
  if(data?.jobs.length===0&&!error)return null;
  const valid=data?.jobs.filter(job=>!job.excluded_reason)??[];
  const excluded=data?.jobs.filter(job=>job.excluded_reason)??[];
  function render(job:Speech,index:number,rejected=false){
    const label=job.purpose==="timing"&&!rejected?"시간 측정용":rejected?"제외된 음성":job.status==="approved"?"확인 완료":job.status==="queued"?"생성 대기":job.status==="running"?"생성 중":job.timing_ok?"검토 필요":"시간 확인 필요";
    return <article className="work-speech-item" key={job.id} aria-label={`${rejected?"제외 결과":"발화"} ${index+1} ${job.speaker_name}`}>
      <header><h4>{index+1}. {job.speaker_name}</h4><StatusBadge tone={rejected?"danger":job.status==="approved"?"success":"warning"}>{label}</StatusBadge></header>
      <p className="work-speech-text">{job.text}</p>
      <dl className="work-speech-metrics"><div><dt>실제 음성</dt><dd>{job.duration?.toFixed(2)??"미측정"}{job.duration!==null?"초":""}</dd></div><div><dt>배정 시간</dt><dd>{(job.end-job.start).toFixed(2)}초</dd></div><div><dt>영상 내 구간</dt><dd>{job.start.toFixed(2)}–{job.end.toFixed(2)}초</dd></div><div><dt>목소리</dt><dd>{job.voice} · AI 음성</dd></div></dl>
      {rejected&&<p className="work-speech-warning">{reasons[job.excluded_reason!]??"오류가 있는 음성으로 사용 대상에서 제외했습니다."}</p>}
      {!rejected&&job.duration!==null&&!job.timing_ok&&<p className="work-speech-warning">배정 시간을 초과해 확인할 수 없습니다. 원래 음성 시간표를 조정해 주세요. 음성은 자동으로 자르지 않습니다.</p>}
      <div className="work-speech-controls">{job.has_media&&["review","approved"].includes(job.status)?<audio controls preload="none" aria-label={`${job.speaker_name} · ${job.text}${rejected?" · 제외 결과":""}`} src={`/api/v1/audio/jobs/${job.id}/media`}/>:<p className="muted">재생할 음성이 아직 없습니다.</p>}{!rejected&&job.purpose!=="timing"&&<Button variant="secondary" disabled={busy||disabled||!job.can_approve} onClick={()=>void approve(job)}>{job.status==="approved"?"확인 완료":"듣고 확인한 음성 확정"}</Button>}</div>
      {job.transcript&&<details><summary>생성된 음성 전사 확인</summary><p className="work-speech-text">{job.transcript}</p></details>}
    </article>;
  }
  return <Card className="work-speech-review"><section aria-label="대사별 음성 확인">
    <header className="work-speech-heading"><div><h3>대사별 음성 확인</h3><p className="muted">제작 음성 {valid.filter(j=>j.purpose!=="timing").length}개 · 시간 측정용 {valid.filter(j=>j.purpose==="timing").length}개 · 확인 완료 {valid.filter(j=>j.purpose!=="timing"&&j.status==="approved").length}개 · 제외 {excluded.length}개</p></div><Button variant="secondary" disabled={busy} onClick={()=>void refresh()}>음성 새로고침</Button></header>
    {data&&<p className="muted">{data.source_version!==version?`답변 v${version}에 연결된 v${data.source_version}의 음성입니다. `:`답변 v${data.source_version}에서 생성한 음성입니다. `}대사와 목소리를 재생해 확인하세요. 제작 음성의 확정은 에이전트 지침을 변경하지 않습니다.</p>}
    {data?.jobs.some(j=>j.purpose==="timing")&&<p className="muted">시간 측정용 임시 음성입니다. 최종 확정·합성에는 사용하지 않습니다. 캐릭터 설정에서 목소리를 선택한 뒤 제작 음성을 생성하고 시간을 다시 검증하세요.</p>}
    {disabled&&<p className="work-speech-warning">답변 수정 또는 생성 중에는 음성을 확정할 수 없습니다.</p>}
    {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
    <div className="work-speech-list">{valid.map((job,i)=>render(job,i))}</div>
    {excluded.length>0&&<details className="work-speech-excluded"><summary>제외된 음성 {excluded.length}개 · 사유와 이전 결과 보기</summary><p className="muted">아래 음성은 삭제하지 않고 기록으로 보존합니다. 정상 음성의 확인 개수에 포함하지 않습니다.</p><div className="work-speech-list">{excluded.map((job,i)=>render(job,i,true))}</div></details>}
  </section></Card>;
}
