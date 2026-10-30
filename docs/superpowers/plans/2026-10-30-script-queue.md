# Script queue implementation plan
Goal: customer script execution through a durable local queue, accurate progress and usage tracing.
Architecture: PostgreSQL script_attempts as queue; per-workspace advisory lock serializes local workers. Only explicitly opted-in new attempts auto-run. No automatic retry after uncertain calls. Model/provider pinned at enqueue; policy rechecked before call. Stored agent version immutable.
- [x] Add failing DB tests for idempotent enqueue, concurrency, cancellation, worker recovery, workspace isolation and tracing.
- [x] Extend queue metadata/status transitions; implement background worker, safety limit and heartbeat.
- [x] Connect execute action, polling, deterministic request receipt (not claimed AI reasoning), elapsed time and results.
- [x] Run mock tests + full checks, migrate and start local processes. Publish improved writer version and perform one bounded real request; verify result and usage record without logging keys.
- [x] Document limits and evidence. No automatic external publishing. Preserve existing queued manual attempts.
