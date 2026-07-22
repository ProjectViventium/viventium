# Productivity Live-Eval Secret Isolation - 2026-07-20

## Summary

- Result: `PARTIAL`
- Build/source under test: isolated parent release worktree workflow source
- Runtime/artifact under test: GitHub Actions workflow definitions; no hosted run artifact
- Environment: local static QA with synthetic names and no provider-secret values
- Tester: Codex release-safety audit
- Related change: isolate untrusted pull-request validation from protected provider-backed live eval

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `REL-009` | `PARTIAL` | RED two failures; GREEN 19 workflow tests | Source boundary passes; hosted policy remains external |
| `REL-UC-004` | `PARTIAL` | Workflow source and static CLI test | GitHub Actions PR/manual deployment path was not run |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `REL-UC-004` | Open an activation-code PR, then manually run the live eval from protected default branch | Local CLI/static workflow source only | `PARTIAL` | Static PR workflow contains no secret references; live workflow is separately gated | Workflow diff, test output, requirement and case updates | Run both workflows on GitHub and inspect sanitized protection/deployment evidence |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: productivity activation CI live-eval gate
- Requirement: public/private boundary, CI provider-secret boundary
- Use case: contributor PR validation followed by release-owner protected live eval
- QA case: `REL-009` and `REL-UC-004`
- Expected result: PR code and dependency lifecycle receive no provider credentials; only the
  reviewed protected-branch eval step receives dedicated synthetic credentials
- Actual evidence: pre-fix regression failed on three secret references; split source passes 19/19
  workflow tests, including exact-pin fetch and shell pass/failure/outage semantics, and YAML parsing
- Remaining gap or fix: verify hosted environment reviewers, deployment branch allowlist,
  environment-scoped secrets, default-branch protection, and real check/deployment histories

## Full-View Evidence Checklist

| Evidence surface | Required question | Evidence / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Doc 40 CI boundary; `REL-009`; `REL-UC-004` |
| Code owning path | Which code path owns the behavior? | The two productivity activation workflow files, component bootstrap, and workflow static tests |
| Docs and nested docs/repos | Which docs or nested repo docs define the expected behavior? | Key principles, doc 40, runtime QA map, release-readiness cases |
| Scripts or harnesses | Which suites exercised it? | `test_ci_release_workflows.py`, `test_no_runtime_nlu.py`, YAML parser, diff check |
| Local/external prerequisite state | Which hosted prerequisite was proven? | GitHub environment/ruleset state is not locally observable; current nested pin is not publicly reachable; `BLOCKED` pending nested publication and owner inspection |
| Logs | Which sanitized logs confirm or contradict the result? | Pytest RED/GREEN totals only; no hosted workflow logs |
| DB/state/persistence | Which persisted state confirms it? | Not applicable to source; hosted deployment history was not run |
| Generated/shipped artifact | Which artifact was inspected? | Workflow YAML parsed locally; no GitHub run artifact exists yet |
| Real user path | Which real path was used like a user? | Local CLI source-validation path only; GitHub Actions path not run |
| Visual/UX comparison | Does visible behavior match? | Not applicable locally; no browser UI or hosted check view was exercised |
| Not run / blocked | Which required surface was not run? | Protected-environment PR/manual hosted run and settings inspection |

The GitHub Actions path is not replaced by static evidence. A local CLI test and source inspection
cannot replace required user-path evidence, so the result remains `PARTIAL`.

## User-Grade Evidence

- Surface exercised: local CLI against GitHub Actions workflow source
- Real user path: contributor/release-owner GitHub Actions PR and manual paths were not run; local CLI validation only
- Visible outcome: terminal showed the pre-fix secret-boundary failures and the post-fix 19/19 pass
- Expanded/detail state: failure detail named the PR-reachable workflow and exact secret-boundary class
- Persistence/reload result: not applicable to static source; hosted deployment history remains unverified
- Local/external prerequisite state: repository-admin view of GitHub environment and branch rules was unavailable
- Evidence retrieval classification, if applicable: unsupported configuration for local inspection of hosted policy
- Fallback path, if applicable: source/static CLI review used; hosted browser/computer inspection is blocked pending repository-owner access
- Backend/log/DB confirmation: no backend or DB applies; only sanitized pytest and YAML-parser output was inspected
- Final model/runtime wording check: no model/runtime output applies; workflow failure text remains explicit
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit tests are supporting evidence, not substitutes for any required visible-UI, detail-state, persistence, or wording step.

## Automated Evidence

```bash
python -m pytest tests/release/test_ci_release_workflows.py -q
python -m pytest tests/release/test_ci_release_workflows.py tests/release/test_no_runtime_nlu.py -q
python -m pytest tests/release/test_qa_operating_contract.py -q -k 'not release_tests_have_central_qa_ownership'
python -c 'parse every workflow YAML file'
git diff --check -- workflow-test-and-documentation-files
git ls-remote public-librechat-origin pinned-commit
```

## Findings

- Defects: the prior PR-triggered job exposed Groq, OpenAI, and Anthropic secrets at job scope,
  including npm lifecycle and PR-controlled test code
- Regressions: none in the local workflow contracts after the split; synthetic shell execution
  preserves all-pass and partial-provider recovery while wrong decisions and an all-provider outage
  fail the live gate closed
- Flakes: none observed
- Environment issues: hosted environment/ruleset configuration cannot be proven from local source;
  the current local LibreChat pin is not yet reachable from its public origin
- Residual risks: a malicious change merged to the protected branch can still misuse live secrets.
  Protected-branch PR gates, dedicated synthetic spend-limited credentials, environment-only
  storage, and deployment-branch restrictions are mandatory external controls. A multi-member
  organization should additionally require a separate environment reviewer; the current sole-owner
  organization must not enable no-self-review because it would create an impossible approval queue.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
