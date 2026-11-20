# AI review spans

Approved scope: AI classifies exact source phrases for human review. Never alter stored plan, copying, video payloads, approvals or existing assets. No video generation.

1. Add independent envelope metadata and workspace/request/version storage. Fields identify clip, prompt/audio/edit section, exact quote and category. Reject nonmatching/ambiguous/overlapping spans; no keyword fallback.
2. Generate metadata with the planning AI; compute canonical audio text before classification. Existing plans use a classification-only maintenance command with the saved agent model and accounting, no rewrite.
3. Read annotations through clip GET and render only against matching source text. Keep legends, focus and copying unchanged.
4. Test preservation, invalid/duplicate/overlap, audio and stale source behavior; full backend/frontend checks. Inspect desktop and narrow light/dark UI without approving or generating videos.
