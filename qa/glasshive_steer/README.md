# GlassHive Steer QA

Date: April 17, 2026

## Scope

Validate the glossy GlassHive watch footer end to end:

1. launch a fresh project from the `:8780` UI
2. wait for the initial run to become active
3. send a steer from the watch footer while the run is still active
4. confirm the original run is interrupted
5. confirm the replacement steer run starts automatically
6. confirm the steer action changes real workspace state, not just UI text
7. queue a follow-up from the same footer without interrupting current work
8. confirm the queued follow-up starts only after the current run settles

## Automated Coverage

- `python -m pytest viventium_v0_4/GlassHive/runtime_phase1/tests/test_api.py -q`
- `python -m pytest viventium_v0_4/GlassHive/runtime_phase1/tests/test_profile_runtime.py -q`
- `python -m pytest viventium_v0_4/GlassHive/runtime_phase1/tests -q`
- `python -m pytest viventium_v0_4/GlassHive/frontends/glass-drive-ui/tests -q`

## Live QA Flow

Environment:

- API: `http://127.0.0.1:8766`
- glossy UI: `http://127.0.0.1:8780`
- browser driver: Playwright CLI

Project prompt:

- run `bash -lc 'echo GLASSHIVE_STEER_QA_START > steer_qa.log; sleep 90; echo GLASSHIVE_STEER_QA_FINISH >> steer_qa.log'`
- final token for the original run: `GLASSHIVE_STEER_QA_DONE`

Steer payload:

- `STEER TEST: stop the previous sleep. Immediately append GLASSHIVE_STEER_MESSAGE_APPLIED to steer_qa.log, then reply with exactly GLASSHIVE_STEER_OVERRIDE_DONE.`

Queued follow-up payload:

- `QUEUE TEST: after the current run finishes, append GLASSHIVE_QUEUE_MESSAGE_APPLIED to queue_qa.log, then reply with exactly GLASSHIVE_QUEUE_DONE.`

## Result

Pass.

Observed behavior:

- the original run entered `interrupted`
- the original run emitted `run.interrupted`
- the steer run was auto-started without manual retry
- the steer run completed successfully
- workspace state changed as requested:
  - `steer_qa.log` existed
  - file contents were `GLASSHIVE_STEER_MESSAGE_APPLIED`
- the watch page returned to `Latest result`
- the runtime output included `GLASSHIVE_STEER_OVERRIDE_DONE`
- queue gestures were also verified:
  - long-press `Send` queued a non-interrupting follow-up
  - `Cmd/Ctrl+Enter` queued a non-interrupting follow-up
  - modifier-click `Send` queued the same non-interrupting follow-up path
  - the current active run was not interrupted by the queue gesture
  - the queued follow-up started after the active run settled
  - queued follow-ups settled cleanly to `completed`; the worker did not regress to `ready` while a queued follow-up was still executing
  - queued workspace state changed as requested
  - the send button tooltip and visible helper copy explained the queue gestures in the footer UI

## Visual Operator Smoke

An additional local operator-smoke pass was run against the real glossy UI with an intentionally obvious
color-change story for a non-technical workflow:

1. launch a fresh workspace from `http://127.0.0.1:8780`
2. ask the worker to create `hello_story.html` as a solid blue `Hello World` page and keep the run alive
3. verify the live desktop visibly shows the blue page
4. use normal `Send` to steer the page from blue to red
5. verify the original run becomes `interrupted`, the replacement steer run becomes `running`, and the live desktop visibly updates to red
6. use long-press `Send` to queue a follow-up to make the page purple
7. verify the follow-up routes through the queued operator-message path and the final delivered page visibly updates to purple

Observed outcome:

- the glossy launch form successfully created and opened a fresh workspace
- the blue page was visible in the sandbox browser inside the live desktop
- steering to red interrupted the original run and updated both the file and the visible browser page
- long-press queueing to purple routed through the non-interrupting `worker_message` path
- the final page and file both settled to purple with `PURPLE_DONE`
- the footer copy remained understandable while moving through the blue -> red -> purple flow

Timing note:

- if a long-press queue release lands right as the current run finishes, the follow-up may start immediately instead of sitting in a visibly queued state for long; that boundary behavior still preserved the correct non-steer path and felt acceptable in local QA

## Root Causes Fixed

1. Stopping the `screen` session alone did not stop the underlying `run.sh` and Codex process tree.
2. Heal logic could attribute an older finished run's artifacts to the current steer run.
3. The steer replacement instruction was too weak and could degrade into acknowledgement-only output instead of real execution.
4. Healed runs could restart a replacement processor while the stale original processor was still unwinding, which could incorrectly flip the worker to `ready` during an active queued follow-up.

## Product Truth

`Steer + send` is now defined as a redirect operation, not a passive message:

- stop the active run
- stop the active run's live process tree
- start the queued steer run automatically
- treat the steer instruction as an execution mandate

`Queue follow-up` is now defined as the non-interrupting sibling action:

- preserve the current active run
- store the next instruction as a queued operator message
- start it only after the active run settles
- keep the worker in `running` until the queued follow-up itself settles
- expose it through long-press `Send` and `Cmd/Ctrl+Enter` or modifier-click send

## Residual UX Note

The top-ribbon result preview currently shows the first steer-result line, while the full run output contains the final completion token. This did not block execution correctness, but it is still worth polishing.
