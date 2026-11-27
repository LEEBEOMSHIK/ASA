"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, message } from "../lib/registry";
import { ActionIcon, Button, DisclosureSummary, StatusBadge } from "./ui";
import "./editing.css";

export type EditPlan = {
  format: "asa_edit_plan_v1";
  title: string;
  summary: string;
  aspect_ratio: string;
  resolution: string;
  segments: {
    source_id: string; label?: string; start: number; duration: number;
    motion: string; transition: string; volume: number; caption: string;
  }[];
  tracks: {
    source_id: string; label?: string; start: number; offset: number; duration: number; volume: number;
  }[];
};

export function isEditPlan(value: unknown): value is EditPlan {
  return !!value && typeof value === "object" && "format" in value && value.format === "asa_edit_plan_v1"
    && "segments" in value && Array.isArray(value.segments);
}

type Job = {
  id: string;
  answer_version: number;
  status: "queued" | "running" | "review" | "approved" | "failed";
  error_code?: string;
  created_at: string;
  started_at?: string;
  finished_at?: string;
};

const states = {
  queued: "합성 대기",
  running: "합성 중",
  review: "합성 완료 · 검토 필요",
  approved: "완성 영상 확정됨",
  failed: "합성 실패",
} as const;

const errors: Record<string, string> = {
  editing_approval_required: "최신 편집 계획을 먼저 확정해 주세요.",
  editing_source_missing: "선택한 원본 자료를 찾을 수 없거나 확정 상태가 달라졌습니다. 자료 선택을 확인해 주세요.",
  editing_source_too_short: "원본보다 긴 구간이 있습니다. 시작 시간과 길이를 수정해 주세요.",
  editing_plan_invalid: "편집 계획의 시간·자료 종류·형식을 확인해 주세요.",
  editing_interrupted: "합성이 중단됐습니다. 이력에서 확인하고 다시 합성할 수 있습니다.",
  editing_caption_font_missing: "자막용 한글 글꼴이 서버에 없습니다. 관리자에게 확인해 주세요.",
  editing_caption_too_long: "자막을 줄이거나 장면을 나눠 주세요.",
  editing_source_limit: "선택 자료가 300MB를 초과합니다. 자료를 나눠 주세요.",
  editing_queue_full: "합성 대기 작업이 많습니다. 완료 후 다시 요청해 주세요.",
};

const motionLabels: Record<string, string> = { static: "고정", zoom_in: "완만한 확대", zoom_out: "완만한 축소" };
const hasVideo = (job: Job) => job.status === "review" || job.status === "approved";

function sceneTimeline(segments: EditPlan["segments"]) {
  let offset = 0;
  return segments.map((segment, index) => {
    const start = offset;
    offset += segment.duration;
    const image = segment.source_id.startsWith("image:");
    const label = segment.label?.replace(new RegExp("^" + (index + 1) + "\\s*[.·)]\\s*"), "")
      || (image ? "씬 이미지" : "영상 클립");
    return { segment, start, end: offset, label, image };
  });
}

type SceneTimeline = ReturnType<typeof sceneTimeline>;

function sceneTime(seconds: number) {
  const tenths = Math.round(seconds * 10);
  const minutes = Math.floor(tenths / 600);
  const remainder = tenths % 600;
  const wholeSeconds = String(Math.floor(remainder / 10)).padStart(2, "0");
  return minutes + ":" + wholeSeconds + (remainder % 10 ? "." + remainder % 10 : "");
}

function SceneNavigation({ scenes, active, disabled, onSeek }: {
  scenes: SceneTimeline; active: number; disabled: boolean; onSeek: (scene: SceneTimeline[number]) => void;
}) {
  return <nav className="editing-scene-navigation" aria-label="장면 이동">
    <div className="editing-result-heading">
      <h4>장면 이동</h4>
      <p className="helper-text">{active + 1} / {scenes.length} 장면</p>
    </div>
    <ol className="editing-scene-list">
      {scenes.map((scene, index) => <li key={index}>
        <Button className="editing-scene-jump" variant="secondary" disabled={disabled}
          aria-current={active === index ? "step" : undefined} onClick={() => onSeek(scene)}>
          <ActionIcon kind="play" />
          <span className="editing-scene-label">{index + 1}. {scene.label}</span>
          <span className="editing-scene-time">{sceneTime(scene.start)}</span>
        </Button>
      </li>)}
    </ol>
  </nav>;
}

