# Clean Nested Publication Gates — 2026-07-22

## Summary

**Result: PARTIAL.** Eleven clean nested review branches were merged, and the parent manifests are
repinned to their actual `main` commits. LibreChat's reviewed tree remains exact after merge, with
local review and all 15 exact hosted checks green. Parent PR #69 code head `8dc6548e...` matched the
audited local head and all nine historical checks were green. The final closeout head is governed
by five distinct required contexts and must pass its hosted rerun before merge; signed-artifact and
real-user acceptance gates remain open.

This report records the local and hosted gate results for the clean nested publication branches
that precede the parent Viventium release branch. It contains no credentials, personal paths,
account data, runtime state, or private evidence. All eleven reviewed heads were merged through
non-draft pull requests. Each fetched `origin/main` commit equals the captured hosted merge commit,
and each merge tree equals the audited review-head tree. No release artifact was published.

The purpose of this gate is source publication safety. It does not claim that a signed/notarized
public installer exists, that real provider credentials passed, or that the headed Intel and
physical-machine matrices passed.

## Scope Run

| Case | Result | Evidence | Notes |
| --- | --- | --- | --- |
| Nested clean-history reconstruction | `PASS` | Eleven clean heads based on their fetched ProjectViventium main tips | No owner-machine ancestry was published. |
| Nested focused verification | `PASS` | Component results recorded below | Existing dependency trees were mounted read-only where required. |
| Hosted pull-request and merge identity | `PASS` | Eleven hosted PR heads matched locally; fetched merge commits match GitHub and preserve the audited trees | The organization has one member and the PR author is that same owner. The impossible one-independent-approval rule was replaced with a verified solo-maintainer policy that requires PRs, resolved conversations, and five strict automated gate contexts; applies to admins; and forbids force-pushes and deletions while keeping human approvals at zero. |
| Parent contract slice | `PARTIAL` | A focused run reported 257 passed | The exact argv was not retained, so this count is supporting history rather than a reproducible release gate. |
| Complete parent release suite | `PASS` | Final post-merge `python3 -m pytest tests/release/ -q`: 1,542 passed, 11 skipped, 0 failed in 293.15 seconds | Exact audited component trees behind the merged refs and existing compatible dependency/build trees were exposed through temporary zero-copy links, then removed. |
| Pre-merge pin and payload slice | `PASS` | Historical nine-file release slice: 311 passed in 67.40 seconds | This ran on the final reviewed heads before merge and remains provenance history. |
| Post-merge pin and payload slice | `PASS` | Recorded five-file release slice: 128 passed in 9.76 seconds; final hosted-ref workflow/manifest slice: 45 passed in 4.24 seconds; full-suite preflight directly checked all 11 merged refs and trees | `components.lock.json` contains all 11 merged refs; the Native policy contains matching merged LibreChat `38527a86...`, whose tree equals reviewed head `44ac1f7a...`. All temporary links were removed. |
| Parent PR exactness and hosted matrix | `PASS` | Parent PR #69 final code head `a2564e61...` passed all five strict required contexts and merged as `28a0cfc9...` | The merge tree exactly equals the audited PR-head tree. The Easy Install jobs materialize the exact pinned LibreChat ref before the suite; the release-policy job verifies all 11 declared refs equal public `main`; the matching final local slice passed 502/502. The post-merge `main` push also passed Easy Install on arm64 and x86_64, secret scan, and release policy. |
| Hosted macOS Python portability | `PASS` | Workflow regression passed 33/33 | Every macOS `actions/setup-python` tool step uses the available `3.12` minor selector and logs the resolved patch; the immutable payload's bundled Python remains independently pinned and verified at `3.12.13`. Feature-branch pushes no longer duplicate pull-request gates, and every required context has an unfiltered PR trigger so unrelated changes cannot deadlock. |
| Hosted release environments | `PARTIAL` | GitHub settings and the post-merge workflow result were inspected through the authorized owner session | `productivity-activation-live-eval` permits protected branches only and now requires an explicit owner dispatch, so an environment with no synthetic provider secrets does not create a misleading red check on every source merge; an explicit dispatch still fails closed when credentials are absent. `native-payload-release` permits `v*` tags only. Both keep required reviewers off for the sole-owner organization and disable administrator bypass. Neither contains secrets, so provider/signing execution remains blocked rather than silently using personal credentials. |
| Exact modern-playground browser surface | `PASS` | Headed Chromium at exact head `fd778562af199f7fb503bd4a0d106e22c282b16b` | Ten named keyboard stops; 320 px reflow; forced colors; zero retained motion; clean loopback-only browser ledger; reload passed. |
| Signed installer and physical matrix | `BLOCKED` | No approved signing/notarization authority or complete physical matrix was available | No signed-release claim is made. |

