# Native coordination source publication — 2026-11-08

## Summary

QA mode: **blast-radius**. Selected component tests, retained model evaluations and bounded browser
checks passed. Two new source-retention inference probes are **BLOCKED** by provider availability.
Final independent source/PR review and fresh CI remain open. Installed end-to-end acceptance remains
**PARTIAL**; this report does not activate an installation or prove physical phone audio.

The [cognitive system](../../../docs/architecture/cognitive-system.md) owns the speaking Main,
Native coordinator and independent Workers. The host preserves original context; Native owns
execution. This report records evidence for that separation without claiming a complete live journey.

## Scope Run

| Component | Selected evidence | Result and limit |
| --- | --- | --- |
| Core | Owning compiler, private-data boundary, native publication, helper lifecycle, media and transport banks | Affected source checks passed; no project-wide test total is inferred. |
| LibreChat host | Retained 86-suite / 5,754-test evidence; 1,053 affected source/store/authority checks; 61 Main/source fixture checks; 45 managed-upgrade checks | Scoped selections overlap and are not added. One existing Redis resume case remains skipped. Changed-code and accessibility lint passed. |
| Voice frontend | 656 tests; typecheck and production build | Passed; rendering and request lifecycle do not establish audible call quality. |
| xPerfect / Native | 3,775 unique selected runtime tests; 30 UI tests; two executor-ownership probes | Passed. Three runtime cases skipped under the non-enterprise test configuration. These are separate selections. |
| Health component | 63 tests passed; two provider opt-in checks skipped | Real-provider acceptance is not inferred from skipped checks. |
| Model behavior | 66 prompt evaluations (33 baseline/proposed pairs), five composed Main evaluations and 24 Native contract runs; two new source-retention probes | Existing proposed cases passed. Both new probes are BLOCKED by provider availability and are not counted as passes. No combined end-to-end total is inferred. |
| Browser | Production frontend bundles exercised against synthetic API responses | Bounded visible controls and state checks; no live Telegram or physical audio claim. |

## Traceability

