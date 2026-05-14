# Telegram Runtime Cases

## Case TR-001: Polling Conflict Is Visible

- **Expected outcome:** A running Telegram bridge or Telegram Codex sidecar with recent
  `getUpdates` conflict evidence is reported as `Running with issues`.
- **Forbidden result:** `bin/viventium status` says the service is simply `Running` while recent logs
  show another bot process is consuming the same token.
- **Evidence to capture:** synthetic unit test, sanitized status output, and a local runtime note.
- **Last run:** 2026-05-14, automated synthetic coverage added.

## Case TR-002: Provider Authentication Failure Is Actionable

- **Expected outcome:** A stopped Telegram bridge with recent provider-auth evidence is reported as
  `Action Required` with user-safe refresh guidance.
- **Forbidden result:** raw provider error text, token values, account identifiers, or private logs
  appear in public status or QA artifacts.
- **Evidence to capture:** synthetic unit test and public-safe QA report.
- **Last run:** 2026-05-14, automated synthetic coverage added.

## Case TR-003: Telegram Codex Restart Clears Scoped Orphans

- **Expected outcome:** `--restart` kills only Telegram Codex processes scoped to the configured
  Telegram Codex checkout before starting a new sidecar.
- **Forbidden result:** duplicate Telegram Codex pollers or broad process kills outside the Viventium
  checkout.
- **Evidence to capture:** static launcher regression test and local status after restart.
- **Last run:** 2026-05-14, static regression coverage added.
