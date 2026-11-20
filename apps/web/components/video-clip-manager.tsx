"use client";
import {type ReviewAnnotation} from '../lib/video-review-highlights';
import {VideoReviewText} from './video-review-text';
import { useCallback, useEffect, useRef, useState } from "react";
import { videoJobTime, videoOrientation } from "../lib/video-job-time";
import {videoCostLabel,totalVideoCost,type VideoEstimate} from "../lib/video-cost";
import { videoTimestamp } from "../lib/video-connection";
import { api, message } from "../lib/registry";
import { ActionIcon, DisclosureSummary, Button, Card, StatusBadge } from "./ui";
import { VideoAssetReviewPanel } from "./video-asset-review-panel";
import { VideoClipRevisionDialog } from "./video-clip-revision-dialog";
import { VideoSourcePanel } from "./video-source-panel";
import { VideoClipRetryDialog } from "./video-clip-retry-dialog";
import { AudioProduction } from "./audio-production";
import "./character-studio.css";
import "./video-clip-manager.css";

type Clip = {
  clip_id: string; scene_id: string; shot_id: string; image_id: string; prompt: string;
  source_start_seconds: number; source_end_seconds: number; duration_seconds: number;
  continuity_in: string; continuity_out: string; source_excerpt: string; split_reason: string;
  style_application?:string; edit_notes?:string;
  quality?:{image_status:string;image_reason:string};
  reference_inputs?: {character_image_ids:string[];video?:{job_id:string}[];audio?:{job_id:string;speaker_id:string;start_seconds:number;end_seconds:number}[]}[];
  connection_type?: "cut" | "continue"; previous_clip_id?: string | null;
};
type Plan = {model_key: string; model_revision: string; aspect_ratio: string; clips: Clip[]};
type Job = {inherited?:boolean;answer_version?:number;finished_at?:string|null;progress_stage?:string; provider_status?:string; diagnostics?:{stage?:string;category?:string;http_status?:number;provider_code?:string;request_id?:string}|null; paused?:boolean; id: string; clip_id: string; status: string; reference_valid?: boolean; error_code?: string; estimate: string | number | null; created_at:string; updated_at:string;voice_direction_prompt?:string};
type Jobs = {model_issues?:Record<string,string>;model_provider?:string;model_label?:string;estimates?:Record<string,VideoEstimate>;reference_delivery?:{configured:boolean;error:string|null};changed_clips?:string[];previous_attempts?:Job[];review_validation?:{complete:boolean;covered_sections:number;total_sections:number}|null;review_annotations:ReviewAnnotation[];plan_approvals:Record<string,{approved:boolean;fingerprint:string}>; is_latest:boolean; enabled: boolean; available_models:string[]; worker_online:boolean; jobs: Job[]; rates:Record<string,number|null>;voice_delivery?:{mode:string;supports_audio?:boolean;error:string|null;clips:{clip_id:string;prompt:string}[];speakers:{id:string;name:string;role:string;enabled:boolean;instructions:string;language:string;speed:number}[]}};
const labels: Record<string,string> = {queued:"실행 대기",submitting:"요청 전송 중",running:"영상 생성 중",
  review:"영상 검토 필요",approved:"영상 확정됨",unknown:"생성 결과 확인 필요",failed:"생성 실패"};
