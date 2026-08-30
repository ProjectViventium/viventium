# Release Readiness QA

## Scope

- Owning requirements doc: `AGENTS.md`, `docs/requirements_and_learnings/01_Key_Principles.md`
- Runtime/code owners: parent repo, nested component repos, component pin manifests, and public QA artifacts
- User-visible surfaces: public pull requests, fresh install/upgrade paths, local browser QA evidence
- Out of scope: private runtime logs, screenshots with account data, local App Support state, and owner-machine-only artifacts

## Quality Bar

- Primary user outcome: a reviewer can trust the branch is public-safe and reproducible from Git.
- Speed/latency expectation: release packaging must not block product QA, but it must fail closed on private data or broken pins.
- Persistence/reload expectation: generated/runtime artifacts are not treated as source; nested component commits and parent pins must match.
- Failure behavior: blockers are documented before push; no PR is called production-ready while verification remains theoretical.
- Public/private boundary: reports use hashes, synthetic data, and public-safe placeholders only.

## Environments

- Local: public checkout plus nested component repos
- CI: release tests and public-safety scanners where available
- Connected-account or external-service assumptions: real connected-account checks stay private; public reports use hashes only
- Synthetic fixtures: QA prompts and account identifiers must be synthetic or sanitized

## Required Suites

| Suite | Command or Manual Path | Required When | Historical evidence, not current signoff |
| --- | --- | --- | --- |
| Release tests | `PYTHONPATH=. python -m pytest tests/release -q` in a stable test environment with `pytest` and `pyyaml` | Before parent push | 2026-05-11 local / 2026-05-12 UTC: 504 passed, 2 skipped |
| Diff hygiene | `git diff --check` plus public/private pattern scans | Before staging | 2026-05-11 local / 2026-05-12 UTC: parent, LibreChat, and GlassHive diff checks passed; sensitive-pattern scans found no added private values |
| Browser-visible QA | `node qa/background_agents/evals/run-visible-cards-browser-qa.cjs --headless` with local opt-in env | When background-agent UI behavior changed | 2026-05-11 local / 2026-05-12 UTC: PASS, public-safe report saved |
| Latest-user activation QA | `node qa/background_agents/evals/run-latest-user-activation-browser-qa.cjs --headless` with local opt-in env | When activation history/window behavior changed | 2026-05-11 local / 2026-05-12 UTC: PASS, public-safe report saved |
| Full activation classifier gate | `node qa/background_agents/evals/run-activation-model-evals.cjs --run-live --with-fallbacks --repetitions=1 --concurrency=1 --output-dir=<private-output> --public-report=<public-safe-report>` | Before release while the primary activation model is preview, and after any activation prompt/model/provider/fallback/parser/runtime change | 2026-07-15 PASS with degraded primary-provider health: current 67-case bank completed and passed all 737 target decisions with 100% required recall and activation precision, 0 FP/FN/inconsistency, and 0 unavailable decisions. All 737 Groq/Qwen primary attempts were provider-rejected and recovered by the configured xAI fallback; p50/p95/max was 551/779/1,319 ms. Restore/recheck Groq health and repeat under release-load conditions before multi-user capacity claims. |
| Background interruption/restart QA | `VIVENTIUM_QA_ALLOW_LOCAL_JWT=1 VIVENTIUM_QA_ALLOW_RUNTIME_RESTART=1 node qa/background_agents/evals/run-interruption-restart-browser-qa.cjs --headless` with a local synthetic QA user | When background status persistence, stale recovery, or runtime restart behavior changes | 2026-07-10: PASS; real active Red Team card/DB state, changed API process, same-conversation survival, terminal stale recovery, expanded reload detail, no generation placeholder |
| Nested component tests | Targeted Jest/Pytest suites in changed nested repos | Before nested commit | 2026-05-11 local / 2026-05-12 UTC: focused LibreChat backend 254 passed, focused frontend cortex-card 14 passed, MCP manager 43 passed, Scheduling Cortex 85 passed, GlassHive runtime 109 passed / 3 skipped |

## Coverage Matrix

| Requirement / Surface | Cases | Historical full run |
| --- | --- | --- |
| Parent and nested diffs are public-safe before push | `REL-001`, `REL-002` | 2026-05-12 PASS |
| Nested component commit and parent pin are consistent | `REL-003` | 2026-05-12 PASS |
| User-visible QA evidence is browser-backed and sanitized | `REL-004` | 2026-05-10 PASS |

## Historical 2026-05 Baseline And Current Status

- The 2026-05-11 local / 2026-05-12 UTC release and targeted nested regression pass is retained as
  historical evidence only. It does not establish the current candidate.
- **Current overall result: PARTIAL as of 2026-08-29.** The strengthened QA operating contract
  reports 27 passing content/structure checks plus five expected clean-checkout durability and
  ownership failures. The gates now compare current parent-file bytes with `HEAD` and require
  `HEAD` ownership instead of treating Git-index presence as durability. New owners and current
  documentation repairs are uncommitted, so a clean checkout cannot recover the complete
  source-of-truth set or every central-map target.
- Release remains open for durable tracked ownership; current full-suite reruns; clean checkout and
  install; nested component commit, parent pin, compiled/prebuilt artifact, and installed identity
  agreement; upgrade and rollback; required real-user surfaces; public-safety review; and zero-open
  acceptance. A PR merge is only one publication action and is not the sole remaining gate.
- The current cross-feature release gaps are maintained in
  [`45_Runtime_Feature_QA_Map.md`](../../docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md).
  Prompt compaction separately remains blocked by the provider-native Phase B and full
  source/compiled/live drift gates in requirement 49.
