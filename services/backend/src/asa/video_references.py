"""Server-owned, hash-pinned WAN reference media. Never accepts caller URLs."""
import base64
import hashlib
import importlib
import json
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import UUID

from PIL import Image

from asa.config import Settings
from asa.registry.schemas import RegistryError
from asa.video_analysis import run
from asa.video_contracts import VideoReferenceInputs


def validate_requested(clip_id: str, requested: dict[str, Any] | None,
                       configured: Any) -> None:
    expected = None
    if isinstance(configured, dict) and clip_id in configured.get('clip_ids', []):
        expected = VideoReferenceInputs.model_validate({
            'character_image_ids': configured.get('character_image_ids', []),
            'audio': configured.get('audio', []),
            'video': configured.get('video', []),
        }).model_dump(mode='json')
    if expected != requested:
        raise RegistryError(422, 'video_reference_configuration_mismatch')


def allowed_character_images(selection: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for scene in selection.get('scenes', []):
        try:
            characters = json.loads(scene.get('character_settings', '[]'))
            result.update(str(UUID(c['image_id'])) for c in characters)
        except (ValueError, TypeError, KeyError) as exc:
            raise RegistryError(422, 'video_reference_character_invalid') from exc
    return result


def validate_audio_segment(ref: dict[str, Any], answer: dict[str, Any],
                           clip: dict[str, Any]) -> None:
    start, end = ref['start_seconds'], ref['end_seconds']
    if not 0 <= start < end <= clip['source_end_seconds'] - clip['source_start_seconds']:
        raise RegistryError(422, 'video_reference_audio_segment_invalid')
    if not 1 <= end - start <= 15:
        raise RegistryError(422, 'video_reference_audio_segment_invalid')
    audio = answer.get('audio_plan') or {}
    if not any(s['id'] == ref['speaker_id'] and s['role'] == 'narrator'
               for s in audio.get('speakers', [])):
        raise RegistryError(422, 'video_reference_narrator_required')
    global_start, global_end = (start + clip['source_start_seconds'],
                                end + clip['source_start_seconds'])
    cues = audio.get('cues', [])
    if not any(c['speaker_id'] == ref['speaker_id'] and
               c['start'] <= global_start and c['end'] >= global_end for c in cues):
        raise RegistryError(422, 'video_reference_audio_segment_invalid')
    if any(c['speaker_id'] != ref['speaker_id'] and c['start'] < global_end
           and c['end'] > global_start for c in cues):
        raise RegistryError(422, 'video_reference_audio_overlap')
    if any(e['kind'] == 'sound_effect' and e['start'] < end and e['end'] > start
           for e in (clip.get('quality') or {}).get('events', [])):
        raise RegistryError(422, 'video_reference_audio_overlap')


def extract_audio(video: bytes, start: float, end: float, ffmpeg: str) -> bytes:
    """Extract only the bounded narrator interval; never send the complete source track."""
    if not video or len(video) > 64 * 1024 * 1024 or not 1 <= end - start <= 15:
        raise RegistryError(422, 'video_reference_audio_segment_invalid')
    if ffmpeg == 'ffmpeg':
        ffmpeg = str(importlib.import_module('imageio_ffmpeg').get_ffmpeg_exe())
    with TemporaryDirectory(prefix='asa-reference-audio-') as folder:
        source, output = Path(folder) / 'source.mp4', Path(folder) / 'reference.wav'
        source.write_bytes(video)
        result = run([ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error',
                      '-protocol_whitelist', 'file,pipe', '-i', str(source),
                      '-ss', str(start), '-t', str(end - start), '-map', '0:a:0',
                      '-vn', '-sn', '-map_metadata', '-1', '-ac', '1', '-ar', '24000',
                      '-c:a', 'pcm_s16le', '-y', str(output)], 90)
        if result.returncode or not output.exists() or output.stat().st_size > 15_000_000:
            raise RegistryError(409, 'video_reference_audio_extraction_failed')
        return output.read_bytes()


def audio_source(conn: Any, workspace: Any, request: Any,
                 ref: dict[str, Any]) -> dict[str, Any]:
    row = conn.execute(
        "SELECT j.video,j.answer_version,j.clip_id,v.answer FROM video_clip_jobs j "
        "JOIN script_versions v ON v.workspace_id=j.workspace_id "
        "AND v.request_id=j.request_id AND v.version=j.answer_version "
        "WHERE j.workspace_id=%s AND j.request_id=%s AND j.id=%s "
        "AND j.status IN ('review','approved') AND j.video IS NOT NULL",
        (workspace, request, ref['job_id'])).fetchone()
    if not row:
        raise RegistryError(404, 'video_reference_audio_missing')
    clip = next((c for c in row['answer'].get('clips', []) if c['clip_id'] == row['clip_id']), None)
    if clip is None:
        raise RegistryError(409, 'video_reference_audio_source_changed')
    validate_audio_segment(ref, row['answer'], clip)
    return dict(row)


def resolve_audio(conn: Any, workspace: Any, request_id: Any,
                  reference: dict[str, Any], ffmpeg_path: str) -> bytes:
    row = audio_source(conn, workspace, request_id, reference)
    video = bytes(row['video'])
    if (hashlib.sha256(video).hexdigest() != reference['source_sha256'] or
            row['answer_version'] != reference['source_answer_version']):
        raise RegistryError(409, 'video_reference_audio_source_changed')
    audio = extract_audio(video, reference['start_seconds'], reference['end_seconds'], ffmpeg_path)
    if hashlib.sha256(audio).hexdigest() != reference['audio_sha256']:
        raise RegistryError(409, 'video_reference_audio_source_changed')
    return audio


def image_bytes(conn: Any, workspace: Any, image_id: str) -> bytes:
    row = conn.execute("SELECT j.image FROM character_image_jobs j JOIN character_projects p "
                       "ON p.workspace_id=j.workspace_id AND p.id=j.project_id "
                       "WHERE j.workspace_id=%s AND j.id=%s AND j.status='succeeded' "
                       "AND j.image IS NOT NULL AND p.approved->>j.character_id=j.id::text "
                       "AND NOT EXISTS (SELECT 1 FROM work_item_preferences w WHERE "
                       "w.workspace_id=p.workspace_id AND w.request_id=p.request_id "
                       "AND w.source_version=p.source_version AND w.item_id=j.character_id "
                       "AND w.kind IN ('character_images','scene_images') AND w.excluded)",
                       (workspace, image_id)).fetchone()
    if not row:
        raise RegistryError(404, 'video_reference_image_missing')
    data = bytes(row['image'])
    if len(data) > 20_000_000:
        raise RegistryError(422, 'video_reference_image_invalid')
    with Image.open(BytesIO(data)) as image:
        if (image.format != 'PNG' or not all(240 <= d <= 8000 for d in image.size)
                or max(image.size) / min(image.size) > 8
                or image.convert('RGBA').getchannel('A').getextrema() != (255, 255)):
            raise RegistryError(422, 'video_reference_image_invalid')
    return data


def freeze(conn: Any, settings: Settings, workspace: Any, request: Any,
           spec: dict[str, Any], selection: dict[str, Any], provider: str = 'alibaba') -> None:
    requested = spec.get('reference_inputs')
    if requested is None and provider != 'higgsfield':
        return
    refs = VideoReferenceInputs.model_validate(requested or {})
    allowed = allowed_character_images(selection)
    if any(str(i) not in allowed for i in refs.character_image_ids):
        raise RegistryError(422, 'video_reference_character_not_allowed')
    images = [{'image_id': spec['start_image_id'], 'role': 'scene'}] + [
        {'image_id': str(i), 'role': 'character'} for i in refs.character_image_ids]
    for image in images:
        data = image_bytes(conn, workspace, image['image_id'])
        image['sha256'] = hashlib.sha256(data).hexdigest()
    spec['reference_images'] = images
    if refs.audio:
        from asa.video_reference_delivery import require_audio_delivery

        if provider != 'higgsfield':
            require_audio_delivery(settings)
        ref = refs.audio[0].model_dump(mode='json')
        row = audio_source(conn, workspace, request, ref)
        video = bytes(row['video'])
        audio = extract_audio(video, ref['start_seconds'], ref['end_seconds'], settings.ffmpeg_path)
        spec['reference_audio'] = {
            **ref, 'source_answer_version': row['answer_version'],
            'source_sha256': hashlib.sha256(video).hexdigest(),
            'audio_sha256': hashlib.sha256(audio).hexdigest(),
        }
    if refs.video:
        if provider != 'higgsfield':
            raise RegistryError(422, 'video_reference_mode_unsupported')
        ref = refs.video[0].model_dump(mode='json')
        source = video_source(conn, workspace, request, ref)
        spec['reference_video'] = {**ref, 'source_answer_version': source['answer_version'],
                                   'source_sha256': hashlib.sha256(source['video']).hexdigest()}


def video_source(conn: Any, workspace: Any, request: Any,
                 ref: dict[str, Any]) -> dict[str, Any]:
    row = conn.execute(
        "SELECT video,answer_version,generation_input FROM video_clip_jobs WHERE workspace_id=%s "
        "AND request_id=%s AND id=%s AND status IN ('review','approved') "
        "AND video IS NOT NULL", (workspace, request, ref['job_id'])).fetchone()
    if not row:
        raise RegistryError(404, 'video_reference_video_missing')
    data = bytes(row['video'])
    duration = row['generation_input'].get('duration_seconds')
    if (type(duration) is not int or not 1 <= duration <= 30 or
            not data or len(data) > 64 * 1024 * 1024 or data[4:8] != b'ftyp'):
        raise RegistryError(422, 'video_reference_video_invalid')
    return {**row, 'video': data}


def resolve_upload_media(conn: Any, settings: Settings, workspace: Any,
                         job: dict[str, Any]) -> tuple[bytes, list[tuple[str, bytes, str]]]:
    """Validate every frozen asset before the worker performs its first external upload."""
    spec = job['generation_input']
    refs = VideoReferenceInputs.model_validate(spec.get('reference_inputs') or {})
    expected = [spec['start_image_id'], *map(str, refs.character_image_ids)]
    frozen = spec.get('reference_images', [])
    if [r['image_id'] for r in frozen] != expected:
        raise RegistryError(409, 'video_reference_image_changed')
    images = []
    for ref in frozen:
        data = image_bytes(conn, workspace, ref['image_id'])
        if hashlib.sha256(data).hexdigest() != ref['sha256']:
            raise RegistryError(409, 'video_reference_image_changed')
        images.append(data)
    media = [('reference_image', data, 'image/png') for data in images[1:]]
    if refs.audio:
        ref = spec['reference_audio']
        if any(ref[k] != v for k, v in refs.audio[0].model_dump(mode='json').items()):
            raise RegistryError(409, 'video_reference_audio_source_changed')
        media.append(('reference_audio', resolve_audio(
            conn, workspace, job['request_id'], ref, settings.ffmpeg_path), 'audio/wav'))
    if refs.video:
        ref = spec['reference_video']
        if str(refs.video[0].job_id) != ref['job_id']:
            raise RegistryError(409, 'video_reference_video_source_changed')
        source = video_source(conn, workspace, job['request_id'], ref)
        if (source['answer_version'] != ref['source_answer_version'] or
                hashlib.sha256(source['video']).hexdigest() != ref['source_sha256']):
            raise RegistryError(409, 'video_reference_video_source_changed')
        media.append(('reference_video', source['video'], 'video/mp4'))
    return images[0], media


def resolve_media(conn: Any, settings: Settings, workspace: Any,
                  job: dict[str, Any]) -> tuple[bytes, list[dict[str, str]]]:
    spec = job['generation_input']
    refs = VideoReferenceInputs.model_validate(spec['reference_inputs'])
    expected_ids = [spec['start_image_id'], *map(str, refs.character_image_ids)]
    if [r['image_id'] for r in spec.get('reference_images', [])] != expected_ids:
        raise RegistryError(409, 'video_reference_image_changed')
    images = []
    for ref in spec['reference_images']:
        data = image_bytes(conn, workspace, ref['image_id'])
        if hashlib.sha256(data).hexdigest() != ref['sha256']:
            raise RegistryError(409, 'video_reference_image_changed')
        images.append(data)
    media = [{'type': 'reference_image',
              'url': 'data:image/png;base64,' + base64.b64encode(data).decode('ascii')}
             for data in images[1:]]
    if refs.audio:
        from asa.video_reference_delivery import audio_url

        ref = spec['reference_audio']
        if any(ref[k] != v for k, v in refs.audio[0].model_dump(mode='json').items()):
            raise RegistryError(409, 'video_reference_audio_source_changed')
        resolve_audio(conn, workspace, job['request_id'], ref, settings.ffmpeg_path)
        media.append({'type': 'reference_audio', 'url': audio_url(settings, workspace, job, ref)})
    return images[0], media