const errors: Record<string,string> = {
  video_reference_delivery_unconfigured:"음성 참조 전달 연결이 준비되지 않았습니다. 관리자에게 연결 설정을 요청해 주세요.",
  poll_failed:"영상 서비스 상태 조회에 실패했습니다. 새 영상을 요청하지 않고 기존 작업의 상태를 다시 확인합니다.",
  download_failed:"완성 영상 다운로드에 실패했습니다. 새 영상을 생성하지 않고 기존 결과의 다운로드를 다시 시도합니다.",
  audio_timeline_invalid:"영상 길이를 벗어난 대사·나레이션이 있습니다. 발화 시간표와 영상 길이를 맞춰 주세요.",
  video_duration_unsupported:"클립 길이가 선택한 모델의 지원 범위를 벗어납니다. 클립 계획을 수정하거나 지원 모델을 선택해 주세요.",
  video_reference_audio_unsupported:"선택한 모델은 음성 파일 참조를 지원하지 않습니다. 음성 참조 지원 모델로 계획을 요청해 주세요.",
  video_audio_unsupported:"선택한 영상 모델은 음성 생성을 지원하지 않습니다. 오디오 지원 모델로 비디오 프롬프트를 다시 요청해 주세요.",
  video_voice_cue_crosses_clip:"대사가 클립 경계를 넘어갑니다. 발화가 한 클립 안에 들어가도록 시간표 또는 클립 구성을 수정해 주세요.",
  video_previous_approval_required:"앞 영상을 확인하고 확정한 뒤 생성할 수 있습니다.",
  video_previous_reference_changed:"앞 영상의 확정 버전이 변경되었습니다. 연결을 다시 검토해야 합니다.",
  video_frame_extraction_failed:"앞 영상의 마지막 프레임을 추출하지 못했습니다. 다음 영상은 생성하지 않았습니다.",
  provider_configuration_missing:"관리자가 선택한 영상 서비스의 키와 작업 공간 설정을 확인해야 합니다.",
  endpoint_changed:"접수 후 영상 서비스 작업 공간 또는 리전이 변경됐습니다. 원래 설정과 영상 서비스 작업을 확인해 주세요.",
  submission_uncertain:"전송 결과가 불명확해 자동 재시도를 중지했습니다. 영상 서비스 작업과 과금 내역을 확인해 주세요.",
  provider_rejected:"영상 서비스가 요청을 거절했습니다. 모델 권한·잔액·입력 조건을 확인해 주세요.",
  reference_size:"시작 이미지가 없거나 영상 서비스의 크기 제한을 초과했습니다.",
  input_invalid:"영상 입력 조건을 확인해 주세요. WAN 시작 이미지는 투명하지 않은 PNG, 각 변 240~8000px이어야 합니다.",
  provider_failed:"영상 서비스에서 영상 생성에 실패했습니다.", task_missing:"영상 서비스 작업을 찾지 못했습니다. 작업 만료 여부를 확인해 주세요.",
  output_invalid:"영상 서비스 응답 또는 영상 형식을 확인하지 못했습니다.", worker_interrupted:"전송 중 백그라운드 작업이 중단되어 영상 서비스 결과 확인이 필요합니다.",
};
const stages: Record<string,string> = {queued:"실행 대기",submitting:"요청 보내는 중",provider_pending:"생성 순서 대기",provider_running:"영상 만드는 중",downloading:"영상 가져오는 중",review:"영상 준비 완료"};
const diagnosticCategories: Record<string,string> = {http_status:"영상 서비스 HTTP 오류 응답",transport:"네트워크 전송 오류",invalid_response:"응답 형식 오류",provider_failure:"영상 서비스 처리 실패",authentication:"계정 인증 실패",permission:"권한 거부",quota:"잔액·사용량 제한",rate_limit:"호출 한도",invalid_input:"입력 조건 오류",network:"네트워크 연결 오류",timeout:"응답 시간 초과",provider:"영상 서비스 처리 오류",unknown:"원인 미확인"};
function jobLabel(job?:Job) {
  if(!job)return "미생성";
  if(job.paused&&job.status==="queued")return "보류";
  if(["failed","unknown","approved","review"].includes(job.status))return labels[job.status];
  return stages[job.progress_stage??""]??labels[job.status]??"상태 미확인";
}
function VideoJobProgress({job,onRetry}:{job:Job;onRetry?:(trigger:HTMLButtonElement)=>void}) {
  const halted=["unknown","failed"].includes(job.status);
  const stage=job.progress_stage || (job.status==="running"?"":job.status);
  const order=Object.keys(stages);
  const current=order.indexOf(stage);
  const completed=["review","approved"].includes(job.status);
  const [now,setNow]=useState(()=>Date.now());
  const active=["queued","submitting","running"].includes(job.status);
  useEffect(()=>{if(!active)return;setNow(Date.now());const timer=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(timer);},[active,job.id]);
  const timing=videoJobTime(job,now);
  return <section className="video-job-progress" aria-label="영상 생성 진행 상황">
    <div className="video-job-summary"><strong>{completed?"영상 준비 완료":jobLabel(job)}</strong><span className="video-job-time">{timing.label} <b>{timing.text}</b></span></div>
    {!completed&&!halted&&<p className="helper-text">{job.paused?"생성이 일시 보류되어 있습니다.":"완료되면 이곳에 영상이 표시됩니다. 기다리는 동안 다른 클립을 확인할 수 있습니다."}</p>}
    {job.status==="unknown"&&<p className="notice">진행 확인이 중단되었습니다. 실제 생성 여부는 아직 확인되지 않았으며 자동으로 다시 생성하지 않습니다.</p>}
    {job.status==="failed"&&<p className="notice">영상 생성을 완료하지 못했습니다. 아래 원인을 확인한 뒤 다시 시도하세요.</p>}
    <details className="video-job-details" open={active}><DisclosureSummary>생성 상세</DisclosureSummary>
      <ol className="video-job-stages">{order.map((key,index)=><li key={key} aria-current={!halted&&!completed&&index===current?"step":undefined} data-current={!halted&&!completed&&index===current}>
        <span>{index+1}. {stages[key]}</span><span className="helper-text">{completed?"완료":current<0?"미확인":index<current?"완료":index===current?(halted?"마지막 기록":job.paused?"보류":"현재 단계"):"미도달"}</span>
      </li>)}</ol>
      <dl className="video-job-facts"><div><dt>요청 시각</dt><dd>{videoTimestamp(job.created_at)}</dd></div><div><dt>마지막 상태 확인</dt><dd>{videoTimestamp(job.updated_at)}</dd></div>
        {job.provider_status&&<div><dt>서비스 응답 코드</dt><dd>{job.provider_status}</dd></div>}
        {job.estimate!=null&&<div><dt>예상 비용</dt><dd>${Number(job.estimate).toFixed(2)}</dd></div>}
      </dl>
      <p className="helper-text">경과 시간에는 대기가 포함됩니다. 결과 미확인은 마지막 기록까지 표시하며 예상 완료 시간은 제공하지 않습니다.</p>
    </details>
    {(halted||job.error_code)&&<div className="video-job-diagnostics"><strong>오류 상세</strong>
      <p>{job.error_code ? errors[job.error_code]??"기록된 오류 코드를 관리자가 확인해야 합니다." : "상세 오류 메시지가 기록되지 않았습니다."}</p>
      <dl className="video-job-facts">
        <div><dt>오류 코드</dt><dd>{job.error_code||"기록 없음"}</dd></div>
        <div><dt>실패 단계</dt><dd>{job.diagnostics?.stage==="polling"?"영상 서비스 상태 조회":stages[job.diagnostics?.stage??""]??(job.diagnostics?.stage||"기록 없음")}</dd></div>
        {job.diagnostics?.category&&<div><dt>오류 분류</dt><dd>{diagnosticCategories[job.diagnostics.category]??job.diagnostics.category}</dd></div>}
        {job.diagnostics?.http_status&&<div><dt>HTTP 상태</dt><dd>{job.diagnostics.http_status}</dd></div>}
        {job.diagnostics?.provider_code&&<div><dt>영상 서비스 오류 코드</dt><dd>{job.diagnostics.provider_code}</dd></div>}
        {job.diagnostics?.request_id&&<div><dt>영상 서비스 요청 ID</dt><dd>{job.diagnostics.request_id}</dd></div>}
      </dl>
      {!job.diagnostics?.category&&<p className="helper-text">이 기록에는 영상 서비스의 상세 실패 원인이 없습니다. 인증·잔액 문제로 단정할 수 없습니다.</p>}
    </div>}
    {halted&&onRetry&&<Button variant="secondary" aria-haspopup="dialog" onClick={e=>onRetry(e.currentTarget)}><ActionIcon kind="ai"/>다시 생성</Button>}
  </section>;
}
export function isVideoPlan(value: unknown): value is Plan {
  if (!value || typeof value !== "object" || !("model_key" in value) || !("clips" in value)) return false;
  return Array.isArray(value.clips) && value.clips.length > 0 &&
    value.clips.every(c => c && typeof c.clip_id === "string" && typeof c.prompt === "string" && typeof c.image_id === "string");
}