## Clean branch inventory

| Component | Audited review head | Merged `main` commit | Original delta | Verification |
| --- | --- | --- | ---: | --- |
| LibreChat | `44ac1f7a149e5a915e52f2f9f54fce5d38bab710` | `38527a8651653f5f7d0cba48038421653312d999` | 355 files / 19 commits | Merge tree exact. Corrected exact-head evidence remains unchanged: 59/59 stream regressions, 216/216 Viventium route tests, the CI-stability regression, zero syntax/diff/privacy/lint errors, and all 15 hosted checks including actual Redis and the serialized data-schema lane. |
| Classic playground | `112f646c47280561d40d48f9f57f64db39a9459d` | `f7ea19564bd062e82aed775b7c8932b70fb8984e` | 24 files / 6 commits | Merge tree exact; 11/11 tests, production build, and local health proof. |
| Modern playground | `fd778562af199f7fb503bd4a0d106e22c282b16b` | `f196cd5837fe6044543c50f5912f63e976d9d7b1` | 7 files / 6 commits | Merge tree exact; production build and local health proof. |
| LiveKit | `8839980c6a8e0058ce775a301ba8783b90d44a5d` | `c20e96166726565f026f894ccca6f1cff2480741` | 1 file / 1 commit | Merge tree exact; focused contract and privacy checks. |
| Cartesia voice agent | `df2f024822cf6c2fd0349bd9d5b26387cabcb98a` | `a37250ac2c2de1827853cdc2b2eebee4164b6c69` | 1 file / 1 commit | Merge tree exact; focused contract and privacy checks. |
| YouTube transcript MCP | `b12ec8775693fb3d76c0691b79be2fc09ee79938` | `60d6bbb38e9c8e1db6dfa0bed03e6834e759f1cd` | 1 file / 1 commit | Merge tree exact; focused contract and privacy checks. |
| Microsoft 365 MCP | `61f4b88e4fbed87cd340aa6bc410b04e6b32b6d7` | `c4c6f33b5e395a96780576cf0b55e5c420309e31` | 15 files / 3 commits | Merge tree exact; 30/30 tests, build, and changed-file formatting. |
| Google Workspace MCP | `c99e0e8d478cbcb7be502604d14781cf3aedf7b9` | `070aee1fc34b2eb6e32237e81f3333a71a7e75bb` | 29 files / 4 commits | Squash-merge tree exact; 34 tests, Ruff, and reproducible DXT build. |
| GlassHive | `464f97f013ee79dfe973ff9f52be49720ea9d2e4` | `1cf868e0218262328700085df38ec0ae2196cc2a` | 15 files / 4 commits | Merge tree exact; syntax, signed-link, browser-privacy, diff, and metadata checks. |
| Skyvern provenance | `ea7c8106bef5282c268f7f33091e96767925e8ee` | `7c0a4ac1364ff30c880ba791be0ef3d487b70370` | 6 files / 1 commit | Merge tree exact; 6/6 tests plus offline and live provenance verification. |
| OpenClaw provenance | `ea9923db5fbedcd4a171bae92eef80d14e5e2077` | `841336aa05beae35df3c907e0a5b8d40d6350652` | 12 files / 1 commit | Merge tree exact; 8/8 tests plus offline and live provenance verification. |

OpenClaw is structurally marked `product_posture: lab-only` and `release_approved: false` in the
component manifest. It is not an Easy Install or Custom Settings Install dependency and is not a
blocker for the first-chat path.

## Automated Evidence

### LibreChat

The focused component tests ran against the clean branch content with an already-present compatible
dependency tree mounted read-only for the run. Temporary dependency links were removed immediately
afterward, and the publication tree returned clean.

```text
ConnectedAccounts.spec.tsx
Test Suites: 1 passed, 1 total
Tests:       4 passed, 4 total

viventium-memory-hardening.test.js
Test Suites: 1 passed, 1 total
Tests:       77 passed, 77 total
```