| Feature and expected behavior | Requirement and case owner | Actual proof | Remaining acceptance |
| --- | --- | --- | --- |
| Main remains available while Native coordinates independent work using original context | [Cognitive system](../../../docs/architecture/cognitive-system.md); [parallel-work cases](../../parallel-work/cases.yaml), native coordination and responsiveness | Native contract runs, executor-ownership probes and host consumer tests | Live concurrent conversation, steering and callback delivery across user surfaces. |
| Retaining input and claiming later revisions preserve complete originals and prior claims | [Logical-turn continuity](../../../docs/requirements_and_learnings/55_Parallel_Work_Orchestration.md#always-ready-main-and-logical-turn-continuity); [source-retention support](../../background_agents/cases.md#logical-turn-source-retention-support) | Memory/Redis exact-byte, file, order, identity, revision and prior-claim tests; actual claim-to-Main producer checks | Two Native inference probes are BLOCKED; live conversation rehydration and channel acceptance are not inferred. |
| Later results retain source authority and use Main context without duplicating channel facts | [Parallel work](../../../docs/requirements_and_learnings/55_Parallel_Work_Orchestration.md); [Main continuity](../../../docs/requirements_and_learnings/56_Main_Continuity_Kernel.md); result-claim and broker-ingress cases in the [parallel bank](../../parallel-work/cases.yaml) | Source-bound callback/result tests and actual compaction-repair acceptance and rejection checks | New live long-horizon Telegram and audible voice delivery. |
| Registered prompts and Main context arrive on the intended surface | [Prompt architecture](../../../docs/requirements_and_learnings/49_Prompt_Architecture_and_Token_Efficiency.md); [prompt cases](../../prompt-architecture/cases.md), source arrival and exact-model parity | Compiled registry lineage, 66 prompt evaluations (33 baseline/proposed pairs) and five actual composed Main model evaluations | Latency and sustained live-channel acceptance. |
| Public source excludes personal state and preserves component boundaries | [Public/private boundary](../../../docs/requirements_and_learnings/40_Public_Private_Boundaries_and_License_Matrix.md); [runtime cases](../cases.yaml), installed candidate and compatible component cutover | Per-file diff review, independent review, clean source exports and publication safety scans | Installed source, component pin, built payload and active-runtime agreement. |

## Automated Evidence

The prompt bank covers eight changed controls with their existing registered dependencies on the
exact configured model routes. It contains 33 baseline and 33 proposed evaluations: all 33 proposed
subjects passed; 30 baseline subjects passed. Three baseline controls concern policy absent from the
old source. Their model responses are not evidence that an old runtime performed an incorrect action.

Five further evaluations used the actual Main composer, compiled registered prompts and result tail
on Claude Opus 5 Low: Telegram text, web, interactive Workbench, scheduled Workbench and voice.
All five passed with synthetic original messages, memory and Feeling context. Voice call facts used
the actual separate per-turn carrier. This proves composed model-input behavior, not physical audio.

Two additional synthetic cases carry a repaired Redis claim through the existing original-message
reader map, Main composer, registered system formatter and Native context carrier. Both producer
checks passed with complete ordered originals, memory and Feeling context. Their actual Claude Opus
5 Low inference attempts were blocked by provider availability; neither is a model pass. These
fixtures do not run a live database, conversation replay or Telegram delivery. Earlier claim loss
is transport evidence, not proof that a live Main failed to rehydrate original messages.

The 24 real Native runs comprise 16 paired standalone runs, six current application-context cases
and two restricted-tool-policy cases. The worker routes used Codex 6.1 Sol High and Claude Opus 5.5
High, with effective model, effort and source lineage checked. Application callback consumption was
disabled in that fixture. The evidence covers selection, original context, tool policy and typed
receipts; it does not prove specialist side effects or application result delivery.

The selected deterministic banks cover normal, denied, stale, duplicate and recovery conditions.
Separate component totals overlap in scope and must not be added. Independent review supports these
checks; it does not replace them or the remaining user-path evidence.

The source-retention selection comprises 384 stream unit checks, 322 owned-Redis checks, 331 Native
source/capacity checks, five actual Main recurrence checks, nine invalid-source no-dispatch checks
and two typed-source route checks: 1,053 passing checks. One pre-existing Redis resume case remains
skipped. The separate 61-test Main/source fixture selection and 45-test managed-upgrade selection
also passed; repeated subsets are not additional totals. Twelve same-clock Main compositions retain
every model-facing byte, excluding only code-source hash metadata. The locked formatter preserves
complete ASTs, literal values, directives and comments; all 79 changed code files pass lint with
zero errors and 173 recorded warnings. The affected accessibility check passes.

## Full-View Evidence Checklist

| Evidence owner | Review outcome |
| --- | --- |
| Requirements, architecture, component docs and cases | Owning contracts linked above; original-context inheritance and generic Native execution retained. |
| Source, tests and generated artifacts | Reconciled source and production frontend builds checked; no active installation accepted by this report. |
| Logs, DB/state and persistence | Isolated test state, retained-result identity, ownership and reload/recovery checks inspected. |
| User path and visual behavior | Browser checks used production bundles with synthetic services; live Telegram and audible calls remain open. |
| Public/private boundary | Only sanitized product conclusions are included; raw evidence remains outside public repositories. |

## User-Grade Evidence

- Surface exercised: Browser frontend with synthetic services; actual Native CLI/MCP and model routes with isolated synthetic context.
- Real user path: Visible browser controls were exercised; new live Telegram conversations, installed activation and physical voice calls were not accepted by this source task.
- Visible outcome: Bounded UI states matched the tested service responses; model outputs met the recorded source-bound rubrics.
- Expanded/detail state: Detail and failure states have component tests and bounded browser evidence; live account-service behavior is not inferred.
- Persistence/reload result: Isolated source and runtime tests cover saved state and recovery; installed user-session continuity was not rerun here.
- Backend/log/DB confirmation: Candidate-bound test receipts, isolated stores and effective provider invocation lineage support the reported scopes.
- Final model/runtime wording check: Prompt judgment, typed handoff, application callback delivery and audible acceptance are distinct claims.
- Substitution check: Tests, model review and synthetic browser evidence do not replace required installed, live-channel or physical-audio acceptance.

## Findings

The source retains original-context handoff, independent execution, source-bound results and
registered Main context on web, Workbench, Telegram and voice inputs. The host repair includes
ordinary web/default prompt arrival, strict callback identity tests and faithful input retention at
both retention and claim. Memory reuses the canonical source normalizer; Redis no longer evicts
accepted originals by courier count or byte limits. Invalid source and typed overflow still reject
before accepted state changes; Native capacity admission still owns dispatch. Prior claim receipts
remain unchanged. Existing incomplete historical receipts stay marked incomplete; no missing original
is invented. Publication does not change saved user settings or certify a newly activated runtime.

The final semantic source/PR review and fresh CI remain open. Retained independent reviews and
deterministic checks do not close those gates or the two blocked inference probes. No final merge
or installed callback/audio acceptance is claimed.

The [runtime owner](../../../docs/requirements_and_learnings/capabilities/runtime-install-release.md)
and [runtime cases](../cases.yaml) retain the open installed-candidate, login/upgrade/restart,
live delivery and physical-call gates. No latency or endurance result is claimed here.

## Public-Safety Review

- [x] No private prompts, model outputs, personal media, account inventory or raw runtime evidence.
- [x] No credentials, personal or customer identity, machine paths, private URLs or operational identifiers.
- [x] Only public product requirements, bounded test counts, conclusions and remaining gaps are published.
