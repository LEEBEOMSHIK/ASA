"""Resolve approved, immutable video references within a request and workspace."""
import hashlib
import importlib
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from asa.video_analysis import run


def reference_valid(row: dict[str, Any], by_clip: dict[str, dict[str, Any]],
                    seen: frozenset[str] = frozenset()) -> bool:
    """Check a complete request snapshot without fetching video bytes during polling."""
    spec = row["generation_input"]
    if spec.get("connection_type") != "continue":
        return True
    clip_id = str(row["clip_id"])
    if clip_id in seen:
        return False
    parent = by_clip.get(spec.get("previous_clip_id", ""))
    return bool(parent and parent["status"] == "approved" and parent.get("video_sha256")
                and str(parent["id"]) == spec.get("source_job_id")
                and parent["video_sha256"] == spec.get("source_video_sha256")
                and reference_valid(parent, by_clip, seen | {clip_id}))


def approved_source(conn: Any, workspace: Any, request_id: Any, version: int,
                    clip_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT id,video,generation_input,request_id,answer_version FROM video_clip_jobs "
        "WHERE workspace_id=%s AND request_id=%s "
        "AND answer_version=%s AND clip_id=%s AND status='approved'",
        (workspace, request_id, version, clip_id),
    ).fetchone()
    if not row or not row["video"]:
        raise ValueError("video_previous_approval_required")
    if row.get("generation_input", {}).get("connection_type") == "continue":
        source_video(conn, workspace, row)
    return {"source_job_id": str(row["id"]),
            "source_video_sha256": hashlib.sha256(bytes(row["video"])).hexdigest()}


def source_video(conn: Any, workspace: Any, row: dict[str, Any], depth: int = 0) -> bytes:
    if depth >= 100:
        raise ValueError("video_previous_reference_changed")
    spec = row["generation_input"]
    parent = conn.execute(
        "SELECT id,video,generation_input,request_id,answer_version FROM video_clip_jobs "
        "WHERE workspace_id=%s AND request_id=%s "
        "AND answer_version=%s AND clip_id=%s AND status='approved'",
        (workspace, row["request_id"], row["answer_version"], spec["previous_clip_id"]),
    ).fetchone()
    if (not parent or not parent["video"]
            or str(parent["id"]) != spec.get("source_job_id")
            or hashlib.sha256(bytes(parent["video"])).hexdigest()
            != spec.get("source_video_sha256")):
        raise ValueError("video_previous_reference_changed")
    if parent.get("generation_input", {}).get("connection_type") == "continue":
        source_video(conn, workspace, parent, depth + 1)
    return bytes(parent["video"])


def last_frame(video: bytes, ffmpeg: str) -> bytes:
    """Decode all frames into one overwritten PNG: true final frame, bounded timeout."""
    if not video or len(video) > 64 * 1024 * 1024:
        raise ValueError("video_frame_extraction_failed")
    if ffmpeg == "ffmpeg":
        ffmpeg = str(importlib.import_module("imageio_ffmpeg").get_ffmpeg_exe())
    with TemporaryDirectory(prefix="asa-video-frame-") as folder:
        source, output = Path(folder) / "input.mp4", Path(folder) / "last.png"
        source.write_bytes(video)
        result = run([ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
                      "-protocol_whitelist", "file,pipe", "-i", str(source),
                      "-map", "0:v:0", "-an", "-sn", "-vf", "format=rgb24",
                      "-update", "1", "-y", str(output)], 90)
        if result.returncode or not output.exists() or output.stat().st_size > 20_000_000:
            raise ValueError("video_frame_extraction_failed")
        return output.read_bytes()
