# Claude Fable 5 Extra Express Review Reconciliation — 2026-07-18

## Boundary And Verdict

After Codex completed its evidence-backed implementation proposal, Claude Desktop was given the
same user request, the current Express audit package, the relevant requirements, exact owning files,
VM evidence, provisional conclusions, and alternative explanations. The session used Fable 5 at
Extra effort in review-only mode. It was explicitly forbidden to edit, commit, push, publish,
connect an account, or mutate personal/local/cloud state. Claude made no changes.

Claude verdict: **PARTIAL**. Architecture passed after the documented corrections; the release
conclusion remained partial.
It independently supported the shared Express profile, backward-compatible custom path, exact
Mongo pinning/security direction, zero-credential first boot, current-attempt log scoping, truthful
startup gating, and the conclusion that the public bootstrap still installs mutable source rather
than an immutable signed payload.

## Finding Reconciliation

| Claude finding | Disposition | Evidence |
| --- | --- | --- |
| Express preflight/start could accept an arbitrary `PATH` Mongo or fall back to Homebrew. | VALIDATED, FIXED | Express now requires the exact app-owned MongoDB `8.0.23`, Developer ID team, version, process arguments, data path, and port. Legacy/custom paths retain their existing flexibility. Two new regressions failed before the correction and pass after it; the live VM restarted through the exact path. |
| LibreChat nested state and parent delivery pin do not match. | VALIDATED, RELEASE BLOCKED | The tested nested HEAD is `a55efcdc4cfc0847877e30c90f76d693ba31cb25` plus uncommitted changes. `components.lock.json` pins its one-commit descendant `f051e431524e394f18cebcd0dda7df1685d328aa`. No commit, repin, build publication, or installed-artifact promotion was authorized. `INST-022` records this as `FAIL`. |
| Older OAuth async work can race and tear down a newer attempt. | VALIDATED, FIXED | Connected Accounts now assigns every flow an attempt identity. Start, poll, popup monitor, manual completion, cancellation, and cleanup ignore stale attempts; poll success also closes its popup. Real Chromium passed two consecutive cancel/retry attempts. |
| Connected-account OAuth could derive a callback origin from the untrusted request `Host`. | VALIDATED, FIXED | The API now requires the explicit connected-account return origin or configured server domain and fails closed otherwise. The focused API suite includes an untrusted-Host regression and passes 11 tests. |
| Signed-out `/feelings` renders a blank page because the component returns `null`. | REFUTED | `AuthContext` owns the silent refresh and `buildLoginRedirectUrl` transition before the protected component renders. The temporary `null` is a loading state. The repeatable real-browser harness now proves a visible login redirect, so no product source change was made for this claim. |
| Broad installer case IDs hide distinct release gates. | VALIDATED, FIXED IN QA CONTRACT | `INST-015` through `INST-024` now separately own signed payload, vanilla Mac, provider lifecycle, restore, fault matrix, macOS helper/security, Docker delta, delivery alignment, inclusive UX, and Node runtime alignment. Each records expected, forbidden, evidence, and current status. |
| The registration-to-`setup=accounts` redirect crosses files without a direct contract test. | VALIDATED, FIXED | A focused client test now proves registration destination persistence through the login boundary and final Connected Accounts handoff. The VM client run passes 7 tests. |
| Focused automation could be mistaken for full-suite evidence. | VALIDATED, WORDING FIXED | The audit now labels the 386-test result as a focused slice and records broad-suite results separately. Neither automation tier substitutes for the missing exact-artifact user paths. |

## Post-Correction User Evidence

- The corrected Express Native source candidate restarted in the disposable Apple Silicon VM.
- Mongo, API, and web listened only on `127.0.0.1`; neither CLI status nor the final startup banner
  advertised the unreachable guest LAN URL.
- Real Chromium registered a new synthetic user, consumed `setup=accounts`, displayed Connected
  Accounts, started OpenAI authorization with HTTP `200`, survived two cancel/retry attempts,
  discovered Feelings in the ordinary control panel, and preserved it through refresh.
- Provider authorization completion and first answer were intentionally not run; no real provider
  credential or grant was used.
- The final bounded client build passed after explicitly allocating the documented build heap. A
  default-heap OOM is retained as evidence that Easy Install must ship a prebuilt payload.
