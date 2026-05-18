# QA Results

This folder is for public-safe machine-readable or generated QA outputs that support feature reports.

Rules:

- Store outputs under `qa/results/<suite>/<timestamp>/`.
- Include a short Markdown summary beside JSON or structured artifacts.
- Link the result summary from the owning `qa/<feature>/cases.md` or run report.
- Do not store raw private logs, screenshots with private data, database exports, local runtime state,
  cookies, tokens, prompts, transcripts, account identifiers, conversation IDs, message IDs,
  session/call IDs, Telegram chat IDs, Mongo `_id` values, raw provider request/response IDs, or
  stack traces with private paths, or raw runtime dumps here.
- Prefer sanitized counts, hashes, timings, pass/fail status, and synthetic fixture names.
