# Pristine Native Easy Install Exploratory QA — 2026-07-20

## Summary

**FAIL.** The candidate was rejected after a disposable, vanilla Apple-silicon macOS 26.5 guest proved that
the Native payload can install, start, restart, reinstall, preserve its local data through
uninstall/recovery, and render the main LibreChat and Feelings experiences without Homebrew,
Docker, Node, npm, pnpm, uv, or selected Command Line Tools. The same headed-browser run exposed
release-blocking first-admin, closed-registration, password-recovery, and Connected Accounts
defects. The parent Native source was corrected after this payload was assembled, so these results
are exploratory evidence and cannot accept the replacement candidate.

No external provider request, cloud mutation, publication, message, personal credential, or
personal data was used. All account data used the reserved `.invalid` domain. Raw logs,
screenshots, guest state, credentials, and machine-specific paths remain in the private release-QA
area and are intentionally excluded from this public repository.

## Scope Run

| Surface | Evidence-backed state |
| --- | --- |
| Nested LibreChat source | Commit `cf2551b6bc395d3c45600d0baee5bff5d6e236b9`, tree `337c8b0f6c41f309a003c039cff321bb1008e670`, base `7c702629599f5b229f9b49f6ea2f458c6981581a` |
| Source identity | 3,167 tracked LibreChat files compared byte-for-byte; zero mismatches and a clean nested worktree |
| Bundled runtimes | Node 24.16, MongoDB 8.0.23, Python 3.12.13 |
| Production dependency proof | Production install/prune, runtime-load guard, direct `mongodb` dependency check, and production audit passed; audit reported zero vulnerabilities |
| Whole-payload public safety | 133,602 files and 1,972,665,543 bytes scanned; no rejected commit, producer-local identity/path, credential pattern, runtime evidence, or symlink was found |
| Guest | Fresh clone of an untouched vanilla macOS image; dedicated QA directory and synthetic account only |
| Host safety | Read-only payload share, separate writable evidence share, pinned fresh SSH host key, no personal runtime or normal install location touched |

The normal assembler completed copying, metadata, safety scanning, and Apple code-path discovery,
but its sequential Mach-O classification had not completed after more than ten minutes. Because
the parent runtime scripts had already become stale, the exploratory payload was manually finalized
with the already-generated 21-path Apple code list and ad-hoc signatures. This is an additional
reason the payload is rejected. The source-frozen replacement must complete the normal assembler
without this workaround.

## Traceability

`Native Easy Install -> requirement 39 -> INST-014/016/017/028 -> pristine no-tools user journey -> rejected exact payload evidence -> four source corrections -> mandatory replacement run`

## Full-View Evidence Checklist

| Evidence surface | Required question | Evidence / sanitized pointer |
| --- | --- | --- |
| Real user path | Did a novice complete install through first answer? | FAIL: real installer/browser first-admin and account onboarding were exercised, but first-admin submission and Connected Accounts failed. |
| Docs and nested docs | Is product truth tied to the exact source? | Exact LibreChat commit/tree and parent requirements/cases are recorded; the parent source changed afterward, so the artifact is rejected. |
| Logs, DB/state/persistence | Do supporting layers agree? | Loopback health, API registration boundary, preserved synthetic login/Mongo state, restart/reinstall, and doctor evidence agree with the reported partial lifecycle. |
| Generated/shipped artifact verification | Was the normal immutable candidate path completed? | No. The stale exploratory payload required a manual local-QA finalization and cannot replace normal producer, signing, or shipped-artifact evidence. |
| Public/private safety | Was personal state exposed or changed? | No personal state was accessed; public reporting contains only synthetic values and sanitized counts/hashes. |

## User-Grade Evidence

- Surface exercised: Native installer CLI, headed Chromium browser, LibreChat login/settings/chat shell, Feelings, lifecycle commands, and loopback health surfaces in a disposable vanilla macOS guest.
- Real user path: no-tools inventory -> copy -> install -> start -> first-admin form -> downstream synthetic login workaround -> settings/Feelings -> restart/reinstall -> recovery/upgrade/continuity/uninstall checks.
- Visible outcome: the first-admin page visibly failed to submit, Connected Accounts was absent, Feelings rendered and persisted after refresh, and closed `/register` misleadingly retained an operable form.
- Expanded/detail state: Account settings and the nine-band Feelings page were opened; browser console/network evidence confirmed the silent registration `403` and CSP-blocked setup request.
- Persistence/reload result: synthetic login and Feelings state survived refresh/restart; preserved config and MongoDB recovered after uninstall/reinstall.
- Backend/log/DB confirmation: API/web/hostile registration returned `403`; doctor passed after restart/reinstall; loopback listeners, runtime pointer removal, and preserved synthetic Mongo state matched the visible lifecycle.
- Final model/runtime wording check: upgrade and continuity commands failed truthfully, but the stale first-admin/registration/account UI contradicted the supported novice journey; the candidate is rejected.
- Substitution check: downstream workaround, source tests, logs, and separate provider QA cannot replace an untouched replacement-payload first-admin, Connected Accounts, provider-answer, and persistence run.

