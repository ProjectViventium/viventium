# Telegram recovery and retained failed-reply controls

- Date: 2026-10-20.
- QA mode: blast-radius.
- Result: PASS for SDR-015 startup recovery. The initial two-message smoke check did not
  establish normal conversation recovery; the subsequent escaped provider failure is recorded below.
- Delivery: local active source checkout only; no commit, component pin change, publication, or release claim.

## Cause and change

The installed helper repeatedly tried to restart a runtime with Docker offline. The managed
LiveKit prerequisite rejected the restart before the launcher's normal Docker auto-start path.
Core API and Redis were unreachable, so Telegram could not answer. Telegram logs also recorded
Core source-order connection failures. The cause of the earlier Docker outage is not established.

The prerequisite now calls the existing Docker auto-start and bounded readiness helper before
teardown. Explicit Docker skip and configured external LiveKit behavior stay fail-closed. No
native LiveKit fallback, provider change, or source-order bypass was added.

## Evidence

| Check | Result |
| --- | --- |
| Actual-helper regression before fix | Failed: stopped Docker was rejected before launch |
| Selected lifecycle and LiveKit provenance regressions | 5 passed, 38 deselected |
| Shell syntax and changed-file whitespace | Passed |
| Independent review | No material concern; wait and Docker probes are bounded |
| Final active restart | Core API, frontend, Redis, RAG, scheduler health and Telegram polling recovered |
| Real Telegram arithmetic check | One correct answer, 43 |
| Real Telegram contextual follow-up | One correct answer, 86 |
| Reopen Telegram chat | Both answers remained visible |
| Saved message parts and delivery acknowledgements | Two source messages, two matching terminal answers, one committed presentation each |
| Browser | Recovered frontend rendered the sign-in page |

The first recovery attempt overlapped the launcher edit and stopped with a shell parse error.
It was stopped through the supported CLI. The final restart used the stable, syntax-checked file.

Test command:

```sh
uv run --no-project --python 3.12 --with pytest python -m pytest tests/release/test_optional_runtime_provenance.py -q -k 'restart_livekit or native_livekit_never or native_no_docker_path or skip_docker_rejects'
```

## Escaped normal-conversation failure

The user reported another failure after the initial recovery claim. The failed text reached the
configured native Codex route. Generic connection diagnostics were counted as typed internal
retries, so the host stopped native recovery after three notices. A private fork of the same
history recovered through the native HTTPS transport fallback after four notices and completed
in 24.69 seconds on the same account and model. No provider, model, account, or prompt changed.

The native event adapter now ignores generic top-level error diagnostics and completed error
items for liveness accounting. They neither consume typed retry budget nor refresh meaningful
progress. The existing operator deadline, inactivity watchdog, terminal failures, quota handling,
and typed retry handling remain active. Three focused tests failed before the change; 51 affected
native liveness, deadline, cleanup, and attention checks passed after it. Independent review
found no material concern. The active runtime was restarted through the supported CLI.

The first real replay then exposed retained attention locks from earlier failed native runs.
The exact owner-scoped provider cancellation API released the failed Main run and an old failed
maintenance compactor run. The queued maintenance successor started immediately. No database,
conversation history, native session, or generated configuration was edited to recover them.
The first replay failed before native admission; it is not counted as a successful reply.

Final natural-conversation replay: PASS for TR-031 and TELEGRAM-UC-027. The previously failed
natural text received one complete answer and its configured voice presentation. The next normal
follow-up also received both. Native runs completed in 17.6 and 21.9 seconds; text plus voice
delivery took about 22 and 27 seconds from receipt. Both persisted after reopening Telegram.
Mongo showed two complete, non-error assistant messages with committed delivery acknowledgements
and two presentation references each. Internal cortex notes were absent from the visible answers.
The same account, configured GPT 6.1 Sol/high route, persistent provider session, and saved history
were retained. The existing branch reselect protocol created a new native Codex session from the
saved history; the follow-up reused it. No fallback, omitted history messages, or pruned tool
payloads were recorded.

Focused native commands (run from the component checkout):

