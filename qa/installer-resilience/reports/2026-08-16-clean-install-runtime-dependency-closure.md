# Clean-Install Runtime Dependency Closure QA Run - 2026-08-16

## Summary

- Result: PASS for `INST-005`.
- Build/source under test: parent commit `8d62bbab70513d1a6fcce9cc20bb470f001442cc`.
- Runtime/artifact under test: fresh public clone, freshly bootstrapped pinned components, generated
  runtime configuration, and private Viventium-Health runtime.
- Environment: macOS arm64, new temporary clone, empty isolated App Support root, supported
  headless/no-start installer path.
- Tester: Codex local QA.
- Related change: clean-install runtime dependency closure for Parallel Work.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `INST-005` | PASS | Public install and doctor exited successfully; `924` parent release tests passed with `5` documented skips | No unresolved runtime placeholder or state-root escape remained |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `INST-005-UC-001` | Install Viventium from a fresh public clone with an explicit empty local state root | Public `install.sh` CLI followed by `bin/viventium doctor` | PASS | Installer displayed configured services and next steps; doctor reported successful compilation, resolved placeholders, and valid pinned components | Exact parent/component refs, private health-runtime modes, manifest metadata, generated key presence, and state containment were inspected | None for `INST-005`; start/browser acceptance belongs to the Parallel Work runtime cases |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: installer/runtime dependency closure used by Parallel Work.
- Requirement: `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md` and
  `docs/requirements_and_learnings/55_Parallel_Work_Orchestration.md`.
- Use case: a new local user installs the pushed public candidate into an empty selected state root.
- QA case: `INST-005`.
- Expected result: pinned dependencies exist, generated placeholders resolve, private runtime modes
  are enforced, doctor passes, and generated state does not escape the selected root.
- Actual evidence: public install and doctor passed; four nested component refs matched the parent
  lock; required generated keys were present; `9` generated YAML placeholders had `0` unresolved
  keys; the GlassHive DB path remained inside the selected root.
- Remaining gap or fix: none for this installer case.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Requirement 39 clean-install closure; `INST-005` |
| Code owning path | Which code path owns the behavior? | `bin/viventium`, component bootstrap, config compiler, and health-runtime installer |
| Docs and nested docs/repos | Which docs or nested repo docs define the expected behavior? | Requirements 39 and 55; parent component lock |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | Public installer, doctor, release suite, and the four owning regression modules |
| Local/external prerequisite state | Which required prerequisite was proven? | Native macOS prerequisites were available; network fetches resolved public pinned components |
| Logs | Which sanitized logs confirm or contradict the result? | Installer and doctor both exited `0`; doctor confirmed compiled config, resolved placeholders, and pinned components |
| DB/state/persistence | Which state confirms it? | Generated GlassHive DB path was contained under the selected isolated state root; no DB contents were read |
| Generated/shipped artifact | Which generated or installed artifact was inspected? | Health runtime directory/executable/manifest modes were `0700`/`0700`/`0600`; manifest component ref matched the lock |
| Real user path | Which supported entrypoint was used like a user? | `install.sh --headless --config-input ./config.minimal.example.yaml --app-support-dir /tmp/viventium-qa-app-support --no-start`, then `bin/viventium doctor` |
| Visual/UX comparison | Does the delivered result match expectations? | CLI summary showed the configured install and honest setup-needed rows; no false started-service claim was made |
| Not run / blocked | Which required surface was not run? | Browser/runtime start is outside `INST-005` and remains tracked by the Parallel Work QA catalog |

## User-Grade Evidence

- Surface exercised: public installer and doctor CLI.
- Real user path: fresh public clone to supported headless/no-start install, followed by doctor.
- Visible outcome: install completed with configured-service and next-step tables; doctor passed every
  applicable check.
- Expanded/detail state: exact component refs, safe manifest fields, permissions, generated key
  names, placeholder counts, and state-root containment were inspected.
- Persistence/reload result: the installed health runtime's status command returned `ready` from the
  generated artifact after installation.
- Local/external prerequisite state: native prerequisites and public component fetches were healthy.
- Evidence retrieval classification: successful.
- Fallback path: not applicable.
- Backend/log/DB confirmation: generated config contained all six required runtime keys, with no
  secret values printed; all `9` YAML placeholders resolved; state containment passed.
- Final model/runtime wording check: installer correctly described the runtime as configured, not
  started, because `--no-start` was used.
- Substitution check: automated tests supported but did not replace the real public install/doctor
  run.

## Automated Evidence

```bash
python3 -m pytest tests/release/ -q
# 924 passed, 5 skipped

./install.sh --headless --config-input ./config.minimal.example.yaml \
  --app-support-dir /tmp/viventium-qa-app-support --no-start
bin/viventium --app-support-dir /tmp/viventium-qa-app-support doctor
# PASS
```

Pinned refs observed:

- parent `8d62bbab70513d1a6fcce9cc20bb470f001442cc`
- LibreChat `020a01d9f65a7c5e374c2413699faf0efb108943`
- GlassHive `6167132ad0aa1d8d6d30746fe9c9631f56310d9f`
- Viventium-Health `70e718d21bfa0b120b100ab2b82410cd82e1b8a4`
- modern playground `83044a509b2ccd798deee916291776912b5c1b9e`

## Findings

- Defects: none remaining in `INST-005`.
- Regressions: none observed.
- Flakes: none observed.
- Environment issues: none.
- Residual risks: runtime start and browser/Telegram/voice Parallel Work acceptance remain separate
  release gates and are not implied by this installer-only PASS.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
