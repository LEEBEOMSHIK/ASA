"""Local-only rendering of explicitly selected, validated media; never invokes AI."""

import io
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw, ImageFont

from asa.audio_media import MAX_OUTPUT, command
from asa.editing_contracts import EditPlan
from asa.video_analysis import run


def probe(path: Path, ffmpeg: str) -> tuple[float, bool]:
    result = run(
        command(ffmpeg)
        + ["-protocol_whitelist", "file,pipe", "-loglevel", "info", "-i", str(path)],
        30,
    )
    match = re.search(rb"Duration: (\d+):(\d+):([\d.]+)", result.stderr)
    if not match:
        raise ValueError("editing_media_invalid")
    h, m, s = (float(v) for v in match.groups())
    return h * 3600 + m * 60 + s, b"Audio:" in result.stderr


def caption_image(text: str, width: int, height: int, path: Path) -> None:
    fonts = [
        Path("C:/Windows/Fonts/malgun.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ]
    font_path = next((p for p in fonts if p.is_file()), None)
    if font_path is None:
        raise ValueError("editing_caption_font_missing")
    font = ImageFont.truetype(str(font_path), max(24, width // 25))
    image = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(image)
    lines, line = [], ""
    for char in text:
        if char == "\n" or draw.textlength(line + char, font=font) > width * 0.86:
            lines.append(line)
            line = "" if char == "\n" else char
        else:
            line += char
    lines.append(line)
    spacing = max(32, width // 20)
    y = height - max(height // 12, 32) - len(lines) * spacing
    if y < height * 0.35:
        raise ValueError("editing_caption_too_long")
    for line in lines:
        x = (width - draw.textlength(line, font=font)) / 2
        draw.text((x, y), line, font=font, fill="white", stroke_width=2, stroke_fill="black")
        y += spacing
    image.save(path)


def centered_zoom(motion: str, duration: float) -> str:
    # Interpolate a fractional crop around the center rather than rounding the
    # crop to whole pixels on every frame.
    last_frame = max(1, round(duration * 24) - 1)
    travel = f"0.06*min(in/{last_frame},1)"
    zoom = f"1+{travel}" if motion == "zoom_in" else f"1.06-{travel}"
    left = f"W*(1-1/({zoom}))/2"
    top = f"H*(1-1/({zoom}))/2"
    return (
        "perspective=sense=source:eval=frame:interpolation=cubic"
        f":x0='{left}':y0='{top}':x1='W-({left})':y1='{top}'"
        f":x2='{left}':y2='H-({top})':x3='W-({left})':y3='H-({top})'"
    )


def render(plan: EditPlan, assets: dict[str, bytes], ffmpeg: str) -> bytes:
    side = 720 if plan.resolution == "720p" else 1080
    width, height = {
        "9:16": (side, side * 16 // 9),
        "16:9": (side * 16 // 9, side),
        "1:1": (side, side),
    }[plan.aspect_ratio]
    width, height = width // 2 * 2, height // 2 * 2
    with TemporaryDirectory(prefix="asa-edit-") as folder:
        root = Path(folder)
        outputs = []
        for i, seg in enumerate(plan.segments):
            data = assets[seg.source_id]
            src = root / f"source{i}"
            still = seg.source_id.startswith("image:")
            if still:
                with Image.open(io.BytesIO(data)) as image:
                    image.convert("RGB").save(src, format="PNG")
                args = ["-framerate", "24", "-i", str(src)]
                sound = False
            else:
                if data[4:8] != b"ftyp" and data[:4] != b"\x1aE\xdf\xa3":
                    raise ValueError("editing_media_invalid")
                src.write_bytes(data)
                length, sound = probe(src, ffmpeg)
                if seg.start + seg.duration > length + 0.06:
                    raise ValueError("editing_source_too_short")
                args = ["-protocol_whitelist", "file,pipe", "-ss", str(seg.start), "-i", str(src)]
            vf = (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1"
            )
            if still:
                if seg.motion != "static":
                    vf += ",format=yuv444p"
                vf += ",loop=loop=-1:size=1:start=0,setpts=N/(24*TB)"
                if seg.motion != "static":
                    vf += "," + centered_zoom(seg.motion, seg.duration)
            else:
                vf += ",fps=24"
            if seg.transition == "fade":
                fade = min(0.25, seg.duration / 4)
                vf += f",fade=t=in:d={fade},fade=t=out:st={seg.duration - fade}:d={fade}"
            if not sound:
                args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
            audio_index = 0 if sound else 1
            filters = f"[0:v]{vf}[base]"
            out_video = "[base]"
            if seg.caption:
                png = root / f"caption{i}.png"
                caption_image(seg.caption, width, height, png)
                args += ["-loop", "1", "-i", str(png)]
                overlay_index = 1 if sound else 2
                filters += f";[base][{overlay_index}:v]overlay=0:0[v]"
                out_video = "[v]"
            # AAC priming and padding from each clip would overlap at cuts.
            # Keep the intermediate audio as 48 kHz, stereo, 16-bit PCM.
            out = root / f"part{i}.mov"
            part_limit = MAX_OUTPUT + round(seg.duration * 48_000) * 4
            result = run(
                command(ffmpeg)
                + args
                + [
                    "-filter_complex",
                    filters,
                    "-map",
                    out_video,
                    "-map",
                    f"{audio_index}:a:0",
                    "-af",
                    f"volume={seg.volume},apad",
                    "-t",
                    str(seg.duration),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "fast",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "pcm_s16le",
                    "-ar",
                    "48000",
                    "-ac",
                    "2",
                    "-fs",
                    str(part_limit),
                    str(out),
                ],
                600,
            )
            if result.returncode or not out.exists() or out.stat().st_size >= part_limit:
                raise ValueError("editing_render_failed")
            outputs.append(out)
        listing = root / "list.txt"
        listing.write_text(
            "".join(f"file '{part.name}'\nduration {seg.duration:.6f}\n"
                    for part, seg in zip(outputs, plan.segments, strict=True)),
            encoding="utf-8",
        )
        args = ["-f", "concat", "-safe", "1", "-i", str(listing)]
        mix_filters = [
            "[0:a]aresample=async=1:min_hard_comp=0.001:first_pts=0,"
            f"apad,atrim=duration={plan.duration},asetpts=N/SR/TB[original]"
        ]
        labels = ["[original]"]
        for i, track in enumerate(plan.tracks, 1):
            path = root / f"track{i}.wav"
            raw = assets[track.source_id]
            if not raw.startswith(b"RIFF"):
                raise ValueError("editing_media_invalid")
            path.write_bytes(raw)
            length, sound = probe(path, ffmpeg)
            if not sound or track.offset + track.duration > length + 0.06:
                raise ValueError("editing_source_too_short")
            args += ["-ss", str(track.offset), "-i", str(path)]
            mix_filters.append(
                f"[{i}:a]atrim=duration={track.duration},asetpts=PTS-STARTPTS,"
                f"volume={track.volume},adelay={round(track.start * 1000)}:all=1[a{i}]"
            )
            labels.append(f"[a{i}]")
        audio_output = "[original]"
        if plan.tracks:
            audio_output = "[mixed]"
            mix_filters.append(
                "".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=first,"
                f"alimiter=limit=0.95:level=0:latency=1{audio_output}"
            )
        final = root / "final.mp4"
        result = run(
            command(ffmpeg)
            + args
            + [
                "-filter_complex",
                ";".join(mix_filters),
                "-map",
                "0:v",
                "-map",
                audio_output,
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-t",
                str(plan.duration),
                "-movflags",
                "+faststart",
                "-fs",
                str(MAX_OUTPUT),
                str(final),
            ],
            120,
        )
        if result.returncode or not final.exists() or final.stat().st_size >= MAX_OUTPUT:
            raise ValueError("editing_render_failed")
        return final.read_bytes()
