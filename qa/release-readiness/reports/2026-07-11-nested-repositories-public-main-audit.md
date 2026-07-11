# Nested Repositories Public Main Audit — 2026-07-11

## Summary

- Result: **PASS** for the pre-publication line audit, secret/privacy scan, affected automated tests,
  production builds, generated runtime, and installed service restart.
- Result: **PARTIAL** for the synthetic Feelings chat/reaction leg because the disposable QA account
  intentionally had no connected model provider; the UI displayed the truthful provider error.
- Publication state: GlassHive PR #36 and LibreChat PR #56 were reviewed and merged in dependency
  order. Parent PR #63 exists at the exact audited head; fresh-clone install and upgrade acceptance
  passed. Final parent CI/review and merge remain pending.
- Scope: 286 changed or newly added files across the parent repository, GlassHive, and
  LibreChat. Every file is listed below.

## Scope Run

| Repository | Base reviewed | Publication boundary | Result |
| --- | --- | --- | --- |
| Parent Viventium | PR #63 exact remote head matches the audited local commit | Public product, installer, compiler, docs, QA, Prompt Workbench, Telegram | PASS/PARTIAL pending merge |
| GlassHive | PR #36 merged to public `main` | Public worker runtime and tests | PASS |
| LibreChat fork | PR #56 merged to public `main` | Public fork source, packages, prompts, scheduling, and tests | PASS/PARTIAL |

The audit treated tracked source, untracked candidate files, generated runtime output, component pins,
and live installed behavior as separate delivery surfaces.

## Traceability

`all local nested-repository development -> public/private boundary and install/upgrade requirements
-> per-file candidate inventory -> line scan and semantic review -> automated/build/runtime/browser
evidence -> review-only Claude pass -> exact PR diff -> dependency-ordered merge`

Expected result: all intended development is publishable without secrets, personal data, private
operating context, machine-local paths, or functionality/install regressions. Actual result before
publication: scanners and manual review found no remaining new leak; affected paths pass; named
baseline/environment gaps are separated below.

## Full-View Evidence Checklist

| Evidence surface | Actual evidence |
| --- | --- |
| Owning requirements | Key principles, architecture/system maps, installer/compiler, public/private boundary, runtime QA map, stable runtime, GlassHive, memory, Telegram, voice, prompt architecture, periphery, and Feelings docs reviewed. |
| Source and nested repos | Parent, GlassHive, and LibreChat working trees inventoried independently; local HEADs compared with fetched remotes. |
| Public-safety scans | Candidate-tree gitleaks, TruffleHog, custom identity/home-path/email/token patterns, diff-only scans, QA public-safety test, image inspection, and baseline comparison. |
| Automated tests | Parent release suite, GlassHive runtime tests, LibreChat API/package/client tests, Scheduler, Telegram, Voice Gateway, focused regressions, lint, formatting, syntax, and compile checks. |
| Builds | LibreChat package build and production client build/post-build verification passed. |
| Generated runtime | Config compiled; placeholders resolved; `MONGO_AUTO_INDEX=false` present. |
| Installed runtime | Supported developer activation compiled and restarted the current checkout; status reported all local surfaces running. |
| Fresh install/upgrade | A new public-remote clone bootstrapped exact merged component pins; isolated headless install and supported upgrade passed compile, doctor, placeholder, pin, and continuity gates. |
| Database/migration | Startup log confirmed memory/provider unique indexes ready only after the dry-run guard; synthetic QA user/state was removed after browser QA. |
| Browser/UX | Real Chrome run exercised Feelings load, enable, manual controls, reaction drawer, refresh persistence, and 320/390/768/1024/1440 layouts. |
| Remaining gap | Synthetic account lacked connected model auth, so detached reaction completion is BLOCKED by account setup; visible UI showed the provider error truthfully. |

## User-Grade Evidence

- Surface exercised: installed LibreChat web UI and Feelings route in real Chrome.
- Real user path: open Feelings, enable it, manipulate Current/Nature/return speed, open/close the
  Reaction Cortex, refresh, inspect responsive layouts, then send a synthetic isolated chat turn.
- Visible outcome: controls and values updated, the state survived refresh, desktop/mobile layouts
  remained usable, and the unconfigured provider produced a clear visible error.
- Expanded/detail state: Reaction Cortex routing/status drawer opened and restored focus on Escape.
- Persistence/reload result: manual band values and return speed persisted after reload.
- Backend/log/DB confirmation: Feelings API writes succeeded; generated runtime matched source;
  startup migration completed; disposable QA DB state and user were cleaned.
