# Unified library implementation plan

**Goal:** Replace the image-only landing page with a workspace-scoped library of existing and future production materials, viewed by type or work.
**Architecture:** Read existing immutable answers and media metadata; do not duplicate media or modify approval state. Explicit library collections organize request families and standalone uploads. Unassigned materials remain visible. Titles never establish identity. Existing image selection and version tools remain available.
**Tech stack:** FastAPI, PostgreSQL, Next.js, shared UI tokens/components.
**Spec:** User-approved proposal in this chat: scripts/scenes/characters/images/audio/videos, previews, versions/status/download, original-work links, fixed sidebar width.

## Constraints and review focus
- All queries and collection mutations scoped by workspace; CSRF and optimistic revisions.
- No paid generation, original-answer edits, or approval as part of browsing.
- Existing generic/unclassified and deleted-source assets remain discoverable.
- Same titles do not merge unrelated work; uploads can remain unassigned.
- Paginate metadata; media only loads on detail. No raw job input/secrets returned.
- Preserve sidebar CSS, existing image selector contracts and legacy routes.

## Tasks
- [x] Add failing DB tests for existing versions, workspace isolation, type filters, detail, collection assignment/conflicts; unit tests for classification and work families.
- [x] Add library query/service/router and collection migration, register API. Read all supported sources, provide bounded listing and detail, assign source families to user-named works without altering source data.
- [x] Replace /characters landing with library UI: type/work views, filters, responsive cards, native preview and collection dialogs, original-work links, downloads; retain legacy image browsers and navigation preference identity.
- [x] Validate focused tests then backend pytest/ruff/mypy and frontend typecheck/build. Review implementation and check actual browser themes, narrow layouts, controls and computed geometry without saving user data.
- [x] Record evidence and unverified states in WORKBOARD; no commit/push requested in this turn.

Execution: proceed inline under the user's explicit implementation authorization. Existing checkout reused to preserve related uncommitted work.