- The final independently guarded parent suite collected 1,024 tests: 1,014 passed, 2 unrelated
  QA-report hygiene tests failed, and 8 skipped. Every Express behavioral test passed. The guard
  also caught and eliminated a test's accidental real-Keychain call.

## Release Meaning

Claude's review strengthens the source candidate but does not change the release decision. The
installer remains `PARTIAL` until the exact signed/notarized payload, truly vanilla Mac, complete
provider lifecycle and persistent answer, full restore, headed helper/Keychain/Gatekeeper path,
fault/accessibility matrices, physical Docker delta, and nested-pin-build-installed alignment pass.

## Verbatim Original-Prompt Completion Re-Review

After the user challenged completion, a new isolated Claude Desktop session received the complete
original prompt, the current evidence packet, provisional `NOT DONE` conclusion, competing
explanation, and exact decision questions. The session visibly showed Fable 5 and Extra effort.
The complete 11,181-character packet was verified in the composer before the explicit Send action,
and the empty composer plus full message preview were verified after submission. An earlier malformed
attempt had submitted only the first paragraph while leaving the remainder in the composer; it was
stopped, discarded, and is not evidence for this review.

Fable used three independent read-only verification agents and returned:

> **`NOT DONE` is the only defensible conclusion.**

Reconciled findings:

| Finding | Disposition |
| --- | --- |
| The history inventory is accurate across local refs, but the new audit/source-candidate package is uncommitted and therefore not a durable release artifact. | CONFIRMED. Preserve selectively and locally before any cleanup; no blanket staging or push. |
| The owner-versus-new-user map is analytical rather than a literal procedural walkthrough. | CONFIRMED. Add both step-by-step persona journeys and execute the existing-user cloned-state lane. |
| The persistent OSS inspiration workspace requested literally does not exist; only disposable shallow inspections and retained research/SHAs exist. | CONFIRMED. Either create a safe persistent research workspace outside the public repo or explicitly agree that disposable clones are the deliverable. |
| Preflight/common/doctor select Node 24 while the launcher still installs and forces Node 20. | CONFIRMED, reproduced by a failing contract, then fixed in source. A properly submitted follow-up review found the optional Skyvern launcher still selected Node 20; a wider local sweep also found the macOS helper path did. The contract was expanded and failed before both were aligned. `INST-024` remains `PARTIAL`: six source surfaces, 90 focused tests, both shell syntax checks, and helper build pass, while exact-artifact process/build/start/restart acceptance remains open. |
| Brain Setup still derives several `Ready` states from configuration rather than a successful live request. | CONFIRMED with nuance: live service probes exist elsewhere, but the user-facing readiness contract remains failed (`INST-009`). |
| The trusted-origin OAuth change, client-side attempt identity/cancel-retry work, registration handoff, and Feelings sidebar entry exist only in the dirty nested LibreChat working tree. | CONFIRMED. The parent pin has older underlying OAuth/Feelings functionality but not the tested hardening/onboarding/sidebar delta. |
| The fail-closed OAuth origin needs an installer-level proof that every supported mode supplies a trusted origin. | CONFIRMED new unhappy path. API tests prove fail-closed behavior; add cross-mode generated/runtime config and browser recovery coverage. |
| `install.experience` is absent from both public example configs, and README does not present the Express journey. | CONFIRMED new front-door gap. The wizard/compiler carry the dirty profile, but the public documentation/preset surfaces do not yet make it discoverable. |
| Pruned Groq/xAI endpoints need a late-key reconfigure test proving they return without reinstalling. | CONFIRMED new lifecycle gap. |
| Meilisearch remains part of the Native core and needs an explicit resource/necessity decision for low-spec Macs. | CONFIRMED new performance/brittleness question. |
| `INST-UC-004` reports an older PASS against a superseded nightly-workflow contract. | CONFIRMED stale acceptance wording; it must show the current contract failure while retaining the historical result as lineage only. |

The physical-machine boundary is unchanged. Headed helper/SMAppService/Keychain/Gatekeeper and the
Native-versus-Docker delta remain blocked until a safe headed physical target is available. A
complete synthetic restore, a pristine Tart base, provider grant/first answer, readiness truth,
Node alignment, documentation/preset gaps, and the late-key lifecycle can proceed locally without
touching the shared personal Mac.
