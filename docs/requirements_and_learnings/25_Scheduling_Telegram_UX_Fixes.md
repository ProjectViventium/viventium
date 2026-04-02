# Scheduling Telegram UX Fixes

**Date:** 2026-02-11
**Status:** Implemented
**Scope:** Fix "Checking now." and "(No response generated.)" noise on Telegram for scheduler-triggered runs

---

## 1. Problem

Scheduler-triggered runs were producing unwanted Telegram messages:

| Symptom | Root Cause |
|---------|-----------|
| **"Checking now."** sent when nobody asked | `pickHoldText()` in `brewingHold.js` is context-blind — always returns a hold acknowledgment, even for scheduler runs where no human is waiting |
| **"(No response generated.)"** sent for empty responses | Hardcoded fallback in `dispatch.py` treats empty `final_text` as an error, but for scheduled runs it means "nothing to report" |

---

## 2. Root Cause Detail

### Issue 1: "Checking now."

1. `dispatch.py` sends payload with `scheduleId` to `/api/viventium/telegram/chat`
2. `telegram.js` spreads `safeIncoming` (which includes `scheduleId`) into `req.body`
3. `client.js` — tool cortex activates → `shouldDeferToolCortexMainResponse()` returns true
4. `pickToolCortexHoldText({ responseMessageId, agentInstructions })` called — **no awareness of who triggered the run**
5. `brewingHold.js:pickHoldText()` returns `"Checking now."` (fallback)
6. `dispatch.py` — `is_no_response_only("Checking now.")` returns false → **sent to Telegram**

### Issue 2: "(No response generated.)"

1. Model returns empty or NTA content that gets stripped → `final_text` is empty
2. `dispatch.py` line 817: `elif not final_text: final_text = "(No response generated.)"` → **sent to Telegram**
3. Empty scheduled response = "nothing to report" — intentional silence, not a failure

---

## 3. Fix (Implemented)

### Approach

- Use the **existing `scheduleId` field** (already flowing through scheduler.js and telegram.js routes into `req.body`) to inform hold behavior
- Treat empty output from scheduler dispatch as intentional silence
- Leverage the **existing `{NTA}` suppression pipeline** — no new suppression logic needed

### Why `scheduleId` (not a new `viventiumRunSource` field)

- `scheduleId` already exists and flows through the entire pipeline — zero new plumbing
- Its presence directly and unambiguously signals "this was triggered by the scheduler"
- Per principle: *"Use as much as what's already there"* and *"Minimal changes for beautifully simple results"*

### Why not the full config-driven approach

- A `viventium.brewing_hold.by_run_source` config in `librechat.yaml` is architecturally elegant but over-engineered for 2 run sources
- Would require threading `req.config` into `brewingHold.js` — a larger refactor than needed
- Per principle: *"Do not overcomplicate things"*
- Can be added later when multiple non-user run sources warrant it

---

## 4. Files Changed

| File | Change | Lines |
|------|--------|-------|
| `viventium_v0_4/LibreChat/api/server/services/viventium/brewingHold.js` | `pickHoldText()` gains `scheduleId` parameter; returns `{NTA}` when present | ~8 lines |
| `viventium_v0_4/LibreChat/api/server/controllers/agents/client.js` | Pass `scheduleId: this.options.req?.body?.scheduleId` to `pickToolCortexHoldText()` | 1 line |
| `viventium_v0_4/LibreChat/viventium/MCPs/scheduling-cortex/scheduling_cortex/dispatch.py` | Extend `suppress_final` to cover empty/whitespace; remove hardcoded `"(No response generated.)"` fallback; add `reason` to log | ~5 lines |

---

## 5. How It Works End-to-End

### Scheduled run + tool cortex activation (was: "Checking now." → insights)

1. Scheduler fires → `scheduleId` in payload
2. Tool cortex activates → `pickHoldText({ scheduleId: "..." })` → returns `{NTA}`
3. `{NTA}` streamed → dispatch.py receives as `final_text`
4. `is_no_response_only("{NTA}")` → true → suppressed → **nothing sent**
5. Phase B follow-up with insights → **sent normally**

### Scheduled run + empty response (was: "(No response generated.)")

1. Model returns empty/NTA → `final_text` is empty
2. `not str("").strip()` → true → suppressed → **nothing sent**

### User-initiated run (unchanged)

1. User sends message → no `scheduleId` in body
2. Tool cortex activates → `pickHoldText({})` → returns normal hold text
3. User sees "Checking now." → Phase B follow-up delivers results

---

## 6. Tests

### `brewingHold.spec.js` (3 new tests)

- `pickHoldText returns {NTA} when scheduleId is present`
- `pickHoldText returns {NTA} for scheduler runs even when env/instructions are configured`
- `pickHoldText returns normal hold text when scheduleId is absent`

### `test_dispatch.py` (4 new tests)

- `test_dispatch_telegram_suppresses_empty_final_text`
- `test_dispatch_telegram_suppresses_whitespace_final_text`
- `test_dispatch_telegram_suppresses_nta_final_text`
- `test_dispatch_telegram_still_sends_followup_when_final_suppressed`

---

## 7. Observability

Suppressed messages are logged with reason:

```
[scheduling-cortex] Suppressing scheduled Telegram delivery (no-response): task_id=xxx reason=nta
[scheduling-cortex] Suppressing scheduled Telegram delivery (no-response): task_id=xxx reason=empty
```

---

## 8. References

- `01_Key_Principles.md` — avoid hardcoding, do not overfit, separation of concerns
- `11_Scheduling_Cortex.md` — scheduler architecture, `{NTA}`, self-continuity
- `21_No_Response_Feature.md` — `{NTA}` contract and suppression points
- `02_Background_Agents.md` — Tool Cortex Brewing Hold