## What Was Actually Run

| User path | Actual result | Evidence / remaining work |
| --- | --- | --- |
| Preinstall inventory | **PASS** | Homebrew, Docker, Node, npm, pnpm, and uv absent. macOS shipped Python/xcodebuild/clang stubs were present, but Command Line Tools were absent or unselected. All scoped Viventium locations were absent. |
| Payload copy | **PASS** | 135 seconds from the read-only share into the dedicated guest QA directory. |
| Native install | **PASS** | One second; no package manager or developer-tool installation occurred. |
| Native start and health | **PASS** | Ready in 17 seconds; API, web, and MongoDB were healthy and listening only on their intended loopback surfaces. |
| First-admin browser handoff | **FAIL** | The real page rendered, but its Content Security Policy omitted `connect-src 'self'`, so Chromium blocked submission. The stale form also omitted the backend-required confirmation password. No visible recovery message appeared. |
| First-admin happy path | **BLOCKED** | Could not pass through the supported browser surface. A synthetic admin was provisioned directly in the disposable guest solely to explore downstream paths; this workaround is not acceptance evidence. |
| Login and main chat shell | **PASS** | Headed Chromium logged in after the documented workaround and rendered the real LibreChat UI. |
| Connected Accounts | **FAIL** | The Account settings contained no Connected Accounts section because Native did not project a secret-free capability flag into startup configuration. Setup could not guide the user to a provider. |
| Useful provider answer | **BLOCKED** | With Connected Accounts absent and cloud calls forbidden, no supported synthetic-provider answer could be produced from this exact payload. The separate integrated loopback-provider QA does not substitute for pristine-payload proof. |
| Feelings navigation | **PASS** | After the documented workaround, the control-panel Feelings button opened the nine-band page. Enabling Feelings showed the awake state, and the enabled state persisted after refresh. |
| Closed ordinary registration | **FAIL** | After first-admin closure, `/register` still displayed an operable registration form. Submit returned HTTP 403 only in the browser console; the page showed no visible error or route-level guidance. |
| Registration boundaries | **PASS** | The API-boundary checks passed: direct API, web proxy, and hostile-origin registration attempts each returned HTTP 403 after closure. The backend was safe even though the visible UX was misleading. |
| Restart and login persistence | **PASS** | Restart completed in 9 seconds; doctor passed and the synthetic login remained valid. |
| Reinstall and login persistence | **PASS** | Reinstall completed without resetting the account; start and login passed. |
| Password recovery | **FAIL** | The command was missing in the candidate: it had no supported Native password-reset command. A bundled local one-time reset-link command was added to source after assembly and must be proven in the replacement payload. |
| Upgrade without signed bootstrap | **PASS** | The path failed closed: the check reported `native_signed_bootstrap_required`; an attempted restart upgrade failed without mutating the install. |
| Snapshot / restore | **PASS** | The truthful-refusal behavior passed, while the release gate remains open: both commands failed with explicit messages that public transactional continuity integration is not yet available. No false success was reported, but the required restore lifecycle remains unproven. |
| Uninstall preservation | **PASS** | Runtime pointer removed while config and MongoDB data remained. |
| Reinstall after uninstall | **PASS** | Install/start recovered the preserved account; login and doctor passed, then the stack stopped cleanly. |
| Post-lifecycle host inventory | **PASS** | No Homebrew, Docker, Node, npm, pnpm, uv, or selected Command Line Tools appeared. Work remained confined to the dedicated QA directory. |

## Automated Evidence

- Exact source identity compared 3,167 tracked LibreChat files with zero mismatches.
- Production dependency install/prune/load checks and production vulnerability audit passed.
- Whole-payload safety scanning covered 133,602 files and 1,972,665,543 bytes with no rejected
  producer identity/path, credential pattern, runtime evidence, or symlink.