function EditingTimeline({ plan, scenes }: { plan: EditPlan; scenes: SceneTimeline }) {
  return <div className="editing-plan-body">
    <h4>{plan.title}</h4>
    <p>{plan.summary}</p>
    <ol className="editing-timeline">
      {scenes.map(({ segment, start, label, image }, index) => {
        const id = segment.source_id.split(":")[1];
        const media = segment.source_id.startsWith("reference:")
          ? "/api/v1/library/references/" + id + "/media"
          : "/api/v1/video-clips/asset/" + id + "/video";
        return <li key={index}>
          <div className="editing-segment-heading">
            <strong>{index + 1}. {label}</strong>
            <span className="helper-text">{start.toFixed(1)}초부터 · {segment.duration}초</span>
          </div>
          <p className="helper-text">
            {!image && <>원본 {segment.start}초부터 · </>}
            {segment.transition === "fade" ? "검정 페이드" : "컷 전환"} · {motionLabels[segment.motion]}
            {!image && <> · 음량 {Math.round(segment.volume * 100)}%</>}
          </p>
          {segment.caption && <p>자막: {segment.caption}</p>}
          <details>
            <DisclosureSummary>원본 자료 확인</DisclosureSummary>
            {image ? <img className="editing-original" src={"/api/v1/characters/images/" + id + "/asset"} alt={label} loading="lazy" />
              : <video className="editing-original" controls preload="none" playsInline src={media} />}
          </details>
        </li>;
      })}
    </ol>
    {plan.tracks.length > 0 && <section>
      <h4>음성·음악 배치</h4>
      <ul>{plan.tracks.map((track, index) => <li key={index}>
        {track.label || "음원"} · {track.start}초부터 {track.duration}초 · 원본 {track.offset}초부터 · 음량 {Math.round(track.volume * 100)}%
      </li>)}</ul>
    </section>}
  </div>;
}

function VideoActions({ job, disabled, approve }: { job: Job; disabled: boolean; approve: (id: string) => void }) {
  return <div className="editing-actions">
    {job.status === "review" && <Button disabled={disabled} onClick={() => approve(job.id)}>
      <ActionIcon kind="confirm" />이 완성 영상 확정
    </Button>}
    <a className="button button--secondary" download={"edited-" + job.id + ".mp4"} href={"/api/v1/editing/jobs/" + job.id + "/media"}>
      <ActionIcon kind="download" />다운로드
    </a>
  </div>;
}

