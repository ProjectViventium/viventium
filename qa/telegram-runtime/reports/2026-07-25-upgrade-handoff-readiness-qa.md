# Telegram Upgrade Handoff Readiness QA Run - 2026-07-25

## Summary

- Result: `PASS-AUTOMATED/PARTIAL-LIVE`
- Build/source under test: local universal-upgrade hardening candidate
- Runtime/artifact under test: generated owner-only Telegram launch package and user launchd job
- Environment: local macOS runtime using synthetic/public-safe report data
- Tester: Codex plus independent review-only release reviewer
- Related change: detached-start monitoring and Telegram cross-checkout handoff hardening

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `TR-011` | `PASS-AUTOMATED/PARTIAL-LIVE` | 23 focused handoff tests, 41 Telegram release tests, two successful real launchd handoffs | External Telegram message delivery was not run. |
| `STABLEDEV-012` | `PARTIAL` | Attempt-scoped detached marker regressions and protected-hash comparison | Complete local-runtime promotion remained pending at report time. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `TELEGRAM-UC-010` | Restart across a checkout handoff and recover safely if the candidate fails. | Telegram runtime launch package, user launchd job, and handoff CLI | `PARTIAL` | One recognized predecessor stopped; one successor entered polling and committed; cleanup reported no remaining job. | Typed owner receipt, exact PID/start/repo/cwd checks, sanitized PTB start/stop timestamps, transaction cleanup, source/tests, and owning docs. | Send and receive an external synthetic Telegram turn after the complete latest runtime is promoted. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Telegram bridge continuity during universal local upgrade.
- Requirement: `03_Telegram_Bridge.md`, `50_Stable_Dev_Runtime.md`, and stable token-hash poller
  ownership without duplicate polling or lost rollback.
- Use case: `TELEGRAM-UC-010`, restart from a successor checkout and preserve one working poller.
- QA case: `TR-011`, upgrade handoff preserves one recognized poller.
- Expected result: exact predecessor ownership is proven before stop; successor commits only after
  typed polling/webhook readiness bound to its attached process identity; failure preserves rollback.
- Actual evidence: the generated clean-environment launch package entered PTB polling in about one
  second; a real user launchd predecessor-to-successor handoff succeeded twice. The post-fix repeat
  revalidated the exact attached PID/start/repo/cwd at wait and commit. Cleanup left no PID file,
  owner receipt, handoff transaction, or launchd job. Protected configuration hashes stayed exact.
- Remaining gap or fix: promote the complete latest local runtime, send an external synthetic text
  turn, measure reply latency, refresh/restart, and correlate delivery with runtime/log evidence.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Telegram bridge and stable-runtime requirements; `TELEGRAM-UC-010`; `TR-011`. |
| Code owning path | Which code path owns the behavior? | Poller handoff helper, full-stack Telegram launcher, detached upgrade monitor, and PTB singleton readiness publisher. |
| Docs and nested docs/repos | Which docs or nested repo docs define the expected behavior? | Telegram bridge, stable dev runtime, runtime QA map, and `qa/telegram-runtime/cases.md`. |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | Handoff helper CLI, generated launch script, launchd, focused Telegram tests, CLI upgrade tests, and release-suite gate. |
| Local/external prerequisite state | Which required local service, provider, Docker-backed sidecar, OAuth grant, API key, model, or hosted dependency was proven healthy or degraded? | Existing private Telegram configuration loaded successfully and Telegram API startup calls completed; complete core runtime and external message delivery were not exercised. |
| Logs | Which sanitized logs confirm or contradict the result? | PTB reported polling start, predecessor shutdown, and successor `Application started`; no token-bearing lines were retained. |
| DB/state/persistence | Which sanitized state, DB count/hash, persisted message, config, or artifact confirms it? | Exact protected config/helper/binding/owner-environment hashes were unchanged; post-run Telegram ownership state was empty. No message DB row was created. |
| Generated/shipped artifact | Which generated config, compiled bundle, prebuilt helper, or installed artifact was inspected when applicable? | The owner-only generated Telegram runtime environment and launch script were used without exposing their contents. |
| Real user path | Which browser/computer, Telegram, voice, installer, CLI, MCP/tool, scheduler, or GlassHive path was used like a user? | Local Telegram runtime restart/handoff through the same generated launchd path used by Viventium upgrade. |
| Visual/UX comparison | Does the visible UI/UX or delivered result match the expected behavior and supporting evidence? | CLI phases and sanitized runtime status matched the one-predecessor/one-successor transition; no Telegram chat bubble was delivered, so user delivery remains partial. |
| Not run / blocked | Which required surface was not run, and why is the result partial or blocked? | External Telegram send/reply, measured reply latency, and full promoted-runtime persistence were deferred until the complete candidate is active. |

