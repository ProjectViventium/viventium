# Post-union installed connected-accounts QA — 2026-08-13

- Result: **PARTIAL**.
- Scope: installed local production after the reviewed parent and nested changes were merged.
- Public parent revision: `1394cb2ba85b74d50a5f4f248daeb000c0d1ea01`.
- Exact component revisions: LibreChat `541a4c4fdac97f54333d25a79de9c34e4319db04` and
  GlassHive `987c98b399c672cc45344b69c5dcb5e9612bdf9c`.
- Data safety: synthetic non-personal requests only; no mailbox, calendar, file, or health data was
  requested or changed.

## What actually ran

| Surface | Actual evidence | Result |
| --- | --- | --- |
| Installed provenance | Active checkout, helper checkout, and live stack owner all resolved to one clean clone at the public parent revision. All 12 nested checkouts were clean at their exact lock refs. | PASS |
| LibreChat browser | A real Chromium session sent a synthetic Main request, rendered the final answer, expanded the activity state, and retained the answer after reload. The persisted assistant message had `error=false`, `unfinished=false`, and no external tool call. | PASS for visible delivery and persistence; PARTIAL for the specialist round trip |
| Telegram | Telegram Desktop sent a read-only synthetic connected-account status request. A concise degraded answer returned in about 19 seconds, remained finished after runtime restart, and did not claim mailbox facts. | PASS for truthful degraded delivery and restart persistence; PARTIAL for the specialist round trip |
| Telegram delivery control | The installed bridge received a valid required structured `audio=skip` disposition. With the standing voice preference enabled, it delivered text and did not synthesize unwanted audio. | PASS |
| Target initialization | Runtime logs reached the Connected Accounts target and began its configured tool initialization. Initialization then failed closed because the selected Anthropic connected account required reconnection. No workspace tool executed. | PARTIAL — user reauthentication required |
| Automated integration | Parent release/manifest/migration slice 71/71; LibreChat API 90/90; LibreChat package/API 99/99; Telegram 425/425; GlassHive full collection 1,257 with exit 0 and five existing skips. | PASS |

## Requirement judgment

The union repair is installed from exact public source and the formerly drifting Main graph migration
is present. Browser and Telegram delivery are no longer running from the original dirty checkout,
and both surfaces persist a truthful result through reload or restart.

`CA-HANDOFF-019` remains **PARTIAL**, not PASS: the specialist target could not complete a tool-backed
round trip while its Anthropic connected account required reconnection. The installed runtime failed
closed and did not invent account evidence. Reconnect that account through **Settings > Account >
Connected Accounts**, then repeat the same synthetic read-only browser and Telegram checks and
correlate the visible answer with the specialist run, tool evidence, final Main synthesis, message
completion, and delivery acknowledgement.

No screenshots or private runtime records are published with this report.
