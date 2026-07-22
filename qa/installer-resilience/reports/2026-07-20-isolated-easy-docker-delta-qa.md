# Isolated Easy Install Docker delta QA — 2026-07-20

## Summary

`PASS` for the scoped Easy Install Docker core source-candidate lane and its newly hardened
failure, recovery, credential-recovery, and removal boundaries. This is `PARTIAL`, not
public-release acceptance: supported component bootstrap, Docker Desktop GUI/Keychain/TCC behavior,
physical sleep/wake and resource behavior, browser-level Recall answers, exact signed payload, and
nested pin/shipped-artifact alignment remain open.

The run used a dedicated Apple-silicon VM and Docker endpoint with no host filesystem mounts. It
installed and started the core, exercised registration and duplicate-registration guidance,
Connected Accounts, Feelings, supported stop/start, local password recovery, fresh login,
Docker-daemon loss/recovery, failed-start rollback, and preserve-data uninstall. All accounts and
data were synthetic. Raw screenshots, logs, generated secrets, database state, and the disposable
runtime remain outside the public repository.

## Scope Run

- Parent source candidate in an isolated publication worktree; no commit, push, release, or cloud
  mutation. Browser/runtime evidence used LibreChat tree
  `923824d23f6ab47350b14efc0e994e04423fcb3a`. The final reviewed LibreChat candidate is commit
  `039fb75f27a947f35570904d669905941ac7a257`, tree
  `a76737f4b694aee09df921d086516e478181a8c8`; its only change from the exercised runtime tree is the
  dependency-audit parser and its test.
- A follow-up Recall-enabled install used the same private runtime copy plus the uncommitted RAG
  portability candidate. It proved the supported install and restart path, but creates a new nested
  LibreChat delivery delta, so the earlier candidate commit/tree identifiers are not sufficient for
  final release alignment.
- Dedicated no-host-mount VM: four CPUs, 8 GiB RAM, ARM64 Ubuntu guest, Docker `29.5.2`.
- Dedicated Docker socket, context, config, containers, volumes, Compose project names, App Support
  target, high loopback ports, browser cache, and removal-backup root.
- Easy Install compatibility config: `install.mode: docker`, internal
  `install.experience: express`; optional providers, channels, remote access, voice, Recall/RAG,
  web search, and worker services disabled.
- A QA-only empty component manifest was necessary because the parent lock and shipped Native
  metadata still select LibreChat `7c702629599f5b229f9b49f6ea2f458c6981581a`, not the final
  candidate. The exercised LibreChat source was copied into private mutable QA state without `.git`,
  local environment files, logs, or dependency state. Therefore this run does not prove supported
  component bootstrap or shipped-artifact alignment.

## Traceability

| Feature | Requirement | Use case | QA case | Expected result | Actual evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| Easy Install Docker core | Native and Docker share one lifecycle | Install, open setup, restart, stop, recover account, uninstall | `INST-014`, `INST-021` | Core reaches browser setup without optional services and preserves state | 132-second corrected-candidate install, loopback API/web/Mongo, real Chromium Connected Accounts and Feelings, supported stop/start, password recovery, fresh login, and uninstall evidence | Public manifest/component bootstrap and exact shipped artifact |
| Docker outage | Selected daemon is a required Docker-mode prerequisite | Stop daemon, preflight, restore and restart | `INST-001`, `INST-011`, `INST-019` | Preflight fails closed; recovery is bounded | Explicit-endpoint preflight returned `1` with Docker-daemon guidance; cold recovery reached API/web in 21 polls and the later fault recovery was healthy on the first poll | Docker Desktop GUI/startup semantics and user-visible DB-operation failure during outage |
| Failed-start rollback | Only current-attempt processes are drained | Force Docker Mongo failure and native fallback | `INST-019` | Recorded target process group and pid records disappear; unrelated processes remain | Failed install returned nonzero, logged the drained group, and left API/web/Mongo ports, owned Mongo process, pid, and pgid records clean | Wider crash/reboot/concurrency matrix |
| Helper and Telegram ownership | Fixed-name local artifacts require target proof | Uninstall from a new shell; stop Telegram-disabled install | `INST-019`, `INST-025`, `TR-010` | Helper removal comes from persistent receipt; disabled Telegram never touches launchctl | Mode-`0600` no-helper receipt survived shell exit; uninstall skipped helper removal; disabled/no-receipt stop made no Telegram/launchctl call | Headed signed-helper, SMAppService, TCC and legacy physical migration |
| Docker data continuity | Restart and preserve-data uninstall retain synthetic state | Restart, inspect user record, recover credential, uninstall | `INST-005`, `INST-019` | Named volume survives restart and uninstall | The tested synthetic identity remained singular after stop/start; local password recovery returned one single-use link; fresh login succeeded; removal backup was mode `0700`; named Mongo volume and synthetic users remained after uninstall | Independent public restore and browser re-login after restore |
| Recall/RAG no-host-share continuity | Local Recall remains isolated, restart-persistent, and restore-honest | Opt in, embed/query synthetic corpus, restart, snapshot, restore | `RAG-004`, `RAG-006`, `RAG-007` | Supported install reaches semantic health; restart retains facts; restore requires derived rebuild | Recall-enabled install reached API/web/RAG; synthetic retrieval returned two distinctive facts; a 1,280-file PostgreSQL migration matched byte-for-byte; supported stop/launch retained both facts; complete snapshot and independent restore passed with explicit rebuild/reauth markers | Browser model answer and actual restored-corpus rebuild |

