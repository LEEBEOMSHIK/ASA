"use client";
import { useCallback, useEffect, useState } from "react";
import { api, message } from "../lib/registry";
import { Button, Card, StatusBadge } from "./ui";
import { AudioProduction } from "./audio-production";
import "./character-studio.css";

type Clip = {
  clip_id: string; scene_id: string; shot_id: string; image_id: string; prompt: string;
  source_start_seconds: number; source_end_seconds: number; duration_seconds: number;
  continuity_in: string; continuity_out: string; source_excerpt: string; split_reason: string;
  style_application?:string; edit_notes?:string;
  connection_type?: "cut" | "continue"; previous_clip_id?: string | null;
};
type Plan = {model_key: string; model_revision: string; aspect_ratio: string; clips: Clip[]};
type Job = {id: string; clip_id: string; status: string; reference_valid?: boolean; error_code?: string; estimate: string | number | null; created_at:string; updated_at:string;voice_direction_prompt?:string};
type Jobs = {enabled: boolean; available_models:string[]; worker_online:boolean; jobs: Job[]; rates:Record<string,number|null>;voice_delivery?:{mode:string;supports_audio?:boolean;error:string|null;clips:{clip_id:string;prompt:string}[];speakers:{id:string;name:string;role:string;enabled:boolean;instructions:string;language:string;speed:number}[]}};
const labels: Record<string,string> = {queued:"실행 대기",submitting:"요청 전송 중",running:"영상 생성 중",
  review:"검토 필요",approved:"확정",unknown:"공급자 결과 확인 필요",failed:"생성 실패"};
const errors: Record<string,string> = {
  audio_timeline_invalid:"영상 길이를 벗어난 대사·나레이션이 있습니다. 발화 시간표와 영상 길이를 맞춰 주세요.",
  video_audio_unsupported:"선택한 영상 모델은 음성 생성을 지원하지 않습니다. 오디오 지원 모델로 비디오 프롬프트를 다시 요청해 주세요.",
  video_voice_cue_crosses_clip:"대사가 클립 경계를 넘어갑니다. 발화가 한 클립 안에 들어가도록 시간표 또는 클립 구성을 수정해 주세요.",
  video_previous_approval_required:"앞 영상을 확인하고 확정한 뒤 생성할 수 있습니다.",
  video_previous_reference_changed:"앞 영상의 확정 버전이 변경되었습니다. 연결을 다시 검토해야 합니다.",
  video_frame_extraction_failed:"앞 영상의 마지막 프레임을 추출하지 못했습니다. 다음 영상은 생성하지 않았습니다.",
  provider_configuration_missing:"관리자가 선택한 공급자의 키와 작업 공간 설정을 확인해야 합니다.",
  endpoint_changed:"접수 후 공급자 작업 공간 또는 리전이 변경됐습니다. 원래 설정과 공급자 작업을 확인해 주세요.",
  submission_uncertain:"전송 결과가 불명확해 자동 재시도를 중지했습니다. 공급자 작업과 과금 내역을 확인해 주세요.",
  provider_rejected:"공급자가 요청을 거절했습니다. 모델 권한·잔액·입력 조건을 확인해 주세요.",
  reference_size:"시작 이미지가 없거나 공급자의 크기 제한을 초과했습니다.",
  input_invalid:"영상 입력 조건을 확인해 주세요. WAN 시작 이미지는 투명하지 않은 PNG, 각 변 240~8000px이어야 합니다.",
  provider_failed:"공급자에서 영상 생성에 실패했습니다.", task_missing:"공급자 작업을 찾지 못했습니다. 작업 만료 여부를 확인해 주세요.",
  output_invalid:"공급자 응답 또는 영상 형식을 확인하지 못했습니다.", worker_interrupted:"전송 중 워커가 중단되어 공급자 결과 확인이 필요합니다.",
};
export function isVideoPlan(value: unknown): value is Plan {
  if (!value || typeof value !== "object" || !("model_key" in value) || !("clips" in value)) return false;
  return Array.isArray(value.clips) && value.clips.length > 0 &&
    value.clips.every(c => c && typeof c.clip_id === "string" && typeof c.prompt === "string" && typeof c.image_id === "string");
}

