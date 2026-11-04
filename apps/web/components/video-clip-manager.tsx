"use client";
import { useCallback, useEffect, useState } from "react";
import { api, message } from "../lib/registry";
import { Button, Card, StatusBadge } from "./ui";
import "./character-studio.css";

type Clip = {
  clip_id: string; scene_id: string; shot_id: string; image_id: string; prompt: string;
  source_start_seconds: number; source_end_seconds: number; duration_seconds: number;
  continuity_in: string; continuity_out: string; source_excerpt: string; split_reason: string;
  style_application?:string; edit_notes?:string;
};
type Plan = {model_key: string; model_revision: string; aspect_ratio: string; clips: Clip[]};
type Job = {id: string; clip_id: string; status: string; error_code?: string; estimate: string | number | null; created_at:string; updated_at:string};
type Jobs = {enabled: boolean; worker_online:boolean; jobs: Job[]; rates:Record<string,number|null>};
const labels: Record<string,string> = {queued:"실행 대기",submitting:"요청 전송 중",running:"영상 생성 중",
  review:"검토 필요",approved:"확정",unknown:"공급자 결과 확인 필요",failed:"생성 실패"};
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
  const eligible = plan.clips.filter(c => mode === "generate" ? !byClip.has(c.clip_id) : byClip.get(c.clip_id)?.status === "review");
  const seconds = plan.clips.filter(c => selected.includes(c.clip_id)).reduce((total,c)=>total+c.duration_seconds,0);
  const rate = data?.rates[plan.model_key];
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
      <Button variant="secondary" disabled={busy || !data?.enabled} onClick={()=>enter("generate")}>선택 생성</Button>
      <Button variant="secondary" disabled={busy || !data?.jobs.some(j=>j.status==="review")} onClick={()=>enter("approve")}>선택 확정</Button>
    </div></div>
    {data && !data.enabled && <p className="notice">영상 생성 연결을 기다리고 있어요. 클립별 프롬프트와 시작 이미지를 먼저 확인할 수 있습니다.</p>}
    {data?.enabled && !data.worker_online && <p className="notice">영상 워커 연결 대기 중입니다. 접수한 클립은 워커가 연결되면 생성됩니다.</p>}
    {error && <p role="alert" className="field-error">{error} <Button variant="secondary" onClick={refresh}>상태 새로고침</Button></p>}
    <nav className="character-picker scene-manager-picker" aria-label="영상 클립 선택">{plan.clips.map((c,i) =>
      <button key={c.clip_id} type="button" disabled={busy || (!!mode && !eligible.includes(c))}
        aria-pressed={mode ? selected.includes(c.clip_id) : current===c.clip_id}
        onClick={()=>{setCurrent(c.clip_id); if(mode) setSelected(ids=>ids.includes(c.clip_id)?ids.filter(x=>x!==c.clip_id):[...ids,c.clip_id]);}}>
        <strong>장면 {c.scene_id} · 클립 {i+1}</strong><span>{c.duration_seconds}초 · {labels[byClip.get(c.clip_id)?.status ?? ""] ?? "미생성"}</span>
      </button>)}</nav>
    {mode === "generate" && <p className="helper-text">선택한 클립 {seconds}초 · {rate == null ? "예상 비용 미확인" : `예상 비용 $${(rate*seconds).toFixed(2)}`}</p>}
    {mode && <div className="script-actions"><Button variant="secondary" disabled={busy} onClick={()=>setSelected(eligible.map(c=>c.clip_id))}>모두 선택</Button>
      <Button variant="secondary" disabled={busy} onClick={()=>enter(null)}>취소</Button>
      <Button disabled={busy || !selected.length} onClick={submit}>{selected.length}개 {mode==="approve"?"검토한 영상 확정":"유료 영상 생성 요청"}</Button></div>}
    <Card><div className="stack"><div className="card-heading"><h3>장면 {clip.scene_id} · 컷 {clip.shot_id}</h3>
      <StatusBadge>{labels[job?.status ?? ""] ?? "미생성"}</StatusBadge></div>
      <p>{clip.source_start_seconds}–{clip.source_end_seconds}초 · 생성 {clip.duration_seconds}초 · {plan.aspect_ratio}</p>
      {job && <p className="helper-text">접수 후 {Math.max(0,Math.floor(((["queued","running","submitting"].includes(job.status) ? Date.now() : Date.parse(job.updated_at))-Date.parse(job.created_at))/1000))}초
        {job.estimate != null && ` · 예상 비용 $${Number(job.estimate).toFixed(2)}`}</p>}
      {job && ["review","approved"].includes(job.status) && <video controls preload="metadata" style={{maxWidth:"100%",maxHeight:"60vh"}} src={`/api/v1/video-clips/asset/${job.id}/video`} />}
      <details><summary>확정 시작 이미지</summary><img alt={`장면 ${clip.scene_id}의 확정 이미지`} loading="lazy"
        style={{maxWidth:"100%",maxHeight:"50vh"}} src={`/api/v1/characters/images/${encodeURIComponent(clip.image_id)}/asset`} /></details>
      <div><h4>영상 제작 지시</h4><p>{clip.prompt}</p></div>
      {clip.style_application && <div><h4>참고 스타일 반영</h4><p>{clip.style_application}</p></div>}
      {clip.edit_notes && <div><h4>후반 편집 지시</h4><p>{clip.edit_notes}</p></div>}
      <details><summary>대본과 장면 연결 확인</summary><p>{clip.source_excerpt}</p><p>시작 모습 · {clip.continuity_in}</p>
        <p>종료 모습 · {clip.continuity_out}</p><p>{clip.split_reason}</p></details>
    </div></Card>
  </section>;
}