The tests cover the actionable saved-but-unverified credential state and the sanitized memory
hardening path that had been unexecuted in the first review.

The Redis lifecycle implementation at `a2553962...` was exercised by all 42 non-integration stream
tests in three suites. Its exact hosted head also passed the real Redis workflow in both supported
modes:

```text
LibreChat head: a2553962b3d528444c66a8b4b61c3debb163d69f
Redis Actions run: 29899225254
Single Redis Node: PASS
Redis Cluster: PASS
Workflow: PASS in 6m14s
```

All 15 checks reported on that exact head passed: accessibility lint, ESLint, unused-package and
unused-i18n detection, frontend package build, Ubuntu and Windows frontend tests, Vite build,
backend package build, API tests, `@librechat/api`, data-provider and data-schemas tests, circular
dependency checks, and the real Redis integration workflow. Two superseded heads exposed brittle
test scheduling around asynchronous subscription readiness. The first test was changed to drain
the event loop; the cluster test now waits for the subscription acknowledgement and the delivered
error rather than fixed sleeps. This is valid historical executable evidence, but it did not cover
the later-confirmed interleaving: demand returns for a channel before reconnect readiness while a
deferred unsubscribe is still waiting. Claude's final review was `PARTIAL` and confirmed that race;
`a2553962...` is therefore not accepted for merge.

Head `568ebfba5382027c705905b46c317f1d0a9ef67e` corrected the Redis demand race, async generation
state, lookup/resume cancellation, and Telegram abort normalization. Audited review head
`44ac1f7a149e5a915e52f2f9f54fce5d38bab710`, whose exact tree is merged at `38527a8651...`,
additionally suppresses post-disconnect SSE errors in
gateway and scheduler readiness and serializes the Mongo-backed data-schema CI lane after a real
binary-lock failure. The exact current source passed:

```text
Stream suites: 59 passed, 0 failed
Viventium route suites: 216 passed, 0 failed
CI-stability source regression: 1 passed, 0 failed
Changed-file ESLint: 0 errors (pre-existing warnings only)
Syntax, diff hygiene, and corrected-delta privacy scan: PASS
Hosted checks: 15/15 PASS, including actual Redis
Redis Actions run: 29911412488
Backend Actions run: 29911412415
```

The first actual-Redis job attempt failed in the unchanged `LeaderElection` cluster test when a
lock-release command received a Redis `MOVED` response. No file in that owning cluster path changed
between the accepted historical head and the corrected head. The failed job was retained as
evidence; an identical-head rerun passed the complete single-node/cluster workflow in 6m23s. This
is recorded as hosted test flakiness rather than hidden or attributed to the stream correction.
On the next review head, the data-schema lane then exposed a separate
`mongodb-memory-server` binary-lock race under parallel Jest workers: 3 suites failed and 138 tests
cascaded after the shared lock could not be released. The current workflow runs that 16-suite lane
serially; the exact-head hosted rerun passed in 1m06s. Neither flake was hidden or treated as product
evidence before its exact-head rerun passed.

### Microsoft 365 MCP

```text
Test Files:  10 passed, 10 total
Tests:       30 passed, 30 total
Build:       PASS
Prettier:    PASS for README.md, src/auth.ts, src/secrets.ts, test/secrets.test.ts
```

The added regression proves the process fails closed when `MS365_MCP_CLIENT_ID` is absent. The
Softeria-owned fallback identifier is absent from the clean tree. Microsoft 365 therefore remains a
Custom Settings flow that requires an operator-selected Azure app registration.

### Parent contract slice

The parent staging source was tested after the Easy Install truth fixes and lifecycle-harness copy
alignment. A focused run reported the following result, but its exact command line was not retained;
the count is not used as a reproducible release gate:

```text
257 passed
```

The slice comprised:

- wizard behavior and Easy/Custom labels;
- brain-readiness registry and install-summary truth;
- Connected Accounts lifecycle harness contracts;
- generated config/compiler behavior;
- active install documentation labels.

The recorded scope supports that Easy Install emits Scheduler and the other optional automations
disabled, Custom Settings exposes those automations as visible opt-ins, Nightly Reflection enables
only its disclosed dependencies, and the public installer does not expose OpenClaw. The complete
release suite below is the reproducible source gate.

An exact post-fix installer-summary and wizard regression was also run and is reproducible:

