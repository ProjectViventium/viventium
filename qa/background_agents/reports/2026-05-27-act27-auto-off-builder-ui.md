# ACT-27 Agent Builder Auto-Off UI QA

- Started: 2026-05-27T14:00Z
- Scope: local Agent Builder display for background-cortex `activation.enabled` after broker-first soft-retirement.
- Source of truth: live Mongo main-agent row has `activation.enabled: false` for Deep Research, MS365, and Google.
- UI change: attached background cortices now show `Auto-on` / `Auto-off`, an on/off switch, and an active/attached count.
- Browser evidence: real local Chrome tab at `localhost:3190/c/new`, Agent Builder advanced settings.
- Visible summary: `8 active / 11 attached`.
- Visible disabled rows:
  - `Deep Research Auto-off`
  - `MS365 Auto-off`
  - `Google Auto-off`
- Automated browser check: Playwright authenticated local run found 3 `Auto-off` rows, 8 `Auto-on` rows, and no page errors.
- Typecheck note: full frontend typecheck remains blocked by pre-existing unrelated errors; targeted typecheck output contained no `BackgroundCorticesConfig` errors after the local typing fix.
- Result: PASS.
