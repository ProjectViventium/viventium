# Modern Playground Default Release Regression — 2026-07-21

## Summary

- Result: `PASS` for scoped source identity, stale-listener rejection, and candidate browser path.
- Source under test: isolated parent release candidate and clean modern-playground candidate.
- Runtime under test: clean modern candidate on a temporary loopback QA port with source ref
  `4d4d78c974e3e7baec9b049ce91e194b5b808740`.
- Visible result: Viventium's optimized `agent-starter-react` application rendered, not the legacy
  `agents-playground` UI.
- Boundary: final merged parent pin and fresh-install artifact identity remain release-wide gates.

The classic repository was inspected because the release audit covers every nested repository. It
remains an explicit Custom Settings fallback and is not a default install dependency.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `MPV-010` | `PASS` | Exact `/api/health` verifier, real Chromium, compiler/component-selection tests | Modern Viventium UI and its exact source ref were proven; wrong classic and stale modern identities were rejected. |
| `MPV-UC-008` | `PASS` | No-config, modern, classic, disabled selection matrix | Classic is selected only explicitly. |
| `MPV-027` | `PASS` | Failure-first regression and isolated headed Chromium | Direct navigation now explains the disabled safe state and how to recover. |

## Natural User Use Case Checklist Run

| Use case | Natural user action | Real surface used | Result | Visible evidence | Supporting evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| Default voice UI | Open the playground after enabling Voice with defaults. | Real Chromium and clean candidate server | `PASS` | Title `Viventium Voice Assistant`, Viventium branding, modern listening/speaking controls, and expanded Listening provider choices. | Exact health identity, clean component tree, compiler and selector tests. | Repeat source-to-installed identity check after final merged parent pin. |
| Wrong/stale listener | Start or upgrade while classic or an older modern listener occupies the selected surface. | Synthetic exact health endpoints and verifier | `PASS` | Not applicable; the verifier rejected both before the browser path could be called healthy. | Variant and source-ref mismatch tests plus launcher contract. | Final installed upgrade run remains required. |
| Explicit classic fallback | Select classic mode deliberately. | Config/compiler and component selector | `PASS` | Not opened because the scoped question was default drift. | Only the explicit classic value selects the legacy component. | Separate classic unhappy-path QA remains owned by its fallback review. |
| Voice disabled | Install with Voice disabled. | Component selector | `PASS` | No playground is expected. | Selector excludes both playground components. | None for this scoped rule. |
| Direct URL without a call session | Open the Modern Playground without first choosing Voice in a conversation. | Isolated headed Chromium with no call-session parameters or standalone agent | `PASS` | The disabled action is followed by `Open Voice from a Viventium conversation. This page joins that conversation securely.` | Exact source identity, zero browser warning/error, and no non-loopback/backend request. | Authenticated call and audible delivery remain separate cases. |

## Traceability

`modern voice UI -> voice and installer requirements -> default voice-capable install -> MPV-010 -> modern selected and visibly rendered -> process/browser/test evidence -> merged pin proven; exact fresh-install identity still required`

- Feature: default LiveKit voice playground selection.
- Requirement: voice requirements and installer requirement 39.
- Use case: `MPV-UC-008`.
- QA case: `MPV-010`.
- Expected result: default/no-config installs select `agent-starter-react`; classic requires explicit
  selection.
- Actual evidence: source-bound runtime identity, wrong/stale rejection, real browser rendering, and
  focused release tests.
- Remaining gap: rebuild the parent artifact and repeat installed/fresh-install identity comparison.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | What defines acceptance? | Voice requirements, installer requirement 39, `MPV-010`, `MPV-UC-008`. |
| Code owning path | What selects the component? | Config compiler, bootstrap component selector, public CLI, full-stack launcher. |
| Docs and nested docs/repos | Do roles agree? | Requirement 52 identifies `agent-starter-react` as modern/default and `agents-playground` as classic/default-off. |
| Scripts or harnesses | What ran? | `verify_playground_identity.py`, focused release tests, and real Chromium. |
| Local/external prerequisite state | What was available? | Running loopback modern playground; no provider credential or microphone was needed for selection proof. |
| Logs | What corroborated the UI? | No private runtime log was required or published. |
| DB/state/persistence | What state was inspected? | None; account/chat/call persistence was outside the selection question. |
| Generated/shipped artifact | Was release identity final? | Candidate source ref was proven; final signed/notarized installed artifact is not yet available. |
| Real user path | What user surface ran? | Chromium opened the standard playground URL and rendered the modern Viventium home view. |
| Visual/UX comparison | Did it match? | Yes: Viventium title, branding, and modern provider controls; no legacy LiveKit Agents Playground. |
| Not run / blocked | What remains? | Audible call, microphone/TCC, Intel, and final signed artifact are separate cases. |

