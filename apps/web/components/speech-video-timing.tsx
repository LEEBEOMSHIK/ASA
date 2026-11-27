"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "../lib/registry";
import {
  speechVideoFit, speechVideoPlacement, type SpeechVideoSource, type VideoTimingReference,
} from "../lib/speech-video-timing";
import { ActionIcon, Button, DisclosureSummary, Field, StatusBadge } from "./ui";
import styles from "./audio-production.module.css";

type Take = { src: string; duration: number | null };
type Cue = { id: string; start: number; end: number; video_timing?: VideoTimingReference | null };
type Adjustment = Pick<Cue, "start" | "end" | "video_timing"> & { emotion?: string };
const sourceKey = (source: Pick<SpeechVideoSource, "review_id" | "suggestion">) =>
  `${source.review_id}:${source.suggestion}`;
const seconds = (value: number) => value.toFixed(2).replace(/\.?0+$/, "");

export function SpeechVideoTiming({ path, fieldId, cue, take, busy, supportsDirection, onApply, onRemove }: {
  path: string;
  fieldId: string;
  cue: Cue;
  take?: Take;
  busy: boolean;
  supportsDirection: boolean;
  onApply: (adjustment: Adjustment) => void;
  onRemove: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [sources, setSources] = useState<SpeechVideoSource[] | null>(null);
  const [selection, setSelection] = useState<string | null>(null);
  const [offsetInput, setOffsetInput] = useState<string | null>(null);
  const [error, setError] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const url = `${path}/video-timing-sources?cue_id=${encodeURIComponent(cue.id)}`;
  const reference = cue.video_timing;
  const appliedKey = reference ? sourceKey(reference) : "";
  const selectedKey = selection ?? appliedKey;
  const source = sources?.find(item => sourceKey(item) === selectedKey);
  const observingApplied = Boolean(reference && selectedKey === appliedKey);
  const offsetValue = offsetInput ?? String(observingApplied ? reference?.clip_offset ?? 0 : source?.timeline_start ?? 0);
  const offset = offsetValue.trim() === "" ? NaN : Number(offsetValue);
  const placement = source ? speechVideoPlacement(source, offset) : null;
  const fit = source && reference && observingApplied && take
    ? speechVideoFit(source, reference.clip_offset, cue, take.duration) : "unmeasured";

  useEffect(() => {
    if (!open) return;
    let alive = true;
    setSources(null);
    setError(false);
    void api<SpeechVideoSource[]>(url).then(result => {
      if (alive) setSources(result);
    }).catch(() => {
      if (alive) setError(true);
    });
    return () => { alive = false; };
  }, [open, url, loadAttempt]);

  return <details className={styles.history} onToggle={event => setOpen(event.currentTarget.open)}>
    <DisclosureSummary>{reference ? "영상 타이밍 참고 · 연결됨" : "영상 타이밍 참고"}</DisclosureSummary>
    {open && <div className={styles.videoTiming}>
      {error ? <div className={styles.videoTimingBody}>
        <p role="alert" className="field-error">영상 검수 근거를 불러오지 못했습니다.</p>
        <div className="audio-actions"><Button variant="secondary" onClick={() => setLoadAttempt(attempt => attempt + 1)}>
          <ActionIcon kind="refresh"/>다시 불러오기
        </Button></div>
      </div> : !sources ? <p role="status">영상 검수 근거를 불러오는 중…</p> : sources.length === 0
        ? <p className="muted">이 원문과 일치하는 영상 검수 근거가 없습니다. 클립 결과의 ‘AI 영상 검수’에서 발화 근거를 확인하세요.</p>
        : <Field id={fieldId+"source"} label="참고할 영상 검수">
          {props => <select {...props} value={source ? selectedKey : ""} disabled={busy} onChange={event => {
            setSelection(event.target.value);
            setOffsetInput(null);
          }}>
            <option value="">영상 검수 선택</option>
            {sources.map(item => <option key={sourceKey(item)} value={sourceKey(item)}>
              {`${item.clip_id} · 답변 v${item.answer_version} · 약 ${seconds(item.start_seconds)}초${sourceKey(item) === appliedKey ? " · 연결됨" : ""}${item.title ? " · "+item.title : ""}`}
            </option>)}
          </select>}
        </Field>}
      {reference && sources && !sources.some(item => sourceKey(item) === appliedKey) &&
        <p role="status" className="muted">이전에 연결한 영상 검수 근거를 현재 확인할 수 없습니다.</p>}
      {source && <div className={styles.videoTimingGrid}>
        <SpeechVideoPreview key={`${selectedKey}:${observingApplied ? take?.src ?? "" : ""}`}
          source={source} take={observingApplied ? take : undefined}
          localStart={reference ? cue.start - reference.clip_offset : source.start_seconds}/>
        <div className={styles.videoTimingBody}>
          <div className="audio-actions">
            <StatusBadge>{source.basis === "mouth" ? "입 모양 표본" : "장면 변화 표본"}</StatusBadge>
            <strong>영상 내 약 {seconds(source.start_seconds)}–{seconds(source.end_seconds)}초</strong>
          </div>
          {source.title && <p className="muted">{source.title}</p>}
          <p>{source.observed}</p>
          <p><strong>권장 연출</strong> {source.delivery}</p>
          <p className="muted">정지 프레임에 근거한 제안이에요. 발화 시작과 입 모양은 영상을 보고 확인하세요.</p>
          {fit !== "unmeasured" && <p role="status">
            <StatusBadge tone={fit === "fits" ? "success" : "warning"}>
              {fit === "fits" ? "실측 길이가 표본 구간 안에 들어옴" : "실측 길이 또는 시작 시점 조정 필요"}
            </StatusBadge>
          </p>}
          <Field id={fieldId+"offset"} label="전체 영상에서 이 클립의 시작 (초)"
            hint={placement ? `적용될 발화 시간 ${seconds(placement.start)}–${seconds(placement.end)}초` : undefined}
            error={placement ? undefined : "전체 영상 기준으로 올바른 클립 시작 시간을 입력해 주세요."}>
            {props => <input {...props} type="number" min={0} max={3600} step="any" value={offsetValue}
              disabled={busy} onChange={event => setOffsetInput(event.target.value)}/>}
          </Field>
          <div className="audio-actions"><Button variant="secondary" disabled={busy || !placement} onClick={() => {
            if (!placement) return;
            onApply({ ...placement, video_timing: {
              review_id: source.review_id, suggestion: source.suggestion, clip_offset: offset,
            }, ...(supportsDirection ? { emotion: source.delivery } : {}) });
            setSelection(null);
            setOffsetInput(null);
          }}><ActionIcon kind="confirm"/>{supportsDirection ? "시간·연출 적용" : "시간 적용"}</Button></div>
          <p className="muted">{supportsDirection
            ? "적용한 시간과 연출을 확인한 뒤 설정을 저장하세요."
            : "선택한 음성 모델에는 자유 입력 연출이 전달되지 않아 시간만 적용합니다."}</p>
        </div>
      </div>}
      {reference && <div className="audio-actions"><Button variant="secondary" disabled={busy} onClick={() => {
        onRemove();
        setSelection(null);
        setOffsetInput(null);
      }}><ActionIcon kind="close"/>영상 참고 연결 해제</Button></div>}
    </div>}
  </details>;
}

function SpeechVideoPreview({ source, take, localStart }: {
  source: SpeechVideoSource;
  take?: Take;
  localStart: number;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const audio = useRef<HTMLAudioElement>(null);
  const [videoDuration, setVideoDuration] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [comparing, setComparing] = useState(false);
  const limit = useRef(0);
  const comparison = useRef<{ voiceStarted: boolean } | null>(null);
  const canCompare = videoDuration != null && localStart >= 0 && localStart < videoDuration;

  function stop() {
    if (!comparison.current) return;
    comparison.current = null;
    video.current?.pause();
    audio.current?.pause();
    if (video.current) video.current.muted = false;
    setComparing(false);
  }

  function jumpToObservation() {
    const player = video.current;
    if (!player) return;
    stop();
    player.currentTime = source.start_seconds;
  }

  async function playTogether() {
    const player = video.current, voice = audio.current;
    if (!player || !voice || !canCompare || comparison.current) return;
    const playback = { voiceStarted: false };
    comparison.current = playback;
    setError("");
    limit.current = Math.min(player.duration, localStart + (take?.duration ?? player.duration));
    setComparing(true);
    try {
      player.muted = true;
      player.currentTime = localStart;
      voice.currentTime = 0;
      await player.play();
      if (comparison.current !== playback) return;
      if (player.seeking || Math.abs(player.currentTime - localStart) > 0.12) {
        throw new Error("Video did not reach the selected playback point");
      }
      await voice.play();
      if (comparison.current === playback) playback.voiceStarted = true;
    } catch {
      if (comparison.current !== playback) return;
      stop();
      setError("함께 재생하지 못했습니다. 다시 시도해 주세요.");
    }
  }

  function followVideoClock() {
    const player = video.current, voice = audio.current;
    if (!comparison.current?.voiceStarted || !player || !voice) return;
    if (player.currentTime >= limit.current) {
      stop();
      return;
    }
    if (!player.seeking && voice.readyState >= HTMLMediaElement.HAVE_METADATA) {
      const position = Math.max(0, player.currentTime - localStart);
      if (position < voice.duration && Math.abs(voice.currentTime - position) > 0.12) {
        voice.currentTime = position;
      }
    }
  }

  useEffect(() => {
    const player = video.current, voice = audio.current;
    return () => {
      comparison.current = null;
      player?.pause();
      voice?.pause();
      if (player) player.muted = false;
    };
  }, [take?.src]);

  return <div className={styles.videoTimingBody}>
    <video className={styles.videoTimingPlayer} ref={video} controls playsInline preload="metadata"
      aria-label={`${source.clip_id} 참고 영상`} src={`/api/v1/video-clips/asset/${source.job_id}/video`}
      onLoadedMetadata={event => setVideoDuration(event.currentTarget.duration)}
      onError={() => { stop(); setVideoDuration(null); setError("참고 영상을 재생할 수 없습니다."); }}
      onPause={stop} onSeeking={() => { if (comparison.current && Math.abs((video.current?.currentTime ?? 0) - localStart) > 0.25) stop(); }}
      onPlaying={followVideoClock} onTimeUpdate={followVideoClock}
      onEnded={stop}/>
    <div className="audio-actions">
      <Button variant="secondary" disabled={videoDuration == null} onClick={jumpToObservation}>
        <ActionIcon kind="camera"/>관측 시점으로 이동
      </Button>
      {take && <Button variant="secondary" disabled={!canCompare}
        onClick={comparing ? stop : () => void playTogether()}>
        <ActionIcon kind={comparing ? "stop" : "play"}/>{comparing ? "재생 중지" : "제작 음성과 함께 재생"}
      </Button>}
    </div>
    {take && <audio ref={audio} src={take.src} preload="auto" onEnded={stop}
      onError={() => { stop(); setError("제작 음성을 재생할 수 없습니다."); }}/>}
    {take && <p className="muted">함께 재생할 때는 참고 영상의 원래 소리를 잠시 끕니다.</p>}
    {error && <p role="alert" className="field-error">{error}</p>}
  </div>;
}
