# ASA-081 agent output contract
- Keep queue, idempotency, workspace locks and historical script versions.
- Add nullable answer JSON to versions. Old title/narration remains a legacy view, never forced on new agent outputs.
- Registered instructions become system message; registered output schema wraps the model response and is validated before persistence.
- Revision includes original input and selected previous answer, with no script-specific scope.
- Customer UI renders/edits declared types without exposing JSON. Preserve old script editing.
- Tests: arbitrary structured/free output, schema rejection, revision snapshot, persistence and legacy regressions. Run full checks then one real improved-writer request.