## User-Grade Evidence

- Surface exercised: real Chromium against the running Modern Playground.
- Real user path: opened the temporary loopback candidate URL as a user.
- Visible outcome: Viventium's branded optimized voice UI rendered.
- Expanded/detail state: the Listening picker expanded and showed OpenAI, AssemblyAI, and Whisper.
- Persistence/reload result: refresh preserved the visible modern Viventium surface; no account or
  provider state was changed.
- Backend/log/DB confirmation: `/api/health` reported the expected modern variant and exact source
  ref; no private DB or account state was read.
- Final model/runtime wording check: the visible title said `Viventium Voice Assistant`; it did not
  claim to be LiveKit Agents Playground.
- Substitution check: process inspection and automated tests support, but do not replace, the real
  browser result. The browser result does not replace final installed-artifact identity or audible
  voice QA.

The private screenshot and process details remain outside the public repository. They contain no
test-account conversation or personal message content and are not a release artifact.

## Automated Evidence

```text
Exact playground identity tests passed after a failure-first implementation.
Focused selector, compiler, CLI, and optional-runtime provenance tests passed.
Real Chromium opened the clean candidate, expanded Listening providers, and refreshed successfully.
```

## Findings

- Defect found and fixed: the launcher and CLI previously accepted a generic successful HTTP
  listener as the selected playground, so a stale classic server could be mislabeled and reused.
  Health now requires exact product, surface, variant, and component source-ref identity.
- UX defect found and fixed: direct navigation previously showed a disabled action without saying
  why. The fail-closed state now tells the user to open Voice from a Viventium conversation, and the
  isolated browser regression proves the guidance without reading provider or personal state.
- Drift risk: a complete component lock inventories the classic fallback for reproducibility. Lock
  presence must not be confused with bootstrap selection or activation.
- Upgrade drift fixed: installed starts no longer preserve an arbitrary clean component branch head;
  the reviewed component lock owns normal installed-runtime alignment. Development activation keeps
  its explicit current-checkout behavior.
- Established versus candidate modern tree: the established optimized tree was clean. The isolated
  candidate preserves it and adds reviewed dependency and repository-hygiene changes only.
- Residual risk: final merged pin and fresh-install artifact identity still need release-wide proof.

## Post-review call-start hardening

Result: `PARTIAL`, not release acceptance.

- The modern and classic playgrounds now bind the 40-character source ref through Next build
  configuration. Fresh production builds of both current candidates compiled the expected ref
  directly into `/api/health`; the route no longer reads the launch-time source-ref variable.
- LibreChat now rejects oversized declared identity responses before reading the body and bounds
  chunked responses while streaming. It creates no durable call session after a failed identity
  guard.
- The call button maps structured failures to concise inline recovery guidance, connects that copy
  to the retry action with `aria-describedby`, and does not alert raw JSON or deep links.
- Focused evidence: 18 parent identity/startup-guard checks passed; both playground production
  builds passed; 11 classic-playground tests passed. The builds reused the existing isolated
  candidate dependency trees and build directories; no dependency install, clone, VM, Docker image,
  or personal runtime state was created.
- Remaining gap: the available gateway `/health` endpoint starts before worker registration and does
  not prove LiveKit dispatch or selected provider readiness. This pass therefore does not add a
  misleading port probe. Full acceptance still requires the current LibreChat component suite, a
  headed inline-error/retry run, registered LiveKit worker evidence, provider readiness, and an
  audible synthetic call against the final shipped artifact.

## Public-Safety Review

- No username, home path, hostname, account identifier, conversation, token, provider request, or
  personal screenshot is included.
- Public evidence uses component names, test totals, and sanitized behavior only.
- Raw browser/process evidence remains in the designated private QA directory outside git.