export function EditingResult({ plan, requestId, version, approved, disabled, canApprove, onApprove }: {
  plan: EditPlan;
  requestId: string;
  version: number;
  approved: boolean;
  disabled: boolean;
  canApprove: boolean;
  onApprove: () => void;
}) {
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [loadError, setLoadError] = useState("");
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(Date.now);
  const [activeScene, setActiveScene] = useState(0);
  const [mediaFailed, setMediaFailed] = useState(false);
  const operation = useRef<string | null>(null);
  const loadId = useRef(0);
  const statusRef = useRef<HTMLElement>(null);
  const playerRef = useRef<HTMLVideoElement>(null);
  const path = "/work-requests/" + requestId + "/editing";

  const refresh = useCallback(async () => {
    const seq = ++loadId.current;
    try {
      const response = await api<{ jobs: Job[] }>(path);
      if (seq !== loadId.current) return;
      setJobs(response.jobs);
      setLoadError("");
    } catch (error) {
      if (seq === loadId.current) setLoadError(message(error));
    }
  }, [path]);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => { setNow(Date.now()); void refresh(); }, 3000);
    return () => { clearInterval(timer); loadId.current++; };
  }, [refresh]);

  const matching = jobs?.filter(job => job.answer_version === version) ?? [];
  const current = matching.find(job => job.status !== "failed") ?? matching[0];
  const earlier = jobs?.filter(job => job.id !== current?.id) ?? [];
  const scenes = useMemo(() => sceneTimeline(plan.segments), [plan.segments]);
  const duration = scenes[scenes.length - 1]?.end ?? 0;
  const state = current ? states[current.status] : jobs ? "합성 영상 없음" : loadError ? "합성 상태 확인 실패" : "합성 상태 확인 중";
  const tone = current && hasVideo(current) ? "success" : current?.status === "failed" || (!jobs && loadError) ? "danger" : "neutral";

  async function compose() {
    setBusy(true);
    setActionError("");
    operation.current ??= crypto.randomUUID();
    try {
      const queued = await api<{ id: string }>(path + "/compose", "POST", { id: operation.current, version });
      operation.current = null;
      loadId.current++;
      setJobs(previous => previous?.some(job => job.id === queued.id) ? previous : [
        { id: queued.id, answer_version: version, status: "queued", created_at: new Date().toISOString() },
        ...(previous ?? []),
      ]);
      requestAnimationFrame(() => {
        statusRef.current?.focus({ preventScroll: true });
        statusRef.current?.scrollIntoView({ block: "nearest" });
      });
      await refresh();
    } catch (error) {
      setActionError(error instanceof Error ? errors[error.message] || message(error) : message(error));
    } finally {
      setBusy(false);
    }
  }

  async function approveVideo(job: string) {
    setBusy(true);
    setActionError("");
    try {
      await api("/editing/jobs/" + job + "/approve", "POST", {});
      await refresh();
    } catch (error) {
      setActionError(message(error));
    } finally {
      setBusy(false);
    }
  }

  function syncScene(time: number) {
    const index = scenes.findIndex(scene => time < scene.end);
    setActiveScene(index < 0 ? Math.max(0, scenes.length - 1) : index);
  }

  function seekToScene(scene: SceneTimeline[number]) {
    const player = playerRef.current;
    if (!player) return;
    // Seek just inside the clip so a cut does not display the previous last frame.
    const target = scene.start === 0 ? 0 : scene.start + Math.min(1 / 24, scene.segment.duration / 2);
    player.currentTime = Number.isFinite(player.duration) ? Math.min(player.duration, target) : target;
    syncScene(target);
  }

  const showCompose = !!jobs && (!current || current.status === "failed");
  return <section className="editing-result" aria-label="영상 합성 결과">
    <section className="editing-output" ref={statusRef} tabIndex={-1} aria-label="완성 영상 상태">
      <div className="editing-result-heading">
        <div>
          <h3>합성 영상</h3>
          <p className="helper-text">{plan.segments.length}장면 · {duration.toFixed(1)}초 · {plan.aspect_ratio} · {plan.resolution}</p>
        </div>
        <span role="status"><StatusBadge tone={tone}>{state}</StatusBadge></span>
      </div>
      {current && hasVideo(current) ? <div className="editing-preview" data-portrait={plan.aspect_ratio === "9:16"}>
        <video ref={playerRef} controls playsInline preload="metadata" aria-label={"합성 영상 계획 v" + version}
          onLoadedMetadata={event => { setMediaFailed(false); syncScene(event.currentTarget.currentTime); }}
          onTimeUpdate={event => syncScene(event.currentTarget.currentTime)}
          onError={() => setMediaFailed(true)}
          src={"/api/v1/editing/jobs/" + current.id + "/media"} />
        <div className="editing-preview-actions">
          <div className="editing-preview-controls">
            <VideoActions job={current} disabled={busy} approve={approveVideo} />
            {mediaFailed && <p className="field-error" role="alert">영상을 불러오지 못했습니다.</p>}
          </div>
          <SceneNavigation scenes={scenes} active={activeScene} disabled={mediaFailed} onSeek={seekToScene} />
        </div>
      </div> : <>
        {current?.status === "queued" && <p className="helper-text">요청을 접수했습니다. 차례가 되면 합성을 시작합니다.</p>}
        {current?.status === "running" && <p className="helper-text">합성 중입니다. 완료되면 이곳에 영상이 표시됩니다.</p>}
        {current && (current.status === "queued" || current.status === "running") && <p className="helper-text">
          접수 후 {Math.max(0, Math.floor((now - Date.parse(current.created_at)) / 1000))}초
        </p>}
        {current?.status === "failed" && <p className="field-error" role="alert">
          {errors[current.error_code ?? ""] || "영상을 합성하지 못했습니다. 편집 계획과 자료를 확인해 주세요."}
        </p>}
        {showCompose && <div className="editing-output-next">
          <p className="helper-text">{approved ? "계획 확정됨 · 합성을 실행하면 이곳에 영상이 표시됩니다."
            : canApprove ? "편집 계획을 확인하고 확정해 주세요." : "이 버전은 합성 가능한 확정 계획이 아닙니다."}</p>
          {approved ? <Button disabled={busy || disabled || !!loadError} onClick={() => void compose()}>
            <ActionIcon kind="play" />{busy ? "접수 중…" : current?.status === "failed" ? "다시 합성" : "영상 합성"}
          </Button> : canApprove && <Button disabled={disabled} onClick={onApprove}>
            <ActionIcon kind="confirm" />편집 계획 확정
          </Button>}
        </div>}
      </>}
      {loadError && <p className="field-error" role="alert">합성 상태를 불러오지 못했습니다. {loadError}</p>}
      {actionError && <p className="field-error" role="alert">{actionError}</p>}
    </section>
    <details className="editing-detail">
      <DisclosureSummary>편집 계획 · {plan.segments.length}장면</DisclosureSummary>
      <div className="editing-detail-body"><EditingTimeline plan={plan} scenes={scenes} /></div>
    </details>
    {earlier.length > 0 && <details className="editing-detail">
      <DisclosureSummary>다른 합성 이력 · {earlier.length}건</DisclosureSummary>
      <div className="editing-detail-body editing-plan-body">
        {earlier.map(job => <div className="editing-job" key={job.id}>
          <div className="editing-result-heading">
            <strong>편집 계획 v{job.answer_version}</strong>
            <StatusBadge tone={hasVideo(job) ? "success" : job.status === "failed" ? "danger" : "neutral"}>{states[job.status]}</StatusBadge>
          </div>
          {job.error_code && <p className="helper-text">{errors[job.error_code] || "영상을 합성하지 못했습니다."}</p>}
          {hasVideo(job) && <details>
            <DisclosureSummary>영상 보기</DisclosureSummary>
            <video controls playsInline preload="none" aria-label={"이전 합성 영상 계획 v" + job.answer_version}
              src={"/api/v1/editing/jobs/" + job.id + "/media"} />
            <VideoActions job={job} disabled={busy} approve={approveVideo} />
          </details>}
        </div>)}
      </div>
    </details>}
  </section>;
}
