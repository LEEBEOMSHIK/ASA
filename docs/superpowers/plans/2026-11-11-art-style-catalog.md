# Common art style catalog implementation plan

Approved scope: shared workspace art style presets edited by administrators in agent editing; work common and character/scene section headings; preserve existing saved work settings and generated assets.

- [x] Add workspace-scoped catalog storage with optimistic revision, authenticated reading and admin-only writing. Bootstrap existing six presets without rewriting work data. Validate bounded raster uploads; no external fetch or executable SVG.
- [x] Add common catalog editor with type, label, generation instructions and preview upload/replace. Explicit separate shared-catalog save, unsaved guard/error handling. Use shared UI tokens.
- [x] Load catalog in WorkArtStyle, filter by media type, retain custom/legacy prompts and store selected instructions as existing work snapshot. Existing image and video enqueue chains consume the same snapshot.
- [x] Separate work-common heading from character/scene section headings, retain sidebar width.
- [x] Verify permission, validation, revision conflicts, work snapshot preservation and image/video propagation with offline tests. Run full pytest/ruff/mypy/typecheck/build. Browser desktop/narrow/light/dark selection, layout and cleanup; record actual limits.
