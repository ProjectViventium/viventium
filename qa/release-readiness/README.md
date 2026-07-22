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
| Release tests | `python3 -m pytest tests/release/ -q` in the reviewed stable test environment | Before parent push | PASS 2026-07-22 corrected-pin candidate: 1,539 passed, 11 skipped, 0 failed in 275.92 seconds |
| Diff hygiene | `git diff --check` plus public/private pattern scans | Before staging | PARTIAL 2026-07-22: complete parent-candidate inventory, diff hygiene, special-file/binary classification, and public-safety review passed locally; staged/remote parent-PR exactness remains under `REL-008` |
| Browser-visible QA | `node qa/background_agents/evals/run-visible-cards-browser-qa.cjs --headless` with local opt-in env | When background-agent UI behavior changed | PASS 2026-05-11 local / 2026-05-12 UTC; public-safe report saved |
| Latest-user activation QA | `node qa/background_agents/evals/run-latest-user-activation-browser-qa.cjs --headless` with local opt-in env | When activation history/window behavior changed | PASS 2026-05-11 local / 2026-05-12 UTC; public-safe report saved |
| Full activation classifier gate | `node qa/background_agents/evals/run-activation-model-evals.cjs --run-live --with-fallbacks --repetitions=1 --concurrency=1 --output-dir=<private-output> --public-report=<public-safe-report>` | Before release while the primary activation model is preview, and after any activation prompt/model/provider/fallback/parser/runtime change | PARTIAL: the fixture-backed parser and fallback contracts pass. A release-candidate live run with dedicated synthetic credentials remains required; owner-account provider health and routing observations are private evidence and are not a public release result. |
| Background interruption/restart QA | `VIVENTIUM_QA_ALLOW_LOCAL_JWT=1 VIVENTIUM_QA_ALLOW_RUNTIME_RESTART=1 node qa/background_agents/evals/run-interruption-restart-browser-qa.cjs --headless` with a local synthetic QA user | When background status persistence, stale recovery, or runtime restart behavior changes | PASS 2026-07-10; real active Red Team card/DB state, changed API process, same-conversation survival, terminal stale recovery, expanded reload detail, no generation placeholder |
| Nested component tests | Targeted Jest/Pytest suites in changed nested repos | Before nested commit | PARTIAL 2026-07-22; all 11 reviewed heads are clean, pushed, and represented by open hosted PRs. Corrected LibreChat `44ac1f7a149e5a915e52f2f9f54fce5d38bab710` passes 59 stream tests and 216 Viventium route tests locally and all 15 hosted checks, including actual Redis. Independent approvals and merges remain open. |

## Coverage Matrix

| Requirement / Surface | Cases | Last Full Run |
| --- | --- | --- |
| Parent and nested diffs are public-safe before push | `REL-001`, `REL-002` | PARTIAL 2026-07-22; complete local parent-candidate and nested-delta public-safety reviews passed, and all 11 nested heads are hosted in open PRs. Corrected LibreChat local and all 15 hosted checks passed; independent approval, nested merge, post-merge repinning, and parent staging/PR inspection remain open. |
| Nested component commit and parent pin are consistent | `REL-003` | PARTIAL 2026-07-22: both parent manifests point to pushed LibreChat review head `44ac1f7a149e5a915e52f2f9f54fce5d38bab710`, and the other managed refs match their reviewed hosted heads. Source/pin identity now aligns for review; merged, built, shipped, and installed identity is not yet proven. |
| User-visible QA evidence is browser-backed and sanitized | `REL-004` | 2026-05-10 PASS |

## Current Status

- Current reconstructed parent result: `python3 -m pytest tests/release/ -q` passed on 2026-07-22
  with 1,539 passed, 11 skipped, and 0 failed in 275.92 seconds against temporary zero-copy links to
  all 11 exact reviewed component heads. The recorded corrected pin/payload/provenance slice passed
  311/311. A prior 174-pass run against rejected LibreChat `a2553962...` remains supporting history
  because its exact argv was not retained.
- All 11 reviewed nested heads are clean and hosted in open PRs. LibreChat PR 67 now points to
  corrected commit `44ac1f7a149e5a915e52f2f9f54fce5d38bab710`; both parent manifests match it.
  Local evidence is 59/59 stream tests and 216/216 Viventium route tests, with independent review and
  Claude Desktop Fable 5 Extra reporting no remaining P0-P3 finding. All 15 hosted checks pass,
  including actual Redis; independent approval and merge remain separate gates.
- Known gaps: independent PR approvals and merges; post-merge component identities; rebuilt,
  signed/notarized payload and installed-artifact equality; pristine exact-artifact install; real
  optimized provider-answer persistence; Intel and native assistive-technology coverage; the wider
  physical fault/Docker matrix; authenticated bootstrap freshness; and parent-PR exactness. Passing
  source suites or opening PRs does not close those gates.
- Next required hardening: keep provider-native structured Phase B and full doc-49 runtime/source/
  compiled A/B/C drift gate as explicit post-baseline work before main-prompt compaction.

## Current Gate Audit

- [2026-07-22 clean nested publication gates](reports/2026-07-22-clean-nested-publication-gates.md)
- [2026-07-20 release gate matrix audit](reports/2026-07-20-release-gate-matrix-audit.md)
