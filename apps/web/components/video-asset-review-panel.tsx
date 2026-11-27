"use client";
import { useEffect, useId, useRef, useState } from "react";
import { api, message } from "../lib/registry";
import { type SpeechVideoSource } from "../lib/speech-video-timing";
import { Modal } from "./character-library";
import { ActionIcon, Button, StatusBadge } from "./ui";
import "./video-asset-review-panel.css";

type SpeechSuggestion = Pick<SpeechVideoSource,"start_seconds"|"end_seconds"|"observed"|"delivery"|"basis"> & {text:string};
type ReviewResult = {summary:string;checks:{category:string;verdict:"pass"|"issue"|"unverified";expected:string;observed:string;timestamp_seconds:number|null}[];limitations:string[];speech_suggestions?:SpeechSuggestion[]};
type Review = {id:string;status:string;result:ReviewResult|null;error_code:string|null;created_at:string;started_at:string|null;finished_at:string|null;agent_ref:string};
type Snapshot = {configured:boolean;available:boolean;reason:string|null;worker_online:boolean;reviews:Review[]};
const states:Record<string,string> = {queued:"검수 대기",running:"검수 중",succeeded:"검수 의견 도착",failed:"검수 실패",unknown:"호출 확인 필요"};
const categories:Record<string,string> = {visual:"화면 품질",prompt:"제작 지시 반영",style:"화풍",continuity:"장면 연속성",timing:"시간 구성",audio:"오디오",lipsync:"입 모양과 음성 일치"};
const unavailableReasons:Record<string,string> = {review_disabled:"AI 검수가 비활성화되어 있습니다. 관리자에게 검수 기능 설정을 확인해 달라고 요청해 주세요.",script_ai_disabled:"AI 호출이 비활성화되어 있습니다. 관리자에게 AI 실행 설정을 확인해 달라고 요청해 주세요.",video_review_unavailable:"완료된 영상이 있어야 검수를 요청할 수 있습니다.",model_not_configured:"검수 모델이 설정되어 있지 않습니다. 에이전트의 모델 설정을 확인해 주세요.",review_tools_unsupported:"검수 에이전트의 도구 설정을 확인해 주세요. 영상 검수는 도구 없는 이미지 입력 모델을 사용합니다."};
const verdicts = {pass:"확인됨",issue:"문제 발견",unverified:"미검증"};

function ReviewAnswer({result}:{result:ReviewResult}) {
  return <div className="video-asset-review-result"><p>{result.summary}</p>
    <p className="helper-text">샘플 프레임에서 관찰한 의견입니다. ‘확인됨’은 영상 전체의 품질 보증이나 사용자 확정을 뜻하지 않습니다.</p>
    {!!result.speech_suggestions?.length&&<section className="video-asset-review-check">
      <h4>음성 제작에 참고할 발화</h4>
      <p className="helper-text">음성 제작에서 원문이 같은 발화에 이 검수를 연결할 수 있습니다.</p>
      <dl>{result.speech_suggestions.map((suggestion,index)=><div key={index}>
        <dt>{suggestion.text}</dt>
        <dd>영상 내 약 {suggestion.start_seconds}–{suggestion.end_seconds}초 · {suggestion.basis==="mouth"?"입 모양 표본":"장면 변화 표본"}</dd>
        <dd>{suggestion.observed}</dd>
        <dd><strong>권장 연출</strong> {suggestion.delivery}</dd>
      </div>)}</dl>
    </section>}
    {result.checks.map((check,index)=><section key={index} className="video-asset-review-check">
      <div className="video-asset-review-heading"><h4>{categories[check.category]??"검토 항목"}</h4><StatusBadge tone={check.verdict==="pass"?"success":"warning"}>{verdicts[check.verdict]}</StatusBadge></div>
      {check.timestamp_seconds!=null&&<p className="helper-text">관찰 시점 · {check.timestamp_seconds}초</p>}
      <dl><div><dt>요청한 내용</dt><dd>{check.expected}</dd></div><div><dt>관찰한 내용</dt><dd>{check.observed}</dd></div></dl>
    </section>)}
    {result.limitations.length>0&&<section><h4>검수 한계 · 직접 확인할 내용</h4><ul>{result.limitations.map((item,index)=><li key={index}>{item}</li>)}</ul></section>}
  </div>;
}

