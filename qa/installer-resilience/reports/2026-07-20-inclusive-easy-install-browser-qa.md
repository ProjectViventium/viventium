# Inclusive Easy Install browser QA — 2026-07-20

## Summary

`PASS` for the scoped browser matrix, not whole-release acceptance. The isolated real-browser run
closed the setup handoff, keyboard, narrow/mobile, localization-fallback, reduced-motion,
forced-colors, refresh/restart, provider-fault, and Feelings-fault rows. It found and fixed four
user-visible defects. VoiceOver, native helper/Keychain/TCC, Intel, signed payload, parent pin, and
release-installed artifact proof remain separate external or delivery-alignment gates.

## Scope Run

- Disposable Apple-silicon macOS VM cloned from synthetic QA state; no host mounts, clipboard, or
  personal browser/profile state.
- Dedicated synthetic user and invalid-shaped synthetic key values only.
- Browser traffic was restricted to loopback; the final full run recorded zero external attempts
  and zero page exceptions.
- Raw screenshots, browser ledgers, and synthetic runtime state remained in private QA storage. No
  account identifiers, credentials, raw logs, local paths, or screenshots were added to this repo.

## Traceability

| Feature | Requirement | Use case | QA case | Expected result | Actual evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| Easy Install browser onboarding | Inclusive, low-friction setup | Connect and recover four providers without a mouse | `INST-023` | Keyboard, narrow, locale, motion, and fault paths remain usable | Real Chromium focus, viewport, locale, fault/retry, refresh, restart, ten-session handoff stress, source, and build evidence below | Native assistive technology and exact shipped artifact |
| Feelings discovery | Flagship feature is reachable without URL or provider knowledge | Open Feelings with no provider keys and recover from a GET outage | `INST-012`, `EMO-UC-038` | Keyboard discovery, provider-free load, refresh, reduced motion, retry | Account-menu active-descendant trace, visible Feelings surface, 320px audit, injected GET failure and recovery | Right-control parity, native assistive technology, exact shipped artifact |

## Full-View Evidence Checklist

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Real user path: Chromium registration/login, Settings, Connected Accounts, account menu, and
  Feelings were operated as a user; mocks did not replace the visible path.
- Docs and nested docs: installer and Emotional Cortex case catalogs were updated to point to this
  result and retain their wider open matrices.
- Logs, DB/state/persistence: browser request outcomes, visible state, fresh-session persistence,
  runtime stop/start health, source hashes, and production chunks were correlated without publishing
  raw private state.
- Supporting evidence cannot replace required user-path evidence; VoiceOver/native UI and the exact
  shipped payload remain `BLOCKED` in this lane.

## User-Grade Evidence

- Surface exercised: Easy Install login handoff, LibreChat Settings > Account > Connected Accounts,
  keyboard account menu, and the authenticated/signed-out Feelings browser route.
- Real user path: a real Playwright-driven Chromium registered or logged in a synthetic user,
  opened/closed/retried provider dialogs, used keyboard navigation, resized the live dialog, changed
  locale and media preferences, opened Feelings, refreshed, and repeated provider inspection after
  a runtime stop/start.
- Visible outcome: four truthful missing/saved provider cards, retained failed-save input, specific
  retry copy, keyboard-opened Feelings, stable 320/390 layouts, German fallback labels, and recovered
  Feeling spectrum were observed on screen.
- Expanded/detail state: each provider region, key dialog, Settings tab order, listbox
  active-descendant, Feelings switch, error state, retry control, and accessibility finding target
  was inspected.
- Persistence/reload result: Feelings off-state survived refresh; four connected-provider states
  survived a fresh browser context and a real runtime stop/start.
- Backend/log/DB confirmation: loopback API responses confirmed key save/delete and Feelings
  recovery; runtime health returned on both user-facing ports; source/build hashes matched. Raw DB
  rows and logs were intentionally not published.
- Final model/runtime wording check: the UI says only `Local credential saved` for invalid-shaped
  synthetic keys and does not claim provider validity; this report does not claim a live model answer.
- Substitution check: focused tests, source inspection, hashes, API outcomes, and production build
  support the browser findings but do not replace the real user path.