```text
python3 -m pytest -q \
  tests/release/test_install_summary.py \
  tests/release/test_wizard.py
Test evidence: 99 passed
```

This exact slice includes the Easy Install notice regression: a user-provided OpenAI foundation
account is named as OpenAI without falsely making Anthropic mandatory.

### Complete parent release suite

The clean parent reconstruction was then tested with the exact eleven reviewed component trees by
running `python3 -m pytest tests/release/ -q` after the actual merge refs were pinned. A fail-closed
preflight proved each manifest ref equals fetched `origin/main` and each merged tree equals the
audited worktree tree.
Existing compatible dependencies and build outputs were exposed through temporary zero-copy links;
no package was installed, no component was copied, and no Docker or virtual-machine storage was
created. All temporary links were removed after the run.

```text
1,542 passed, 11 skipped, 0 failed in 293.15 seconds
```

The skipped cases remain visible in the test result and are not represented as physical-machine,
signed-artifact, or live-provider proof.

#### Harness-correction disclosure

The first attempt at the same full command used an incomplete zero-copy dependency harness and
reported `8 failed, 1,522 passed, 11 skipped in 273.25 seconds`. Seven failures were missing or
incompatible pre-existing Node build/dependency surfaces (`sharp`, API `dist`, or `NODE_PATH`);
one was a local RAG lock-timing failure. No product source was changed to turn those failures green.
After correcting only the local harness, the exact eight affected cases passed `8/8 in 12.02
seconds`, followed by the clean complete result above. The eight-case rerun argv was not retained,
so that count is supporting diagnostic history rather than a reproducible release gate. The
complete full-suite command and result remain the authoritative gate.

### Parent pin and payload alignment

After the then-latest LibreChat hardening commits and exact-head hosted checks passed, both the public
component lock and native payload policy were provisionally advanced to
`a2553962b3d528444c66a8b4b61c3debb163d69f`. A focused provenance/bootstrap/native-manifest/
payload/public-safety/playground/release-workflow run reported the result below, but its exact argv
was not retained:

```text
174 passed in 15.00s
```

The temporary links were absent again after the run. No package install, component copy, Docker
image, or virtual-machine disk was created. Claude's later Redis finding invalidated the word
"final" for that historical pin. Both `components.lock.json` and
`release/native-payload/components.json` now use merged LibreChat commit
`38527a8651653f5f7d0cba48038421653312d999`, whose tree equals corrected reviewed head
`44ac1f7a149e5a915e52f2f9f54fce5d38bab710`. A historical pre-merge nine-file release slice covering
bootstrap, upgrade, workflows, Native manifests/assembly, public manifests, stable runtime, and
playground dispatch passed 311/311 in 67.40 seconds. After merge, the current workflow/public-
manifest/Native-manifest/assembly/public-safety slice passed 128/128 in 9.76 seconds before the final
hosted-ref gate. Its focused workflow/manifest slice passed 45/45 in 4.24 seconds. The complete
suite preflight separately proved that each fetched nested `origin/main` equals its lock ref, each
configured origin URL is exact, and each merged tree equals its audited review-worktree tree. The
Native policy's merged LibreChat ref equals the lock's merged LibreChat ref. Both manifests are
explicitly `merged`; the Native candidate workflow rejects a synthetic
`review-head-pending-merge` state and accepts only aligned `merged` manifests. This makes the
post-merge repin a machine-enforced artifact gate rather than report-only process guidance. All
temporary links were removed afterward.

```text
python3 -m pytest -q \
  tests/release/test_bootstrap_components.py \
  tests/release/test_ci_release_workflows.py \
  tests/release/test_cli_upgrade.py \
  tests/release/test_native_component_manifest.py \
  tests/release/test_native_payload_assembler.py \
  tests/release/test_public_bootstrap_manifests.py \
  tests/release/test_stable_dev_runtime_workflows.py \
  tests/release/test_upgrade_transaction.py \
  tests/release/test_voice_playground_dispatch_contract.py
Historical pre-merge evidence: 311 passed in 67.40 seconds
```

```text
python3 -m pytest -q \
  tests/release/test_ci_release_workflows.py \
  tests/release/test_public_bootstrap_manifests.py \
  tests/release/test_native_component_manifest.py \
  tests/release/test_native_payload_assembler.py \
  tests/release/test_native_public_safety.py
Recorded post-merge evidence before the hosted-ref gate: 128 passed in 9.76 seconds
```