export function VideoAssetReviewPanel({jobId,title,onClose}:{jobId:string;title:string;onClose:()=>void}) {
  const [data,setData]=useState<Snapshot|null>(null);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const [retry,setRetry]=useState(0);
  const alive=useRef(false), pending=useRef(false), sequence=useRef(0);
  const dispatch=useRef<string|null>(null);
  const helpId=useId();
  const path=`/video-clips/jobs/${encodeURIComponent(jobId)}/reviews`;
  useEffect(()=>{
    alive.current=true;
    let cancelled=false;
    let timer:ReturnType<typeof setTimeout>;
    async function poll() {
      if(!pending.current){
        const turn=++sequence.current;
        try {const next=await api<Snapshot>(path);if(!cancelled&&turn===sequence.current){setData(next);setError("");}}
        catch(e){if(!cancelled&&turn===sequence.current)setError(message(e));}
      }
      if(!cancelled)timer=setTimeout(()=>void poll(),5000);
    }
    void poll();
    return()=>{cancelled=true;alive.current=false;sequence.current++;clearTimeout(timer);};
  },[path,retry]);
  const active=data?.reviews.some(r=>["queued","running"].includes(r.status));
  const available=!!data?.configured&&data.available&&data.worker_online;
  async function request() {
    if(pending.current||!available||active||error)return;
    pending.current=true;sequence.current++;setBusy(true);setError("");
    dispatch.current??=crypto.randomUUID();
    try {
      await api(path,"POST",{id:dispatch.current});
      dispatch.current=null;
      if(alive.current){const next=await api<Snapshot>(path);if(alive.current)setData(next);}
    } catch(e){if(alive.current)setError(message(e));}
    finally {pending.current=false;if(alive.current)setBusy(false);}
  }
  const reason=!data?"검수 연결 상태를 확인하고 있습니다.":!data.configured?"이 작업에는 영상 검수 에이전트가 연결되어 있지 않습니다. 에이전트 설정의 ‘답변 이후 작업’에서 연결하고 저장하면 이 영상의 다음 검수 요청부터 적용됩니다.":!data.available?(unavailableReasons[data.reason??""]??"영상 검수 연결을 사용할 수 없습니다. 관리자에게 검수 에이전트의 모델·이미지 입력 지원·연결 설정 확인을 요청해 주세요."):!data.worker_online?"영상 검수 워커가 오프라인입니다. 연결된 뒤 요청할 수 있습니다.":active?"이미 진행 중인 검수가 있습니다. 완료 후 새 검수를 요청할 수 있습니다.":"검수는 아래 요청 버튼을 눌렀을 때만 실행됩니다.";
  return <Modal title={`${title} · AI 영상 검수`} onClose={onClose} className="video-asset-review-modal"><div className="video-asset-review-panel">
    <p id={helpId} role="status">{reason}</p>
    <p className="helper-text">생성 당시 제작 지시와 발화 원문을 영상의 샘플 프레임과 비교합니다. 별도 AI 비용이 발생하며 정확한 금액은 실행 전 확인되지 않습니다. 실제 발화·음색·립싱크와 샘플 사이 움직임은 영상을 직접 재생해 확인하세요.</p>
    <Button disabled={!available||busy||!!active||!!error} aria-describedby={helpId} onClick={()=>void request()}><ActionIcon kind="ai"/>{busy?"검수 접수 중…":active?"검수 진행 중":"AI 영상 검수 요청"}</Button>
    <p className="helper-text">AI 의견만 기록합니다. 영상 재생성·사용자 확정·자동 재시도는 하지 않습니다.</p>
    {error&&<div role="alert"><p>{error}</p><Button variant="secondary" disabled={busy} onClick={()=>setRetry(n=>n+1)}><ActionIcon kind="refresh"/>상태 다시 확인</Button></div>}
    <section className="video-asset-review-history"><h3>검수 실행 이력 · {data?.reviews.length??0}회</h3>
      {data&&!data.reviews.length&&<p className="muted">아직 요청한 영상 검수가 없습니다.</p>}
      {data?.reviews.map((review,index)=><article className="video-asset-review-entry" key={review.id}>
        <div className="video-asset-review-heading"><h4>{data.reviews.length-index}번째 검수</h4><StatusBadge tone={review.status==="failed"?"danger":"neutral"}>{states[review.status]??"확인 필요"}</StatusBadge></div>
        <p className="helper-text">요청 {new Date(review.created_at).toLocaleString("ko-KR")}{review.finished_at&&` · 종료 ${new Date(review.finished_at).toLocaleString("ko-KR")}`}</p>
        {["queued","running"].includes(review.status)&&<p role="status">백그라운드 검수 상태를 확인하고 있습니다. 모달을 닫아도 접수된 검수는 유지됩니다.</p>}
        {["failed","unknown"].includes(review.status)&&<p className="notice">검수를 완료하지 못했습니다. 영상과 확정 상태는 유지됩니다. 관리자 사용량 기록과 연결 설정을 확인해 주세요. 호출 결과·과금이 불명확할 수 있어 자동으로 다시 요청하지 않습니다.</p>}
        {review.result&&(index===0?<ReviewAnswer result={review.result}/>:<details><summary>이전 검수 의견 보기</summary><ReviewAnswer result={review.result}/></details>)}
      </article>)}
    </section>
  </div></Modal>;
}