- Final model/runtime wording check: the provider failure was not presented as success.
- Substitution check: browser-visible controls, detail state, refresh, and error were directly run;
  automated tests were not used as substitutes. Detached model reaction remains BLOCKED rather than
  inferred from unit tests.

## Automated Evidence

- Parent release suite: 888 passed, 2 skipped; one environment-only `pip` metadata check passed in
  the Voice Gateway venv, and one dated-report gate has the same 18-file violation set on unchanged
  main. This candidate adds zero new report-template violations.
- Parent targeted failure/feature set: 212 passed.
- Prompt Workbench and exact-model eval harness after UTC fallback hardening: 132 passed.
- Parent public-safety gate: passed.
- GlassHive full runtime suite: passed.
- LibreChat client: 123 suites / 1,336 tests passed.
- LibreChat affected package/API suites: passed, including the 71-test memory-hardening suite.
- LibreChat full API: deterministic shard 1/2 passed and exited cleanly; shard 2/2 reported 92
  passed suites, 2 skipped suites, 1,629 passed tests, and 18 skipped tests. After the passing
  summary, a pre-existing periodic recovery timer kept Jest open and the process was terminated;
  no test failed. The earlier complete parallel run's only load-sensitive activation timing cases
  passed in isolation.
- Scheduling Cortex: 323 passed.
- Telegram: 110 passed plus 6 subtests.
- Voice Gateway: 341 passed plus 48 subtests.
- LibreChat package build and production client build/post-build verification: passed.
- LibreChat PR CI after two stale test-expectation fixes: all reported build, API/package/client,
  Ubuntu, Windows, lint, circular-dependency, schema/provider, i18n, and Vite checks passed.
- Changed JS/TS lint: 81 files, zero errors; 68 non-blocking existing/style warnings.
- `git diff --check`: passed in all three repositories.
- Fresh-clone acceptance: public PR branch clone was clean; isolated install and upgrade passed. The
  post-upgrade continuity warning was only unavailable Mongo introspection because the acceptance
  stack was intentionally not started; there were no continuity errors.

## Findings

- Fixed before publication: ordinary web attachments no longer receive bridge-only extracted image
  payloads; memory unique-index rollout is dry-run guarded; RAG health no longer leaks exception
  details; snapshot ordering is correct; PPTX extraction is bounded before decompression; prompt
  registry parity, provider/tool ownership, tests, and docs align.
- Fixed during final audit: lint errors, stale React dependencies, an unlocalized Feelings nav label,
  stale OpenAI-first memory-hardener expectation, a generated evaluation report exemption, and two
  stale CI expectations (the synthetic PPTX byte count and raw-source activation-policy wording).
  A remaining owner-location-like timezone fallback/report label was replaced with neutral UTC or
  configured-local wording, with a regression test for the standalone Workbench fallback.
- Baseline debt, not introduced: the dated-report contract has 18 historical main-branch violations;
  dependency audit totals match baseline.
- Environment-only: the synthetic QA account had no connected primary provider.
- Cloud exposure: both nested PR heads were public-safe. No leaking commit was published, so no
  remote history cleanup was required.

## Publication Evidence

- GlassHive PR #36: exact remote head matched the audited 8-file local commit; Claude verdict
  APPROVE; merged to `main` at `ebc9bbab2d7e0954c5723207982f105e5fcea82c`.
- LibreChat PR #56: exact remote head matched the audited 149-file local commit. Initial GitHub CI
  exposed two stale test expectations; both test-only fixes passed locally and the complete rerun
  passed. Claude approved the original diff and re-approved the exact two-line final delta; merged
  to `main` at `f051e431524e394f18cebcd0dda7df1685d328aa`.
- Parent component manifest pins both merged nested SHAs and the fetched, independently reviewed
  public `main` heads for the other clean nested repositories.
- Claude parent verdict: publication-safe with no blocking code defect; required gates were final
  component pins and fresh-clone/parent-PR evidence (all now complete).
- Parent PR #63: remote head `7312bbab542bb2f24dfc3f91025be43b92bff641` exactly matched the
  audited 129-file local commit before this evidence-only report update.
- Fresh public-remote clone: headless install bootstrapped and validated LibreChat
  `f051e431524e394f18cebcd0dda7df1685d328aa`, GlassHive
  `ebc9bbab2d7e0954c5723207982f105e5fcea82c`, and modern playground
  `83044a509b2ccd798deee916291776912b5c1b9e`; compiler/doctor passed and generated
  `MONGO_AUTO_INDEX=false`. Supported upgrade then passed with no continuity error.