```sh
runtime_phase1/.venv/bin/python -m pytest runtime_phase1/tests/test_profile_runtime.py runtime_phase1/tests/test_host_run_leases.py -q -k 'provider_liveness or native_jsonl_tail or codex_transport_recovery or native_maintenance_timing or codex_usage_limit_turn_failed or host_native_configured_timeout_survives or host_cli_runtime_uses_configured_timeout_when_set or host_cli_runtime_honors_caller_timeout'
runtime_phase1/.venv/bin/python -m pytest runtime_phase1/tests/test_provider_deadline_cleanup.py runtime_phase1/tests/test_conversation_provider.py::test_provider_liveness_attention_keeps_typed_code_and_rejects_late_answer -q
```

## Retained deadline generation

The maintenance job reached its original response deadline, but native cleanup remained
unconfirmed. Its exact recorded supervisor and child were still alive. A newer, never-invoked
queued successor had become the worker's latest run, so the old exact-deadline cleanup guard
returned before claiming cleanup. This did not block the two successful foreground replies.

The shared Store predicate now permits cleanup of that recorded expired generation only while
the successor remains queued and has no current or historical native invocation, confirmed
startup, active lease, or restore hold. Ownership and operator controls remain checked. Claim and
finalization repeat the predicate inside their transactions. Normal activity reconciliation can
retry unconfirmed cleanup for the already-failed request. Failed history, queued source/request,
and saved native context remain intact; no generic worker Stop or process-name kill was added.

Four new cases failed before this change. The deadline-cleanup module passed 23 checks, and the
adjacent conversation-provider deadline/timeout selection passed 23. These batches overlap the
earlier 51-check selection and must not be summed as unique tests. Independent review approved
the actual patch, including invocation races at claim and finalization.

```sh
runtime_phase1/.venv/bin/python -m pytest runtime_phase1/tests/test_provider_deadline_cleanup.py -q -o addopts=''
runtime_phase1/.venv/bin/python -m pytest runtime_phase1/tests/test_conversation_provider.py -q -o addopts='' -k 'deadline or timeout'
```

Final candidate activation and recovery: PASS. The managed stop removed the recorded expired
supervisor and child. Startup automatically began the preserved queued successor before the
recovery API read. The exact owner-scoped activity API returned 200 and left both the failed
history and invoked replacement unchanged. The successor's source, request instruction, and
original deadline hashes matched. It started a new native session with the same admitted source;
no same-native-thread claim is made for maintenance. The new safe-cleanup branch itself is proved
by the regressions; managed stop made that branch unnecessary in this live recovery.

The final restarted Telegram bot answered a third natural turn with one text and one voice
presentation. The answer remained visible after reopening the chat; Mongo recorded a complete,
non-error assistant message and committed delivery acknowledgement with two presentation refs.
All four active native source hashes matched the tested candidate. The maintenance successor later
reached its original deadline. Reconciliation removed its exact native supervisor and child,
returned the worker to ready, and left no active lease or cleanup claim. The new deadline cleanup
therefore also passed a natural failure path without a further recovery write. The maintenance
result failed by deadline; it is not claimed complete.

## Existing supervision gaps

The existing helper missed the launcher's `FATAL_STARTUP:` marker. A failed automatic attempt
therefore held its full thirty-minute readiness wait before the existing retry policy could run.
Its automatic failure guidance also remained only in logs. The helper now recognizes that marker
in the current attempt's log segment after the CLI exits. It shows the existing guidance and retry
time in its status row; Stop, explicit Start and healthy recovery clear it. No new supervisor or
notification permission was added.

The helper install/supervision bank passed 59 distinct checks, including executable Swift
regressions for the fresh fatal marker, stale-log exclusion, active-CLI fence and status wording.
One environment-dependent check required the missing HTTP client dependency and passed unchanged
with that dependency supplied. The universal helper was rebuilt and installed through the existing
installer with its configuration preserved. Both installed Mach-O architectures match every
file-backed prebuilt section and UUID; code-signature verification passed. The installed process
is running. Exact menu inspection is BLOCKED by the available app-control surface, which cannot
select the menu-bar-only helper. No real outage was induced for that screenshot.

CLI status also treated a retained serving receipt as proof that missing services were starting.
It now requires an actual startup operation or the existing fresh private owner/PID/repository-bound
claim. Missing required services without that proof report Action required. Both summary modules
passed 84 tests, including unsafe, stale, foreign and unrelated-process claim rejection. Live CLI
status reports the currently running Core and Telegram services.