- Public-safety regression for this report passed after sanitization.
- These checks support the findings but do not accept the failed or worked-around browser path.

## Findings

- Release blocker: supported first-admin submission was broken by CSP and payload mismatch.
- Release blocker: Native did not expose the Connected Accounts capability or a provider-answer path.
- Release blocker: stopped-stack Native password recovery was absent.
- UX defect: closed ordinary registration retained a form and hid the backend rejection.
- Passed supporting lifecycle: no-tools start, loopback health, restart/reinstall persistence,
  fail-closed upgrade, truthful continuity refusal, preserved-data uninstall, and cleanup.

## Source Corrections Triggered By This Run

The run produced four independent product corrections after candidate assembly:

1. a cookie-bound, clean first-admin browser handoff with `connect-src 'self'`, confirmation
   password, visible progress/error states, retry, and replay protection;
2. interception of ordinary `/register` plus a truthful closed-state redirect;
3. a bundled local `password-reset-link` recovery command using bundled Node/MongoDB and minimal
   environment projection; and
4. a secret-free Native Connected Accounts capability source so setup can expose provider
   onboarding before any key exists.

Focused source tests are supporting evidence only. None of these corrections exists in the rejected
payload evaluated here, so the final user journey must be rerun from a newly assembled immutable
candidate. The Connected Accounts correction also requires four sanitized LibreChat changes (the
config projection, capability helper, and active helper/route regressions) that are not part of
`cf2551b6bc395d3c45600d0baee5bff5d6e236b9`; a new nested commit and parent pin are therefore
required before the replacement build.

The current composite source passed 185 parent Native assembler/compiler/onboarding tests and 29
focused LibreChat capability/config/key/direct-auth tests. A direct source-worktree probe under the
exact Native capability plus OpenAI/Anthropic `user_provided` sentinels projected both endpoints as
user-provided. Formatting, diff-check, and a targeted public-safety scan passed. These checks show
that the code content is ready to commit; they do not create an immutable delivery identity or
replace the clean payload/browser run.

## Acceptance Status

| Gate | Status |
| --- | --- |
| `INST-014` shared novice Native lifecycle | **PARTIAL** — core lifecycle passed, supported onboarding/first answer did not |
| `INST-016` pristine no-tools Mac | **FAIL** — hidden developer dependencies were absent, but the supported first-run user path failed |
| `INST-017` exact-payload provider lifecycle | **BLOCKED** — Connected Accounts was hidden and no external provider call was permitted |
| `INST-028` exact-candidate public safety | **PASS** — scoped only to this rejected artifact; the replacement candidate must be rescanned |
| Release readiness | **BLOCKED** — not ready |

## Public-Safety Review

- [x] Synthetic `.invalid` account data only; no personal credentials, accounts, messages, or files.
- [x] Raw screenshots, logs, guest state, and machine-specific paths remain in private QA storage.
- [x] Public evidence uses commit/tree identifiers, aggregate counts, timing, and bounded outcomes.
- [x] No cloud mutation, provider request, external message, publication, commit, push, or release.
- [x] Manual exploratory finalization and downstream workaround are disclosed and never called acceptance.

## Mandatory Replacement Run

After a parent-source freeze, commit the required sanitized LibreChat capability projection, align
the parent component pin to that successor of `cf2551`, and rebuild the exact payload. Let the
normal assembler and all signing scans finish, then clone another untouched vanilla guest. Run the
entire path without a direct-API workaround:

1. inventory, copy, install, start, first-admin mismatch/error/retry/success, and closed-registration
   redirect;
2. automatic Connected Accounts onboarding, synthetic key add/replace/disconnect/delete, useful
   loopback-provider answer when the supported payload exposes a safe fixture path, refresh and
   restart persistence;
3. Feelings navigation/persistence and truthful missing-account guidance;
4. stopped-stack password reset, unknown/malformed account failures, new-password login, and old
   password rejection;
5. reinstall, signed-bootstrap upgrade/rollback, snapshot/restore, uninstall preservation/recovery,
   doctor, cleanup, resource, accessibility, Keychain/TCC, Intel, and fault matrices; and
6. final exact commit/tree, parent pin, build metadata, shipped archive, installed artifact,
   signature/notarization, and whole-payload public-safety alignment.

Until that source-frozen run passes, the pristine Native Easy Install and release gates remain open.
