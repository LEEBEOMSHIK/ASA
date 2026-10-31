"use client";
import { useEffect, useState } from "react";
import { elapsedTime } from "../lib/image-job-time";

export type ImageJob = {
  id: string; version: number; status: string; model: string; base_id: string | null;
  created_at: string; started_at: string | null; finished_at: string | null;
  change: string; character: { name: string; appearance: string; image_prompt: string };
};
export function ImageJobProgress({job, online, baseVersion, approved = false}: {job: ImageJob; online: boolean; baseVersion?: number; approved?: boolean}) {
  const active = job.status === "queued" || job.status === "running";
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!active) return;
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [active, job.id]);
  const success = job.status === "succeeded";
  const uncertain = job.status === "unknown";
  const stepIndex = job.status === "queued" ? 1 : success ? 3 : 2;
  const steps = ["요청 접수", "실행 대기", "이미지 생성·저장", approved ? "확정 완료" : "결과 검토"];
  const progress = <ol className="image-job-steps" aria-label="이미지 작업 단계">{steps.map((label, index) => {
    const done = index < stepIndex || (index === 3 && success && approved);
    const current = index === stepIndex && !done;
    const interrupted = current && !active && !success;
    const state = done ? "완료" : current ? interrupted ? uncertain ? "확인 필요" : "중단됨" : success ? "검토 필요" : "진행 중" : "대기";
    return <li key={index} data-state={done ? "done" : interrupted ? "interrupted" : current ? "current" : "pending"} aria-current={current ? "step" : undefined}>
      <span className={current && active ? "image-step-mark image-step-mark--active" : "image-step-mark"} aria-hidden="true">{done ? "✓" : interrupted ? "!" : index + 1}</span>
      <span><strong>{label}</strong><small>{state}</small></span>
    </li>;
  })}</ol>;
  if (!active) return <section className="image-job-progress" aria-label="이미지 생성 진행">{progress}<p className="muted">v{job.version} · {success ? "생성 완료" : uncertain ? "호출 결과 확인 필요" : "생성 실패"} · 전체 소요 {elapsedTime(job.created_at, job.finished_at)}{job.started_at && ` · 생성 처리 ${elapsedTime(job.started_at, job.finished_at)}`}</p></section>;
  const queued = job.status === "queued";
  return <section className="image-job-progress" aria-label="이미지 생성 진행">
    <strong role="status">{queued ? "이미지 생성 대기" : "이미지 생성 중"} · v{job.version}</strong>
    {progress}
    <div className="image-job-times" aria-live="off"><span>접수 후 {elapsedTime(job.created_at, now)}</span><span>{queued ? `대기 ${elapsedTime(job.created_at, now)}` : `생성 처리 ${elapsedTime(job.started_at, now)}`}</span></div>
    <p>{queued ? online ? "요청이 저장되었습니다. 앞선 작업이 끝나면 순서대로 시작합니다." : "실행 서비스 연결을 기다리고 있습니다. 연결이 복구되면 저장된 요청을 처리합니다. 다시 요청하지 않아도 됩니다." : "이미지 생성 요청을 처리하고 있습니다. 이미지 생성 API의 응답과 결과 저장이 끝나면 여기에 표시합니다."}</p>
    {!queued && !online && <p role="status">실행 서비스의 연결 확인이 늦어지고 있습니다. 결과가 확인되기 전에는 중복 요청하지 마세요.</p>}
    <p className="muted">{job.character.name} · {job.base_id ? baseVersion ? `v${baseVersion} 이미지 수정` : "기존 이미지 수정" : "새 기준 이미지 생성"} · {job.model}</p>
    <details><summary>이번 요청에 적용한 내용</summary><dl className="image-job-settings"><dt>외형·의상</dt><dd>{job.character.appearance}</dd><dt>이미지 제작 지침</dt><dd>{job.character.image_prompt}</dd>{job.change && <><dt>요청한 변경</dt><dd>{job.change}</dd></>}</dl></details>
    <p className="muted">다른 화면으로 이동해도 실행 서비스가 켜져 있으면 백그라운드에서 계속 처리합니다. 최근 작업에서 다시 확인할 수 있습니다. 생성 시간은 요청에 따라 달라지며 정확한 진행률은 제공되지 않습니다.</p>
  </section>;
}
