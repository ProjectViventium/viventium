# Stable Dev Runtime QA Run - 2026-08-05

## Summary

- Result: PARTIAL while the real installed-helper recovery lane waits for the one-time macOS
  Documents-folder approval. Current-checkout activation, artifact installation, automated
  supervision behavior, canonical Prompt Workbench ownership, current browser reachability, and
  Conversation Recall recovery passed.
- Build/source under test: the current dirty development checkout, including its dirty nested
  LibreChat and GlassHive working trees.
- Runtime/artifact under test: generated local-prod config, the shipped universal helper prebuilt,
  installed macOS helper, native API/frontend/playground processes, Prompt Workbench, and
  Docker-backed Recall services.
- Environment: local macOS native runtime with Docker-backed optional services.
- Tester: Codex.
- Release-readiness note: this proves the exact local working tree requested by the developer. It
  does not prove that the dirty tree is the latest clean remote release; the root branch has no
  usable upstream, remote inspection was unavailable, and selected component pins differ from the
  checked-out component commits.

## Scope Run

| Case ID | Result | Evidence | Remaining gap |
| --- | --- | --- | --- |
| `SDR-003` | PASS | Active checkout, helper checkout, live stack owner, and initial running process roots matched this checkout after validated activation. | None for local activation; release/latest-remote status remains unproven. |
| `SDR-007` | PASS | Status exposed Recall degradation until semantic recovery and retained the independent Memory Hardening warning. Prompt Workbench status now requires active-checkout ownership evidence and rejects even a healthy listener owned by another checkout. | The Memory Hardening warning belongs to a prior scheduled run and was not mutated. |
| `SDR-012` | PARTIAL | Desired-state/backoff/persistence tests passed; the rebuilt shipped prebuilt was installed; its source and binary integrity metadata match; the installed executable differs only in expected signing/link-edit metadata; helper/login registration points at this checkout. | The post-stop relaunch is waiting at the operating-system folder approval prompt, so full service recovery and post-recovery browser refresh are not yet proven. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Result | Actual evidence | Remaining gap |
| --- | --- | --- | --- | --- |
| `STABLEDEV-UC-001` | Activate this checkout, restart local prod, inspect status, and open web surfaces. | PASS | Supported activation validated config and doctor, installed the final helper, converged checkout ownership, and rendered LibreChat and the modern playground in a headed browser with refresh persistence and zero console errors. | A post-recovery browser rerun is required after the live recovery lane. |
| `STABLEDEV-UC-002` | Inspect status with an enabled optional service degraded. | PASS | Recall authentication failure was classified rather than reported as an empty result; after credential reconciliation its semantic health returned `UP`. The unrelated maintenance warning stayed visible. | None for truthful classification. |
| `STABLEDEV-UC-003` | Verify Prompt Workbench ownership and isolation. | PARTIAL | A stale Workbench from another checkout was stopped only after process/path verification. The active checkout then reclaimed canonical port `8781`; status now resolves the owned state file instead of trusting a configured port alone. Main-stack ownership was unchanged. | The native helper submenu control was not clicked in this run. |
| `STABLEDEV-UC-006` | Inspect update safety on dirty development work. | PARTIAL | Read-only update inspection refused to present dirty root/component state as release-ready and did not mutate it. | Clean remote comparison, successful update, and headed update modal were not run. |
| `STABLEDEV-UC-008` | Stop a desired-running stack outside the helper menu and wait for automatic recovery. | PARTIAL | The installed helper detected the stop and submitted a bounded relaunch from this checkout. macOS blocked script access and displayed the expected protected-folder approval prompt. | User approval, completed recovery, health convergence, and browser refresh remain. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: a stable installed local-prod runtime backed by the current development checkout.
- Requirement: `docs/requirements_and_learnings/50_Stable_Dev_Runtime.md`, including durable helper
  desired-state supervision.
- Use case: a developer promotes this checkout and expects the installed app to keep using and
  recovering it after login.
- QA cases: `SDR-003`, `SDR-007`, `SDR-012`, `STABLEDEV-UC-001`, and
  `STABLEDEV-UC-008`.
- Expected result: one active-checkout pointer, no source copy, validated config, a source-matched
  shipped helper installed through the supported signed-app path, truthful owned-sidecar status,
  bounded automatic recovery, and
  working browser surfaces after recovery.
- Actual evidence: activation and artifact alignment passed; the helper persisted desired state and
  attempted recovery; the real recovery is paused at the required macOS folder-approval boundary.
- Remaining fix: approve the visible operating-system prompt, then complete health, ownership,
  persistence, and browser verification.

## Full-View Evidence Checklist

