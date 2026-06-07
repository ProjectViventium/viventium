<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# Telegram Pre-Start API Outage RCA - 2026-06-06

## Scope

Investigate why Telegram returned:

```text
Failed to reach Viventium. Please retry.
```

The investigation covered logs, Mongo state, owning code, nested docs, targeted automated tests,
Playwright browser QA, Computer inspection of Telegram desktop state, and a ClaudeViv review-only
second opinion. Raw private chat content, local App Support paths, user/account identifiers, and
secret-bearing values are intentionally excluded.

## Requirement Links

- `docs/requirements_and_learnings/01_Key_Principles.md`: user-facing error copy must name the
  correct failure class, including local runtime unavailable, instead of a generic service failure.
- `docs/requirements_and_learnings/03_Telegram_Bridge.md`: Telegram must return complete responses
  or clear errors; detached/local launches must not leave Telegram pointed at a dead local API and
  must recover the API when the real API child dies.
- `qa/telegram-detached-api-stability/cases.md`: `TGAPI-003`, `TGAPI-004`, and new `TGAPI-005`.

## Finding

The exact Telegram copy is emitted by the Telegram bridge before any SSE stream or LibreChat agent
turn starts. The failure happened while the local LibreChat API was unavailable on the Telegram
bridge origin. The later failed Telegram turn did not create a Mongo Telegram ingress row, so it
never entered the LibreChat Telegram route, agent pipeline, provider-auth path, stream-resume path,
or model/tool execution path.

## Evidence

| Layer | Result |
| --- | --- |
| Code | `TelegramVivBot/utils/librechat_bridge.py` yields the exact copy from the non-link `_start_chat` exception path before stream handling. Stream-time failures use a different classifier and different copy. |
| Helper/API logs | API backend clean-exited at 19:27:47 local and did not listen again on the local API port until 19:37:32 local. |
| Telegram bot logs | Before recovery, bridge polling and delivery checks repeatedly logged connection attempts failed; the failed user turn logged a pre-start chat failure at 19:36:23 local. |
| Voice behavior | The fallback length matched the logged 40-character TTS request, so always-voice synthesized the transport failure as audio. |
| Mongo | Latest Telegram ingress event was 19:23:46 local; zero Telegram ingress rows existed after 19:30 local; Telegram mappings existed. |
| Current runtime | API health returned HTTP 200 after recovery; status showed LibreChat API and Telegram Bridge running/ready, while unrelated surfaces still had warmup/setup issues. |
| Playwright | `http://localhost:3190` opened in a real browser, reached the Viventium login page, and had no console errors. |
| Computer | Telegram desktop was responsive, but live send/receive was not run because sending from the user's Telegram account requires action-time confirmation. |
| ClaudeViv | Review-only Claude pass confirmed the core RCA and product gaps, and refined the watchdog finding as a recovery-envelope issue rather than merely "slow". |

## Ruled Out

- Telegram linking: mappings existed, and the link-required exception path is separate.
- Stream resume/completed-job retention: the exact text is emitted before stream setup; stream
  failures have separate copy.
- Provider auth/model connected-account failure: current setup may still need user verification, but
  this turn did not reach the provider route.
- Telegram polling conflict: the bot was alive and generated the fallback; the problem was its
  upstream API origin being unavailable.

## Product Gaps

1. Pre-start `_start_chat` failures are collapsed into a generic string instead of class-specific
   local-runtime/API-restarting copy.
2. The fallback is yielded as a plain assistant-style string, so always-voice can synthesize it as
   audio.
3. The detached API watchdog eventually recovered the API, but observed recovery took about ten
   minutes, far outside the intended health-check cadence.
4. The bridge default origin remains `localhost`, while the active API binds to loopback; this can
   make restart windows harsher when host resolution prefers an unavailable address family.

## QA Results

| Check | Result |
| --- | --- |
| Release contracts | PASS: `7 passed` for detached API watchdog and Telegram transcription/runtime contracts. |
| Telegram bridge tests | PASS: `96 passed` for the Telegram bridge suite. |
| API health | PASS: recovered API returned HTTP 200. |
| Browser surface | PASS: Playwright reached the Viventium login page with no console errors. |
| DB correlation | PASS: no post-19:30 ingress rows, proving the failed turn did not enter the route. |
| Computer/Telegram live send | PARTIAL/BLOCKED: Telegram app inspection succeeded; sending a synthetic Telegram message requires user confirmation. |
| Public safety | PASS: report uses sanitized summaries only. |

## Recommended Fixes

- Replace the generic pre-start yield with a non-spoken bridge error event that classifies
  connection refused/unreachable/timeout as local API unavailable or restarting.
- Add a strictly pre-ingress retry for transient connect failures so no duplicate tool/action turn is
  created.
- Ensure stream/final error paths remain text-only where they represent transport or runtime errors.
- Harden the detached API watchdog path that can leave recovery passive during an outage, and make
  status truthfully degraded until the API route is reachable again.
- Align Telegram bridge origin defaults/generated config with the active loopback binding.

## Completion State

RCA is complete and evidence-backed. Product fix is not implemented in this run. The live Telegram
send/receive confirmation remains blocked until the user confirms sending a synthetic Telegram test
message from their account.
