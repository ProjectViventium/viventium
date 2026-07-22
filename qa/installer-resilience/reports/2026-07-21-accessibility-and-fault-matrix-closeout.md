# Accessibility and fault-matrix closeout — 2026-07-21

## Exact-head browser confirmation — 2026-07-22

The scoped modern-playground result was rerun in real headed Chromium against exact reviewed head
`fd778562af199f7fb503bd4a0d106e22c282b16b` using
`qa/modern-playground-voice/scripts/direct-entry-accessibility-browser-qa.cjs`. The source server was
loopback-only and used an existing dependency tree through a temporary link.

Result: `PASS`. The direct page failed closed with **Open from Viventium** and explained that Voice
must be opened from a Viventium conversation. Keyboard traversal found ten named stops. At
`320 x 760`, document width remained exactly 320 pixels, the first graphic began at `y=40`, full
content remained vertically scrollable, Reduce Motion left zero non-zero animation/transition
durations, and reload preserved the visible state. Browser evidence recorded zero external
requests, failed HTTP responses, and console warnings/errors. The screenshot was visually inspected
and retained only in private QA evidence.

The temporary Next cache peaked at 95 MB and was deleted immediately after the run; temporary source
and dependency links were removed, the loopback server stopped, and the exact component worktree
returned clean. This confirmation remains scoped: it does not claim a real call, audible output,
VoiceOver, native permissions, or signed installed-artifact acceptance.

## Summary

- Result: `PARTIAL`; the scoped source/browser lane passes, while physical and signed-artifact
  acceptance remains blocked.
- Build/source under test: isolated parent release candidate and exact modern-playground nested head.
- Runtime/artifact under test: source-only modern playground plus rebuilt universal helper fallback.
- Environment: headed Chromium on macOS; local Swift and release-test toolchains.
- Tester: Codex independent QA subtask, reviewed by the root release audit.
- Related change: bootstrap announcements, helper semantics, Reduce Motion, and narrow-layout recovery.

This run did not use VoiceOver, TCC, Keychain, Gatekeeper, Docker Desktop, an Intel Mac, a physical
fault, a voice call, or the exact signed/notarized payload.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `INST-020` | `PARTIAL` | Bootstrap/helper source contracts and both Swift packages compiled; helper source/binary digests align. | Helper remains linker/ad-hoc signed with no Team ID. |
| `INST-023` | `PARTIAL` | Headed browser keyboard, forced-colors, narrow-layout, and Reduce Motion checks passed. | Native VoiceOver and permission-dialog interaction were not run. |
| `MPV-028` | `PASS` for scoped direct-entry page | At `320 x 760`, horizontal overflow was zero, the first graphic began at `y=40`, tall content scrolled downward, and retained motion-duration count was zero. | No authenticated call, microphone, LiveKit audio, or installed payload was exercised. |
| `INST-019` | `PARTIAL` | A 300-case synthetic fault/native slice initially passed 296 and correctly failed four stale helper-delivery checks; the five affected checks passed after rebuild. | Physical crash, power, reboot, sleep, and broader resource faults remain open. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `MPV-028` | Open Voice directly at narrow size with forced colors and Reduce Motion, then navigate by keyboard. | Headed Chromium modern playground | `PASS` for scoped page | Ten named keyboard stops; no clipped top content; no horizontal overflow or retained motion. | Exact nested source, browser network/console ledger, CSS/DOM checks, and requirement/case updates agree. | Real call/audio and installed artifact. |
| `INST-020` | Launch Easy Install and understand changing install, cancel, retry, success, and helper status. | Compiled AppKit/SwiftUI source and artifact checks; visible native flow not run | `PARTIAL` | Source exposes bounded status announcements and named helper status semantics. | Both Swift packages compile; universal helper and hash sidecars align. | Developer ID artifact, VoiceOver, TCC/Keychain, and visible native interaction. |
| `INST-019` | Encounter an interrupted or failed install and recover without losing a prior good state. | Synthetic release-test harness | `PARTIAL` | No physical UI claim; four stale-artifact failures were caught before rebuild. | 300 collected cases plus post-rebuild focused passes. | Physical crash/power/resource/network matrix. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Easy Install inclusive native UI and modern Voice direct-entry recovery.
- Requirement: `39_Installer_and_Config_Compiler.md` and `06_Voice_Calls.md`.
- Use case: keyboard/narrow/forced-colors/Reduce Motion setup; changing native status and recovery.
- QA case: `INST-020`, `INST-023`, `INST-019`, and `MPV-028`.
- Expected result: content remains perceivable and operable; motion preference is honored; changing
  native status is announced; stale helper artifacts fail closed.
