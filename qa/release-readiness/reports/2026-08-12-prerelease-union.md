# Prerelease Union Acceptance — 2026-08-12

## Summary

- Result: PARTIAL
- Build/source under test: parent candidate `8d67302164bb78af146902779587317236651280`
  with the four reviewed nested merge commits listed below.
- Runtime/artifact under test: fresh no-local source install compiled from the exact candidate.
- Environment: isolated macOS arm64 native runtime, noncanonical App Support root, and isolated
  high ports.
- Tester: Codex, with a bounded independent review-only second opinion.
- Related change: consolidate outstanding public-safe product work into one parent prerelease union.

Source consolidation, the clean install, first run, and the supported running-install upgrade path
passed. The overall result remains `PARTIAL` because signed/notarized Native distribution,
credentialed health-provider access, and audible LiveKit calls are separate external release gates.
The parent candidate was assembled in an isolated workspace; original development workspaces were
not modified.

### Published nested commits

| Component | Pull request | Merged `main` commit | Exactness | Verification |
| --- | --- | --- | --- | --- |
| LibreChat | `ProjectViventium/viventium-librechat#104` | `b8501b3c3c752b86663aa846019f59f7855d8634` | Merge tree equals reviewed head | 4,165 API tests passed / 19 skipped; 1,578 client tests passed; 418 data-schema tests passed / 3 skipped; 15/15 hosted checks passed |
| GlassHive | `ProjectViventium/GlassHive#75` | `3f4f74c90e6de15444bbd71fa12406d0c5d47337` | Merge tree equals reviewed head | Runtime, UI, real-browser, and secret-scan gates passed |
| Viventium Health | `ProjectViventium/Viventium-Health#1` | `91a9bbf5ff8bd0963dd3dc33bfd388c66fa7ed69` | Merge tree equals reviewed head | 52 tests passed / 2 credentialed live-provider tests skipped; build, isolated install, and first-run CLI smoke passed |
| Modern playground | `ProjectViventium/agent-starter-react#11` | `95b324c7498c50a7421751e5dd71971e268a3a84` | Merge tree equals reviewed head | 153 tests, formatting, supported-Node production build, hosted check, and real-browser first-run QA passed |

Both `components.lock.json` and the Native payload component policy declare `merged`. LibreChat is
identical in both manifests. Every parent component ref was compared with its fetched public
`origin/main`; all twelve matched.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `REL-002` | `PASS` | Fresh no-local clone installed with pinned runtimes, compiled config, and passing doctor | Services remained stopped as requested by `--no-start` |
| `REL-003` | `PASS` | Running-install upgrade produced `ok` pre/post audits and an `ok` strict comparison | No semantic or metadata continuity differences; running intent restored |
| `REL-008` | `PASS` | Nested merge trees equal reviewed heads; twelve parent refs equal public `origin/main` | Parent manifests carry exact merged refs |
| `REL-009` | `PASS` | Complete file ledger, public-safe metadata review, diff hygiene, and Gitleaks | No candidate leak found |
| `REL-010` | `PARTIAL` | Source/native policy checks passed | Signed/notarized Native artifacts and physical-machine matrix remain external |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `REL-UC-001` | Install from a fresh public-style clone without starting services | Installer CLI | `PASS` | Installer completed and doctor reported a usable stopped installation | Exact component refs, generated config, and pinned runtime receipts were inspected | None |
| `REL-UC-002` | Start the freshly installed product and create an account | Installer CLI and headed Chromium | `PASS` | Registration rendered; a synthetic account registered and reached the main UI | Runtime health and sanitized authentication logs agreed with the visible result | None |
| `REL-UC-003` | Open the connected-account detail state | Headed Chromium | `PASS` | Connected Accounts opened automatically after first login | Browser state and runtime logs agreed | None |
| `REL-UC-004` | Refresh after first login | Headed Chromium | `PASS` | Authentication and setup state persisted after reload | Isolated persistence state survived the refresh | None |
| `REL-UC-005` | Upgrade an existing running installation with restart | Public upgrade CLI | `PASS` | Upgrade completed and the user-facing runtime returned healthy | Transaction ledger committed; strict continuity comparison reported no differences | None |
| `REL-UC-006` | Log in after upgrade and refresh | New headed Chromium session | `PASS` | The pre-upgrade synthetic account opened the main UI and remained authenticated after refresh | Post-upgrade runtime health and sanitized login logs agreed | None |
| `REL-UC-007` | Upgrade an established but deliberately stopped installation | Public upgrade CLI | `PARTIAL` | Operation failed closed and restored the stopped state | Private stopped-storage comparison passed, but the outer pre-audit could not inspect stopped MongoDB | Remove the safe outer-audit false negative |
| `REL-UC-008` | Use live health-provider data | Health CLI/provider boundary | `BLOCKED` | Not run | Two credentialed live-provider tests were skipped | Owner OAuth credentials are required |
| `REL-UC-009` | Complete an audible LiveKit call | Modern playground/voice boundary | `BLOCKED` | Not run | Source, build, test, and first-run browser gates passed | Private credentialed voice runtime is required |
| `REL-UC-010` | Install a signed/notarized Native release | Native distribution boundary | `BLOCKED` | No release artifact was published | Source policy and packaged-component checks passed | Release-owner signing and physical-machine matrix are required |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: prerelease publication union and installer/upgrade continuity.
- Requirement: merge public-safe nested work first, pin exact public commits, and prove clean install
  plus existing-user upgrade without loss or reliance on development-machine leftovers.
