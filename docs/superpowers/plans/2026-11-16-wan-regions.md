# WAN region controls

User-approved scope: show active region and switch Singapore/Tokyo after authentication. Preserve existing requests and materials; no video generation or S01 resubmission.

Design: region credentials stay in server environment, separately named Singapore/Tokyo key and workspace variables. Existing WAN variables remain a fallback only for their own region. Workspace DB stores only active region and revision, never secrets. Authentication uses read-only task GET; selection alone changes nothing. Apply rechecks fresh authentication server-side and checks revision. Existing jobs resolve their frozen endpoint against configured regional profiles, never against the newly selected region or arbitrary URLs.

1. Backend: regional configuration resolver + tests; active-region migration/service; admin check/apply APIs; resolve active settings in model catalog/auth and enqueue under policy lock; workers resolve saved endpoint; regression cases for legacy/default, missing/denied, cross-workspace, stale revision, active queued/running preservation and secret non-disclosure.
2. Frontend: dedicated compact region section within video management, current badge, select target, separate authentication and apply actions, status/error feedback, no secrets in client. New API GET management.wan_regions {active_region,revision,regions:[{region,label,connection_state,connection_check}]}; POST /wan-regions/{region}/check; PUT /wan-region {region,revision}.
3. Integration: migrate local schema, retain Singapore current setting, no real switch to missing Tokyo. Run backend pytest/ruff/mypy and frontend typecheck/build. Browser desktop/mobile dark/light, keyboard/error/disabled state and DOM spacing. Restore temporary UI state. Record verified vs unverified.
