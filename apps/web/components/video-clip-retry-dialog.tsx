"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, message } from "../lib/registry";
import { videoTimestamp } from "../lib/video-connection";
import { videoRetryEligible, videoRetryReady } from "../lib/video-retry";
import { Modal } from "./character-library";
import { ActionIcon, Button, DisclosureSummary } from "./ui";

type Review = {
  original: {id:string;clip_id:string;status:string;provider:string;model:string;provider_endpoint:string|null;region?:string|null;provider_task:string|null;provider_status:string|null;created_at:string;updated_at:string;error_code:string|null};
  target: {provider:string;model:string;provider_endpoint:string|null;region?:string|null;estimate?:number|null}|null;
  target_fingerprint:string;eligible:boolean;reason:string|null;guidance:string;
};
const retryErrors:Record<string,string>={
  video_retry_target_changed:"현재 공급자·리전·모델·요금 또는 생성 설정이 변경되었습니다. 확인 정보를 다시 불러오고 새 대상을 확인하세요.",
  video_management_forbidden:"공급자 기록 확인과 유료 재시도는 작업 공간 소유자 또는 관리자만 진행할 수 있습니다.",
  video_job_missing:"이 영상 요청을 찾을 수 없습니다. 창을 닫고 최신 생성 상태를 확인하세요.",
  video_retry_superseded:"이미 재시도 요청이 있습니다. 창을 닫고 최신 생성 상태를 확인하세요.",
  video_retry_not_eligible:"이 요청은 재시도할 수 있는 실패·결과 미확인 상태가 아닙니다.",
  video_retry_recovery_required:"공급자 작업 ID가 있습니다. 원래 공급자에서 기존 결과를 확인·복구하세요.",
  video_retry_input_changed:"원래 영상 입력이 변경되었습니다. 계획과 기준 이미지를 다시 확인하세요.",
  video_clip_plan_approval_required:"이 클립의 계획 확정이 필요합니다. 최신 계획을 검토·확정한 뒤 다시 확인하세요.",
  video_plan_approval_required:"최신 영상 계획을 검토·확정한 뒤 다시 확인하세요.",
  video_retry_authentication_required:"현재 공급자 계정 인증을 확인해야 합니다. 영상 생성 관리에서 연결을 확인한 뒤 다시 시도하세요.",
  video_retry_acknowledgment_required:"이전 요청의 결과 미확인 안내를 확인해 주세요.",
  video_retry_conflict:"다른 요청과 충돌했습니다. 창을 닫고 최신 생성 상태를 확인하세요.",
  video_generation_disabled:"현재 영상 생성이 허용되지 않았습니다. 생성 관리 설정을 확인하세요.",
};
function retryError(reason:unknown){return reason instanceof ApiError?(retryErrors[reason.code]??message(reason)):message(reason);}
function providerName(provider:string){return provider==="alibaba"?"WAN · Alibaba":provider==="runway"?"Runway":provider==="higgsfield"?"WAN 3 · Higgsfield":provider;}
function regionName(region?:string|null){return ({singapore:"싱가포르",tokyo:"도쿄",beijing:"베이징","ap-southeast-1":"싱가포르","ap-northeast-1":"도쿄","cn-beijing":"베이징"} as Record<string,string>)[region??""]??region;}
function originalRegion(original:Review["original"]){
  if(original.region)return regionName(original.region);
  if(original.provider!=="alibaba")return null;
  try {
    const host=new URL(original.provider_endpoint??"").hostname;
    if(host.endsWith(".ap-southeast-1.maas.aliyuncs.com"))return "싱가포르";
    if(host.endsWith(".ap-northeast-1.maas.aliyuncs.com"))return "도쿄";
    return ({"dashscope-intl.aliyuncs.com":"싱가포르","dashscope.aliyuncs.com":"베이징","dashscope.ap-northeast-1.aliyuncs.com":"도쿄"} as Record<string,string>)[host]??null;
  }catch{return null;}
}