- Use case: fresh install, first-run browser flow, running-install upgrade, and post-upgrade reload.
- QA case: `REL-002`, `REL-003`, `REL-008`, `REL-009`, and `REL-010`.
- Expected result: exact reviewed component refs, healthy fresh install, preserved account/state across
  upgrade, clean privacy review, and explicit external gates.
- Actual evidence: exact merge-tree comparisons, full release tests, isolated installer/runtime
  evidence, real-browser flows, strict continuity manifests, file ledger, and secret scan.
- Remaining gap or fix: stopped-runtime outer-audit false negative; credentialed provider and voice
  checks; signed/notarized Native artifact matrix.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | PASS — release readiness and installer continuity through `REL-002/003/008/009/010` |
| Code owning path | Which code path owns the behavior? | PASS — installer, upgrade transaction/audit, component manifests, and nested runtime source were traced |
| Docs and nested docs/repos | Which docs define expected behavior? | PASS — installer/config compiler requirements, public/private boundary requirements, QA map, continuity operations, and nested repo docs were reviewed |
| Scripts or harnesses | Which suites exercised it? | PASS — full parent release suite, focused manifest/Native tests, nested suites, public installer, upgrade CLI, and Playwright |
| Local/external prerequisite state | Which prerequisites were proven healthy or degraded? | PARTIAL — isolated MongoDB/API/frontend were healthy; owner OAuth, private LiveKit credentials, and signing infrastructure were unavailable |
| Logs | Which sanitized logs confirm the result? | PASS — install, health, authentication, transaction, and restart conclusions matched visible behavior; raw logs remain private |
| DB/state/persistence | What confirms persistence? | PASS — synthetic account authentication survived initial reload and the strict running-upgrade comparison |
| Generated/shipped artifact | What generated or shipped output was inspected? | PARTIAL — compiled config, runtime receipts, browser build, component manifests, and mounted component trees were inspected; signed release artifact was not run |
| Real user path | Which path was used like a user? | PASS — installer and upgrade CLI plus headed Chromium registration, login, connected-account detail, and refresh |
| Visual/UX comparison | Did visible behavior match expected behavior? | PASS — tested install and browser paths matched expectations, with zero console errors |
| Not run / blocked | Which surfaces remain open? | BLOCKED — credentialed health-provider records, audible LiveKit call, and signed/notarized Native distribution |

