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
