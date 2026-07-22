# Native Bootstrap Finder UX QA — 2026-07-20

## Summary

**PARTIAL** for the local source candidate. The prior Finder behavior—running a terminal-oriented
launcher with no visible progress or recovery surface—is covered by a new native AppKit Easy Install
window and automated source/compiled contracts. The required headed interaction is still
**BLOCKED** because the local desktop was locked during Computer Use; this report does not generalize
source/build success into visible macOS acceptance or public-release readiness.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `INST-020` | PARTIAL | Compiled bootstrap, release build, strict ad-hoc signature check | Headed helper/installer interaction and publisher trust remain blocked. |
| `INST-023` | PARTIAL | AppKit accessibility source contract and compiled executable | VoiceOver, visible focus, keyboard, and Reduce Motion interaction remain blocked. |

## Traceability

`Finder Easy Install -> 39_Installer_and_Config_Compiler.md -> INST-020/INST-023 -> native AppKit window -> source/compiled evidence -> locked-desktop gap`

| Feature | User outcome | Case | Expected | Actual evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- |
| Finder-launched Native Bootstrap | A novice sees progress, safe Cancel, failure/Retry, and success/Open Viventium instead of invisible stderr | `INST-020`, `INST-023` | Accessible bounded native window; CLI automation unchanged | AppKit source contract, real release build, compiled headless fixture, ad-hoc signature verification | Headed layout/control/VoiceOver/Reduce Motion run on exact candidate |

## Full-View Evidence Checklist

| Evidence surface | Required question | Evidence / sanitized pointer |
| --- | --- | --- |
| Feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap | Is the Finder path traceable end to end? | Source/build evidence maps to installer cases `INST-020` and `INST-023`; headed evidence remains explicitly BLOCKED. |
| Real user path | Was the Finder-launched installer used visibly? | BLOCKED because Computer Use reported the Mac was locked; compiled CLI execution cannot replace required user-path evidence. |
| Docs and nested docs | Is current product truth recorded? | Installer requirement 39, living installer cases, README, and this report were updated. |
| Logs, DB/state/persistence | Did supporting evidence contradict the product result? | Exact synthetic child arguments, stdout, stderr, and exit status were verified; no product DB or personal runtime state was used. |
| Generated/shipped artifact verification | Was an exact distributable proven? | Local release build and disposable ad-hoc bundle verification passed; Developer ID/notarized shipped artifact remains BLOCKED. |

## What Changed

- A no-argument launch selects one foreground AppKit window titled **Easy Install Viventium**.
- The window shows a textual stage, progress, bounded detail, cooperative Cancel, visible failure,
  Retry, Quit, success, and Open Viventium.
- GUI mode sends child stdout/stderr to the null device and renders only fixed product copy. It does
  not collect or display raw commands, paths, logs, errors, secrets, or token-bearing URLs.
- Cancel sends an interrupt once, disables repeated cancellation, and reports that it is finishing a
  safe checkpoint. It does not force-terminate the child.
- Return activates the current primary action; Escape requests Cancel while work is active. Standard
  controls carry accessibility labels/help. Reduce Motion replaces animated indeterminate progress
  with a static progress state while retaining the textual stage.
- Any invocation with command-line arguments remains headless and uses only the bundled
  `Contents/Resources/runtime/python/bin/python3` path.