| Evidence surface | Result |
| --- | --- |
| Requirement/use case | Stable Dev Runtime current-checkout promotion and durable supervision are mapped to `SDR-003`, `SDR-007`, and `SDR-012`. |
| Owning code | Public CLI activation/runtime-checkout flow, launcher, helper installer/prebuilt, macOS helper controller, and install-summary status logic were inspected. |
| Runtime state | Active checkout, helper binding, and stack owner converged on this checkout; desired state is `running`. |
| Generated/shipped/installed artifact | Config compiled and doctor passed. Swift release build passed. The universal helper prebuilt and integrity metadata were rebuilt and matched current helper source. Supported installation then applied the app bundle's ad-hoc signature; after removing signatures from temporary architecture slices, each installed slice differed from the shipped slice by one byte in `__LINKEDIT` virtual-size metadata and no executable-content bytes. |
| Prompt Workbench | Stale cross-checkout process was identified and stopped surgically; current owned state now serves canonical port `8781`. |
| Recall | RAG API and vector DB containers were recreated from this checkout's compose definition and current bind mount after authentication repair; the existing corpus remained present and semantic health returned `UP`. |
| Browser | Initial headed LibreChat and modern-playground checks, refresh, and console inspection passed; post-recovery rerun is pending. |
| Scheduler/provider state | A scheduled workflow reports partial/error results because an OpenAI connected account requires reconnection. This is an independent user-auth issue, not silently repaired here. |
| Memory maintenance | A prior forced-termination receipt leaves Memory Hardening marked Action Required; stale dead PID/lock evidence was inspected and left for the owning self-healing run. |
| Public/private safety | No source was copied into install paths; this report contains no secrets, private records, screenshots, personal identifiers, or absolute local paths. |

## User-Grade Evidence

- Surface exercised: supported local-prod activation/status CLI, installed macOS helper, headed
  LibreChat and modern-playground browser surfaces, Prompt Workbench, and the macOS protected-folder
  approval boundary.
- Real user path: activate this checkout, observe checkout ownership and service status, open and
  refresh the local web surfaces, stop the desired-running stack outside the helper, and wait for
  automatic helper recovery.
- Visible outcome: the initial browser surfaces rendered cleanly and refreshed without console
  errors; the recovery attempt visibly reached the required macOS Documents-folder approval prompt.
- Expanded/detail state: CLI details showed all four checkout-owner surfaces aligned, canonical
  Workbench ownership on port `8781`, core services running, and independent scheduler/maintenance
  warnings still visible.
- Persistence/reload result: the initial LibreChat refresh passed and helper desired state survived
  reinstall/reactivation; the required post-recovery refresh is pending the operating-system prompt.
- Local/external prerequisite state: local native prerequisites, Docker-backed Recall, SearXNG,
  Firecrawl, and both workspace MCP services were checked; scheduler provider auth remains degraded.
- Evidence retrieval classification, if applicable: Recall's initial result was local prerequisite
  unavailable because its API could not authenticate to the vector database; it was not treated as
  a successful empty result.
- Fallback path, if applicable: no mock substituted for the blocked recovery path; the visible macOS
  approval is recorded as the remaining user action.
- Backend/log/DB confirmation: helper logs show bounded recovery submission, persisted desired state
  remains `running`, process roots match this checkout, and the preserved Recall corpus remained
  available after semantic health recovery.
- Final model/runtime wording check: status says `needs attention` for scheduler/maintenance issues
  and does not call the dirty checkout the latest clean remote release.
- Substitution check: logs, state, API responses, source inspection, model review, and unit tests
  support the activation and partial recovery evidence; they do not replace the pending post-approval
  service convergence and browser refresh.

## Automated Evidence

```bash
uv run --with pytest --with pyyaml python -m pytest tests/release/test_stable_dev_runtime_workflows.py -q
uv run --with pytest --with pyyaml python -m pytest \
  tests/release/test_macos_helper_supervision.py \
  tests/release/test_macos_helper_install.py \
  tests/release/test_install_summary.py -q
swift build -c release --package-path apps/macos/ViventiumHelper
./scripts/viventium/build_macos_helper_fallback.sh
bin/viventium dev-runtime activate-current --validate --restart \
  --allow-protected-folder --allow-dirty-local-testing
```

- Stable runtime workflow tests: 39 passed.
- Helper supervision/install/status tests: 90 passed after rebuilding the shipped helper prebuilt.
- Swift release build: passed.
- Activation config compilation and doctor: passed.
- Current browser: LibreChat and modern playground passed; refresh passed; zero console errors.

## Findings

- The runtime originally used another checkout, so the answer to the developer's initial question
  was no.
- The installed helper source originally provided login startup but did not preserve a complete
  durable current-source supervision contract. Desired state, bounded exponential backoff,
  stop/resume semantics, config preservation, and shipped artifact coverage were added.
- Status could report a stale Prompt Workbench on the configured port as green even when it belonged
  to another checkout. Runtime health now requires an ownership record matching the active checkout;
  the configured URL remains visible only as operator context.
- The current checkout is dirty and selected component commits do not all match the parent lock.
  Exact local-working-tree alignment is proven; latest clean remote/release alignment is not.
- The real protected-folder recovery attempt surfaced the expected one-time macOS permission
  boundary. It remains a hard user-path gate rather than being replaced with mocks or source
  inspection.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots, personal emails, account IDs, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo identifiers, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, raw DB exports, App Support dumps, or private checkout names.
- [x] Private runtime evidence is summarized with public-safe conclusions only.
