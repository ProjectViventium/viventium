# Native Feelings Navigation QA Run - 2026-07-19

## Summary

- Result: **PASS** for the running-stack user path; **PARTIAL** for the stopped-stack
  start-and-open continuation and public publisher trust.
- Build/source under test: isolated current-public-baseline helper source with direct `/feelings`
  navigation and the matching universal prebuilt.
- Runtime/artifact under test: clean isolated helper installation using synthetic local state.
- Environment: isolated macOS QA state beside, but not inside, the established runtime.
- Tester: Codex with native accessibility inspection and browser verification.
- Related change: first-level `Open Feelings`, path-aware browser opening, and stopped-state
  confirmation.

No private desktop screenshot, account value, raw conversation, credential, hostname, or
machine-local path is published here.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `EMO-049` | PARTIAL | Source/prebuilt hash and strings, native menu inspection, browser route | Host presence passed; public Developer ID/notarization was outside this run. |
| `EMO-UC-038` | PARTIAL | Native menu action, browser result, stopped-state confirmation, helper log | Running path passed; full stopped-stack launch was intentionally not run. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `EMO-UC-038a` | Open Feelings while Viventium is running | Installed native V menu and browser | PASS | Menu showed `Open Feelings`; the action opened a tab titled `Viventium Feelings` on `/feelings`. | Helper source/prebuilt strings and HTTP `200` agreed with the visible route. | None for this local path. |
| `EMO-UC-038b` | Open Feelings while Viventium is stopped | Installed native V menu and confirmation dialog | PARTIAL | The dialog explained that Viventium was stopped and offered `Start and Open Feelings` or `Cancel`. | Helper log showed stopped state; source wired the affirmative action to `startStack(openPath: "/feelings")`. | The affirmative full-stack start/open continuation was not run. |
| `EMO-UC-038c` | Keep using the generic Open action | Installed native V menu | PASS | `Open` remained present beside the additive Feelings action. | Source contract and menu enumeration agreed. | None. |
| `EMO-UC-038d` | Relaunch after the isolated check | Installed helper | PASS | The isolated helper exited and the pre-existing helper was restored. | Process-path comparison confirmed only the prior helper remained. | No private process path is published. |

## Traceability

`native V menu -> Open Feelings -> /feelings -> live Feelings surface`

- Feature: Feelings discovery from the native macOS status menu.
- Requirement: `docs/requirements_and_learnings/54_Emotional_Cortex_And_Feeling_State.md`.
- Use case: a user opens Feelings without knowing its URL, whether the stack is running or stopped.
- QA case: `EMO-049` and `EMO-UC-038`.
- Expected result: running opens immediately; stopped asks before starting and then opens the same
  route; generic Open remains available.
- Actual evidence: running route and stopped confirmation passed on the real surfaces.
- Remaining gap or fix: run the affirmative stopped-stack continuation on a disposable target;
  public release also requires a Developer ID-signed and notarized immutable helper artifact.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which contract is proven? | Doc 54, `EMO-049`, and `EMO-UC-038`. |
| Code owning path | Which code owns it? | `ViventiumHelperApp.swift`: `openFeelings`, path-aware `startStack`, and `openBrowser`. |
| Docs and nested docs/repos | What defines expected behavior? | Doc 54 plus `qa/emotional-cortex/cases.md`. No nested repo owns the native menu. |
| Scripts or harnesses | What exercised it? | Helper build/install checks, native accessibility inspection, browser route check, and focused release tests. |
| Local/external prerequisite state | What was healthy or degraded? | Isolated local stack was healthy for the running path; production signing/notarization was unavailable. |
| Logs | What confirms the result? | Sanitized helper state transitions confirmed running/stopped selection and restoration. |
| DB/state/persistence | What confirms persistence? | No DB mutation is owned by this navigation action; isolated helper state was removed and the prior helper process restored. |
| Generated/shipped artifact | What artifact was inspected? | Matching universal prebuilt and clean installed local-QA helper; publisher provenance was not proven. |
| Real user path | What was used like a user? | Native V menu, stopped-state macOS dialog, and browser `/feelings` route. |
| Visual/UX comparison | Did visible and supporting evidence agree? | Yes for the running action, modal copy, additive generic Open action, and route. |
| Not run / blocked | What remains? | Affirmative stopped-stack start/open, Developer ID signature, Gatekeeper, notarization, and staple verification. |

## User-Grade Evidence

- Surface exercised: installed native macOS V menu, native confirmation dialog, and browser.
- Real user path: click `Open Feelings` while running; repeat while stopped and inspect/cancel the
  explicit confirmation.
- Visible outcome: the running action opened the live Feelings page; the stopped action offered a
  truthful start-and-open choice.
- Expanded/detail state: menu states and the full stopped-state dialog/button set were inspected.
- Persistence/reload result: isolated helper termination and restoration of the prior helper were
  confirmed; the navigation action owns no user FeelingState mutation.
- Local/external prerequisite state: local stack healthy for the running path; publisher signing and
  notarization unavailable.
- Evidence retrieval classification, if applicable: not applicable; this path performs navigation,
  not provider retrieval.
- Fallback path, if applicable: the generic `Open` action remained available.
- Backend/log/DB confirmation: sanitized helper logs and HTTP `200` supported the visible result;
  DB evidence is not applicable because the action does not mutate state.
- Final model/runtime wording check: native copy accurately distinguished running and stopped state
  and did not promise that a cancelled start had completed.
- Substitution check: logs, HTTP, source, strings, and tests support the native/browser evidence;
  they do not replace the unrun affirmative stopped-stack continuation or publisher-trust proof.

## Automated Evidence

```bash
# Historical run recorded for this candidate:
python3 -m pytest \
  tests/release/test_feelings_contract.py \
  tests/release/test_feelings_navigation_contract.py \
  tests/release/test_macos_helper_install.py \
  tests/release/test_native_stack_helpers.py -q

./scripts/viventium/build_macos_helper_fallback.sh
file apps/macos/ViventiumHelper/prebuilt/ViventiumHelper-universal
```

- Focused release tests: **36 passed, 0 failed** in the historical run.
- Full-platform reaction boundary tests: **31 backend** plus **18 API-package** Feelings tests passed.
- Helper architecture: universal `x86_64` plus `arm64`.
- Local artifact integrity: source and binary digests matched the exact prebuilt.
- Public artifact trust: **not proven**; the local-QA artifact was not a Developer ID-signed,
  notarized, stapled release.

## Findings

- Defects: none on the exercised running-stack navigation path.
- Regressions: generic `Open` remained available; no navigation regression observed.
- Flakes: none recorded.
- Environment issues: a second heavy stack was deliberately not started beside the established
  runtime.
- Residual risks: affirmative stopped-stack continuation and public signed/notarized artifact remain
  unaccepted. Source/tests cannot substitute for those gates.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
