"""Bounded local media decoding and deterministic separate-track composition."""

import importlib
import io
import re
import wave
from pathlib import Path
from tempfile import TemporaryDirectory

from asa.audio_contracts import Music
from asa.video_analysis import run

MAX_AUDIO = 32 * 1024 * 1024
MAX_OUTPUT = 256 * 1024 * 1024


def executable(configured: str) -> str:
    return (
        str(importlib.import_module("imageio_ffmpeg").get_ffmpeg_exe())
        if configured == "ffmpeg"
        else configured
    )


def command(ffmpeg: str) -> list[str]:
    return [executable(ffmpeg), "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]


def pcm_wav(pcm: bytes) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(24000)
        out.writeframes(pcm)
    return buffer.getvalue()


def wav_duration(data: bytes) -> float:
    with wave.open(io.BytesIO(data), "rb") as source:
        return source.getnframes() / source.getframerate()


def normalize_audio(data: bytes, ffmpeg: str) -> tuple[bytes, float]:
    if not data or len(data) > 16 * 1024 * 1024:
        raise ValueError("audio_file_limit")
    # Reject playlist/script demuxers before FFmpeg can follow local file references.
    recognized = (
        data.startswith((b"RIFF", b"ID3", b"OggS", b"fLaC"))
        or data[4:8] == b"ftyp"
        or (len(data) > 2 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0)
    )
    if not recognized:
        raise ValueError("audio_decode_failed")
    with TemporaryDirectory(prefix="asa-audio-") as folder:
        src, out = Path(folder) / "input", Path(folder) / "output.wav"
        src.write_bytes(data)
        result = run(
            command(ffmpeg)
            + [
                "-protocol_whitelist",
                "file,pipe",
                "-i",
                str(src),
                "-map",
                "0:a:0",
                "-vn",
                "-ac",
                "1",
                "-ar",
                "24000",
                "-c:a",
                "pcm_s16le",
                "-t",
                "601",
                "-fs",
                str(MAX_AUDIO),
                str(out),
            ],
            90,
        )
        if result.returncode or not out.exists():
            raise ValueError("audio_decode_failed")
        value = out.read_bytes()
        seconds = wav_duration(value)
        if not 0 < seconds <= 600 or len(value) >= MAX_AUDIO:
            raise ValueError("audio_file_limit")
        return value, seconds


def compose(
    videos: list[tuple[bytes, float]],
    speech: list[tuple[bytes, float]],
    music: bytes | None,
    options: Music,
    ffmpeg: str,
) -> bytes:
    duration = sum(seconds for _, seconds in videos)
    if not videos or not 0 < duration <= 3600:
        raise ValueError("audio_timeline_invalid")
    with TemporaryDirectory(prefix="asa-composition-") as folder:
        root = Path(folder)
        args = command(ffmpeg)
        filters = []
        for index, (video, seconds) in enumerate(videos):
            path = root / f"v{index}.mp4"
            path.write_bytes(video)
            probe = run(
                command(ffmpeg)
                + [
                    "-protocol_whitelist",
                    "file,pipe",
                    "-i",
                    str(path),
                    "-map",
                    "0:v:0",
                    "-an",
                    "-progress",
                    "pipe:1",
                    "-f",
                    "null",
                    "-",
                ],
                90,
            )
            decoded = re.findall(rb"out_time_us=(\d+)", probe.stdout)
            if probe.returncode or not decoded or int(decoded[-1]) / 1_000_000 + 0.04 < seconds:
                raise ValueError("audio_video_too_short")
            args += ["-protocol_whitelist", "file,pipe", "-i", str(path)]
            filters.append(
                f"[{index}:v]trim=duration={seconds},setpts=PTS-STARTPTS,"
                f"fps=24,setsar=1,format=yuv420p[v{index}]"
            )
        filters.append(
            "".join(f"[v{i}]" for i in range(len(videos))) + f"concat=n={len(videos)}:v=1:a=0[v]"
        )
        tracks = []
        windows = []
        for n, (audio, start) in enumerate(speech):
            seconds = wav_duration(audio)
            if start + seconds > duration + 0.02:
                raise ValueError("audio_timing_adjustment_required")
            index = len(videos) + n
            path = root / f"a{n}.wav"
            path.write_bytes(audio)
            args += ["-i", str(path)]
            filters.append(f"[{index}:a]adelay={round(start * 1000)}:all=1[a{n}]")
            tracks.append(f"[a{n}]")
            windows.append(f"between(t,{start},{start + seconds})")
        if music is not None:
            path = root / "music.wav"
            music_length = wav_duration(music)
            if options.offset >= music_length or options.start >= duration:
                raise ValueError("audio_music_timing")
            segment = min(options.end or duration, duration) - options.start
            if not options.loop:
                segment = min(segment, music_length - options.offset)
            index = len(videos) + len(speech)
            # Crop once so every loop starts at the chosen source offset.
            with wave.open(io.BytesIO(music), "rb") as source:
                source.setpos(round(options.offset * source.getframerate()))
                with wave.open(str(path), "wb") as target:
                    target.setparams(source.getparams())
                    target.writeframes(source.readframes(source.getnframes()))
            if options.loop:
                args += ["-stream_loop", "-1"]
            args += ["-i", str(path)]
            fade = min(options.fade, segment / 2)
            duck = "+".join(windows) if windows else "0"
            volume = (
                f"{options.volume}*if(gt({duck},0),0.3,1)" if options.duck else str(options.volume)
            )
            filters.append(
                f"[{index}:a]atrim=duration={segment},asetpts=PTS-STARTPTS,"
                f"afade=t=in:d={fade},afade=t=out:st={segment - fade}:d={fade},"
                f"adelay={round(options.start * 1000)}:all=1,volume='{volume}':eval=frame[m]"
            )
            tracks.append("[m]")
        if tracks:
            filters.append(
                "".join(tracks) + f"amix=inputs={len(tracks)}:normalize=0,"
                f"alimiter=limit=0.95:level=0,apad,atrim=duration={duration}[a]"
            )
        else:
            filters.append(f"anullsrc=r=24000:cl=mono,atrim=duration={duration}[a]")
        out = root / "final.mp4"
        result = run(
            args
            + [
                "-filter_complex",
                ";".join(filters),
                "-map",
                "[v]",
                "-map",
                "[a]",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "20",
                "-c:a",
                "aac",
                "-t",
                str(duration),
                "-movflags",
                "+faststart",
                "-fs",
                str(MAX_OUTPUT),
                str(out),
            ],
            600,
        )
        if result.returncode or not out.exists() or out.stat().st_size >= MAX_OUTPUT:
            raise ValueError("audio_composition_failed")
        return out.read_bytes()
