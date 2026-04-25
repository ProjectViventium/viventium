# Scheduler Misfire Catch-Up QA - 2026-04-25

## Scope

Validate that local-runtime sleep or delayed scheduler ticks no longer silently drop user-created
one-time reminders after the misfire grace window.

## Public-Safe Incident Shape

Synthetic equivalent of the observed failure:

1. A user asks for a one-time reminder for the next morning.
2. The schedule is created successfully with `schedule.type=once`, `created_source=user`, and a
   Telegram delivery channel.
3. The local host is unavailable past the 900 second misfire grace.
4. The scheduler wakes roughly 85 minutes after the due time.

Previous behavior: the once task was marked `missed`, deactivated, and left all delivery ledger
fields empty.

Expected behavior after this change: if the task is still inside the catch-up window, it dispatches
late with an honest visible late notice. If it is beyond the catch-up window, it is marked missed
with a complete delivery ledger.

## Acceptance Criteria

- User-created one-time reminders catch up when late but within the configured catch-up window.
- The catch-up delivery carries `metadata.scheduler_misfire` into dispatch.
- Delivered catch-up text is prefixed with a deterministic late notice.
- Successful catch-up rows persist `last_delivery_reason=delivered_late` and include
  `last_delivery.late_delivery`.
- Too-late one-time reminders are marked `missed`, deactivated, and record
  `last_delivery_outcome=missed`, `last_delivery_reason=catch_up_window_exceeded`,
  `last_delivery_at`, and structured due/late/policy details.
- Recurring and heartbeat-style tasks remain strict by default and do not spam catch-up deliveries.
- Explicit `metadata.misfire_policy.mode=strict` overrides the default user-once catch-up behavior.
- No runtime code inspects prompt text or reminder wording to decide catch-up behavior.

## Automated Evidence

Command:

```bash
cd viventium_v0_4/LibreChat/viventium/MCPs/scheduling-cortex
./.venv/bin/python -m unittest discover -s tests
```

Result:

```text
Ran 73 tests in 0.089s
OK
```

Targeted regression coverage added:

- `test_user_once_misfire_within_window_dispatches_catch_up`
- `test_user_once_misfire_beyond_window_marks_missed_with_ledger`
- `test_recurring_misfire_uses_strict_missed_ledger_without_catch_up`
- `test_metadata_strict_policy_overrides_user_once_catch_up_default`
- `test_late_delivery_notice_is_prepended_to_visible_delivery`

Installed-runtime verification:

- The same scheduling-cortex source/test files were synced into the installed local runtime tree.
- The parent component lock now pins LibreChat to the nested commit that contains this fix:
  `1e720508963fcfeddbfb9c0e481c4000df4d4cce`.
- The installed runtime tree passed the same `unittest discover -s tests` suite:

```text
Ran 73 tests in 0.110s
OK
```

- The local Scheduling Cortex MCP was restarted on port 7110 from the patched installed runtime.
- Health probe returned:

```json
{"status":"ok"}
```

## Residual Risk

This patch does not promise exact wall-clock delivery while the host computer is asleep. It makes
the local scheduler honest and resilient after wake. Phone-grade exact-time delivery would require a
separate wake-scheduling or cloud-dispatch design.