The accessibility choices follow Apple's
[AppKit accessibility guidance](https://developer.apple.com/documentation/appkit/accessibility-for-appkit),
[accessibility-label API](https://developer.apple.com/documentation/appkit/nsaccessibilityprotocol/setaccessibilitylabel(_:)),
and [Reduce Motion signal](https://developer.apple.com/documentation/appkit/nsworkspace/accessibilitydisplayshouldreducemotion).
Cooperative Cancel uses Foundation's documented
[`Process.interrupt()`](https://developer.apple.com/documentation/foundation/process/interrupt()).

## User-Grade Evidence

- Surface exercised: compiled Viventium Bootstrap CLI plus the Finder-launched native installer source; the headed AppKit surface was attempted through Computer Use and blocked by the locked Mac.
- Real user path: Finder launch, visible progress, Cancel, failure/Retry, success/Open, and Quit were the required installer journey; no visible interaction was claimed because the session could not be unlocked safely.
- Visible outcome: BLOCKED; no window screenshot or accessibility-tree observation was captured. The compiled UI contract is supporting evidence only.
- Expanded/detail state: BLOCKED; bounded detail, failure, success, and recovery states compile but were not visually expanded or inspected.
- Persistence/reload result: the UI owns no durable user state; exact headless child completion and exit propagation passed, while headed cancel/retry persistence remains blocked.
- Backend/log/DB confirmation: the compiled fixture proved exact arguments, stdout, stderr, and exit `23`; no database, personal logs, or runtime account was accessed.
- Final model/runtime wording check: source copy consistently says Easy Install, preserves last-known-good recovery truth, and does not display child output; visible wording remains unconfirmed.
- Substitution check: automated source/build/CLI evidence cannot replace the missing headed installer, VoiceOver, focus, Reduce Motion, cancel/retry, and success/Open run.

## Automated Evidence

| Check | Result | Evidence |
| --- | --- | --- |
| TDD reproduction | PASS | The RED state was observed: the new source contract initially failed for missing AppKit, Easy Install title, progress, Retry/Open, and Reduce Motion handling. |
| Focused Bootstrap suite | PASS | `4 passed`; source UX/privacy contract, compiled executable forwarding fixture, and foreground-app plist contract. |
| Existing bundled-Python and candidate workflow contracts | PASS | `2 passed`; exact bundled interpreter ownership and dual-architecture producer contract. |
| Compiled CLI semantics | PASS | Synthetic bundled interpreter received `-B`, the exact installer path, `--self-check`, and the synthetic value in order; stdout and stderr matched exactly; wrapper exit status was `23`. |
| Release build | PASS | Swift production build completed for the local Apple-silicon host. |
| Local bundle integrity | PASS | Supporting evidence only: the disposable synthetic app bundle passed ad-hoc `codesign --verify --deep --strict`. Gatekeeper rejected the ad-hoc app as expected; this is not Developer ID/notarization evidence. |
| Headed native interaction | BLOCKED | Computer Use reported that the Mac was locked and automatic unlock failed before it could inspect the window or accessibility tree. No password or permission bypass was attempted. |

## Findings

- Fixed: a Finder launch no longer depends on invisible terminal output for progress or recovery.
- Fixed: command-line callers retain exact bundled-interpreter argument, stream, and exit semantics.
- Open: headed native interaction, assistive-technology behavior, publisher signing/notarization,
  and exact shipped-artifact acceptance remain release blockers.

## Happy And Unhappy Path Status

| Path | Status | Notes |
| --- | --- | --- |
| Finder no-argument launch selects GUI | PARTIAL | Automated source and compiled-app checks pass; visible session evidence remains blocked. |
| CLI argument, stream, and exit forwarding | PASS | Real compiled executable and synthetic bundled interpreter. |
| Missing bundled resource | PARTIAL | Produces a bounded Retry/Quit failure state in source; not visually exercised. |
| Long install progress | PARTIAL | Textual stage plus normal/reduced-motion progress branches compile; not visually exercised. |
| Cancel and safe checkpoint wording | PARTIAL | One cooperative interrupt passes in source; no force kill; activation-stage fault run remains required. |
| Nonzero failure and Retry | PARTIAL | Bounded generic failure copy passes in source; no raw child output; visible retry not exercised. |
| Success and Open Viventium | PARTIAL | Fixed loopback client origin passes in source; visible success/open not exercised. |
| Quit, close, and Command-Q while active | PARTIAL | Active termination requests Cancel in source; real focus/window interaction remains required. |
| VoiceOver, keyboard, Reduce Motion | PARTIAL | Labels/help/key equivalents and reduced-motion branch compile; exact native assistive-technology run remains required. |
| Developer ID, notarization, stapling, Gatekeeper | BLOCKED | Requires release credentials/authority and exact immutable candidate. |

## Security Review

Trust boundaries are the signed app bundle, bundled interpreter/script, release CLI arguments, child
streams, and the local browser handoff. GUI mode accepts no user input, executes no path derived from
the window or child output, displays only bounded constants, and opens only a fixed loopback URL.
Headless arguments are intentionally forwarded to the bundled installer's existing parser. No new
network destination, credential store, privilege, package dependency, or updater was introduced.

## Public-Safety Review

- [x] Synthetic paths and values only; no personal user, host, account, or App Support data recorded.
- [x] GUI mode discards raw child output and renders bounded product-owned copy.
- [x] New files passed diff hygiene and private-path, identity, and credential-pattern scans.
- [x] Ad-hoc signing is labeled supporting evidence and not publisher provenance.
- [x] Locked-desktop and external release-authority blockers are stated without substitution.

## Rerun Gate

On an unlocked disposable/headed Mac, assemble the synthetic app outside the public repository and
run every step in the `INST-020` / `INST-023` procedure. Capture only public-safe window and
accessibility evidence. Then repeat on the exact Developer ID signed/notarized candidate across
normal, Reduce Motion, VoiceOver, cancellation checkpoints, failure/Retry, success/Open, and Quit.
Until that run passes, the correct status is **PARTIAL**, not done.