## Full-View Evidence Checklist

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Real user path: terminal install/start/stop/preflight/password-reset-link/uninstall and real
  Chromium registration, duplicate-registration recovery, account setup, Feelings navigation,
  password update, and fresh login were operated against the live isolated runtime.
- Expanded/detail state: Connected Accounts showed OpenAI, Anthropic, Groq, and Grok (xAI) with no
  saved local credential and explicit API-key actions; Feelings showed all nine bands and the off
  state.
- Persistence/state: Mongo named-volume identity and synthetic user counts were checked before and
  after the supported stop/start and again after uninstall; the tested identity remained singular,
  a fresh credential login reached authenticated chat after restart, and target App Support was
  moved to a recoverable mode-`0700` backup.
- Runtime evidence: process groups, pid files, socket listeners, Docker container/volume ownership,
  preflight exit status, stop output, and launch health were correlated with the visible browser
  path.
- Supporting evidence cannot replace required user-path evidence. Unit tests and source inspection
  support the ownership boundaries; Docker Desktop GUI, Keychain/TCC, physical power state,
  browser-level Recall answers, and exact installed-artifact proof remain `BLOCKED` or `PARTIAL`.

## User-Grade Evidence

- Surface exercised: Easy Install CLI, browser registration/login shell, ordinary chat sidebar,
  Connected Accounts, Feelings, preflight recovery guidance, stop, and uninstall.
- Real user path: the source-candidate command installed and launched the app, Chromium navigated
  the visible setup surfaces, the runtime completed a supported stop/start and was faulted, a local
  operator link reset the synthetic password, and uninstall ran from a new shell without inheriting
  the install-time helper-skip variable.
- Visible outcome: registration and setup rendered without page exceptions; account cards gave
  truthful missing-credential guidance; Feelings was discoverable and rendered its full disabled
  spectrum; daemon-down preflight named Docker and the repair action.
- Expanded/detail state: all four provider cards, account menu, sidebar controls, Feelings bands,
  receipt decision, and recovery output were inspected.
- Persistence/reload result: the synthetic user row persisted in the named Mongo volume through
  daemon and runtime stop/start. The pre-restart storage snapshot was not treated as sufficient;
  local password recovery changed the credential, and a new browser context then logged in and
  reached authenticated chat with Agent Builder, Prompt Templates, and Feelings visible.
- Backend/log/DB confirmation: the post-restart existing-email registration path kept one row for
  the tested synthetic identity. The API intentionally returned generic `200` guidance to resist
  account enumeration. Corrected visible copy did not claim registration success; it told the user
  to sign in with the existing password or reset it. The local reset endpoint returned `200`, and
  the subsequent fresh login returned `200` and authenticated chat.
- Final model/runtime wording check: no provider key was connected in this lane and no model answer
  is claimed. Provider lifecycle answers are owned by the separate synthetic provider reports.
- Substitution check: focused tests, source, logs, DB counts, and Docker inspection support but do
  not replace the actual browser/CLI evidence.

## Results

| Path | Result | Actual evidence |
| --- | --- | --- |
| Core Easy Install Docker install | `PARTIAL` | Fresh corrected source-candidate install completed in 132 seconds including dependency and web builds; API, web, and Mongo were healthy. Bootstrap remained partial because a QA-only empty component manifest bypassed the parent-lock/final-candidate mismatch. |
| Local privacy | `PASS` for tested core | API, web, and Mongo published only on dedicated `127.0.0.1` ports. |
| Connected Accounts empty state | `PASS` | Four provider cards showed no local credential and offered the appropriate API-key action. |
| Feelings discovery | `PASS` | Ordinary sidebar navigation opened the full nine-band Feelings page in the off state. |
| Docker-daemon outage | `PASS` for preflight/recovery | With the isolated socket pinned, preflight returned `1`; after daemon restart the core returned healthy. The host API/web processes stayed reachable during the short database outage, so a database-backed browser action during the outage remains unrun. |
| Supported stop/start and credential recovery | `PASS` | `stop` followed by `start` changed service PIDs, restored API/web health, retained the tested identity, produced one local reset link, accepted the replacement password, and allowed a fresh authenticated browser login. |
| Duplicate-registration recovery | `PASS` | The existing-email API returned generic `200` anti-enumeration guidance; visible copy offered sign-in or reset and did not claim a new registration succeeded. |
| Failed-start cleanup | `PASS` | Forced Docker-Mongo failure started native Mongo, the install returned nonzero, and rollback drained the exact recorded process group; no owned process, listener, or stale pid/pgid record remained. |
| Disabled Telegram stop | `PASS` | Stop log contained no Telegram or launchctl access; synthetic no-receipt/valid-receipt release tests also passed. |
| Separate-shell uninstall | `PASS` | Persistent no-helper receipt was read before App Support moved; helper removal was skipped, recovery backup mode was `0700`, repo remained, and Docker volume data remained. |
| Recall/RAG continuity | `PARTIAL` | Restart plus snapshot and independent restore passed. The no-host-share VM used isolated Ollama and long binds to a product-owned daemon PostgreSQL path plus a byte-identical read-only route mirror. Supported install reached semantic health; synthetic `/embed` and `/query` returned the codeword and time; both survived direct Compose and supported CLI restart. The restore correctly excluded PGVector as derived state and wrote a rebuild-required marker; an actual rebuild and browser model answer were not run. |

