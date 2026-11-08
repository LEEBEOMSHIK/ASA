# WAN 3.0 integration

Goal: connect WAN 3.0 image-to-video through Alibaba Model Studio, preserving Runway and workspace isolation.

Architecture: server-side provider adapter, explicit keys and region/workspace configuration, immutable queued endpoint, existing video queue and result store. Initial profile: 720p, 2–30 seconds, 9:16/16:9, optional native audio. No automatic generation or provider submission retries. Cost remains unknown until an administrator configures the direct API rate.

- [x] Add failing provider request/auth/state tests, implement adapter and settings.
- [x] Connect per-model readiness and enqueue validation; preserve snapshots and reject unsupported configuration.
- [x] Refactor worker to submit once/poll saved task with provider-specific parsing; test unknown submissions and result download.
- [x] Expose WAN status/style guidance and setup instructions. Preserve saved agent model allowlists; adding WAN to an agent is an explicit editor save.
- [x] Run pytest/ruff/mypy/typecheck/build, inspect actual UI, document limitations.

Verification: pytest 400 passed; mypy 65 files, frontend typecheck/build and 3 guidance tests passed. Targeted WAN Python lint passed; full Ruff retains 97 pre-existing findings. Mock HTTP + isolated database tests cover success, uncertain submission, rejection, expired task, workspace separation and idempotent enqueue. Local task-ID migration applied. No real provider authentication or generation: WAN credentials/workspace absent and video generation disabled. Desktop light/dark inspected; narrow DOM geometry checked, narrow screenshots timed out. User agent settings were not saved during UI verification.

Sources: https://docs.modelstudio.console.alibabacloud.com/en/model-studio/wan3-video-generation-api-reference (2026-11-06). First-frame Base64 input, async POST, task GET, 20,000 character limit; provider prompt rewriting explicitly off. Credentials and generated assets stay outside Git. No paid calls as part of verification.