## User-Grade Evidence

- Surface exercised: Telegram runtime startup and cross-checkout restart through the real user
  launchd job used by the local Viventium launcher.
- Real user path: start a configured poller, verify typed readiness, prepare takeover, stop the
  recognized predecessor, start and attach the successor, wait for typed readiness, commit, then
  stop and inspect cleanup.
- Visible outcome: the diagnostic reported predecessor ready, predecessor stopped, and successor
  ready/identity committed; no duplicate poller or stranded handoff remained.
- Expanded/detail state: owner and transaction state showed one exact PID/start/repo/cwd identity;
  success-edge exit and reused-PID variants retained rollback in synthetic tests.
- Persistence/reload result: a second post-fix real handoff also succeeded; cleanup after both runs
  left no PID file, owner receipt, transaction, or launchd job.
- Local/external prerequisite state: the configured Telegram API path and generated private launch
  package were healthy; the complete Viventium core and an external user message were not run.
- Evidence retrieval classification, if applicable: not applicable; this was runtime ownership and
  startup QA rather than provider/web evidence retrieval.
- Fallback path, if applicable: launchd and clean-environment direct launch both reached typed
  readiness; no browser/computer/local-delegation fallback applied.
- Backend/log/DB confirmation: sanitized PTB lifecycle timestamps, exact protected hashes, process
  identity receipts, and empty post-run ownership state support the result; no message DB evidence
  exists because no external message was sent.
- Final model/runtime wording check: this report claims launch and handoff readiness only and
  explicitly does not claim Telegram message delivery, reply latency, or complete upgrade readiness.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for the required external Telegram send/reply and
  promoted-runtime persistence path, so the live result remains `PARTIAL`.

## Automated Evidence

```bash
uv run --with pytest python -m pytest tests/release/test_telegram_poller_handoff.py -q
uv run --with pytest --with pyyaml python -m pytest \
  tests/release/test_telegram_codex_runtime_paths.py \
  tests/release/test_telegram_launchctl_ownership.py \
  tests/release/test_telegram_lazy_startup_contract.py \
  tests/release/test_telegram_media_prereqs.py \
  tests/release/test_telegram_poller_handoff.py \
  tests/release/test_telegram_transcription_error_contract.py -q
uv run --with pytest --with pyyaml python -m pytest tests/release/test_cli_upgrade.py -q
bash -n bin/viventium
bash -n viventium_v0_4/viventium-librechat-start.sh
python3 -m py_compile scripts/viventium/telegram_poller_handoff.py
git diff --check
```

## Findings

- Defects: the detached wrapper's normal exit was treated as activation failure; Telegram guard
  lifetime was shorter than the attach/readiness contract; ready receipts were not bound and
  revalidated against the attached process at every commit edge; raw numeric timeout overrides
  could trigger Bash octal/overflow behavior.
- Regressions: no focused Telegram, CLI upgrade, shell syntax, Python compilation, or protected
  state regression remained after correction.
- Flakes: none observed in the two real handoffs or focused suites.
- Environment issues: the complete core runtime was stopped during this report; external Telegram
  delivery therefore remained intentionally unclaimed.
- Residual risks: external send/reply latency, full promoted-runtime restart persistence, and
  cross-surface delivery evidence remain required.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
