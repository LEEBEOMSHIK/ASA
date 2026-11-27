type Window = { start_seconds: number; end_seconds: number };
type Placement = { start: number; end: number };

export type VideoTimingReference = {
  review_id: string;
  suggestion: number;
  clip_offset: number;
};

export type SpeechVideoSource = Window & Omit<VideoTimingReference, "clip_offset"> & {
  job_id: string;
  request_id: string;
  answer_version: number;
  clip_id: string;
  title?: string;
  timeline_start?: number | null;
  observed: string;
  delivery: string;
  basis: "mouth" | "event";
};

export function speechVideoPlacement(window: Window, clipOffset: number): Placement | null {
  const start = clipOffset + window.start_seconds;
  const end = clipOffset + window.end_seconds;
  if (!Number.isFinite(start) || !Number.isFinite(end) || clipOffset < 0 || start < clipOffset
      || end > 3600 || end - start < 0.001) return null;
  return { start: Number(start.toFixed(3)), end: Number(end.toFixed(3)) };
}

export function speechVideoFit(window: Window, clipOffset: number, cue: Placement,
  duration: number | null): "unmeasured" | "outside" | "fits" {
  const placement = speechVideoPlacement(window, clipOffset);
  if (duration == null || !Number.isFinite(duration) || duration <= 0 || !placement) return "unmeasured";
  const tolerance = 0.02;
  if (cue.start < placement.start - tolerance
      || cue.start + duration > Math.min(cue.end, placement.end) + tolerance) return "outside";
  return "fits";
}
