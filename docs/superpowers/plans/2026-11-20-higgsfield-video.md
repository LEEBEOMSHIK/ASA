# Higgsfield WAN integration

User approved preserving Alibaba and adding Higgsfield WAN 3.0, automatic reference image/audio/video upload, estimated cost, and mobile/light verification. No real generation or user data mutation.

Implementation: add a separate provider adapter and configured model profile, preserve frozen provider/model for existing jobs. Upload only validated workspace media with signed uploads; never leak credentials to upload hosts. Model-specific payloads and status mapping; idempotent submission. Preserve original assets. Price based on resolution/reference-video presence, expose estimate without generation. Keep unknown estimates explicit.

Tasks: provider HTTP adapter and mocked tests; registry/reference/worker wiring and tests; provider selection/management/cost UI; full backend/frontend checks and actual browser QA with mocked fixtures only. Existing dirty changes must remain untouched.

No API credentials supplied: live authentication, upload, quote and paid generation remain unverified; no generation is authorized.