export function VideoClipManager({plan, requestId, version, approvalDisabled, onPlanApproval}: {plan:Plan; requestId:string; version:number; approvalDisabled:boolean; onPlanApproval:()=>void}) {
  const path = `/video-clips/${requestId}/${version}`;
  const [retryJob,setRetryJob]=useState<string|null>(null);
  const retryTrigger=useRef<HTMLButtonElement|null>(null);
  function closeRetry(){setRetryJob(null);requestAnimationFrame(()=>retryTrigger.current?.isConnected&&retryTrigger.current.focus());}
  const [reviewJob,setReviewJob]=useState<string|null>(null);
  const reviewTrigger=useRef<HTMLButtonElement|null>(null);
  function closeReview(){setReviewJob(null);requestAnimationFrame(()=>reviewTrigger.current?.isConnected&&reviewTrigger.current.focus());}
  const [data,setData] = useState<Jobs | null>(null);
  const [error,setError] = useState("");
  const [notice,setNotice] = useState("");
  const revisionNotice=useRef<HTMLParagraphElement>(null);
  const [busy,setBusy] = useState(false);
  const [showRevision,setShowRevision] = useState(false);
  const revisionTrigger=useRef<HTMLButtonElement|null>(null);
  const revisionOperation=useRef<{fingerprint:string;id:string}|null>(null);
  const refreshSequence=useRef(0);
  const submitting=useRef(false);
  const [pending,setPending]=useState<Record<string,"sending"|"accepted">>({});
  const progressTarget=useRef<HTMLDivElement>(null);
  const [focusRequest,setFocusRequest]=useState(0);
  useEffect(()=>{
    if(!focusRequest)return;
    const target=progressTarget.current;
    if(!target)return;
    target.focus({preventScroll:true});
    target.scrollIntoView({block:"start",behavior:window.matchMedia("(prefers-reduced-motion: reduce)").matches?"instant":"smooth"});
  },[focusRequest]);
  const [mode,setMode] = useState<"generate"|"approve"|null>(null);
  const [selected,setSelected] = useState<string[]>([]);
  const [current,setCurrent] = useState(plan.clips[0].clip_id);
  const refresh = useCallback(async () => {
    const sequence=++refreshSequence.current;
    try {
      const snapshot=await api<Jobs>(path);
      if(sequence===refreshSequence.current) { setData(snapshot); setError("");
        setPending(previous=>Object.fromEntries(Object.entries(previous).filter(([id])=>!snapshot.jobs.some(job=>job.clip_id===id)))); }
    } catch (e) { if(sequence===refreshSequence.current) setError(message(e)); }
  }, [path]);
  useEffect(() => { void refresh(); },[refresh]);
  const active = Object.keys(pending).length>0 || data?.jobs.some(j => ["queued","submitting","running"].includes(j.status));
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => { void refresh(); },5000);
    return () => window.clearInterval(timer);
  },[active,refresh]);
  const byClip = new Map(data?.jobs.map(j => [j.clip_id,j]));
  const clip = plan.clips.find(c => c.clip_id === current) ?? plan.clips[0];
  const job = byClip.get(clip.clip_id);
  const imageProblem = (c:Clip) => c.quality && c.quality.image_status!=="compatible"
    ? c.quality.image_reason || "시작 이미지와 계획의 호환 여부가 확인되지 않았습니다." : null;
  const referenceDeliveryBlocked = (c:Clip) => !!c.reference_inputs?.some(input=>input.audio?.length) && !data?.reference_delivery?.configured;
  const ready = (c:Clip) => {
    if(data?.model_issues?.[c.clip_id] || imageProblem(c) || pending[c.clip_id] || referenceDeliveryBlocked(c)) return false;
    const previous = byClip.get(c.previous_clip_id ?? "");
    return c.connection_type !== "continue" || (previous?.status === "approved" && previous.reference_valid !== false);
  };
  const clipStatus = (c:Clip) => byClip.get(c.clip_id)?.status ?? (pending[c.clip_id] || (imageProblem(c)?"image_blocked":"pending"));
  const pendingLabels:Record<string,string>={pending:"미생성",sending:"요청 보내는 중",accepted:"접수 완료",image_blocked:"시작 이미지 검토 필요"};
  const planApproved = (id:string) => !!data?.plan_approvals[id]?.approved;
  const approvedCount = plan.clips.filter(c=>planApproved(c.clip_id)).length;
  const parent = byClip.get(clip.previous_clip_id ?? "");
  const eligible = plan.clips.filter(c => mode === "generate" ? planApproved(c.clip_id) && !byClip.has(c.clip_id) && ready(c) : byClip.get(c.clip_id)?.status === "review" && byClip.get(c.clip_id)?.reference_valid !== false);
  const seconds = plan.clips.filter(c => selected.includes(c.clip_id)).reduce((total,c)=>total+c.duration_seconds,0);
  const rate = data?.rates[plan.model_key];
  const clipEstimate = (c:Clip) => data?.estimates ? data.estimates[c.clip_id]?.amount_usd ?? null : rate == null ? null : rate*c.duration_seconds;
  const selectedEstimates = plan.clips.filter(c=>selected.includes(c.clip_id)).map(clipEstimate);
  const totalEstimate = totalVideoCost(selectedEstimates);
  const connected = !!data?.enabled && !!data.available_models?.includes(plan.model_key) && !data.voice_delivery?.error;
  const available = !!data?.is_latest && !approvalDisabled && connected;
  const planActionsDisabled=busy||approvalDisabled||!data?.is_latest;

  function enter(next:typeof mode) { setMode(next); setSelected([]); }
  async function submit(action:"generate"|"approve", ids:string[]) {
    if(submitting.current || busy || !ids.length) return;
    if(action==="generate" && (!available || ids.some(id=>{
      const target=plan.clips.find(c=>c.clip_id===id);
      return !target || !planApproved(id) || byClip.has(id) || !ready(target);
    }))) return;
    submitting.current=true; setBusy(true); setNotice(""); setError("");
    if(action==="generate") {
      setCurrent(ids[0]); enter(null);
      setPending(previous=>({...previous,...Object.fromEntries(ids.map(id=>[id,"sending" as const]))}));
      setFocusRequest(n=>n+1);
    }
    try {
      await api(action === "approve" ? path+"/approve" : path,"POST",{clip_ids:ids});
      if(action==="generate") setPending(previous=>({...previous,...Object.fromEntries(ids.map(id=>[id,"accepted" as const]))}));
      enter(null); void refresh(); onPlanApproval();
    } catch(e) {
      setPending(previous=>Object.fromEntries(Object.entries(previous).filter(([id])=>!ids.includes(id))));
      setError(message(e));
    } finally { submitting.current=false; setBusy(false); }
  }
  async function updateClipPlans(action:"approve"|"revoke", ids:string[]) {
    if(!ids.length || !data || planActionsDisabled) return;
    const fingerprints:Record<string,string> = {};
    for(const id of ids) {
      const snapshot=data.plan_approvals[id];
      if(!snapshot) return;
      fingerprints[id]=snapshot.fingerprint;
    }
    setBusy(true); setNotice(""); refreshSequence.current++;
    try {
      if(action==="revoke") {
        const {revoked}=await api<{revoked:number}>(path+"/plan-revoke","POST",{clip_ids:ids,fingerprints});
        if(mode==="generate") enter(null);
        setNotice(`${revoked}개 클립의 계획 확정을 해제했습니다.`);
      } else {
        await api(path+"/plan-approve","POST",{clip_ids:ids,fingerprints});
      }
      await refresh(); onPlanApproval();
    } catch(e) { setError(message(e)); } finally { setBusy(false); }
  }
  function closeRevision() {
    setShowRevision(false);
    requestAnimationFrame(()=>revisionTrigger.current?.focus({preventScroll:true}));
  }
  function revisionAccepted() {
    setShowRevision(false);
    setNotice("이 클립의 AI 계획 수정 요청을 접수했습니다. 완료되면 새 답변 버전이 표시됩니다.");
    requestAnimationFrame(()=>revisionNotice.current?.focus());
    onPlanApproval();
  }
  return <section className="video-clip-manager" aria-label="영상 클립 관리">
    <div id="followup-video_plans" className="video-plan-approval">
      <div>
        <h3>클립 계획 확정 · {approvedCount}/{plan.clips.length}개</h3>
        <p className="helper-text">새 영상을 생성하려면 클립 계획을 확정하세요. 확정을 해제하면 새 영상 생성에 다시 확정이 필요합니다. 접수·진행 중인 생성과 생성된 영상은 유지됩니다.</p>
      </div>
      <div className="video-plan-actions">
        <Button disabled={planActionsDisabled||approvedCount===plan.clips.length} onClick={()=>void updateClipPlans("approve",plan.clips.filter(c=>!planApproved(c.clip_id)).map(c=>c.clip_id))}><ActionIcon kind="confirm"/>{approvedCount===plan.clips.length?"전체 계획 확정됨":"전체 계획 확정"}</Button>
        <Button variant="secondary" disabled={planActionsDisabled||approvedCount===0} onClick={()=>void updateClipPlans("revoke",plan.clips.filter(c=>planApproved(c.clip_id)).map(c=>c.clip_id))}><ActionIcon kind="undo"/>전체 계획 확정 해제</Button>
      </div>
      {notice&&<p ref={revisionNotice} tabIndex={-1} role="status" className="helper-text video-plan-notice">{notice}</p>}
    </div>
    <div id="followup-video_clips" className="video-clip-overview">
    <div className="video-clip-heading"><h3>영상 클립 관리 · {plan.clips.length}개</h3><div className="script-actions">
      <Button variant="secondary" disabled={busy || !available || !plan.clips.some(c=>planApproved(c.clip_id)&&!byClip.has(c.clip_id)&&ready(c))} aria-expanded={mode==="generate"} onClick={()=>enter(mode==="generate"?null:"generate")}><ActionIcon kind="ai"/>선택 생성</Button>
      <Button variant="secondary" disabled={busy || !data?.jobs.some(j=>j.status==="review")} aria-expanded={mode==="approve"} onClick={()=>enter(mode==="approve"?null:"approve")}><ActionIcon kind="confirm"/>선택 영상 확정</Button>
    </div></div>
    {data && !connected && <p className="notice">선택한 모델의 영상 생성 연결을 기다리고 있어요. 클립별 프롬프트와 시작 이미지를 먼저 확인할 수 있습니다.</p>}
    {data&&!data.is_latest&&<p className="helper-text">이전 계획입니다. 계획 확정·해제·수정과 새 영상 생성은 최신 답변에서 진행하세요.</p>}
    {available && !data?.worker_online && <p className="notice">영상 워커 연결 대기 중입니다. 접수한 클립은 워커가 연결되면 생성됩니다.</p>}

    {error && <p role="alert" className="field-error">{error} <Button variant="secondary" onClick={refresh}><ActionIcon kind="refresh"/>상태 새로고침</Button></p>}
    <div className="scene-status-summary" role="status" aria-label="영상 클립 상태 요약">{["pending","image_blocked","sending","accepted","queued","submitting","running","review","approved","failed","unknown"].map(status=>{const count=plan.clips.filter(c=>clipStatus(c)===status).length;return count>0?<span className={`scene-count scene-count--${status}`} key={status}>{pendingLabels[status]??labels[status]} <strong>{count}</strong></span>:null;})}</div>
    <nav className="character-picker scene-manager-picker" aria-label="영상 클립 선택">{plan.clips.map((c,i) =>
      <button key={c.clip_id} type="button" disabled={busy || (!!mode && !eligible.includes(c))}
        aria-pressed={mode ? selected.includes(c.clip_id) : current===c.clip_id}
        onClick={()=>{setCurrent(c.clip_id); if(mode) setSelected(ids=>ids.includes(c.clip_id)?ids.filter(x=>x!==c.clip_id):[...ids,c.clip_id]);}}>
        <strong>장면 {c.scene_id} · 클립 {i+1}</strong><span>{c.duration_seconds}초 · {byClip.has(c.clip_id) ? jobLabel(byClip.get(c.clip_id)) : (pending[c.clip_id] ? (pending[c.clip_id]==="sending"?"요청 보내는 중":"접수 완료") : referenceDeliveryBlocked(c) ? "음성 참조 연결 필요" : imageProblem(c) ? "시작 이미지 검토 필요" : ready(c) ? "미생성" : "앞 영상 확정 대기")}</span>
        {byClip.get(c.clip_id)?.inherited&&<span className="video-origin-tag">v{byClip.get(c.clip_id)?.answer_version} 영상 이어받음</span>}
        {data?.changed_clips?.includes(c.clip_id)&&<span className="video-change-tag">계획 변경 · 새 생성 필요</span>}
        <span>{planApproved(c.clip_id)?"계획 확정됨":"계획 검토 필요"} · {c.connection_type === "continue" ? "연속 동작" : "컷 전환"}</span>
      </button>)}</nav>
    {mode === "generate" && <p className="helper-text">선택한 클립 {seconds}초 · {videoCostLabel(totalEstimate)}</p>}
    {mode && <div className="script-actions"><Button variant="secondary" disabled={busy} onClick={()=>setSelected(eligible.map(c=>c.clip_id))}><ActionIcon kind="confirm"/>모두 선택</Button>
      <Button variant="secondary" disabled={busy} onClick={()=>enter(null)}><ActionIcon kind="close"/>취소</Button>
      <Button disabled={busy || !selected.length || (mode==="generate" && !available)} onClick={()=>void submit(mode!,selected)}><ActionIcon kind={mode==="approve"?"confirm":"ai"}/>{selected.length}개 {mode==="approve"?"검토한 영상 확정":"유료 영상 생성 요청"}</Button></div>}
    </div>
    {data?.voice_delivery?.mode==="video"&&<details className="video-clip-notes"><DisclosureSummary>영상에 전달할 목소리 특징</DisclosureSummary><div className="voice-directions"><p className="muted">비디오 프롬프트를 요청할 때 저장된 특징입니다. 캐릭터 설정을 바꿨다면 다시 요청해야 새 특징이 반영됩니다. 실제 음색과 대사는 생성 영상에서 확인하세요.</p>{data.voice_delivery.error&&<p role="alert" className="notice">{errors[data.voice_delivery.error]||"음성 시간표를 확인해 주세요."}</p>}{data.voice_delivery.speakers.map(s=><div key={s.id}><strong>{s.name} · {s.role==="narrator"?"공통 나레이션":"캐릭터"}</strong><p>{s.enabled?(s.instructions||"목소리 특징 미지정"):"사용 안 함"}</p>{s.enabled&&<p className="muted">{s.language} · 속도 의도 {s.speed}배</p>}</div>)}</div></details>}
    <Card className="video-clip-detail"><div className="video-clip-content"><div className="card-heading"><h3>장면 {clip.scene_id} · 컷 {clip.shot_id}</h3>
      <StatusBadge>{job?jobLabel(job):pendingLabels[clipStatus(clip)]}</StatusBadge></div>
      {job?.inherited&&<section className="video-version-notice" aria-label="이전 영상 이어받음"><ActionIcon kind="confirm"/><div><strong>v{job.answer_version} 영상과 생성 상태를 이어받았습니다</strong><p>이 클립의 계획과 생성 조건은 변경되지 않았습니다. 기존 영상·생성 이력·검수 기록을 그대로 사용합니다.</p></div></section>}
      {data?.changed_clips?.includes(clip.clip_id)&&<section className="video-version-notice video-version-notice--changed" aria-label="클립 계획 변경"><ActionIcon kind="edit"/><div><strong>계획 변경 · 새 영상 생성 필요</strong><p>이전 계획과 생성 조건이 달라졌습니다. 현재 계획을 확인·확정한 뒤 생성해 주세요. 기존 영상과 이력은 보존됩니다.</p></div></section>}
      <div ref={progressTarget} tabIndex={-1} className="video-progress-target" aria-label={`장면 ${clip.scene_id} 영상 생성 진행`}>
        {pending[clip.clip_id]&&!job&&<section className="video-job-progress video-submission-status" role="status" aria-live="polite">
          <strong>{pending[clip.clip_id]==="sending"?"영상 생성 요청을 보내고 있습니다":"영상 생성 요청이 접수됐습니다"}</strong>
          <p>{pending[clip.clip_id]==="sending"?"접수 결과를 기다리고 있습니다. 다시 누르지 않아도 됩니다.":"실행 대기 → 영상 생성 → 결과 가져오기 순서로 진행됩니다. 현재 단계를 확인하고 있습니다."}</p>
          <p className="helper-text">상태를 자동으로 확인합니다. 새로고침하거나 다시 생성할 필요가 없습니다.</p>
        </section>}
        {job&&!["review","approved"].includes(job.status)&&<VideoJobProgress job={job} onRetry={trigger=>{retryTrigger.current=trigger;setRetryJob(job.id);}}/>}
        {error&&!job&&<p role="alert" className="field-error">{error}</p>}
      </div>
      {job&&["review","approved"].includes(job.status)&&<section className={`video-result video-result--${videoOrientation(plan.aspect_ratio)}`} aria-label="생성 영상 검토">
        <div className="video-result-player"><video key={job.id} aria-label={`장면 ${clip.scene_id} 생성 영상`} controls playsInline preload="metadata" src={`/api/v1/video-clips/asset/${job.id}/video`}/></div>
        <div className="video-result-review">
          <div className="video-result-intro"><h4>생성된 영상</h4><p>표정·동작과 목소리를 재생해 확인하세요.</p></div>
          <VideoSourcePanel requestId={requestId} version={version} clipId={clip.clip_id} jobId={job.id}/>
          <VideoJobProgress job={job}/>
          <div className="video-result-action"><strong>영상에서 바꾸고 싶은 부분이 있나요?</strong><p className="helper-text">수정 내용을 바탕으로 계획을 보완합니다. 새 계획을 확인·확정한 뒤 영상 생성을 별도로 요청하세요. 기존 영상은 유지됩니다.</p><Button variant="secondary" disabled={planActionsDisabled} aria-haspopup="dialog" onClick={e=>{revisionTrigger.current=e.currentTarget;setShowRevision(true);}}><ActionIcon kind="ai"/>수정 요청</Button></div>
          <div className="video-result-action"><strong>AI 영상 검수</strong><p className="helper-text">계획과 비교한 검수 결과와 이력을 확인합니다. 열기만으로 비용이 발생하지 않습니다.</p><Button variant="secondary" aria-haspopup="dialog" onClick={e=>{reviewTrigger.current=e.currentTarget;setReviewJob(job.id);}}><ActionIcon kind="ai"/>AI 영상 검수</Button></div>
          <div className="video-result-action"><strong>{job.status==="approved"?"영상 확정됨":"영상 확인 후 확정"}</strong><p className="helper-text">{job.status==="approved"?"확정한 영상은 다음 작업에서 사용할 수 있습니다.":"계획 확정과 별개로, 이 영상 결과를 사용하도록 확정합니다."}</p>{job.status==="review"&&<Button disabled={busy||job.reference_valid===false} onClick={()=>void submit("approve",[clip.clip_id])}><ActionIcon kind="confirm"/>이 영상 확정</Button>}</div>
        </div>
      </section>}
      {!!data?.previous_attempts?.some(previous=>previous.clip_id===clip.clip_id)&&<details className="video-clip-history"><DisclosureSummary>이 클립의 이전 생성 이력 · {data.previous_attempts.filter(previous=>previous.clip_id===clip.clip_id).length}건</DisclosureSummary><div>{data.previous_attempts.filter(previous=>previous.clip_id===clip.clip_id).map(previous=>["review","approved"].includes(previous.status)?
        <section key={previous.id} className={`video-result video-result--${videoOrientation(plan.aspect_ratio)}`} aria-label={`이전 답변 ${previous.answer_version??version} 생성 영상`}>
          <div className="video-result-player"><video aria-label={`장면 ${clip.scene_id} 이전 생성 영상`} controls playsInline preload="metadata" src={`/api/v1/video-clips/asset/${previous.id}/video`}/></div>
          <div className="video-result-review"><div className="video-result-intro"><h4>이전 생성 영상 · 답변 {previous.answer_version??version}</h4><p>보관된 결과입니다. 현재 계획으로 다시 생성한 영상이 아닙니다.</p></div>
            <VideoJobProgress job={previous}/><VideoSourcePanel requestId={requestId} version={previous.answer_version??version} clipId={previous.clip_id} jobId={previous.id}/>
          </div>
        </section>:<VideoJobProgress key={previous.id} job={previous}/>)}</div></details>}
      <dl className="video-clip-specs" aria-label="클립 시간과 시작 기준">
        <div><dt>영상 모델</dt><dd>{data?.model_label??(plan.model_key==="hf-wan3"?"WAN 3 · Higgsfield":plan.model_key)}</dd></div>
        <div><dt>계획상 구간</dt><dd>{clip.source_start_seconds}–{clip.source_end_seconds}초</dd></div>
        <div><dt>생성 요청 길이</dt><dd>{clip.duration_seconds}초</dd></div>
        <div><dt>화면 비율</dt><dd>{videoOrientation(plan.aspect_ratio)==="portrait"?"세로형":videoOrientation(plan.aspect_ratio)==="square"?"정사각형":"가로형"} {plan.aspect_ratio}</dd></div>
        <div className="video-clip-start"><dt>시작 기준</dt><dd>{clip.reference_inputs?.length ? "씬·캐릭터 이미지와 선택 음성·영상을 참고해 생성 · 첫 프레임 고정 안 함" : clip.connection_type === "continue" ? `앞 클립 ${clip.previous_clip_id}의 확정 영상 마지막 장면에서 이어 시작` : "확정된 씬 이미지에서 시작"}</dd></div>
      </dl>
      {(data?.model_provider==="higgsfield"||plan.model_key==="hf-wan3")&&<section className="video-model-guidance" aria-label="Higgsfield 자동 참조 전달">
        <strong>{data?.model_label??"선택한 모델"} · Higgsfield에 전달할 자료</strong>
        <p>기준 이미지 1장 · 캐릭터 이미지 {clip.reference_inputs?.reduce((sum,input)=>sum+input.character_image_ids.length,0)??0}장 · 음성 {clip.reference_inputs?.reduce((sum,input)=>sum+(input.audio?.length??0),0)??0}개 · 영상 {clip.reference_inputs?.reduce((sum,input)=>sum+(input.video?.length??0),0)??0}개</p>
        <p className="helper-text">이 계획에 저장된 참조를 사용합니다. 유료 영상 생성 요청 후 서버가 자료를 Higgsfield에 자동 업로드합니다. 화면 열기·계획 확정만으로 업로드하지 않습니다.</p>
      </section>}
      <div className="video-clip-generate" aria-label="현재 클립 계획 확정"><div><strong>{planApproved(clip.clip_id)?"클립 계획 확정됨":"클립 계획 검토 필요"}</strong><p className="helper-text">아래 제작 지시·목소리·시작 이미지를 확인하세요. 확정만으로 생성하거나 비용을 청구하지 않습니다.</p></div>
        <div className="video-plan-actions">
          {planApproved(clip.clip_id)
            ?<Button variant="secondary" disabled={planActionsDisabled} onClick={()=>void updateClipPlans("revoke",[clip.clip_id])}><ActionIcon kind="undo"/>계획 확정 해제</Button>
            :<Button disabled={planActionsDisabled} onClick={()=>void updateClipPlans("approve",[clip.clip_id])}><ActionIcon kind="confirm"/>이 클립 계획 확정</Button>}
          <Button variant="secondary" disabled={planActionsDisabled} aria-haspopup="dialog" onClick={e=>{revisionTrigger.current=e.currentTarget;setShowRevision(true);}}><ActionIcon kind="ai"/>AI로 이 클립 계획 수정</Button>
        </div>
      </div>
      {imageProblem(clip)&&<section className="video-image-blocker" role="status" aria-label="영상 생성 불가 사유">
        <div className="video-image-blocker-heading"><ActionIcon kind="warning"/><strong>영상 생성 불가 · 시작 이미지 확인 필요</strong></div>
        <p>{imageProblem(clip)}</p>
        <p className="helper-text">계획을 확정해도 이 문제는 해제되지 않습니다. 아래 시작 이미지와 제작 지시를 비교해 주세요.</p>
        <strong className="video-image-blocker-next">해결 방법</strong>
        <ul><li>이미지를 유지하려면 ‘AI로 이 클립 계획 수정’에서 현재 이미지 상태부터 이어지도록 요청하세요. 생략하거나 바꿀 행동을 명시해 주세요.</li><li>원래 행동 순서를 유지하려면 씬 이미지 작업에서 행동 시작 전 이미지를 만들고 확정한 뒤, 그 이미지로 영상 계획을 다시 요청하세요.</li></ul>
      </section>}
      {!job&&<div className="video-clip-generate">
        <div><strong>현재 클립 · {clip.duration_seconds}초</strong><p className="helper-text">{videoCostLabel(clipEstimate(clip))} · 유료 영상 생성</p>
          <p className="helper-text" id={`clip-generate-help-${clip.clip_id}`}>{data?.model_issues?.[clip.clip_id]?(errors[data.model_issues[clip.clip_id]]??"모델 지원 조건을 확인해 주세요."):referenceDeliveryBlocked(clip)?errors.video_reference_delivery_unconfigured:imageProblem(clip)?"시작 이미지 검토가 필요하여 생성할 수 없습니다.":pending[clip.clip_id]?"이미 요청한 작업의 진행 상태를 확인하고 있습니다.":!planApproved(clip.clip_id)?"이 클립의 계획을 먼저 확정하세요.":!data?"영상 생성 상태를 확인하고 있습니다.":!connected?"영상 생성 연결 상태를 확인해 주세요.":!ready(clip)?"앞 영상을 검토·확정한 뒤 생성할 수 있습니다.":"이 클립 1개만 생성합니다."}</p>
        </div>
        <Button disabled={busy||!available||!planApproved(clip.clip_id)||!ready(clip)} aria-describedby={`clip-generate-help-${clip.clip_id}`} onClick={()=>void submit("generate",[clip.clip_id])}><ActionIcon kind="ai"/>{busy?"요청 처리 중…":"이 클립 영상 생성"}</Button>
      </div>}
      {!ready(clip) && !referenceDeliveryBlocked(clip) && !imageProblem(clip) && !pending[clip.clip_id] && <p className="notice" role="status">앞 영상을 검토·확정하면 이 클립을 생성할 수 있습니다.</p>}
      {job?.reference_valid === false && <p className="notice" role="status">참조한 앞 영상이 변경되어 다시 검토해야 합니다. 이 영상의 확정과 후속 생성은 차단됩니다.</p>}
      {(clip.connection_type!=="continue" || parent?.status==="approved") && job?.reference_valid !== false && <details><DisclosureSummary>{clip.reference_inputs?.length?"참조 씬 이미지 · 첫 프레임 고정 안 함":"확정 시작 이미지"}</DisclosureSummary><img alt={clip.connection_type === "continue" ? "앞 확정 영상의 마지막 프레임" : `장면 ${clip.scene_id}의 확정 이미지`} loading="lazy"
        style={{maxWidth:"100%",maxHeight:"50vh"}} src={clip.connection_type === "continue" && parent
          ? `/api/v1/video-clips/asset/${parent.id}/last-frame`
          : `/api/v1/characters/images/${encodeURIComponent(clip.image_id)}/asset`} /></details>}
      <VideoReviewText clipId={clip.clip_id} annotations={data?.review_annotations} validation={data?.review_validation} key={clip.clip_id+':'+version} text={clip.prompt} sections={[
        ...(data?.voice_delivery?.mode==="video"?[{key:'voice',title:job?"생성 요청에 전달한 음성 지시":"이 클립의 음성 지시",text:(job?.voice_direction_prompt??data.voice_delivery.clips.find(c=>c.clip_id===clip.clip_id)?.prompt)||"이 클립에 배정된 발화가 없습니다."}]:[]),
        ...(clip.edit_notes?[{key:"edit_notes",title:"후반 편집 지시",text:clip.edit_notes}]:[]),
      ]}/>
      {clip.style_application && <div><h4>참고 스타일 반영</h4><p>{clip.style_application}</p></div>}
      <p className="helper-text">클립 연결은 시작 프레임 전달까지 지원합니다. {data?.voice_delivery?.mode==="video"?"목소리 특징과 대사는 영상 모델에 전달하며, 실제 음성은 생성 영상에서 확인합니다.":"음성·음악 제작에서 컷 연결과 오디오 합성을 진행합니다."} 자막 합성·모델 연장 API는 아직 지원하지 않습니다.</p>
    </div></Card>
    <aside className="video-clip-reference" aria-label="검토 참고 · 대본·장면 연결">
      <details>
        <DisclosureSummary><span className="video-clip-reference-title"><ActionIcon kind="document"/><span><span className="video-clip-reference-label">검토 참고</span><strong>대본·장면 연결</strong></span></span></DisclosureSummary>
        <p className="video-clip-reference-description helper-text">AI가 정리한 대본 발췌와 장면 연결 정보입니다. 제작 지시를 검토할 때 참고하세요.</p>
        <div className="video-clip-reference-body">
          <div><h4>대본 발췌 · 계획 기준</h4><p>{clip.source_excerpt}</p></div>
          <div><h4>시작 모습</h4><p>{clip.continuity_in}</p></div>
          <div><h4>종료 모습</h4><p>{clip.continuity_out}</p></div>
          <div><h4>클립 분할 이유</h4><p>{clip.split_reason}</p></div>
        </div>
      </details>
    </aside>
  {reviewJob && job?.id===reviewJob && <VideoAssetReviewPanel key={reviewJob} jobId={reviewJob} title={`장면 ${clip.scene_id} · 컷 ${clip.shot_id}`} onClose={closeReview}/>}
  {retryJob&&<VideoClipRetryDialog key={retryJob} path={path} jobId={retryJob} title={`장면 ${clip.scene_id} · 클립 ${plan.clips.indexOf(clip)+1}`} onClose={closeRetry} onAccepted={()=>{closeRetry();setNotice("새 영상 생성 요청을 접수했습니다. 이전 요청은 이 클립의 이전 생성 이력에서 확인할 수 있습니다.");void refresh();onPlanApproval();}}/>}
  {showRevision&&<VideoClipRevisionDialog requestId={requestId} version={version} clipId={clip.clip_id}
    title={`장면 ${clip.scene_id} · 클립 ${plan.clips.indexOf(clip)+1}`}
    disabled={planActionsDisabled} operation={revisionOperation} onClose={closeRevision} onAccepted={revisionAccepted}/>}
  {data?.voice_delivery?.mode!=="video"&&<details><summary>기존 별도 음성·음악 제작</summary><p className="muted">이전 제작 방식입니다. 캐릭터의 목소리 특징을 영상 모델에 전달하려면 비디오 프롬프트를 새로 요청해 주세요. 기존 음성은 보존됩니다.</p><AudioProduction key={requestId+":"+version} requestId={requestId} version={version}/></details>}</section>;
}