- Actual evidence: scoped browser and compilation/artifact checks pass after the fixes.
- Remaining gap or fix: run the exact Developer ID/notarized installed artifact with VoiceOver,
  Keychain/TCC, Intel, and physical failure/recovery conditions.

## Full-View Evidence Checklist

| Evidence surface | Required question | Evidence / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Voice requirement plus installer `INST-019`, `INST-020`, `INST-023`, and voice `MPV-028`. |
| Code owning path | Which code path owns the behavior? | Bootstrap AppKit controller, helper SwiftUI menu, and modern-playground layout/global CSS. |
| Docs and nested docs/repos | Which docs or nested repo docs define the expected behavior? | Voice and installer requirements plus installer/modern-playground case catalogs. |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | Release tests, Swift builds, TypeScript/Prettier, and headed browser automation. |
| Local/external prerequisite state | Which required dependency was proven healthy or degraded? | Source-only loopback web server was healthy; LiveKit, provider auth, and signed native services were deliberately absent. |
| Logs | Which sanitized logs confirm or contradict the result? | Browser console had zero warnings/errors; network requests were loopback-only. |
| DB/state/persistence | Which state confirms the result? | Browser media/viewport state confirmed forced colors and Reduce Motion; no DB was applicable to this direct-entry page. |
| Generated/shipped artifact | Which artifact was inspected? | Rebuilt universal helper is `arm64` + `x86_64`; source and binary digest sidecars match. It is not a release signature. |
| Real user path | Which path was used like a user? | Headed Chromium direct-entry page with keyboard navigation at desktop and `320 x 760`. |
| Visual/UX comparison | Does the visible result match expected behavior? | Yes for the scoped page: no clipping/overflow, named stops, forced colors, and zero retained motion. |
| Not run / blocked | Which surface was not run? | VoiceOver, native dialogs, TCC/Keychain, login/reboot/sleep, physical faults, Docker Desktop, Intel, real call/audio, and signed installed artifact. |

## User-Grade Evidence

- Surface exercised: headed Chromium modern Voice direct-entry page.
- Real user path: open the page, traverse ten named keyboard stops, apply forced colors and Reduce
  Motion, resize to `320 x 760`, and inspect the visible setup/recovery surface.
- Visible outcome: the first graphic remained visible at `y=40`; content grew and scrolled downward;
  horizontal overflow and retained motion durations were zero.
- Expanded/detail state: direct-entry recovery guidance remained visible and the logo link resolved
  by role and accessible name.
- Persistence/reload result: the scoped preferences and layout remained correct after page reload;
  authenticated call/session persistence was not applicable and was not claimed.
- Local/external prerequisite state: loopback source server healthy; LiveKit/audio/provider/native
  prerequisites intentionally unavailable for this scoped lane.
- Evidence retrieval classification, if applicable: local prerequisite unavailable for real voice
  and signed-native paths.
- Fallback path, if applicable: no fallback substituted for the blocked VoiceOver, audio, or native
  paths; they remain explicit gaps.
- Backend/log/DB confirmation: zero browser console warnings/errors and loopback-only requests; no DB
  state applied to the direct-entry page.
- Final model/runtime wording check: the page explains that Voice must be opened from a Viventium
  conversation and does not claim a call is ready.
- Substitution check: browser UI proves only the browser surface; source, builds, hashes, and tests
  support but do not replace VoiceOver, physical-native, audio, or installed-artifact evidence.

## Automated Evidence

```bash
python -m pytest tests/release/test_native_bootstrap_ui.py tests/release/test_macos_helper_install.py tests/release/test_playground_identity.py -q
swift build --package-path apps/macos/ViventiumBootstrap
swift build --package-path apps/macos/ViventiumHelper
npx tsc --noEmit
npx prettier --check components/app/app.tsx styles/globals.css
```

Results: 37 focused post-fix tests passed; playground contracts passed `11/11`; both Swift packages,
TypeScript, Prettier, and diff checks passed. The browser produced ten named keyboard stops, zero
console warnings/errors, zero horizontal overflow, zero retained motion durations, and loopback-only
requests. Temporary builds and the source server were removed/stopped after evidence capture.

## Findings

- Defects: missing native announcements, unnamed helper glyph/disabled-button status semantics,
  retained browser motion, and narrow-layout clipping were fixed.
- Regressions: four stale helper-artifact checks correctly failed after source change and passed only
  after the universal helper was rebuilt.
- Flakes: none observed in the focused reruns.
- Environment issues: no Developer ID identity or signed/notarized artifact; physical relay was
  unavailable.
- Residual risks: VoiceOver/TCC/Keychain/Gatekeeper; login/reboot/sleep/crash/power; MDM/no-admin;
  wider resource/network and Docker Desktop faults; Intel; localization; exact installed artifact;
  and real voice/audio.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
