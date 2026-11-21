# Native delivery and continuity source review — 2026-11-20

## Summary

QA mode: **blast-radius**. This is a source publication candidate. Installed activation, migration,
new-user installation and complete live channel acceptance are **NOT RUN** by this publication.
Draft component pins must remain `review-head-pending-merge` until their reviewed commits are on
public main and the remaining acceptance gates are closed. Passing unit checks do not waive them.

## Scope Run

The selected source, synthetic boundary and preview checks below protect the changed paths.
Live provider, channel and installed acceptance remains partial.

## Traceability

| Changed behavior | Requirement and case owner | Evidence and limit |
| --- | --- | --- |
| Native storage uses measured free-byte reserves on both filesystems; isolated execution retains its existing percentage policy | [Parallel work](../../../docs/requirements_and_learnings/55_Parallel_Work_Orchestration.md), [runtime cases](../cases.yaml) | Compiler, release gate, host readiness and Native capacity positive/negative cases pass. Unknown probes fail closed. |
| Startup readiness waits within a bounded window; packaged companion lookup stays inside its package | [Runtime owner](../../../docs/requirements_and_learnings/capabilities/runtime-install-release.md), [runtime cases](../cases.yaml) | Launcher, compiler and packaged-artifact cases pass. No installed candidate was activated. |
| Main continuity uses the stored declaration and proven Native capacity while retaining complete protected source | [Main continuity](../../../docs/requirements_and_learnings/56_Main_Continuity_Kernel.md), [continuity cases](../../main-scheduling-continuity/cases.yaml) | Host/Native source, budget, duplicate and authority cases pass. Native estimates are advisory; explicit operator and Direct API caps remain enforced. |
| Progress remains nonterminal evidence bound to the current owner, source, run and attempt | [Parallel work](../../../docs/requirements_and_learnings/55_Parallel_Work_Orchestration.md), [parallel cases](../../parallel-work/cases.yaml) | Host, Native, publication, stale-attempt and terminal-suppression tests pass. Live concurrent surface acceptance remains open. |
| Accepted work and delivered replies remain distinct; unknown prior effects do not authorize replay | [Interaction delivery](../../../docs/requirements_and_learnings/capabilities/interaction-delivery.md), [delivery cases](../../interaction-delivery/cases.yaml) | Typed receipt, failed reply, interrupted executor and forged model-provenance cases pass. Current-admission-scoped receipt reconciliation does not prove the internal retained-identity helper is wired after revocation. |
| Telegram preserves literal output and sends one message per selected file in mixed-media link order | [Telegram](../../../docs/requirements_and_learnings/03_Telegram_Bridge.md), [channel cases](../../telegram-channels/cases.yaml) | Transport order, definite rejection, uncertain send and authorization tests pass. Failure settlement carries the exact live dispatch permit and atomically rejects its replacement. New live channel acceptance remains open. |
| Task timing and linked Workbench timing change together under the same owner | [Scheduling continuity](../../../docs/requirements_and_learnings/capabilities/main-scheduling-continuity.md), [continuity cases](../../main-scheduling-continuity/cases.yaml) | Owner-isolated transaction, rejected edit, rollback and delivery-only cases pass. Supported model effort is retained. |
| Voice uses SDK 1.8.11 and its fixed local turn recipe; first audio is bounded after text is ready | [Voice](../../../docs/requirements_and_learnings/06_Voice_Calls.md), gateway regression bank | Deterministic voice bank passes, including the actual SDK with a silent mock socket. This does not prove audible output, cold local assets or a signed call. |
| The call frontend retains Core authority before capture/dispatch and stops cold token requests during End | [Voice](../../../docs/requirements_and_learnings/06_Voice_Calls.md), frontend authority/lifecycle tests | Installed-SDK ordering, invalid authority, pending permission, late-track disposal and token reuse pass. Final production preview shows an expired link without a busy microphone, strips the fragment, preserves sound choice after reload and closes settings with Escape. Signed and physical-audio acceptance remain open. |
| Registered communication policy applies saved preferences and preserves exact literal sources | [Prompt architecture](../../../docs/requirements_and_learnings/49_Prompt_Architecture_and_Token_Efficiency.md), [Workbench cases](../../prompt-workbench/cases.yaml) | Synthetic old/proposed positive, negative and adjacent comparisons pass on the exact configured Codex route. Configured Claude comparisons remain quota-blocked. Historical private policy is not evidence for the changed public policy. |

## Automated Evidence

- Core compiler, release gate, Workbench and launcher selection: **934 passed, 4 skipped**. The
  final artifact case was rerun after building its missing client prerequisite and passed. Five
  example cases were checked again after final example edits; these overlap the selection.
- Gateway: **1,382 passed**. Optional MLX dependencies no longer change the consuming service's SDK.
  The native xAI first-PCM timeout, empty-input behavior and partial-audio no-replay cases pass.
- Telegram transport: **935 retained passes** plus two added mixed-media order cases. The final
  affected file rerun passed all 44 cases; overlapping cases are not added to a total.
- LibreChat: **3,151 distinct selected Jest cases** and **62 scheduler cases** passed before the
  bounded permit repair. Its final affected checks passed 193 delivery-service, 9 route and 54
  presentation cases; these selections overlap. Types, changed-code lint and production package/
  client builds passed. A broad orchestration selection and a broad Telegram rerun exhausted the
  isolated test process; neither is reported as a full-bank pass.
