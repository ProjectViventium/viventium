# Post-union installed connected-accounts QA — 2026-08-13

## Summary

- Result: **PARTIAL**.
- Scope: installed local production after the reviewed parent and nested changes were merged.
- Public parent revision: `1394cb2ba85b74d50a5f4f248daeb000c0d1ea01`.
- Exact component revisions: LibreChat `541a4c4fdac97f54333d25a79de9c34e4319db04` and
  GlassHive `987c98b399c672cc45344b69c5dcb5e9612bdf9c`.
- Data safety: synthetic non-personal requests only; no mailbox, calendar, file, or health data was
  requested or changed.

## Scope Run

| Surface | Actual evidence | Result |
| --- | --- | --- |
| Installed provenance | Active checkout, helper checkout, and live stack owner all resolved to one clean clone at the public parent revision. All 12 nested checkouts were clean at their exact lock refs. | PASS |
| LibreChat browser | A real Chromium session sent a synthetic Main request, rendered the final answer, expanded the activity state, and retained the answer after reload. The persisted assistant message had `error=false`, `unfinished=false`, and no external tool call. | PASS for visible delivery and persistence; PARTIAL for the specialist round trip |
| Telegram | Telegram Desktop sent a read-only synthetic connected-account status request. A concise degraded answer returned in about 19 seconds, remained finished after runtime restart, and did not claim mailbox facts. | PASS for truthful degraded delivery and restart persistence; PARTIAL for the specialist round trip |
| Telegram delivery control | The installed bridge received a valid required structured `audio=skip` disposition. With the standing voice preference enabled, it delivered text and did not synthesize unwanted audio. | PASS |
| Target initialization | Runtime logs reached the Connected Accounts target and began its configured tool initialization. Initialization then failed closed because the selected Anthropic connected account required reconnection. No workspace tool executed. | PARTIAL — user reauthentication required |
| Automated integration | Parent release/manifest/migration slice 71/71; LibreChat API 90/90; LibreChat package/API 99/99; Telegram 425/425; GlassHive full collection 1,257 with exit 0 and five existing skips. | PASS |

## Traceability

`installed public union -> native Main handoff -> CA-HANDOFF-019 -> truthful visible delivery and
persistence -> target initialization evidence -> Anthropic reconnect gap`

## Full-View Evidence Checklist

| Evidence surface | Result / sanitized pointer |
| --- | --- |
| Requirement and use case | `CA-HANDOFF-019`: installed browser and Telegram connected-account status request after union repair. |
| Code and component pins | Parent, LibreChat, and GlassHive exact public revisions listed above; all 12 nested repos clean at lock refs. |
| Config and generated artifact | Active checkout, helper, live owner, compiled prompts, and installed Telegram component resolved to the final merged source. |
| Real user paths | LibreChat in Chromium and Telegram Desktop with synthetic read-only requests. |
| Visible result | Both surfaces returned truthful results; neither claimed external account facts without tool evidence. |
| Logs and state | Target initialization reached Connected Accounts, then failed closed on required Anthropic reconnection. Persisted messages were finished and non-error. |
| Persistence | Browser result survived reload; Telegram result survived runtime restart. |
| Not run / blocked | Tool-backed Connected Accounts round trip blocked by Anthropic reauthentication; no account data operation was attempted. |

## User-Grade Evidence

- Surface exercised: LibreChat browser and Telegram Desktop against installed local production.
- Real user path: send synthetic read-only connected-account status request, inspect visible response
  and activity, reload browser, restart runtime, and verify persisted completion.
- Visible outcome: browser and Telegram displayed a truthful result without invented mailbox facts.
- Expanded/detail state: browser activity state rendered; runtime logs showed Connected Accounts
  target initialization before the authentication gate.
- Persistence/reload result: browser response remained after reload; Telegram response remained
  finished after restart.
- Backend/log/DB confirmation: persisted assistant messages had `error=false` and
  `unfinished=false`; no external tool call executed.
- Final model/runtime wording check: degraded answers were scoped to unavailable account state and
  did not claim successful specialist/tool evidence.
- Substitution check: automated tests support but do not replace the real Chromium and Telegram
  Desktop evidence.

## Automated Evidence

- Parent release/manifest/migration slice: 71/71 PASS.
- LibreChat API slice: 90/90 PASS.
- LibreChat package/API slice: 99/99 PASS.
- Telegram full suite: 425/425 PASS.
- GlassHive full collection: 1,257 collected, exit 0, five existing skips.

## Findings

The union repair is installed from exact public source and the formerly drifting Main graph migration
is present. Browser and Telegram delivery are no longer running from the original dirty checkout,
and both surfaces persist a truthful result through reload or restart.

`CA-HANDOFF-019` remains **PARTIAL**, not PASS: the specialist target could not complete a tool-backed
round trip while its Anthropic connected account required reconnection. The installed runtime failed
closed and did not invent account evidence. Reconnect that account through **Settings > Account >
Connected Accounts**, then repeat the same synthetic read-only browser and Telegram checks and
correlate the visible answer with the specialist run, tool evidence, final Main synthesis, message
completion, and delivery acknowledgement.

## Public-Safety Review

- [x] Synthetic non-personal prompts only.
- [x] No account data read or mutation.
- [x] No secrets, credentials, private messages, IDs, logs, database rows, screenshots, or local
  absolute paths published.
- [x] Exact revisions and aggregate test counts only.

No screenshots or private runtime records are published with this report.