export function VideoClipRetryDialog({path,jobId,title,onClose,onAccepted}: {
  path:string;jobId:string;title:string;onClose:()=>void;onAccepted:()=>void;
}) {
  const [review,setReview]=useState<Review|null>(null);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  const [confirmed,setConfirmed]=useState(false);
  const [busy,setBusy]=useState(false);
  const [stale,setStale]=useState(false);
  const pending=useRef(false);
  const operation=useRef<{id:string;bodyKey:string}|null>(null);
  const endpoint=`${path}/jobs/${encodeURIComponent(jobId)}`;
  const load=useCallback(async()=>{
    setLoading(true);setError("");setReview(null);setConfirmed(false);
    try {setReview(await api<Review>(endpoint+"/retry-review"));setStale(false);}
    catch(reason){setError(retryError(reason));}
    finally{setLoading(false);}
  },[endpoint]);
  useEffect(()=>{void load();},[load]);
  const eligible=videoRetryEligible(review);
  const allowed=videoRetryReady(eligible&&!stale&&!!review?.target_fingerprint,review?.original.status==="unknown",confirmed,busy,loading);
  async function submit(){
    if(!allowed||pending.current||!review)return;
    pending.current=true;setBusy(true);setError("");
    const body={acknowledge_unknown:review.original.status==="unknown"&&confirmed,expected_target:review.target_fingerprint};
    const bodyKey=JSON.stringify(body);
    if(operation.current?.bodyKey!==bodyKey)operation.current={id:crypto.randomUUID(),bodyKey};
    try{
      await api(endpoint+"/retry","POST",{id:operation.current.id,...body});
      onAccepted();
    }catch(reason){
      setError(retryError(reason));
      if(reason instanceof ApiError&&reason.code==="video_retry_target_changed"){
        setStale(true);setConfirmed(false);operation.current=null;
      }
    }
    finally{pending.current=false;setBusy(false);}
  }
  return <Modal title={`${title} · 다시 생성`} className="video-clip-retry-dialog"
    onClose={()=>{if(!pending.current)onClose();}}
    footer={<><Button variant="secondary" disabled={busy} onClick={onClose}><ActionIcon kind="close"/>취소</Button>
      <Button disabled={!allowed} onClick={()=>void submit()}><ActionIcon kind="ai"/>{busy?"재시도 접수 중…":"다시 생성"}</Button></>}>
    <div className="video-clip-retry-content">
      {loading&&<p role="status">이전 요청과 현재 설정을 불러오고 있습니다.</p>}
      {review&&<>
        <section><h3>현재 생성 설정</h3>{review.target?<dl className="video-job-facts">
          <div><dt>공급자 · 모델</dt><dd>{providerName(review.target.provider)} · {review.target.model}</dd></div>
          {review.target.region&&<div><dt>리전</dt><dd>{regionName(review.target.region)}</dd></div>}
          <div><dt>예상 비용</dt><dd>{review.target.estimate==null?"미확인":`$${review.target.estimate.toFixed(2)}`}</dd></div>
        </dl>:<p>사용 가능한 현재 모델 설정이 없습니다.</p>}<p className="helper-text">기존 이력은 유지하며, 현재 설정으로 새로 생성합니다. 추가 비용이 발생할 수 있습니다.</p></section>
        {!eligible&&<p role="status" className="notice">{review.original.provider_task?"공급자 작업 ID가 있어 새 생성이 차단됩니다. 원래 공급자에서 기존 작업의 결과를 확인·복구해야 합니다.":retryErrors[review.reason??""]||"현재 상태에서는 재시도할 수 없습니다. 최신 계획·권한·생성 설정을 확인하세요."}</p>}
        {eligible&&review.original.status==="unknown"&&<>
          <p className="notice">이전 요청의 생성 여부를 확인하지 못했습니다. 다시 생성하면 중복 비용이 발생할 수 있습니다.</p>
          <label className="video-clip-cost-acknowledgment"><input type="checkbox" disabled={busy||stale} checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/><span>중복 생성·비용 가능성을 확인했습니다.</span></label>
        </>}
        <details><DisclosureSummary>이전 요청 상세</DisclosureSummary><dl className="video-job-facts">
          <div><dt>공급자 · 모델</dt><dd>{providerName(review.original.provider)} · {review.original.model}</dd></div>
          {originalRegion(review.original)&&<div><dt>원래 리전</dt><dd>{originalRegion(review.original)}</dd></div>}
          <div><dt>원래 리전·접속 주소</dt><dd>{review.original.provider_endpoint||"기록 없음 · 원래 설정을 별도로 확인하세요"}</dd></div>
          <div><dt>앱 요청 ID</dt><dd>{review.original.id}</dd></div>
          <div><dt>공급자 작업 ID</dt><dd>{review.original.provider_task||"기록 없음"}</dd></div>
          <div><dt>공급자 상태</dt><dd>{review.original.provider_status||"기록 없음"}</dd></div>
          <div><dt>접수 시각</dt><dd>{videoTimestamp(review.original.created_at)}</dd></div>
          <div><dt>마지막 기록</dt><dd>{videoTimestamp(review.original.updated_at)}</dd></div>
          <div><dt>오류 코드</dt><dd>{review.original.error_code||"기록 없음"}</dd></div>
        </dl></details>
      </>}
      {error&&<p role="alert" className="field-error">{error}</p>}
      {(!review||stale)&&!loading&&<Button variant="secondary" onClick={()=>void load()}><ActionIcon kind="refresh"/>확인 정보 다시 불러오기</Button>}
    </div>
  </Modal>;
}
