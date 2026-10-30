# ASA-084 input form

User-approved scope: field names, widgets, options, required flags and defaults editable in agent setup; same schema renders preview and execution. Preserve existing keys and immutable published versions.

- Keep input_schema as the source of truth. Use description for label, enum for string options, default for defaults, x-widget for text/textarea/select/radio/slider/number. Slider uses integer min/max with step1.
- Reject incompatible widgets, invalid options/defaults and out-of-range values server-side. Defaults initialize only a fresh form; reopening a request uses its exact submitted values.
- Existing object/array inputs retain advanced editing. New friendly fields are scalar; optional fields can remain unset.
- Implement backend regression tests first, then common form controls/editor; run full checks and browser preview without paid calls.