## Per-File Line Audit

Method: every added/deleted line was included in the candidate-tree and diff-only scans. Each file
also received a semantic judgment based on its owning layer; source files were checked against tests,
requirements, generated output, and the live surface. `+/−` is added/deleted lines; binary images
show `-/−`. Repeated PASS wording is intentional so the inventory remains one-file-at-a-time.

### parent (129 files)

| File | +/− lines | Line-by-line judgment |
| --- | ---: | --- |
| `/dev/null => qa/background_agents/evals/browser-qa-safety.cjs` | 157/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => qa/background_agents/evals/run-activation-model-evals.cjs` | 872/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => qa/background_agents/evals/run-interruption-restart-browser-qa.cjs` | 983/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => qa/background_agents/reports/2026-07-09-activation-routing-model-eval.md` | 311/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => qa/background_agents/reports/2026-07-09-gpt-5-6-conscious-subconscious-routing.md` | 76/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => qa/background_agents/reports/2026-07-09-interruption-restart-browser-qa.md` | 28/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => qa/background_agents/reports/2026-07-10-qa-memory-contamination-prevention.md` | 69/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => qa/config-alignment/reports/2026-07-09-gpt-5-6-agent-builder.md` | 55/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => qa/emotional-cortex/artifacts/2026-07-09-feelings-live-demo-1440.png` | -/- | PASS — synthetic visual inspected; no profile, identifier, or private content. |
| `/dev/null => qa/emotional-cortex/artifacts/2026-07-09-feelings-live-demo-390.png` | -/- | PASS — synthetic visual inspected; no profile, identifier, or private content. |
| `/dev/null => qa/emotional-cortex/prototypes/feelings-live-demo.html` | 2126/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => qa/emotional-cortex/reports/2026-07-09-feelings-embodiment-motion-eval.md` | 115/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => qa/emotional-cortex/reports/2026-07-09-feelings-live-demo.md` | 93/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => qa/emotional-cortex/reports/2026-07-09-feelings-runtime-implementation.md` | 172/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => qa/emotional-cortex/reports/2026-07-10-nine-band-exact-model-eval.md` | 215/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => qa/emotional-cortex/reports/2026-07-11-telegram-voice-feelings-expression.md` | 201/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => qa/emotional-cortex/scripts/feelings_live_demo_qa.cjs` | 321/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => qa/emotional-cortex/scripts/feelings_runtime_browser_qa.cjs` | 1024/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => qa/meeting-transcript-memory/reports/2026-07-11-owner-private-transcript-import-and-recall.md` | 174/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => qa/memory-hardening/reports/2026-07-11-nightly-failure-prevention.md` | 108/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => qa/modern-playground-voice/reports/2026-07-09-grok-4-3-voice-transport-provenance.md` | 77/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => qa/periphery-nightly-insights/evals/cases.json` | 184/0 | PASS — declarative config/prompt reviewed for provider, tool, and install behavior. |
| `/dev/null => qa/periphery-nightly-insights/reports/2026-07-11-nightly-periphery-final-qa.md` | 96/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => qa/periphery-nightly-insights/scripts/run-periphery-evals.py` | 421/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => qa/prompt-architecture/reports/phase-4-exact-model-eval-baseline.md` | 75/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => qa/red-team-cortex/reports/2026-07-09-decision-method-live-browser-qa.md` | 49/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => qa/red-team-cortex/reports/2026-07-09-decision-method-live-sync-qa.md` | 49/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => qa/red-team-cortex/reports/2026-07-09-decision-method-stack-source-qa.md` | 65/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => qa/scheduling-cortex/reports/2026-07-10-workbench-callback-repair.md` | 54/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => qa/telegram-document-attachments/reports/2026-07-09-pptx-text-notes-vision-qa.md` | 105/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => tests/release/test_feelings_contract.py` | 320/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `/dev/null => tests/release/test_openai_model_inventory.py` | 50/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `/dev/null => tests/release/test_periphery_eval_harness.py` | 159/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `/dev/null => viventium_v0_4/prompt-workbench/backend/prompt_workbench/periphery_contract.py` | 50/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => viventium_v0_4/prompt-workbench/backend/prompt_workbench/periphery_snapshots.py` | 595/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `bin/viventium` | 6/1 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `config.full.example.yaml` | 45/7 | PASS — declarative config/prompt reviewed for provider, tool, and install behavior. |
| `config.minimal.example.yaml` | 34/2 | PASS — declarative config/prompt reviewed for provider, tool, and install behavior. |
| `config.schema.yaml` | 75/0 | PASS — declarative config/prompt reviewed for provider, tool, and install behavior. |
| `components.lock.json` | 9/9 | PASS — public component refs pin reviewed, fetched public `main` commits, including both merged nested PRs. |
| `docs/02_ARCHITECTURE_OVERVIEW.md` | 8/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `docs/03_SYSTEMS_MAP.md` | 13/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `docs/requirements_and_learnings/01_Key_Principles.md` | 128/7 | PASS — public-safe requirement/documentation wording reviewed. |
| `docs/requirements_and_learnings/02_Background_Agents.md` | 133/47 | PASS — public-safe requirement/documentation wording reviewed. |
| `docs/requirements_and_learnings/03_Telegram_Bridge.md` | 37/3 | PASS — public-safe requirement/documentation wording reviewed. |
| `docs/requirements_and_learnings/06_Voice_Calls.md` | 27/7 | PASS — public-safe requirement/documentation wording reviewed. |
| `docs/requirements_and_learnings/11_Scheduling_Cortex.md` | 27/1 | PASS — public-safe requirement/documentation wording reviewed. |
| `docs/requirements_and_learnings/20_Memory_System.md` | 51/6 | PASS — public-safe requirement/documentation wording reviewed. |
| `docs/requirements_and_learnings/29_Red_Team_Cortex.md` | 21/3 | PASS — public-safe requirement/documentation wording reviewed. |
| `docs/requirements_and_learnings/32_Conversation_Recall_RAG.md` | 21/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `docs/requirements_and_learnings/37_LibreChat_v083_Config_Alignment.md` | 42/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md` | 53/4 | PASS — public-safe requirement/documentation wording reviewed. |
| `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md` | 2/2 | PASS — public-safe requirement/documentation wording reviewed. |
| `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md` | 5/1 | PASS — public-safe requirement/documentation wording reviewed. |
| `docs/requirements_and_learnings/49_Prompt_Architecture_and_Token_Efficiency.md` | 104/37 | PASS — public-safe requirement/documentation wording reviewed. |
| `docs/requirements_and_learnings/50_Stable_Dev_Runtime.md` | 4/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `docs/requirements_and_learnings/53_Viventium_Periphery_Nightly_Insights.md` | 65/23 | PASS — public-safe requirement/documentation wording reviewed. |
| `docs/requirements_and_learnings/54_Emotional_Cortex_And_Feeling_State.md` | 645/802 | PASS — public-safe requirement/documentation wording reviewed. |
| `qa/agent-config-continuity/cases.md` | 16/0 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/background_agents/01_catalog.md` | 12/11 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/background_agents/03_eval_prompt_bank.md` | 86/0 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/background_agents/05_coverage_matrix.md` | 24/12 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/background_agents/06_agent_signoff_manifest.md` | 14/1 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/background_agents/cases.md` | 11/3 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/background_agents/evals/run-latest-user-activation-browser-qa.cjs` | 346/164 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/background_agents/evals/run-visible-cards-browser-qa.cjs` | 473/245 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/background_agents/README.md` | 32/14 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/config-alignment/cases.md` | 29/0 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/config-alignment/README.md` | 3/1 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/conversation-recall-rag/cases.md` | 36/0 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/emotional-cortex/cases.md` | 119/464 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/emotional-cortex/README.md` | 92/10 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/feature-user-use-case-checklist.md` | 2/1 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/meeting-transcript-memory/cases.md` | 42/28 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/memory-continuity/cases.md` | 28/0 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/memory-hardening/cases.md` | 37/0 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/modern-playground-voice/cases.md` | 59/0 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/periphery-nightly-insights/README.md` | 9/0 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/periphery-nightly-insights/cases.md` | 13/10 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/prompt-architecture/evals/prompt-bank.json` | 2147/0 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/prompt-architecture/evals/run-exact-model-evals.cjs` | 1979/749 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/prompt-workbench/cases.md` | 153/13 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/prompt-workbench/prompt-coverage.yaml` | 16/0 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/red-team-cortex/cases.md` | 18/0 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/release-readiness/README.md` | 2/0 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/release-readiness/reports/2026-07-11-nested-repositories-public-main-audit.md` | self/0 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/release-test-owners.yaml` | 6/0 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/scheduling-cortex/cases.md` | 36/2 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/stable-dev-runtime/cases.md` | 14/0 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/telegram-document-attachments/cases.md` | 21/12 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/telegram-document-attachments/README.md` | 2/0 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/telegram-document-attachments/reports/2026-07-09-telegram-file-ingress-parity.md` | 11/9 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/telegram-runtime/cases.md` | 12/0 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/telegram-voice-replies/cases.md` | 19/12 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `qa/telegram-voice-replies/README.md` | 8/0 | PASS — synthetic/sanitized QA contract or evidence; no raw private artifact. |
| `scripts/viventium/brain_readiness.py` | 1/1 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `scripts/viventium/config_compiler.py` | 399/46 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `scripts/viventium/install_summary.py` | 4/1 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `scripts/viventium/memory_harden.py` | 427/19 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `scripts/viventium/prompt_registry.py` | 4/2 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `tests/release/test_background_agent_browser_qa_harness.py` | 209/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `tests/release/test_background_agent_governance_contract.py` | 141/19 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `tests/release/test_config_compiler.py` | 196/43 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `tests/release/test_config_settings.py` | 14/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `tests/release/test_install_summary.py` | 24/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `tests/release/test_memory_hardening_contract.py` | 356/10 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `tests/release/test_productivity_activation_source_of_truth.py` | 54/77 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `tests/release/test_prompt_architecture_eval_harness.py` | 391/20 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `tests/release/test_prompt_registry.py` | 38/4 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `tests/release/test_prompt_workbench.py` | 836/10 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `tests/release/test_rag_api_override_contract.py` | 249/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `tests/release/test_rag_compose_resource_guardrails.py` | 13/4 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `tests/release/test_scheduled_glasshive_prompts.py` | 64/3 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `tests/release/test_stable_dev_runtime_workflows.py` | 27/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `tests/release/test_telegram_transcription_error_contract.py` | 2/1 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `viventium_v0_4/docs/ARCHITECTURE.md` | 37/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `viventium_v0_4/docs/IMPLEMENTATION_INDEX.md` | 20/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `viventium_v0_4/prompt-workbench/backend/prompt_workbench/app.py` | 54/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `viventium_v0_4/prompt-workbench/backend/prompt_workbench/evals.py` | 69/13 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `viventium_v0_4/prompt-workbench/backend/prompt_workbench/paths.py` | 3/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `viventium_v0_4/prompt-workbench/backend/prompt_workbench/scheduled_prompts.py` | 558/93 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `viventium_v0_4/prompt-workbench/src/api.ts` | 190/76 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `viventium_v0_4/prompt-workbench/src/components/ScheduledPromptsPanel.tsx` | 799/224 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `viventium_v0_4/prompt-workbench/src/styles.css` | 103/2 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `viventium_v0_4/prompt-workbench/src/types.ts` | 73/9 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `viventium_v0_4/telegram-viventium/TelegramVivBot/bot.py` | 5/1 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `viventium_v0_4/telegram-viventium/TelegramVivBot/utils/tts.py` | 13/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `viventium_v0_4/telegram-viventium/tests/test_tts.py` | 4/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `viventium_v0_4/viventium-librechat-start.sh` | 268/24 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |

### GlassHive (8 files)

| File | +/− lines | Line-by-line judgment |
| --- | ---: | --- |
| `runtime_phase1/src/workers_projects_runtime/profile_runtime.py` | 42/4 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `runtime_phase1/src/workers_projects_runtime/run_evidence.py` | 62/11 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `runtime_phase1/src/workers_projects_runtime/runtime_requirements.py` | 1/1 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `runtime_phase1/src/workers_projects_runtime/service.py` | 41/3 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `runtime_phase1/tests/conftest.py` | 6/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `runtime_phase1/tests/test_api.py` | 95/1 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `runtime_phase1/tests/test_profile_runtime.py` | 140/16 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `runtime_phase1/tests/test_run_evidence.py` | 89/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |

### LibreChat (149 files)

| File | +/− lines | Line-by-line judgment |
| --- | ---: | --- |
| `/dev/null => api/server/routes/viventium/__tests__/feelings.spec.js` | 214/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `/dev/null => api/server/routes/viventium/feelings.js` | 336/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => api/server/services/viventium/__tests__/EmotionalReactionService.spec.js` | 489/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `/dev/null => api/server/services/viventium/__tests__/feelingsTelemetry.spec.js` | 101/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `/dev/null => api/server/services/viventium/__tests__/memoryWriterCoordinator.spec.js` | 101/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `/dev/null => api/server/services/viventium/EmotionalReactionService.js` | 631/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => api/server/services/viventium/feelingsTelemetry.js` | 129/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => api/server/services/viventium/memoryWriterCoordinator.js` | 60/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => client/src/components/Feelings/feelings.css` | 1449/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => client/src/components/Feelings/FeelingsView.spec.tsx` | 315/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `/dev/null => client/src/components/Feelings/FeelingsView.tsx` | 1007/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => client/src/data-provider/Feelings/index.ts` | 1/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => client/src/data-provider/Feelings/queries.ts` | 55/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => packages/api/src/feelings/__tests__/config.test.ts` | 64/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `/dev/null => packages/api/src/feelings/__tests__/kernel.test.ts` | 176/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `/dev/null => packages/api/src/feelings/__tests__/service.test.ts` | 213/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `/dev/null => packages/api/src/feelings/config.ts` | 127/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => packages/api/src/feelings/index.ts` | 4/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => packages/api/src/feelings/kernel.ts` | 344/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => packages/api/src/feelings/service.ts` | 324/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => packages/api/src/feelings/types.ts` | 116/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => packages/data-provider/src/types/feelings.ts` | 143/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => packages/data-schemas/src/methods/feelingState.spec.ts` | 197/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `/dev/null => packages/data-schemas/src/methods/feelingState.ts` | 111/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => packages/data-schemas/src/models/feelingState.ts` | 9/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => packages/data-schemas/src/schema/feelingState.ts` | 103/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => packages/data-schemas/src/types/feelingState.ts` | 81/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `/dev/null => viventium/source_of_truth/prompts/cortex/emotional_reaction/activation.md` | 14/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => viventium/source_of_truth/prompts/cortex/emotional_reaction/execution.md` | 27/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => viventium/source_of_truth/prompts/surface/telegram_audio_output.md` | 19/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => viventium/source_of_truth/prompts/surface/telegram_audio_provider_cartesia.md` | 23/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => viventium/source_of_truth/prompts/surface/telegram_audio_provider_chatterbox.md` | 17/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => viventium/source_of_truth/prompts/surface/telegram_audio_provider_plain_tts.md` | 16/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => viventium/source_of_truth/prompts/surface/telegram_audio_provider_xai.md` | 25/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `/dev/null => viventium/source_of_truth/prompts/surface/voice_feeling_expression.md` | 15/0 | PASS — public-safe requirement/documentation wording reviewed. |
| `api/app/clients/tools/util/fileSearch.js` | 191/92 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `api/models/Message.js` | 43/4 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `api/models/Message.spec.js` | 34/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `api/server/controllers/agents/client.js` | 417/70 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `api/server/controllers/agents/client.test.js` | 258/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `api/server/routes/config.js` | 7/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `api/server/routes/memories.js` | 2/1 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `api/server/routes/viventium/__tests__/gateway.spec.js` | 81/3 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `api/server/routes/viventium/__tests__/telegram.spec.js` | 62/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `api/server/routes/viventium/gateway.js` | 178/91 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `api/server/routes/viventium/index.js` | 3/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `api/server/routes/viventium/telegram.js` | 71/3 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `api/server/services/__tests__/BackgroundCortexService.activationPolicy.spec.js` | 93/10 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `api/server/services/BackgroundCortexService.js` | 227/29 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `api/server/services/Files/process.js` | 69/18 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `api/server/services/Files/process.spec.js` | 103/6 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `api/server/services/viventium/__tests__/agentLlmFallback.spec.js` | 3/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `api/server/services/viventium/__tests__/agentSchemaToolBindingPatch.spec.js` | 175/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `api/server/services/viventium/__tests__/conversationRecallService.spec.js` | 94/1 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `api/server/services/viventium/__tests__/GlassHiveCapabilityBroker.spec.js` | 40/1 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `api/server/services/viventium/__tests__/surfacePrompts.spec.js` | 51/1 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `api/server/services/viventium/__tests__/voiceLlmOverride.spec.js` | 74/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `api/server/services/viventium/agentLlmFallback.js` | 13/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `api/server/services/viventium/agentSchemaToolBindingPatch.js` | 79/37 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `api/server/services/viventium/conversationRecallService.js` | 19/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `api/server/services/viventium/GlassHiveCapabilityBootstrapService.js` | 72/13 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `api/server/services/viventium/promptFrameTelemetry.js` | 4/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `api/server/services/viventium/surfacePrompts.js` | 24/3 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `api/server/services/viventium/voiceLlmOverride.js` | 17/1 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `api/test/app/clients/tools/util/fileSearch.test.js` | 209/9 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `api/test/scripts/viventium-agent-runtime-models.test.js` | 117/37 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `api/test/scripts/viventium-memory-hardening.test.js` | 244/3 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `api/test/scripts/viventium-seed-agents.test.js` | 5/5 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `api/test/scripts/viventium-sync-agents.test.js` | 10/2 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `api/test/services/viventium/backgroundCortexFollowUpService.test.js` | 2/2 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `api/test/services/viventium/backgroundCortexService.test.js` | 144/3 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `client/src/components/Nav/AccountSettings.tsx` | 14/1 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `client/src/components/SidePanel/Agents/__tests__/ModelPanel.helpers.spec.ts` | 46/1 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `client/src/components/SidePanel/Agents/ModelPanel.tsx` | 24/6 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `client/src/components/SidePanel/Agents/modelSelection.ts` | 33/1 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `client/src/data-provider/index.ts` | 1/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `client/src/locales/en/translation.json` | 1/0 | PASS — declarative config/prompt reviewed for provider, tool, and install behavior. |
| `client/src/routes/index.tsx` | 11/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `package-lock.json` | 4/0 | PASS — dependency metadata reviewed; security-audit delta matches baseline. |
| `packages/api/package.json` | 4/0 | PASS — declarative config/prompt reviewed for provider, tool, and install behavior. |
| `packages/api/src/agents/__tests__/initialize.test.ts` | 61/10 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `packages/api/src/agents/__tests__/memory.test.ts` | 37/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `packages/api/src/agents/context.spec.ts` | 15/1 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `packages/api/src/agents/context.ts` | 15/1 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `packages/api/src/agents/initialize.ts` | 53/5 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `packages/api/src/agents/memory.spec.ts` | 8/1 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `packages/api/src/agents/memory.ts` | 263/18 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `packages/api/src/endpoints/models.spec.ts` | 6/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `packages/api/src/endpoints/openai/llm.spec.ts` | 30/3 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `packages/api/src/files/documents/crud.spec.ts` | 149/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `packages/api/src/files/documents/crud.ts` | 232/1 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `packages/api/src/index.ts` | 3/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `packages/api/src/memory/policy.spec.ts` | 36/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `packages/api/src/memory/policy.ts` | 34/7 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `packages/data-provider/src/api-endpoints.ts` | 7/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `packages/data-provider/src/config.spec.ts` | 20/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `packages/data-provider/src/config.ts` | 21/1 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `packages/data-provider/src/data-service.ts` | 34/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `packages/data-provider/src/file-config.spec.ts` | 1/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `packages/data-provider/src/file-config.ts` | 2/1 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `packages/data-provider/src/keys.ts` | 5/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `packages/data-provider/src/types.ts` | 1/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `packages/data-provider/src/types/index.ts` | 1/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `packages/data-schemas/src/methods/index.ts` | 4/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `packages/data-schemas/src/methods/memory.spec.ts` | 96/8 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `packages/data-schemas/src/methods/memory.ts` | 230/118 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `packages/data-schemas/src/models/index.ts` | 2/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `packages/data-schemas/src/models/plugins/mongoMeili.spec.ts` | 62/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `packages/data-schemas/src/models/plugins/mongoMeili.ts` | 45/7 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `packages/data-schemas/src/schema/index.ts` | 1/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `packages/data-schemas/src/schema/memory.ts` | 5/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `packages/data-schemas/src/types/index.ts` | 1/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `packages/data-schemas/src/types/memory.ts` | 9/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `rag.yml` | 26/9 | PASS — declarative config/prompt reviewed for provider, tool, and install behavior. |
| `scripts/benchmark-activation-providers.js` | 22/15 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `scripts/viventium-agent-runtime-models.js` | 65/7 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `scripts/viventium-memory-dedupe.js` | 3/1 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `scripts/viventium-memory-hardening.js` | 282/52 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `scripts/viventium-memory-proposal-apply.js` | 26/5 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `scripts/viventium-sync-agents.js` | 3/1 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `viventium/MCPs/scheduling-cortex/scheduling_cortex/dispatch.py` | 119/22 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `viventium/MCPs/scheduling-cortex/scheduling_cortex/models.py` | 19/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `viventium/MCPs/scheduling-cortex/scheduling_cortex/scheduler.py` | 98/0 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `viventium/MCPs/scheduling-cortex/scheduling_cortex/server.py` | 263/5 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `viventium/MCPs/scheduling-cortex/scheduling_cortex/storage.py` | 38/1 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `viventium/MCPs/scheduling-cortex/tests/test_bootstrap.py` | 44/1 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `viventium/MCPs/scheduling-cortex/tests/test_dispatch.py` | 63/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `viventium/MCPs/scheduling-cortex/tests/test_prompt_contract.py` | 158/1 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `viventium/MCPs/scheduling-cortex/tests/test_scheduler.py` | 161/1 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `viventium/MCPs/scheduling-cortex/tests/test_storage.py` | 123/0 | PASS — synthetic regression coverage; fixtures contain no live identity or credential. |
| `viventium/rag_api_overrides/app/routes/document_routes.py` | 19/3 | PASS — owning source diff reviewed for behavior, failure handling, and public safety. |
| `viventium/source_of_truth/local.librechat.yaml` | 662/748 | PASS — declarative config/prompt reviewed for provider, tool, and install behavior. |
| `viventium/source_of_truth/local.viventium-agents.yaml` | 242/577 | PASS — declarative config/prompt reviewed for provider, tool, and install behavior. |
| `viventium/source_of_truth/prompts/cortex/background_analysis/activation.md` | 25/17 | PASS — public-safe requirement/documentation wording reviewed. |
| `viventium/source_of_truth/prompts/cortex/confirmation_bias/activation.md` | 41/21 | PASS — public-safe requirement/documentation wording reviewed. |
| `viventium/source_of_truth/prompts/cortex/deep_research/activation.md` | 21/14 | PASS — public-safe requirement/documentation wording reviewed. |
| `viventium/source_of_truth/prompts/cortex/emotional_resonance/activation.md` | 27/15 | PASS — public-safe requirement/documentation wording reviewed. |
| `viventium/source_of_truth/prompts/cortex/google/activation.md` | 30/52 | PASS — public-safe requirement/documentation wording reviewed. |
| `viventium/source_of_truth/prompts/cortex/online_tool_use/activation.md` | 30/51 | PASS — public-safe requirement/documentation wording reviewed. |
| `viventium/source_of_truth/prompts/cortex/parietal_cortex/activation.md` | 19/12 | PASS — public-safe requirement/documentation wording reviewed. |
| `viventium/source_of_truth/prompts/cortex/pattern_recognition/activation.md` | 24/13 | PASS — public-safe requirement/documentation wording reviewed. |
| `viventium/source_of_truth/prompts/cortex/red_team/activation.md` | 48/21 | PASS — public-safe requirement/documentation wording reviewed. |
| `viventium/source_of_truth/prompts/cortex/red_team/execution.md` | 19/1 | PASS — public-safe requirement/documentation wording reviewed. |
| `viventium/source_of_truth/prompts/cortex/strategic_planning/activation.md` | 27/14 | PASS — public-safe requirement/documentation wording reviewed. |
| `viventium/source_of_truth/prompts/cortex/support/activation.md` | 15/1 | PASS — public-safe requirement/documentation wording reviewed. |
| `viventium/source_of_truth/prompts/mcp/glasshive_workers_server.md` | 2/2 | PASS — public-safe requirement/documentation wording reviewed. |
| `viventium/source_of_truth/prompts/mcp/scheduling_cortex_server.md` | 15/1 | PASS — public-safe requirement/documentation wording reviewed. |
| `viventium/source_of_truth/prompts/surface/voice_call.md` | 5/1 | PASS — public-safe requirement/documentation wording reviewed. |
| `viventium/source_of_truth/prompts/surface/voice_provider_xai.md` | 7/4 | PASS — public-safe requirement/documentation wording reviewed. |

## Public-Safety Review

- [x] No new verified or unverified secret finding relative to fetched-main baselines.
- [x] TruffleHog-only candidate hits are synthetic test URIs or unchanged upstream fixtures.
- [x] No personal email, account identifier, raw private prompt/chat/attachment, customer data, or
  local username/hostname was added.
- [x] No real home-directory or App Support path is present in publication files; sanitizer fixtures
  use explicit synthetic placeholders.
- [x] Both PNG candidates were visually inspected and contain only synthetic Feelings UI.
- [x] Git author/committer identity is the approved public-safe project identity in all three repos.
- [x] Private safety snapshots and browser evidence remain outside all public repositories.

Pending publication gates: final parent PR head/diff and CI review, Claude review of this
evidence-only delta, and final parent merge evidence.
