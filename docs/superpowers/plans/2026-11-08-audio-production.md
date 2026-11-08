# Audio Production Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans task-by-task; user authorized implementation in this session.

**Goal:** Connect character/narrator voices, music assets, reviewed speech and final video composition.
**Architecture:** Workspace/version-scoped PostgreSQL audio settings and immutable job snapshots. Local audio worker calls configurable OpenAI Realtime and FFmpeg; UI edits, previews and explicitly approves versions.
**Tech Stack:** FastAPI, Pydantic, psycopg, WebSocket Realtime, FFmpeg, React/Next.js.
**Spec:** ../specs/2026-11-08-audio-production-design.md

## Global Constraints
- No paid calls in tests; preserve existing data and dirty work; no commit/push in this task.
- Same workspace boundary on every asset/reference; CSRF on mutation; no secret in client/log/Git.
- Audio changes create new revisions; stale approval/composition blocked. Uncertain external calls never auto-replayed.
- Native local processes, existing UI tokens/components; actual browser verification required.

## Review Focus
- Overlong speech or same-speaker overlap must block composition (task 1/3 tests).
- Cross-workspace music/character/video references rejected (task 2 tests).
- Changed voice/text/cue timing cannot silently use stale approved speech (task 2/3 tests).
- Worker restart after submission must mark unknown, not charge twice (task 3 tests).
- Silent/no narration/no music timelines and non-looping short music remain valid (task 1/3 tests).

### Task 1: Contracts and media/provider adapters
Files: new asa/audio_contracts.py, audio_media.py, audio_provider.py, tests/test_audio_production.py; config.py.
Interfaces: AudioSettings(speakers,cues,music,enabled), Voice(model_key,voice,instructions,speed,language); normalize_audio(bytes,ffmpeg)->(WAV bytes,seconds); synthesize(settings,voice,text)->(WAV bytes,transcript); compose(video bytes/durations,voice bytes/timings,music bytes/options,ffmpeg)->MP4 bytes.
- [x] Write and observe failing validation/media/provider tests; implement strict finite time ranges, identifiers, limits, speaker/cue references.
- [x] Decode bounded uploads to WAV using FFmpeg; verify timeline and deterministic mix/concat with test media.
- [x] Add configurable current Realtime voice model, no auto reconnect/retry, bounded PCM and transcript validation; mocked protocol tests.

### Task 2: Workspace-scoped storage and API
Files: registry/migration.sql, registry/audio_routes.py, registry/audio_service.py, api.py, integration/test_audio_production_db.py.
Interfaces: GET/PUT /audio/work/{request_id}/{version}; /audio/catalog; /audio/assets; /audio/sources; POST work/.../speech; /audio/jobs/{id}/approve; POST work/.../compose; GET /audio/jobs/{id}/media.
- [x] Failing authenticated persistence, revision, isolation and old-asset tests.
- [x] Store settings, voice assignments, assets and jobs by workspace. Validate references and snapshot generation input atomically; matching fingerprints reusable, stale results not current.
- [x] Upload base64 bounded music and expose private preview; explicit voice source request/version import.
- [x] Idempotent enqueue with caller UUID; approval checks fingerprint and measured time; source validation again at composition enqueue/run/approve.

### Task 3: Worker and video planning integration
Files: audio_worker.py, worker_control.py, registry/worker_routes.py, video_contracts.py, registry/video_jobs.py, registry/video_planning.py, tests/integration/test_audio_production_db.py.
- [x] Failing restart/duplicate/stale timeline tests; implement graceful-stop audio worker for speech and composition.
- [x] Add optional structured audio plan to video output, common/style audio instructions, editable UI seeds; separate-audio mode forces new video jobs silent.
- [x] Add source snapshots, transcript and duration validation; real FFmpeg fixture verifies output streams and duration. Preserve existing video jobs and require explicit original-audio removal acknowledgement when composing audible clips.

### Task 4: UI and existing agent settings
Files: components/audio-production.tsx, character-studio.tsx, video-clip-manager.tsx, agent-worker-status.tsx, globals.css; scripts/upgrade-audio-production.py.
- [x] Character results voice editor with stable IDs; shared voice fields/catalog. Video audio editor for manual speakers, explicit import, narrator, cues, music upload/library/mix settings.
- [x] Save→generate speech→preview/approve→compose→preview/approve/download; errors and stale/overlong states visible, no auto-paid calls.
- [x] Upgrade only video/character schema markers; revision-check and backup existing agent definitions; preserve old request snapshots.
- [ ] Full visual matrix: desktop light/dark, error/disabled/long-label/focus and narrow DOM verified; narrow screenshots timed out and real audio playback is unverified (documented). No user state saved for screenshots.

### Task 5: Review and completion
- [x] Full backend pytest/ruff/mypy and frontend typecheck/build; targeted fixes then appropriate retest.
- [x] Fresh code review via requesting-code-review skill; record changes and actual/unverified UI/API outcomes.
- [x] Update architecture/local-development/design-system/WORKBOARD and .env.example. No real AI call or commit/push.

## Execution ledger
- 2026-11-08: User approved design after role clarification. Reuse current checkout since integration depends on already authorized uncommitted video/worker work. Run inline; no repeat approval. Start contracts/media tests first.

- Implementation ruling: voices reuse the same /audio/work settings endpoint; /audio/sources supplies explicit character source versions. No redundant voice-specific table or component.
- Tasks 1–4 implemented. Targeted tests cover contracts/provider/FFmpeg, storage conflicts and workspace asset isolation, unknown recovery, measured speech approval, composition retry and source replacement. Source voice IDs retain stable character identity.
- Reviewer found terminal composition deduplication and actual video length issues; fixed with explicit new-attempt partial uniqueness and decoded duration rejection. Non-loop music fade targets actual available length.
- Current model profiles are server configuration, not a new administrator model UI. Realtime cost is recorded as unknown, never zero. Character voice import copies settings; no implicit title matching.
- Actual browser checks and limitations recorded in docs/audio-production.md. Narrow viewport DOM was checked, but screenshot timed out; real AI quality/media playback remains unverified. No user assets saved/approved for UI inspection.

- Final: pytest437 passed; targeted audio9 passed after final upload/foreign-asset checks; mypy77/typecheck/build passed; new audio Ruff clean, repository retains existing97 Ruff findings. Local migration and video agent revision12 applied with backups. No paid calls or commit/push.