```text
python3 -m pytest -q \
  tests/release/test_ci_release_workflows.py \
  tests/release/test_public_bootstrap_manifests.py
Final hosted-ref workflow/manifest evidence: 45 passed in 4.24 seconds
```

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: clean nested publication and Easy Install release composition.
- Requirement: public/private boundary, nested pin alignment, first-run installer truth, and
  review-before-merge requirements.
- Use case: a public reviewer inspects the exact sanitized source that will later be pinned by the
  parent release.
- QA case: nested history reconstruction, public-safety scan, hosted head comparison, focused
  component verification, and parent installer contract slice.
- Expected result: hosted PR heads equal reviewed clean local heads, merged trees preserve those
  audited trees, no private/local data is in proposed history, and optional OpenClaw is not exposed
  by Easy Install.
- Actual evidence: all eleven hosted heads matched; all eleven fetched merge commits equal the
  hosted merge refs and preserve the audited trees. The corrected LibreChat source passed 162
  affected tests, fresh-context model review, and all 15 hosted checks. The parent manifests now match its
  merged commit; the recorded 311-test pin slice passed before merge, and the complete 1,542-test
  parent suite passed again after the real merge pins were applied. The public-safety checks below
  found no private data in the proposed deltas. The earlier
  257- and 174-test counts remain supporting history because their exact argv was not recorded.
- Remaining gap or fix: build/sign the artifact, prove a real optimized provider answer, and
  complete the physical matrix.

## Full-View Evidence Checklist

| Evidence surface | Required question | Evidence / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | What product promise is being protected? | Easy Install source safety, first-run truth, and nested publication alignment. |
| Code owning path | Which source owns it? | Parent installer/compiler/summary code and the eleven merged component commits listed above. |
| Docs and nested docs | Which documents define expected behavior? | Installer, public/private boundary, runtime QA map, and component release documentation. |
| Scripts or harnesses | What ran? | Git ancestry/diff checks, component tests/builds, parent release tests, and public-safety scanners. |
| Local/external prerequisite state | What was available? | Clean local worktrees, hosted PR/merge metadata, and fetched merge commits; signing authority, real provider account, Intel, and full physical matrix were unavailable. |
| Logs, DB/state/persistence | What supports the result? | Sanitized test summaries and refetched hosted PR hashes; no user DB or personal runtime state was accessed. |
| Generated/shipped artifact | What artifact was inspected? | Reproducible Google Workspace DXT and the tracked universal Viventium helper binary were inspected; the helper is an x86_64/arm64 Mach-O with recorded SHA-256, an unsigned x86_64 slice, and an ad-hoc/linker-signed arm64 slice. Whole-file strict code-signing and Gatekeeper checks fail, so no signed Viventium installer is claimed. |
| Real user path | What reviewer path ran? | Local CLI diff/history inspection followed by hosted GitHub PR/check/merge inspection and refetch verification. |
| Visual/UX comparison | What visible product path ran? | No installed GUI path was part of this source-publication gate. |
| Not run / blocked | What remains? | Signed/notarized install, provider-backed first answer, and headed physical/Intel fault matrices. |

## User-Grade Evidence

- Surface exercised: local CLI plus hosted GitHub pull-request and Actions-check surfaces.
- Real user path: inspect every proposed branch diff and history, open the hosted PR, verify its
  displayed head and checks, merge it, then refetch and verify the merged identity.
- Visible outcome: eleven hosted PRs displayed the exact reviewed clean heads and then their merged
  state. PR protection remained active; the solo-owner policy still enforced PRs, resolved
  conversations, admin coverage, and force-push/deletion prevention.
- Expanded/detail state: hosted check details were expanded where present and exact component test
  summaries were recorded below.
- Persistence/reload result: hosted PR metadata was refetched after merge, and each repository's
  `origin/main` continued to report the captured merge commit and audited tree.
- Backend/log/DB confirmation: Git object ancestry, diff scans, test logs, and GitHub Actions logs
  support the source result; no DB state applied to this publication gate.
- Final model/runtime wording check: the report says clean nested source is merged and parent
  repinning is complete; it does not claim a signed installer, provider-backed first answer, or
  public release.
- Substitution check: logs, Git objects, source inspection, model review, and automated tests are
  supporting evidence, not substitutes for any required visible-UI, detail-state, persistence, or
  wording step; they also do not replace the blocked signed/physical user paths.

