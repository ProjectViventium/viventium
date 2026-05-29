# Connected Accounts Handoff QA Cases

## Case ID Convention

Use `CA-HANDOFF-NNN` for durable cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| CA-HANDOFF-001 | `02_Background_Agents.md` connected-accounts-under-GlassHive / hand-off | "any new emails today?" hands off to Connected Accounts, reads **both** Gmail and Outlook, returns a concise summary inline in one turn — no GlassHive worker, no clarification, no plumbing link. | LibreChat Web UI | Manual/browser | PASS 2026-05-28 (`lc_transfer_to_...` → `search_gmail_messages` + `list-mail-messages`, ~35-45s, no leak) |
| CA-HANDOFF-002 | Same | "what's on my calendar this week?" hands off and reads **both** Google Calendar and MS365 calendar, returns an inline week-at-a-glance. | LibreChat Web UI | Manual/browser | PASS 2026-05-28 (`get_events` + `list-calendar-events`, clean inline summary) |
| CA-HANDOFF-003 | Same (routing precision) | A non-connected-account request (generation/reasoning, e.g. "write a haiku about debugging code") is answered **directly with no handoff**. | LibreChat Web UI | Manual/browser | PASS 2026-05-28 (direct answer, no `Transferred to`) |
| CA-HANDOFF-004 | Read-only hand-off; writes stay confirmed/under-broker | Connected Accounts agent carries **only** read tools (search/get/list/read); send/draft/delete/move/modify are absent, so a write request cannot be silently executed by the hand-off path. | Agent config, Web UI | Config check + manual | PASS 2026-05-28 for config (0 write tools); live write-routing exercise PENDING |
| CA-HANDOFF-005 | Main agent stays lean | The main Viventium agent has **no** direct Google/MS365 provider tools; the only added field is one handoff `edge`. Specialists' drift untouched. | Agent config / Mongo | Config check | PASS 2026-05-28 (main = 44 tools + 1 edge; specialists 85/94 unchanged) |
| CA-HANDOFF-006 | gpt-5.4 (OpenAI Responses API) usable for specialist/hand-off agents | A gpt-5.4 / OpenAI-Responses agent streams a reply without the spurious "The model provider could not complete this request." bubble (`response.output is not iterable`). | LibreChat Web UI, unit | Browser + `openaiResponsesOutputPatch.spec.js` | PASS 2026-05-28 (no bubble; 0 `response.output` errors in logs; 2/2 regression tests) |
| CA-HANDOFF-007 | Result quality, not just speed (see `48_GlassHive#results-quality-vs-speed`) | For a "quick rundown" query the path's **result** is accurate on the important items, prioritized, and actionable; literal details (meeting times, names, amounts) are correct. Judge runs on accuracy/completeness/usefulness for the intent, not latency alone. | LibreChat Web UI; output review | Manual output scoring | PASS 2026-05-29: claude-code worker (sonnet-4-6, host) measured vs codex + hand-off. claude worker **88–144s (~2 min, 3 runs) vs codex 301s** — ~2.5–3.4× faster — reading **both** Gmail + Outlook (after fix CA-HANDOFF-009), prioritized + action-items surfaced (Nilay Lad/Zochem reply, Myk Pono YC match), literal meeting time correct (1 PM ET = 10 AM PDT). Decision unchanged (PARITY, not a routing rubric): both paths meet the metric on their own AI; Main Agent/user decide shape, GlassHive owns truth + completeness. Cold-vs-warm: Main Agent spawns a fresh worker per request (no auto-`workspace_continue`); host spawn≈0s so variance is prompt-cache + verbosity, not container warmth. |
| CA-HANDOFF-008 | claude-code worker authenticates on macOS (Keychain) | A GlassHive **claude-code** host worker authenticates and completes a connected-account read instead of exiting "Not logged in · Please run /login". | GlassHive runtime, worker run, Web UI | Live worker run + `test_profile_runtime.py` | PASS 2026-05-29. Root cause: `profile_runtime.py` `_host_env` omitted `USER`/`LOGNAME`; macOS claude resolves its Keychain credential by user, so the worker exited in ~15–20 ms "Not logged in". (Not setsid — full-env worked with and without `start_new_session`.) Fix: pass `USER`/`LOGNAME` through (identity, not secrets). Verified live (worker authed + delivered the rundown) + regression assertion in the host-env test. |
| CA-HANDOFF-009 | claude worker can read MS365/Outlook via broker | The claude-code worker reads Outlook (`list_mail_messages`) instead of failing `expected record, received array at structuredContent`. | LibreChat broker route, worker run, Web UI | Live worker run + `glasshiveCapabilities.spec.js` | PASS 2026-05-29. Root cause: broker `tools/call` set `structuredContent: result` unconditionally; MS365 returns an array, but MCP requires `structuredContent` to be an object, so claude's strict client rejected every Outlook read (codex's lenient client tolerated it — why only codex got Outlook). No tool advertises `outputSchema`, so it's optional. Fix: emit `structuredContent` only for objects; arrays ride in `content[0].text`. Verified live (claude read Gmail + Outlook) + a route regression test (array → omit structuredContent, data in text). |

## Forbidden outcomes (any of these is a FAIL)

- Asking "Gmail or Outlook?" for a generic inbox/email question when both providers are connected.
- Falling back to a browser worker for a simple connected-account read instead of the direct hand-off.
- Surfacing a `View / Steer` worker link, `[local worker link]`, or other worker/run plumbing in the reply for a quick read.
- The main agent acquiring direct provider (`*_mcp_google_workspace` / `*_mcp_ms-365`) tools.
- Handing off for a request that is not about the user's own connected accounts (web/news, math, generation, code).
- A spurious completion-error bubble after a successful gpt-5.4 answer.

## Notes / residual

- CA-HANDOFF-004 write-routing (e.g. "reply to that email") should be exercised live to confirm it routes to the confirmed broker/worker path rather than failing; currently proven only by the read-only tool set.
- Handoff currently fans out to both providers for generic email/calendar; provider-narrowing ("only my gmail") is expected to be honored by the hand-off agent instructions but is not yet a separate case.
- CA-HANDOFF-008 durability gate: the auth fix was verified with the runtime relaunched from a keychain-attached shell (reparented to launchd, matching the helper's detached launch). Re-verify a claude-code worker read **after a real macOS-helper restart**; the helper is an `LSUIElement` GUI app (user Aqua session → Keychain), so the fix is expected complete. For session-independent / enterprise (Panorad) durability, provision a headless token (`claude setup-token` → inject `CLAUDE_CODE_OAUTH_TOKEN` into the worker env), the file/token parity codex has; do not extract/persist the Keychain token.
- Worker default is now `claude-code` via the per-user GlassHive preference (codex weekly credits exhausted). Revert with `PATCH /v1/preferences {"default_worker_profile":""}` (falls back to env default `codex-cli`) when codex credits return.