## Automated Evidence

- `tests/release/test_preflight.py`, `test_cli_upgrade.py`, and
  `test_telegram_launchctl_ownership.py`: `150 passed`.
- QA operating-contract and public-safety checks: `24 passed`.
- Central release-test owner contract plus Telegram ownership tests: `3 passed`.
- RAG launcher/Compose portability and safety contracts: `20 passed`.
- Integrated and clean LibreChat RAG Compose/dependency contracts: `5 passed` each.
- Added explicit regression coverage that Docker mode reports the selected daemon as missing.
- Helper receipt tests cross a real shell boundary; failed-start cleanup uses a real scoped process
  group; Telegram tests record every synthetic launchctl invocation.

## Findings

1. The installer previously remembered helper ownership only in the current process. A persistent,
   atomic, owner-only install receipt now carries that decision across later uninstall commands.
2. Failed install rollback previously restored config without guaranteeing its detached native
   fallback was drained. Rollback now validates and drains only the recorded target-scoped group.
3. Disabled Telegram stop previously touched a fixed LaunchAgent label without target proof. A
   target-bound receipt now gates label inspection and removal.
4. The first daemon-down QA probe went false green because stopping the isolated VM removed its
   Docker context and the CLI fell back to another local context. Repeating with the isolated socket
   explicitly pinned produced the correct failure. This was a QA isolation flaw, not a missing
   preflight branch; no product preflight logic was changed.
5. Existing-email registration intentionally returns a generic success-class response for
   anti-enumeration. The corrected UI keeps that privacy boundary while explicitly offering sign-in
   with the existing password or local password recovery; it no longer claims a new registration
   succeeded.
6. The public `password-reset-link` command previously assumed the parent checkout's nested
   LibreChat path and required a preconfigured client origin. It now validates the selected
   `VIVENTIUM_LIBRECHAT_DIR`, executes only the selected helper script, preserves explicit
   `DOMAIN_CLIENT`, `CLIENT_URL`, then compiled `VIVENTIUM_PUBLIC_CLIENT_URL`, and otherwise
   synthesizes the configured loopback frontend origin. Missing selected source fails closed. Six
   focused regressions and the live reset/login path pass.
7. RAG Compose previously assumed bind sources were visible on the client Mac. The launcher now
   separates default host ownership from explicit daemon ownership, limits daemon PostgreSQL data
   to a nonempty `/var/lib/viventium/` child, validates the route mirror byte-for-byte, and uses
   Compose long bind syntax. Unsafe roots, traversal, prefix-confusion, control characters, and
   colon delimiters fail closed.

## Remaining Release Gaps

- Signed/notarized immutable payload and exact public bootstrap.
- Pristine no-developer-tools Mac proof.
- Supported nested component bootstrap and nested commit -> parent pin -> build -> payload ->
  installed-artifact identity.
- Docker Desktop headed first-launch, Keychain/TCC, helper/SMAppService, battery/sleep/wake, and
  resource-pressure behavior on the physical Mac.
- Intel and declared accessibility/native assistive-technology matrices.
- Browser-level Recall through a synthetic chat provider, followed by an actual rebuild from
  restored canonical conversation state and a post-rebuild browser answer. Snapshot, independent
  restore, and rebuild-required ledger behavior already pass; PGVector is intentionally excluded.
- Independent public restore followed by browser login on the restored target.

## Public-Safety Review

- The public report contains no username, hostname, home-directory path, synthetic credential,
  secret, private screenshot, raw log, database payload, or personal Docker inventory.
- Raw evidence is mode-restricted outside the public repository; public text uses only aggregate
  status, timing, count, and ownership results.
- All test data was synthetic and no cloud change, message, commit, push, publication, or personal
  account action occurred.
