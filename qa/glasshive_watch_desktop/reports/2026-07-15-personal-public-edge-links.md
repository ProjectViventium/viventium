# GlassHive Personal Public-Edge Links QA Run - 2026-07-15

## Summary

- Result: PARTIAL. Fresh opaque workspace and artifact links, fail-closed controls, browser preview,
  download, refresh, runtime state, and public edge health passed. A phone off-LAN has not yet opened
  the link, so the external-browser portion remains operator-run.
- Build/source under test: active root and nested GlassHive developer checkouts.
- Runtime/artifact under test: freshly compiled/restarted local-prod runtime.
- Environment: personal public-links-only mode on a dedicated HTTPS origin.
- Tester: Codex.
- Related change: `GHWATCH-012`.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `GHWATCH-012` | PARTIAL | Real worker, opaque links, Playwright preview/refresh, exact artifact hash, control-path matrix, ref DB summary, three-region health | Phone off-LAN open remains. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `GHWATCH-UC-012` | Open a generated workspace/artifact link and refresh it. | MCP worker, Playwright browser, public edge | PARTIAL | Exact synthetic content, explicit actions, zero console warnings/errors, and refresh persistence. | 86,400-second artifact ref/token alignment; 1,800-second bounded watch session; closed control paths; external health. | Open on a phone with Wi-Fi disabled. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: personal GlassHive public links.
- Requirement: `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`.
- Use case: open a worker or file link away from the host Mac.
- QA case: `GHWATCH-012`.
- Expected result: opaque public links work while launcher/control/raw-token routes stay private.
- Actual evidence: fresh worker links used the dedicated origin; preview/download/refresh passed;
  unauthenticated root, bootstrap, worker, docs, raw-token, and dotfile probes failed closed; three
  external regions reached public health.
- Remaining gap or fix: phone off-LAN link open remains before full PASS.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | What is proven? | Personal public links, `GHWATCH-012`, `GHWATCH-UC-012`. |
| Code owning path | What owns it? | Compiler public-link env, signed-link generation/state, UI ref resolution, public Caddy edge. |
| Docs and nested docs/repos | What defines it? | GlassHive runtime requirement and nested signed-link/server code. |
| Scripts or harnesses | What exercised it? | MCP real worker, Playwright CLI, focused release/UI suites. |
| Local/external prerequisite state | Was it healthy? | Runtime/UI/edge healthy; dedicated DNS and public health passed. |
| Logs | What did logs show? | Edge ref-path logging redacts opaque values; no contradictory UI error. |
| DB/state/persistence | What persisted? | Three fresh refs; artifact ref/token 86,400 seconds; watch ref 86,400 seconds with a renewed 1,800-second session. |
| Generated/shipped artifact | What was inspected? | Generated env and active five-host Caddy config. |
| Real user path | What did the user do? | Completed a real worker task, opened preview, downloaded exact bytes, used expanded output, refreshed. |
| Visual/UX comparison | Did it match? | Yes; public origin, tokenless visible URLs, explicit actions, exact marker. |
| Not run / blocked | What remains? | Off-LAN phone browser open is PARTIAL. |

## User-Grade Evidence

- Surface exercised: GlassHive MCP, Watch / Steer, artifact preview/download.
- Real user path: completed a synthetic task and opened its generated public artifact action in a real
  browser.
- Visible outcome: preview title matched the file and displayed the exact marker.
- Expanded/detail state: latest workspace output and file actions were visible.
- Persistence/reload result: preview and completed result survived refresh.
- Local/external prerequisite state: public health returned 200 from three external regions.
- Evidence retrieval classification, if applicable: successful.
- Fallback path, if applicable: internal Caddy listener used for real-browser interaction because the
  local router lacks NAT loopback; external nodes independently proved WAN reachability.
- Backend/log/DB confirmation: ref/token lifetime, edge state, control status matrix, and exact 43-byte
  artifact hash matched.
- Final model/runtime wording check: new user-visible links use only the dedicated public origin plus
  opaque refs.
- Substitution check: supporting state/tests did not replace real-browser QA; the off-LAN phone step
  remains explicitly PARTIAL.

## Automated Evidence

```bash
python -m pytest tests/release/test_remote_call_tunnel.py \
  tests/release/test_config_compiler.py tests/release/test_install_summary.py -q
HOME=/tmp/viventium-qa-clean-home viventium_v0_4/GlassHive/frontends/glass-drive-ui/.venv/bin/pytest \
  viventium_v0_4/GlassHive/frontends/glass-drive-ui/tests/test_server.py -q
```

Focused results: 217 root release tests and 95 GlassHive UI tests passed.

## Findings

- Defects: compiler key corrected so the runtime now receives the intended 24-hour artifact token
  lifetime rather than its legacy 15-minute default.
- Regressions: none observed.
- Flakes: an initial test command loaded the installed public-mode env by design; isolation with a
  temporary home produced the expected 95-pass result.
- Environment issues: same-LAN custom-domain requests time out without router NAT loopback.
- Residual risks: phone off-LAN open remains; developer checkouts are not yet committed/pinned.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