export function VideoClipManager({plan, requestId, version}: {plan:Plan; requestId:string; version:number}) {
  const path = `/video-clips/${requestId}/${version}`;
  const [data,setData] = useState<Jobs | null>(null);
  const [error,setError] = useState("");
  const [busy,setBusy] = useState(false);
  const [mode,setMode] = useState<"generate"|"approve"|null>(null);
  const [selected,setSelected] = useState<string[]>([]);
  const [current,setCurrent] = useState(plan.clips[0].clip_id);
  const refresh = useCallback(async () => {
    try { setData(await api<Jobs>(path)); setError(""); }
    catch (e) { setError(message(e)); }
  }, [path]);
  useEffect(() => { void refresh(); },[refresh]);
  const active = data?.jobs.some(j => ["queued","submitting","running"].includes(j.status));
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => { void refresh(); },5000);
    return () => window.clearInterval(timer);
  },[active,refresh]);
  const byClip = new Map(data?.jobs.map(j => [j.clip_id,j]));
  const clip = plan.clips.find(c => c.clip_id === current) ?? plan.clips[0];
  const job = byClip.get(clip.clip_id);
  const ready = (c:Clip) => {
    const previous = byClip.get(c.previous_clip_id ?? "");
    return c.connection_type !== "continue" || (previous?.status === "approved" && previous.reference_valid !== false);
  };
  const parent = byClip.get(clip.previous_clip_id ?? "");
  const eligible = plan.clips.filter(c => mode === "generate" ? !byClip.has(c.clip_id) && ready(c) : byClip.get(c.clip_id)?.status === "review" && byClip.get(c.clip_id)?.reference_valid !== false);
  const seconds = plan.clips.filter(c => selected.includes(c.clip_id)).reduce((total,c)=>total+c.duration_seconds,0);
  const rate = data?.rates[plan.model_key];
  const available = !!data?.enabled && !!data.available_models?.includes(plan.model_key) && !data.voice_delivery?.error;
  function enter(next:typeof mode) { setMode(next); setSelected([]); }
  async function submit() {
    setBusy(true);
    try {
      await api(mode === "approve" ? path+"/approve" : path,"POST",{clip_ids:selected});
      enter(null); await refresh();
    } catch(e) { setError(message(e)); } finally { setBusy(false); }
  }
  return <section className="stack" aria-label="영상 클립 관리">
    <div className="card-heading"><h3>영상 클립 관리 · {plan.clips.length}개</h3><div className="script-actions">
      <Button variant="secondary" disabled={busy || !available} onClick={()=>enter("generate")}>선택 생성</Button>
      <Button variant="secondary" disabled={busy || !data?.jobs.some(j=>j.status==="review")} onClick={()=>enter("approve")}>선택 확정</Button>
    </div></div>
    {data && !available && <p className="notice">선택한 모델의 영상 생성 연결을 기다리고 있어요. 클립별 프롬프트와 시작 이미지를 먼저 확인할 수 있습니다.</p>}
    {available && !data?.worker_online && <p className="notice">영상 워커 연결 대기 중입니다. 접수한 클립은 워커가 연결되면 생성됩니다.</p>}
    {data?.voice_delivery?.mode==="video"&&<div className="voice-directions"><h3>영상에 전달할 목소리 특징</h3><p className="muted">비디오 프롬프트를 요청할 때 저장된 특징입니다. 캐릭터 설정을 바꿨다면 다시 요청해야 새 특징이 반영됩니다. 실제 음색과 대사는 생성 영상에서 확인하세요.</p>{data.voice_delivery.error&&<p role="alert" className="notice">{errors[data.voice_delivery.error]||"음성 시간표를 확인해 주세요."}</p>}{data.voice_delivery.speakers.map(s=><div key={s.id}><strong>{s.name} · {s.role==="narrator"?"공통 나레이션":"캐릭터"}</strong><p>{s.enabled?(s.instructions||"목소리 특징 미지정"):"사용 안 함"}</p>{s.enabled&&<p className="muted">{s.language} · 속도 의도 {s.speed}배</p>}</div>)}</div>}
    {error && <p role="alert" className="field-error">{error} <Button variant="secondary" onClick={refresh}>상태 새로고침</Button></p>}
    <nav className="character-picker scene-manager-picker" aria-label="영상 클립 선택">{plan.clips.map((c,i) =>
      <button key={c.clip_id} type="button" disabled={busy || (!!mode && !eligible.includes(c))}
        aria-pressed={mode ? selected.includes(c.clip_id) : current===c.clip_id}
        onClick={()=>{setCurrent(c.clip_id); if(mode) setSelected(ids=>ids.includes(c.clip_id)?ids.filter(x=>x!==c.clip_id):[...ids,c.clip_id]);}}>
        <strong>장면 {c.scene_id} · 클립 {i+1}</strong><span>{c.duration_seconds}초 · {labels[byClip.get(c.clip_id)?.status ?? ""] ?? (ready(c) ? "미생성" : "앞 영상 확정 대기")}</span>
        <span>{c.connection_type === "continue" ? "연속 동작" : "컷 전환"}</span>
      </button>)}</nav>
    {mode === "generate" && <p className="helper-text">선택한 클립 {seconds}초 · {rate == null ? "예상 비용 미확인" : `예상 비용 $${(rate*seconds).toFixed(2)}`}</p>}
    {mode && <div className="script-actions"><Button variant="secondary" disabled={busy} onClick={()=>setSelected(eligible.map(c=>c.clip_id))}>모두 선택</Button>
      <Button variant="secondary" disabled={busy} onClick={()=>enter(null)}>취소</Button>
      <Button disabled={busy || !selected.length || (mode==="generate" && !available)} onClick={submit}>{selected.length}개 {mode==="approve"?"검토한 영상 확정":"유료 영상 생성 요청"}</Button></div>}
    <Card><div className="stack"><div className="card-heading"><h3>장면 {clip.scene_id} · 컷 {clip.shot_id}</h3>
      <StatusBadge>{labels[job?.status ?? ""] ?? "미생성"}</StatusBadge></div>
      {job?.error_code && <p className="notice" role="status">{errors[job.error_code] ?? "공급자 결과와 연결 설정을 확인해 주세요."}</p>}
      <p>{clip.source_start_seconds}–{clip.source_end_seconds}초 · 생성 {clip.duration_seconds}초 · {plan.aspect_ratio}</p>
      <p>{clip.connection_type === "continue" ? `연속 동작 · 앞 클립 ${clip.previous_clip_id}의 확정 영상 마지막 프레임에서 시작` : "컷 전환 · 확정 씬 이미지에서 독립적으로 시작"}</p>
      {!ready(clip) && <p className="notice" role="status">앞 영상을 검토·확정하면 이 클립을 생성할 수 있습니다.</p>}
      {job?.reference_valid === false && <p className="notice" role="status">참조한 앞 영상이 변경되어 다시 검토해야 합니다. 이 영상의 확정과 후속 생성은 차단됩니다.</p>}
      {job && <p className="helper-text">접수 후 {Math.max(0,Math.floor(((["queued","running","submitting"].includes(job.status) ? Date.now() : Date.parse(job.updated_at))-Date.parse(job.created_at))/1000))}초
        {job.estimate != null && ` · 예상 비용 $${Number(job.estimate).toFixed(2)}`}</p>}
      {job && ["review","approved"].includes(job.status) && <video controls preload="metadata" style={{maxWidth:"100%",maxHeight:"60vh"}} src={`/api/v1/video-clips/asset/${job.id}/video`} />}
      {ready(clip) && job?.reference_valid !== false && <details><summary>확정 시작 이미지</summary><img alt={clip.connection_type === "continue" ? "앞 확정 영상의 마지막 프레임" : `장면 ${clip.scene_id}의 확정 이미지`} loading="lazy"
        style={{maxWidth:"100%",maxHeight:"50vh"}} src={clip.connection_type === "continue" && parent
          ? `/api/v1/video-clips/asset/${parent.id}/last-frame`
          : `/api/v1/characters/images/${encodeURIComponent(clip.image_id)}/asset`} /></details>}
      <div><h4>영상 제작 지시</h4><p>{clip.prompt}</p></div>
      {data?.voice_delivery?.mode==="video"&&<div><h4>{job?"생성 요청에 전달한 음성 지시":"이 클립의 음성 지시"}</h4><p style={{whiteSpace:"pre-wrap"}}>{job?.voice_direction_prompt??data.voice_delivery.clips.find(c=>c.clip_id===clip.clip_id)?.prompt??""}</p>{!(job?.voice_direction_prompt??data.voice_delivery.clips.find(c=>c.clip_id===clip.clip_id)?.prompt)&&<p className="muted">이 클립에 배정된 발화가 없습니다.</p>}</div>}
      {clip.style_application && <div><h4>참고 스타일 반영</h4><p>{clip.style_application}</p></div>}
      {clip.edit_notes && <div><h4>후반 편집 지시</h4><p>{clip.edit_notes}</p></div>}
      <p className="helper-text">클립 연결은 시작 프레임 전달까지 지원합니다. {data?.voice_delivery?.mode==="video"?"목소리 특징과 대사는 영상 모델에 전달하며, 실제 음성은 생성 영상에서 확인합니다.":"음성·음악 제작에서 컷 연결과 오디오 합성을 진행합니다."} 자막 합성·모델 연장 API는 아직 지원하지 않습니다.</p>
      <details><summary>대본과 장면 연결 확인</summary><p>{clip.source_excerpt}</p><p>시작 모습 · {clip.continuity_in}</p>
        <p>종료 모습 · {clip.continuity_out}</p><p>{clip.split_reason}</p></details>
    </div></Card>
  {data?.voice_delivery?.mode!=="video"&&<details><summary>기존 별도 음성·음악 제작</summary><p className="muted">이전 제작 방식입니다. 캐릭터의 목소리 특징을 영상 모델에 전달하려면 비디오 프롬프트를 새로 요청해 주세요. 기존 음성은 보존됩니다.</p><AudioProduction key={requestId+":"+version} requestId={requestId} version={version}/></details>}</section>;
}