Supporting evidence cannot replace required user-path evidence. The blocked external surfaces remain
blocked even though their source and automated gates passed.

## User-Grade Evidence

- Surface exercised: public installer CLI, public upgrade CLI, isolated native runtime, and headed
  Chromium.
- Real user path: fresh install, start, synthetic registration, automatic Connected Accounts detail,
  reload, running-install upgrade, new-session login, and post-upgrade reload.
- Visible outcome: the product rendered registration and the main UI; the synthetic user could log
  in before and after upgrade; zero browser console errors were observed.
- Expanded/detail state: Connected Accounts opened automatically after first login.
- Persistence/reload result: authentication and setup persisted on first-run reload; the same
  synthetic account remained usable and authenticated after upgrade and refresh.
- Local/external prerequisite state: isolated local runtime dependencies were healthy. Owner OAuth,
  private LiveKit credentials, and release signing/notarization were unavailable.
- Evidence retrieval classification, if applicable: auth/config missing for credentialed health and
  voice checks; local tested prerequisites were available.
- Fallback path, if applicable: no supporting-evidence substitution was used for blocked health,
  voice, or signed-artifact paths.
- Backend/log/DB confirmation: sanitized health, authentication, transaction, restart, and strict
  continuity results agreed with the visible browser behavior.
- Final model/runtime wording check: this report claims only the exercised source install and
  running-upgrade paths; it labels every unrun external surface `BLOCKED` and the total result
  `PARTIAL`.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for any required visible-UI, detail-state,
  persistence, or wording step.

## Automated Evidence

```bash
python3 -m pytest tests/release/ -q
python3 -m pytest tests/release/test_component_bootstrap.py tests/release/test_native_component_policy.py tests/release/test_public_install_contract.py -q
python3 -m pytest tests/release/test_native_public_safety.py tests/release/test_project_boundary_contamination.py tests/release/test_qa_operating_contract.py tests/release/test_qa_results_public_safety.py tests/release/test_qa_storage_guard.py -q
```

- Parent complete release suite: 2,638 passed, 10 skipped, 0 failed.
- Final parent manifest/bootstrap/Native slice: 145 passed, 0 failed.
- LibreChat: 4,165 API passed / 19 skipped; 1,578 client passed; 418 data-schema passed /
  3 skipped; 15/15 hosted checks passed.
- Modern playground: 153 tests, formatting, supported-Node build, hosted check, and real-browser
  first-run QA passed.
- Viventium Health: 52 passed / 2 credentialed live-provider tests skipped; clean build, isolated
  install, and first-run CLI smoke passed.
- GlassHive: runtime, UI, real-browser, and secret-scan gates passed.
- Bounded independent privacy and functionality/release reviews found no unresolved publication
  blocker after validated fixes. A full-context review that produced no result was stopped at the
  configured 15-minute bound.

## Findings

- Defects: the stopped-runtime outer pre-audit cannot inspect stopped MongoDB and causes a safe
  false negative; rollback restored the stopped state. This remains a scoped P2 follow-up.
- Regressions: none observed in source consolidation, clean install, first run, running-install
  upgrade, or post-upgrade persistence.
- Flakes: none; parent test output contained only temporary-directory cleanup warnings.
- Environment issues: owner OAuth, private LiveKit credentials, and signing/notarization services
  were outside this public-safe run.
- Residual risks: GlassHive public `main` contains an older pre-existing personal-email metadata
  occurrence not introduced here; public history was not rewritten. One reviewed GlassHive helper
  binary is ad-hoc signed. Live provider, audible voice, and signed Native artifact gates remain.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.

## Publication Gate

The parent branch may be proposed through a non-draft pull request after its final file ledger,
secret scan, remote-head comparison, and hosted required checks pass. Merge is allowed only if the
remote PR head remains byte-identical to the locally audited candidate.