```sh
uv run --no-project --python 3.12 --with pytest python -m pytest tests/release/test_macos_helper_install.py tests/release/test_macos_helper_supervision.py -q
uv run --no-project --python 3.12 --with pytest --with httpx python -m pytest tests/release/test_macos_helper_install.py::test_scheduler_speech_materialization_has_native_library_layout -q
uv run --no-project --python 3.12 --with pytest --with pyyaml python -m pytest tests/release/test_install_summary.py tests/release/test_express_launcher_summary.py -q -o addopts=''
```

## Retained foreground attention

The old admission path retried a known failed foreground attention lock as transient occupancy.
Its tool grant then expired and the user received a misleading access-denied error after five
minutes. Admission now returns the existing typed progress-stalled cause immediately only for
exactly owned persistent foreground attention whose native execution has already stopped. Live,
foreign, paused, restored and maintenance occupancy retain their existing fences.

Telegram now offers `/cancel` only after Core verifies the saved failed response. The error's
whitelisted original-response reference locates the private row; it does not grant authority.
Core rechecks owner, conversation, chat/topic, unchanged source, failed native terminal, recovery
deadline, current ACL, configured provider and origin. A short-lived receipt binds that identity
to cancellation. Native cancellation repeats the exact invocation and attention check under the
existing admission and cross-process lifecycle guards. Success requires native acknowledgement
and released execution. No automatic cancellation, mission Stop, model switch, prompt change or
new action store was added.

| Candidate check | Result |
| --- | --- |
| Native attention/control and existing admission bank | 123 passed, including 20 new cases |
| Core control factory and native-response bank | 182 passed, including 16 new cases |
| Core Telegram routes, authentication and topic scope | 5 passed |
| Telegram control, preview and affected bridge checks | 142 passed |
| Core error propagation and final completion metadata | 13 passed |
| Production API package build and compiled export | Passed |
| Independent exact cancellation/lifecycle review | Approved |

These are selected batches, not a project-wide test count. Broad TypeScript checking encountered
unrelated existing errors; it is not claimed passed. The production package build passed.

```sh
# xPerfect
runtime_phase1/.venv/bin/python -m pytest runtime_phase1/tests/test_foreground_attention_admission.py runtime_phase1/tests/test_conversation_provider_g2_g5.py -q
# LibreChat/packages/api
npx jest src/glasshive/foregroundAttention.spec.ts src/glasshive/nativeResponse.spec.ts --runInBand --coverage=false
npm run build
# LibreChat/api
npx jest server/routes/viventium/__tests__/telegram.spec.js --runInBand --coverage=false --testNamePattern=foreground
npx jest --runInBand server/controllers/agents/client.test.js -t 'native provider attention outcome presentation|native owner input outcome presentation|persists the validated foreground attention reference' --silent
```

The compatible activation used managed Stop, the supported immutable Telegram component prepare,
then managed launch. The prepared bot and bridge hashes match the tested source; unchanged
dependency identity was reused. The running bot's working directory resolves to the prepared
immutable component. The rebuilt API loads the new control route and rejects unauthenticated requests with 401. Live CLI reports Core,
Telegram and the installed helper running. The real Telegram `/cancel` command gave a clear
unavailable response with no model turn. The next natural message received one complete text
reply and its configured voice presentation. Both remained visible after reopening Telegram.
Mongo records a complete non-error native response and a committed delivery acknowledgement with
two presentation references. Earlier conversational context remained in the answer.

The active stalled case had already been cancelled during recovery, so true positive control is
proved in isolated native API, Core and bot harnesses only. The visible active-stall case remains
PARTIAL. Helper failure-menu inspection is also unverified as recorded above. These gaps do not
count as passed real-surface evidence or as a fully verified reliability claim.

## Limits and retained evidence

Stopped-daemon auto-start and permanent failure were tested with the actual helper functions and
controlled process boundaries. Docker was restored before the final live restart. Reboot,
off-network browser access, authenticated Web chat, scheduled-job recovery, and the full feature
bank were NOT RUN. No prompt/model behavior changed, so model comparison was not required.

The two synthetic checks and natural recovery replays remain in the existing private Telegram/Core
conversation as verification evidence. No personal history was removed. Screenshots, identifiers, credentials,
private logs, and raw records were not added to this report.

Final status still showed earlier scheduled-delivery failures and unavailable public-hostname
reachability from this network. Those warnings were not counted as healthy or repaired here.


Later Direct Queen configuration and cross-channel observations belong to the
[prepared Direct Queen report](../../voice/reports/2026-10-21-prepared-direct-queen.md). The retained
local measurements above do not certify a new installed release or change the current latency limits.
