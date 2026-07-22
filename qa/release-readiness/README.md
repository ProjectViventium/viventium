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
| Release tests | `python3 -m pytest tests/release/ -q` in the reviewed stable test environment | Before parent push | PASS 2026-07-22 final post-merge tree: 1,542 passed, 11 skipped, 0 failed in 293.15 seconds |
| Diff hygiene | `git diff --check` plus public/private pattern scans | Before staging | PASS 2026-07-22: complete parent-candidate inventory, staged diff hygiene, special-file/binary classification, and public-safety review passed. Parent PR #69 code head `8dc6548e...` had remote parity and green hosted secret/release-policy checks; the final closeout head and required rerun must be confirmed on the hosted PR before merge. |
| Browser-visible QA | `node qa/background_agents/evals/run-visible-cards-browser-qa.cjs --headless` with local opt-in env | When background-agent UI behavior changed | PASS 2026-05-11 local / 2026-05-12 UTC; public-safe report saved |
| Latest-user activation QA | `node qa/background_agents/evals/run-latest-user-activation-browser-qa.cjs --headless` with local opt-in env | When activation history/window behavior changed | PASS 2026-05-11 local / 2026-05-12 UTC; public-safe report saved |
| Full activation classifier gate | `node qa/background_agents/evals/run-activation-model-evals.cjs --run-live --with-fallbacks --repetitions=1 --concurrency=1 --output-dir=<private-output> --public-report=<public-safe-report>` | Before release while the primary activation model is preview, and after any activation prompt/model/provider/fallback/parser/runtime change | PARTIAL: the fixture-backed parser and fallback contracts pass. A release-candidate live run with dedicated synthetic credentials remains required; owner-account provider health and routing observations are private evidence and are not a public release result. |
| Background interruption/restart QA | `VIVENTIUM_QA_ALLOW_LOCAL_JWT=1 VIVENTIUM_QA_ALLOW_RUNTIME_RESTART=1 node qa/background_agents/evals/run-interruption-restart-browser-qa.cjs --headless` with a local synthetic QA user | When background status persistence, stale recovery, or runtime restart behavior changes | PASS 2026-07-10; real active Red Team card/DB state, changed API process, same-conversation survival, terminal stale recovery, expanded reload detail, no generation placeholder |
| Nested component tests | Targeted Jest/Pytest suites in changed nested repos | Before nested commit | PASS 2026-07-22; all 11 audited changes were merged, fetched `origin/main` commits equal the captured GitHub merge refs, and every merge tree equals its clean reviewed head. Corrected LibreChat reviewed head `44ac1f7a...` passes 59 stream tests and 216 Viventium route tests locally and all 15 hosted checks, including actual Redis; its exact tree is merged at `38527a8651...`. |

## Coverage Matrix

| Requirement / Surface | Cases | Last Full Run |
| --- | --- | --- |
| Parent and nested diffs are public-safe before push | `REL-001`, `REL-002` | PASS 2026-07-22; complete local parent-candidate and nested-delta public-safety reviews passed, all 11 nested changes merged with reviewed-tree equality, and parent PR #69 code head `8dc6548e...` matched locally with all hosted checks green. The final closeout head and required rerun must be confirmed on the hosted PR before merge. |
| Nested component commit and parent pin are consistent | `REL-003` | PASS 2026-07-22: both parent manifests declare `merged`; every managed ref equals fetched nested `origin/main`, and every merged tree equals its audited review head. Built, shipped, and installed identity remains separately partial under `REL-008`. |
| User-visible QA evidence is browser-backed and sanitized | `REL-004` | 2026-05-10 PASS |

## Current Status

- Current reconstructed parent result: `python3 -m pytest tests/release/ -q` passed on 2026-07-22
  with 1,542 passed, 11 skipped, and 0 failed in 293.15 seconds against temporary zero-copy links to
  all 11 exact reviewed component trees after their merge refs were pinned. The current post-merge
  workflow/manifest/payload/public-safety slice passed 128/128 in 9.76 seconds before the final
  hosted-ref gate; that gate's focused workflow/manifest slice passed 45/45 in 4.24 seconds. The recorded
  311/311 slice remains pre-merge provenance history. A prior 174-pass run against rejected
  LibreChat `a2553962...` remains supporting history
  because its exact argv was not retained.
- Full-suite prerequisite: the complete release suite reads nested LibreChat, GlassHive, and modern-
  playground source. Materialize the managed component paths at their locked refs first with
  `python3 scripts/viventium/bootstrap_components.py --repo-root "$PWD" --jobs 4`. Until those paths
  exist, run the exact suites named by the applicable hosted workflow; raw missing-path
  `FileNotFoundError` results are an incomplete harness, not product evidence.
- Hosted component-ref equality is intentionally point-in-time and fail-closed: when any managed
  public `main` advances, the parent lock must be reviewed and repinned before an unrelated parent PR
  can pass the release-policy job. Release artifacts remain bound to their immutable reviewed commit;
  later component development does not silently rewrite an existing candidate.
- All 11 reviewed nested changes are merged. Each fetched `origin/main` equals the captured hosted
  merge ref, each merged tree equals its audited review head, and `components.lock.json` carries all
  11 actual merged refs with `publication_state: merged`. The Native policy is also `merged` and
  carries the matching LibreChat ref. LibreChat reviewed head `44ac1f7a...` has
  local evidence of 59/59 stream tests and 216/216 Viventium route tests, fresh-context model review,
  and no remaining Claude P0-P3 finding; all 15 hosted checks pass, including actual Redis. Its exact tree
  is merged and pinned at `38527a8651...`.
- Parent PR #69 code head `8dc6548e...` matched the audited local head and reported all nine
  historical checks green. The final closeout removes duplicate feature-branch push executions,
  so one arm64 Easy Install core job, one x86_64 job, one secret scan, one release-policy job, and
  the productivity activation contract form the five distinct strict required contexts. The hosted
  Easy Install matrix materialized the exact pinned LibreChat ref before testing, while the
  release-policy job verified all 11 declared refs equal public `main`; the matching local compile
  matrix passed 500/500. The final exact head and rerun must be confirmed on the hosted PR before
  merge.
- Known gaps: rebuilt, signed/notarized payload and installed-artifact equality; pristine
  exact-artifact install; real
  optimized provider-answer persistence; Intel and native assistive-technology coverage; the wider
  physical fault/Docker matrix; and authenticated bootstrap freshness. Passing
  source suites or opening PRs does not close those gates.
- Next required hardening: keep provider-native structured Phase B and full doc-49 runtime/source/
  compiled A/B/C drift gate as explicit post-baseline work before main-prompt compaction.

## Current Gate Audit

- [2026-07-22 clean nested publication gates](reports/2026-07-22-clean-nested-publication-gates.md)
- [2026-07-20 release gate matrix audit](reports/2026-07-20-release-gate-matrix-audit.md)