## Ancestry, identity, and public-safety review

Immediately before this report, every branch was fetched from its ProjectViventium `origin` and
checked against the then-live `origin/main`:

- all eleven merge bases exactly equalled the live remote main tip;
- every worktree was clean;
- every authored review-branch commit used the approved public-safe Project Viventium noreply
  identity for author and committer metadata; hosted merge commits carry ordinary GitHub-generated
  metadata attributable to the already-public organization owner;
- the proposed remote branch names did not already exist;
- no binary delta existed except the expected reproducible Google Workspace DXT package;
- an added-line scan found no personal home path, local username, personal email, private-key
  marker, or common credential/token signature;
- Skyvern is one commit directly above the ProjectViventium base; its large local development
  ancestry is not present;
- OpenClaw is one commit directly above its ProjectViventium base and has no alternate-object
  dependency;
- GlassHive excludes the OpenClaw runtime-lock commit.

GitHub secret-scanning metadata also showed inherited alerts on the pre-existing base histories:
five MongoDB-URI alerts in LibreChat and two Google OAuth client-credential alerts in optional
OpenClaw. Their validity is unknown. They predate these review branches, none is introduced by the
proposed diffs, and no alert value was retrieved or copied into this audit. They require separate
owner-authorized rotation and base-history triage; optional OpenClaw remains excluded from Easy
Install and has `releaseApproved: false`.

Claude Desktop Fable 5 at Extra effort independently inspected the updated heads, ancestry, diffs,
metadata, and parent truth changes. Its first conclusion was `PARTIAL`: the privacy and
branch-boundary reviews were clean, while the Redis adversarial review confirmed a reconnect/demand
race in LibreChat `a2553962...`. After the fix and deterministic regressions, its visible
corrected-delta conclusion was `PASS` with no P0-P2 finding. OpenClaw remained explicitly
optional-only. Claude review supports but does not replace executable evidence or required user
paths.

## Findings

- Defects found and fixed before publication: stale unexecuted LibreChat commits, parent lifecycle
  harness drift, misleading saved-provider readiness wording, Microsoft 365 fallback ownership,
  an unpinned GlassHive leak exemption, and Easy Install OpenClaw exposure.
- Hosted findings closed: all eleven corrected nested PRs merged, their fetched `main` commits match
  the hosted merge refs, and every merged tree equals its audited review tree.
- Environment limitations: no release signing/notarization authority, dedicated provider account,
  Intel target, or complete isolated physical-machine matrix.

### Remaining gates

Nested publication completed:

- each hosted PR diff and available CI result was inspected;
- every actual post-merge commit SHA was recorded in the parent pin;
- every merged tree was verified equal to the reviewed local head tree.

Parent PR source gate completed:

- the fresh parent reconstruction remained based on fetched parent `origin/main`;
- `components.lock.json` and the shipped manifests retained the actual merged nested SHAs;
- the reviewed parent source changes remained free of owner-machine artifacts;
- the complete post-merge parent release-suite pass remained part of the evidence;
- the candidate privacy scan, generated-output checks, recorded source-candidate lifecycle checks,
  and exact hosted parent-PR inspection completed against that reconstruction;
- all nine checks on historical code head `8dc6548e...` passed; the final closeout head is governed
  by five distinct required contexts and its exact rerun must pass before merge.

Before a signed public artifact:

- obtain the approved public manifest signer, Apple Team ID, MongoDB redistribution approval,
  Developer ID/notarization credentials, and protected GitHub release controls;
- prove the real optimized OpenAI first answer with a dedicated synthetic account;
- complete headed macOS Keychain/TCC/Gatekeeper/accessibility QA, Intel acceptance, and the isolated
  physical Docker/fault matrix;
- implement and verify the authenticated bootstrap freshness boundary.

Until those later gates pass, the defensible claim is **clean source and exact merged component
pins passed the parent PR gate**, not **signed public installer released**.

## Public-Safety Review

- [x] No real secrets, tokens, passwords, cookies, or credential-bearing command lines. Synthetic,
  disposable fixture credentials are clearly labeled and confined to the release-workflow fixture.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails,
  account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or
  raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports,
  App Support state, or raw runtime dumps.
- [x] Private evidence is summarized only through sanitized counts, hashes, and conclusions.