| User path | Result | Actual evidence |
| --- | --- | --- |
| Easy Install login/setup handoff | `PASS` after fix | Ten fresh browser contexts, alternating desktop and 390px, reached clean `/c/new` with Connected Accounts visible; a separate fresh registration preserved the setup target through login. The intent is captured before auth navigation, restricted to `/c/new?setup=accounts`, resumed across shell replacement, and cleared on user dismissal. |
| Four-provider empty state | `PASS` | OpenAI, Anthropic, Groq, and Grok (xAI) each showed `No local credential saved`; no experimental subscription control appeared. |
| Settings keyboard focus and Escape | `PASS` | All four key controls entered the dialog focus order; Escape closed a populated key dialog and preserved the missing state. |
| Account-menu keyboard activation | `PASS` after fix | The listbox active-descendant sequence reached Help, Connected Accounts, Feelings, Settings, and Log out. Connected Accounts and Feelings both activated with Enter. |
| Key-save network failure and retry | `PASS` after fix | An aborted `PUT /api/keys` left the dialog open, retained the synthetic input, displayed `Failed to save API key. Please try again.`, then succeeded on retry. |
| Disconnect network failure and retry | `PASS` | An aborted key `DELETE` preserved the saved state, displayed the provider-specific retry message, then removed the key on retry. |
| Disconnect/reconnect all four providers | `PASS` | All four cards moved saved -> missing -> saved using the real browser UI. Invalid-shaped local storage was described only as a locally saved credential; live provider validity was not inferred. |
| Browser and runtime-restart persistence | `PASS` | A fresh browser session saw all four saved states; after a real stop/start and healthy `3180`/`3190` probes, a second fresh session again saw all four. |
| 390px and 320px reflow | `PASS` after fix | Settings stayed open across the breakpoint. Document, dialog, and all four provider regions recorded zero horizontal overflow at both widths. |
| Normal accessibility scans | `PASS` | Settled-state Axe scans reported zero serious/critical findings on the actual Connected Accounts dialog at desktop, 390px, and 320px, and on Feelings at 320px. |
| Forced colors plus dark scheme | `PASS` | Real Chromium reported zero serious/critical findings after the browser applied the media change. A same-JavaScript-task diagnostic reproduced transient pre-paint colors at 0 ms; by 100 ms the native system palette was white on black and clean. The acceptance runner now waits for animations, two render frames, and 100 ms before scanning; no broad contrast override was shipped. |
| German locale resilience | `PARTIAL` | German locale changed existing chat copy and Connected Accounts remained complete with English fallback; no raw `com_*` key appeared. The safe fallback passes, but translations for all new copy are incomplete. |
| Feelings discovery without provider keys | `PASS` | Keyboard-only account navigation opened `/feelings` while all four provider credentials were absent. |
| Feelings refresh and 320px | `PASS` | The off-state switch value survived refresh; the page reflowed at 320px and retained its primary surface. |
| Feelings reduced motion | `PASS` | With `prefers-reduced-motion: reduce`, zero Feelings descendants retained a non-zero animation or transition duration. |
| Feelings backend failure/retry | `PASS` | An aborted Feelings GET displayed `Feelings could not be loaded.`; `Try again` restored the Feeling spectrum. |
| Signed-out Feelings | `PASS` | A fresh signed-out browser context requesting `/feelings` returned to login. |

Private screenshot integrity samples (filenames intentionally omitted): Connected Accounts 320px
`d22c2e86c9b0f7250bdde46d41411320a5617cab8ed317e209d1081f90554fc7`; Feelings 320px
`84cc1fe21f8fca4236fbc4b36ad56450d41f381a51e9625fe0bef4ab7c257aec`.

## Findings

### Defects found and candidate fixes

1. **Settings disappeared on mobile/zoom reflow.** `Nav` returned different desktop and mobile React
   trees, unmounting `AccountSettings`. The candidate now uses one stable sidebar DOM shell across
   the breakpoint. The same failing Playwright path reran with the dialog retained and zero overflow.
2. **Account-menu actions were pointer-only.** Most Ariakit options shared `value=""`, so arrow keys
   left virtual focus on the listbox. Stable internal action values restored active-descendant focus
   and Enter activation without matching on user-facing labels.
3. **Failed key saves falsely closed and toasted success.** `saveUserKey` used fire-and-forget
   `mutate`; the dialog could not observe failure. The candidate awaits `mutateAsync`, preserves the
   input/dialog on failure, and clears only after confirmed success.
4. **Setup intent could disappear before Settings mounted.** Chat-route initialization normalized
   `/c/new?setup=accounts` before startup config and `AccountSettings` were ready. Authentication now
   captures only the exact internal setup destination before navigation, including silent refresh,
   and the session-scoped intent survives shell replacement until user dismissal. Same-document URL
   cleanup avoids a router remount. Ten fresh-context logins plus a fresh registration passed.

No regex, prompt matching, provider-label routing, personal state, or generated App Support edits
were used as product fixes.

## Automated Evidence

- Focused client regression suites: `5` suites, `30` tests passed.
- Production client build: `9,686` modules transformed; Vite build and post-build verification
  passed.
- Built client chunk containing the setup-resume contract SHA-256:
  `56c89f981fb5129ba363d4c46c7beee9286d937c938269542db4ce6f5c2ea6fc`.
- The built chunks contain the stable `connected-accounts` action and key-save error path.
- Candidate source hashes matched the source copied into the VM before the production build.
- The last integrated ledger's substantive stages and five accessibility scans all passed. Its final
  status was tripped by a harness assertion that looked for provider cards immediately after reload
  without reopening Settings. The harness now reopens the real surface; an independent fresh-browser
  check confirmed all four provider states persisted. This was a test-navigation defect, not a
  product-persistence failure.
- A broad client TypeScript check was attempted but is not a usable gate in this checkout: it has
  hundreds of pre-existing package/type drift errors outside these files. Focused tests, production
  build, real browser behavior, source hashes, and the built chunk are the applicable evidence here.

### Remaining release gaps

- `PASS` in this lane: settled desktop/390/320 and forced-colors accessibility, setup-handoff stress,
  keyboard operation, fault recovery, refresh, and restart persistence.
- `PARTIAL`: complete translation coverage beyond safe fallback.
- `BLOCKED` externally in this lane: actual VoiceOver/screen-reader traversal, native helper dialogs,
  Keychain/TCC prompts, and Intel hardware.
- Not claimed here: live valid/invalid/quota provider answers, signed/notarized immutable payload,
  pristine no-tools install, physical Docker delta, nested commit/parent-pin/built/shipped/installed
  alignment, or public release readiness.

The browser candidate is accepted. Whole-release acceptance remains closed until the external/native
rows are resolved and the exact signed payload is rebuilt and rerun. The restarted VM still showed
the old phrase `deferred by Express` although current parent source and regression tests require
`deferred by Easy Install`; this is direct stale-payload evidence, not a current source defect.

## Public-Safety Review

- Public diff scan found no local home path, synthetic account identifier, password, token, raw
  request/session ID, private screenshot, or runtime dump in this report.
- Raw evidence remains outside the public repo; only status counts and SHA-256 integrity values are
  recorded here.
- The browser used synthetic non-personal data and made no successful external request.
