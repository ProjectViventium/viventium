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

| Suite | Command or Manual Path | Required When | Last Run |
| --- | --- | --- | --- |
| Release tests | `PYTHONPATH=. python -m pytest tests/release -q` in a stable test environment with `pytest` and `pyyaml` | Before parent push | 2026-05-11 local / 2026-05-12 UTC: 504 passed, 2 skipped |
| Diff hygiene | `git diff --check` plus public/private pattern scans | Before staging | 2026-05-11 local / 2026-05-12 UTC: parent, LibreChat, and GlassHive diff checks passed; sensitive-pattern scans found no added private values |
| Browser-visible QA | `node qa/background_agents/evals/run-visible-cards-browser-qa.cjs --headless` with local opt-in env | When background-agent UI behavior changed | 2026-05-11 local / 2026-05-12 UTC: PASS, public-safe report saved |
| Latest-user activation QA | `node qa/background_agents/evals/run-latest-user-activation-browser-qa.cjs --headless` with local opt-in env | When activation history/window behavior changed | 2026-05-11 local / 2026-05-12 UTC: PASS, public-safe report saved |
| Full activation classifier gate | `node qa/background_agents/evals/run-activation-model-evals.cjs --run-live --with-fallbacks --repetitions=2 --concurrency=1 --output-dir=<private-output> --public-report=<public-safe-report>` | Before release while the primary activation model is preview, and after any activation prompt/model/provider/fallback/parser/runtime change | 2026-07-10 PARTIAL availability: current 63-case bank produced 1,381/1,386 completed-and-passed decisions at concurrency 2; completed-call required recall and activation precision 100%, 0 FP/FN/required-or-forbidden inconsistency, but 5 non-required all-provider unavailable decisions (99.64% completion). Four optional allowed-activation overlaps varied and are reported separately. Release gate remains open until a clean full run completes. |
| Background interruption/restart QA | `VIVENTIUM_QA_ALLOW_LOCAL_JWT=1 VIVENTIUM_QA_ALLOW_RUNTIME_RESTART=1 node qa/background_agents/evals/run-interruption-restart-browser-qa.cjs --headless` with a local synthetic QA user | When background status persistence, stale recovery, or runtime restart behavior changes | 2026-07-10: PASS; real active Red Team card/DB state, changed API process, same-conversation survival, terminal stale recovery, expanded reload detail, no generation placeholder |
| Nested component tests | Targeted Jest/Pytest suites in changed nested repos | Before nested commit | 2026-05-11 local / 2026-05-12 UTC: focused LibreChat backend 254 passed, focused frontend cortex-card 14 passed, MCP manager 43 passed, Scheduling Cortex 85 passed, GlassHive runtime 109 passed / 3 skipped |

## Coverage Matrix

| Requirement / Surface | Cases | Last Full Run |
| --- | --- | --- |
| Parent and nested diffs are public-safe before push | `REL-001`, `REL-002` | 2026-05-12 PASS |
| Nested component commit and parent pin are consistent | `REL-003` | 2026-05-12 PASS |
| User-visible QA evidence is browser-backed and sanitized | `REL-004` | 2026-05-10 PASS |

## Current Status

- Last full QA: 2026-05-11 local / 2026-05-12 UTC release and targeted nested regression pass.
- Current result: implementation tests, release tests, nested backend/frontend/MCP tests, API build,
  browser-visible background-card QA, and latest-user activation browser QA pass in the latest local
  synthetic environment. The browser runs prove named cards, parent answer visibility before and
  after reload, successful stored terminal insights, Groq-first activation config with no drift, no
  stale-history cortex cards on the latest simple turn, and no critical HTTP errors for that
  environment; release approval still requires the remaining packaging and review gates.
- Known gaps: PR merge remains the final publication gate.
- Next required hardening: keep provider-native structured Phase B and full doc-49 runtime/source/
  compiled A/B/C drift gate as explicit post-baseline work before main-prompt compaction.
