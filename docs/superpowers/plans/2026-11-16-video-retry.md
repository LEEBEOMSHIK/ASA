# Video retry after provider record confirmation

User-approved scope: add retry after provider record inspection, preserve original requests/assets, never duplicate S01 during implementation.

- Error/progress area opens a read-only review modal with original request region/time/task and current target configuration.
- Missing task ID, authentication success, failed lookup or empty task list are not proof of no generation. Administrator must inspect the original provider records and enter evidence of no in-progress/completed generation before explicitly submitting.
- Known provider task IDs remain blocked from new generation pending result recovery. No automatic retry or result recovery in this change.
- Explicit retry authenticates the current target, revalidates latest approved plan/reference/policy, then atomically preserves the failed/unknown original and queues one new attempt. Workspace lock, expected original attempt, operation UUID and current-slot uniqueness prevent double submission.
- Existing request and asset IDs remain readable; progress uses only current attempt; previous attempts have accessible immutable status/diagnostics.
- No real retry or generation in verification. Mock API tests cover history, duplication, authorization, invalid confirmation, stale plan, failed auth and current region. Actual browser verifies modal, disabled/filled inputs, sticky actions, mobile/light; no submit.