- xPerfect: initial selected source bank **1,912 passed**. The final frozen provenance/interruption
  source then passed all **1,347 confirmed consumer cases**, with zero failures/errors/skips and
  identical tracked source and clean Git state before/after. An earlier run overlapped source edits
  and is not used as final proof. Eight causal and seven provenance cases are overlapping support.
  A fresh wheel's 247 source members match the final source exactly; no installed activation follows.
- Call frontend: **737 passed**, typecheck and clean-environment production build passed. Dormant
  unsafe markdown rendering and its unused dependency were removed; permissive upstream notices
  remain exact. Light primary and hover preserve readable contrast. Dot-segment identifiers are
  rejected before any Core request. Log-privacy regression guards use synthetic inputs.
- Model behavior: **18/18 controlled Codex comparisons passed** with actual model and source
  lineage checked; configured high effort requested. **18 configured Claude attempts were blocked by HTTP429/quota**; no substituted
  model or effort is counted as a pass. A timed-out earlier control was retained as failure evidence.

Counts across selections overlap and must not be summed. Private raw prompts, outputs, state,
source snapshots, line-level coverage, hashes, logs and screenshots remain outside public repos.
Only sanitized requirements, decisions, synthetic tests and evidence limits are published.

## Findings

The final CI follow-up only formats a privacy test, aligns the frontend job to its declared Node 24
family, and updates three host test fixtures to the current readiness/receipt/prompt contracts.
All 234 affected host cases and 13 actual receipt cases pass; these overlap earlier selections.
Native inference is pinned to its tested 0.2.7 package. The obsolete gateway-only model-prefetch
branch is removed; the separate V1 prefetch and Telegram shared settings remain. Bash syntax,
existing requirement-drift/valid-pin checks and the actual installed-pin predicate pass. A
synthetic native-model prediction succeeds with network and owner-file data reads denied except
the installed packages. This proves current package loading, not cold-install or audible accuracy.

### Open acceptance gates

- Exact configured Claude old/proposed prompt comparisons after quota recovery.
- Real retained Claude repeated-turn tool advertisement and model delivery choice.
- Turn-model accuracy, memory use and cold-start behavior on an installed candidate.
- Signed call, audible two-way speech, local turn detection and physical phone routing.
- Live changed Web/Telegram/Workbench/scheduled/callback journeys and persistence.
- Final remote PR identity, independent diff review and required CI; component public-main pins,
  compiled/released and active artifact agreement before a release claim.

The existing installation and private development remain separate. This source review does not
claim deployment, migration, a clean-machine install, a full test-bank pass or release readiness.

## Full-View Evidence Checklist

| Evidence surface | Result and limit |
| --- | --- |
| Requirements, docs and cases | Changed owners and cases are linked in Traceability; internal helpers are not represented as wired journeys. |
| Source, scripts and tests | Selected compiler, launcher, host, Native, frontend, scheduler and transport paths have synthetic regression evidence. |
| Logs, state and persistence | Isolated fixtures cover retained receipt/state identity, authority, rollback, replacement and replay. Real owner state was not used as a public fixture. |
| Generated artifact | Production frontend/package bundles and the final Native wheel were inspected; no installed/released artifact was activated. |
| Real user and visible surface | Browser production preview was exercised for invalid bootstrap, dialog controls and saved sound choice. Required live channel/audio acceptance remains open. |
| Private boundary | Source-only exports and staged/outgoing-history guards exclude raw private evidence. |

## User-Grade Evidence

- Surface exercised: Browser production preview with synthetic missing/invalid authority.
- Real user path: Open an invalid signed bootstrap, open Voice, select sound route, reload and dismiss settings with Escape.
- Visible outcome: The capability fragment is removed; the page says the link expired and offers a fresh-call recovery instruction without a busy microphone.
- Expanded/detail state: Voice displays the missing/invalid capability and keeps the local Speaker/Earpiece choice available.
- Persistence/reload result: The Earpiece selection survives reload; Speaker was restored after checking it. Escape closes the dialog after its exit animation.
- Local/external prerequisite state: Preview has no Core/provider credentials. Configured Claude returns rate-limit/quota failure; signed/audio acceptance is not attempted.
- Evidence retrieval classification, if applicable: Invalid authority is a request rejection. Claude is rate-limited; neither is treated as an empty success.
- Fallback path, if applicable: No model substitution or production activation was used to bypass the missing prerequisites.
- Backend/log/DB confirmation: Causal fixtures check that invalid authority and dot-segment IDs cause no Core dispatch; Native SDK fixtures check capture/token order and End fences. These support, but do not replace, a signed live call.
- Final model/runtime wording check: Expired link wording matches the missing authority. Receipt wording distinguishes accepted work, completed execution, delivered text and unknown artifacts.
- Substitution check: Source review, tests, logs, model completions and API receipts are supporting evidence. They do not replace the required live UI, channel, persistence or audible steps listed as open.

## Public-Safety Review

- [x] No raw private prompts, model outputs, owner/customer payloads, media, account inventory or runtime state.
- [x] No credentials, personal identity, private URLs, home paths or operational identifiers.
- [x] Synthetic fixtures, product decisions, bounded counts and explicit evidence gaps only.
