# <Feature> QA Cases

## Case ID Convention

Use stable feature-prefixed IDs: `<FEATURE-PREFIX>-NNN`. Keep the prefix short and consistent inside
the folder, such as `BGA-001`, `VOICE-001`, `MCP-001`, or an established existing family such as
`ACT-18`.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `<FEATURE>-001` | `<doc/section>` | `<visible outcome>` | `<Web/Telegram/etc>` | `<command or manual>` | `<date/result/report>` |

## Natural User Use Case Checklist

Use this checklist before claiming feature QA is complete. Add feature-specific rows rather than
leaving this as a generic note.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `<FEATURE>-UC-001` | Happy path a user would try first | `<doc/section>` / `<FEATURE>-001` | `<browser/Telegram/voice/installer/CLI/MCP/scheduler/GlassHive>` | Code, docs/nested docs, logs, DB/state, generated config, scripts, shipped artifacts | `<visible outcome>` | `<date/result/report>` |
| `<FEATURE>-UC-002` | Missing auth, missing config, degraded dependency, local prerequisite unavailable, or first-run/empty state | `<doc/section>` / `<FEATURE>-002` | `<real surface>` | Health/status, prerequisite state such as Docker/provider health when relevant, logs, DB/state, generated config, docs | Honest failure/recovery copy with no invented result | `<date/result/report>` |
| `<FEATURE>-UC-003` | Persistence, reload, restart, retry, cancel, update, or cross-surface parity | `<doc/section>` / `<FEATURE>-003` | `<real surface>` | Stored state, logs, linked surface, artifact or delivery check | Visible state and supporting evidence agree | `<date/result/report>` |

## `<FEATURE>-001` - <Case Name>

- Requirement:
- Risk covered:
- Preconditions:
- Steps:
- Expected result:
- Forbidden result:
- Evidence to capture:
- Full-view evidence minimum:
- Automation:
- Last run:
- Notes:

## Example Case

### `<FEATURE>-001` - Browser-visible state persists after refresh

- Requirement: `<owning doc/section>`
- Risk covered: backend success is reported but the user-visible UI does not show or preserve the result
- Preconditions: local app running; synthetic QA account or fixture; no private user data in prompt
- Steps:
  1. Open the product in a real browser with Playwright CLI or equivalent.
  2. Perform the user action with synthetic input.
  3. Verify the visible UI state and expanded/detail state.
  4. Refresh the page when persistence matters.
  5. Verify backend/log/DB confirmation with sanitized counts or hashes.
- Expected result: visible UI and stored state agree; final model/runtime wording does not contradict the UI
- Forbidden result: logs or DB say success but the visible UI is missing, stale, empty, or contradictory
- Evidence to capture: dated report link, public-safe screenshot if useful, sanitized DB/log counts
- Full-view evidence minimum: real browser path, visible state, detail/expanded state, refresh when
  persistence matters, owning code/log/DB confirmation, and explicit note of anything not run
- Automation: `<command or manual path>`
- Last run: `<date/result/report>`
- Notes:

## Incident Promotion Checklist

When a bug reaches a user or real QA surface:

- [ ] Convert the private/raw report into a synthetic public-safe case.
- [ ] Preserve the failure shape without private names, prompts, accounts, attachments, or local paths.
- [ ] Add both positive and negative controls when the bug was prompt-sensitive or classifier-sensitive.
- [ ] Link the new case from the feature README and any coverage matrix.
- [ ] Add or update automated coverage when the behavior can be checked deterministically.
- [ ] Run the impacted existing cases before claiming the fix is complete.

For evidence-retrieval incidents, also preserve the failure class: successful-empty, provider
unavailable, timeout, rate limit, auth/config missing, request rejected, unsupported configuration,
or local prerequisite unavailable. Named-entity/contact/date/current-fact failures must include the
browser/computer/local-delegation fallback result or the blocked reason.
