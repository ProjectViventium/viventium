# 2026-05-18 Start Chat Single-Click And Mic Auto-On QA

## Summary

The modern-playground Start chat flow could feel like it needed two clicks because the first click
mounted the LiveKit session, while LiveKit's session hook also prepared connection details in the
background before the actual start path fetched connection details again. During that window the
same visible Start chat button could still be pressed, making startup look like a manual two-step.

The microphone also appeared muted because explicit-dispatch startup intentionally connects the
room with the microphone disabled, then publishes the microphone only after the room is connected.
That pre-connect muted phase is required to avoid LiveKit's pre-connect microphone timeout, but it
must be treated as internal startup state, not as the visible default.

The fix makes Start chat single-flight, shows startup and microphone progress, disables duplicate
starts, keeps post-connect microphone enablement in the same start gesture, wraps microphone
enablement in a bounded timeout, and caches connection details briefly so LiveKit prepare/start
calls share one token result for the same call options.

## Requirement Trace

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`
- Runtime doc: `viventium_v0_4/docs/VOICE_CALLS.md`
- QA case: `qa/modern-playground-voice/cases.md` / `MPV-009`
- User-visible goal: one click starts the call and the microphone turns on automatically after room
  connect unless browser permission is denied.

## Root Cause Evidence

- Code evidence: `useSession` prepares connection details when the session hook mounts, and
  `start()` fetches connection details again. Without a short token-source cache, one Start chat
  click can produce duplicate `/api/connection-details` work.
- UI evidence: after the first click, the disconnected welcome view could still be visible while
  start work was in flight, so a second click was still possible.
- Startup contract evidence: `components/app/app.tsx` connects explicit-dispatch call sessions with
  microphone disabled, then calls `setMicrophoneEnabled(true)` after connection. This sequencing is
  correct, but the UI did not clearly show that microphone enablement was part of startup.
- Runtime log evidence: successful local calls show explicit dispatch creation, browser room join,
  user microphone track publish, publisher job assignment, and agent participant join. Permission
  denial in browser QA correctly prevents the microphone-publish step and surfaces a call-start
  error.

## Changes Verified

- `agent-starter-react/components/app/app.tsx`
  - Tracks start as a single in-flight promise and reuses it if another start is requested.
  - Disables the visible Start chat action while startup is in progress.
  - Shows `Starting call...`, `Connecting Viventium to the room...`, and `Turning on mic...` /
    `Turning on your microphone...` progress states.
  - Keeps the existing post-connect `setMicrophoneEnabled(true)` step, behind a bounded timeout, so
    the microphone is enabled automatically after room connect or fails with clear recovery text.
  - Normalizes browser microphone permission and missing-device errors into Viventium-specific copy
    so the page does not leave the user in an unexplained muted state.
  - Uses a module-level short cache for `/api/connection-details` keyed by stable token options so
    LiveKit prepare/start calls do not race duplicate token/dispatch requests.
- `docs/requirements_and_learnings/06_Voice_Calls.md`,
  `viventium_v0_4/docs/VOICE_CALLS.md`, and `qa/modern-playground-voice/cases.md`
  - Added the one-click and mic-auto-enable contract.

## User-Level QA

- Playwright UI smoke with a public-safe synthetic call id:
  - Opened the modern-playground call page.
  - Clicked Start chat once.
  - Confirmed the button changed to `Starting call...` and was disabled while connection work was
    in flight.
  - Held `/api/connection-details` in flight, clicked the button area again, and confirmed the
    duplicate click did not create a second `/api/connection-details` POST.
- Playwright permission-path smoke:
  - A real active local call session reached the session view, then failed at microphone startup
    because the browser context denied microphone access.
  - Confirmed the UI surfaced a clear `Permission denied` call-start error instead of silently
    leaving the call muted.
- Runtime supporting evidence:
  - LiveKit logs from successful local voice starts show user microphone track publication followed
    by publisher job assignment and agent join.

## Automated Checks

- `uv run --with pytest python -m pytest tests/release/test_voice_playground_dispatch_contract.py -q`
  - Result: 29 passed.
- `pnpm exec tsc --noEmit` from `viventium_v0_4/agent-starter-react`
  - Result: passed.
- `bash -n viventium_v0_4/viventium-librechat-start.sh`
  - Result: passed.
- `git diff --check` for the touched public docs, QA files, release test, and launcher script
  - Result: passed.

## Not Run / Remaining Gaps

- A fresh full spoken-turn run after this exact patch was not completed because the Playwright
  browser context hit microphone permission denial. The failure path was visible and correct.
- The microphone auto-enable code path itself is the same post-connect LiveKit publish path already
  shown in local runtime logs; `MPV-001`, `MPV-004`, and `MPV-008` remain the broader full-call
  acceptance cases.

## Second Opinion Follow-Up

- Claude review-only agreed the implementation aligns with the goal.
- Follow-up changes from that review:
  - added release-test assertions for start-promise clearing, cache rejection eviction, stable cache
    key ordering, and bounded prewarm defaults
  - changed microphone permission/missing-device errors to explicit Viventium recovery copy
  - reduced the modern-playground route prewarm default timeout to `20s` per request so a stuck dev
    route compile is warning-only instead of minutes of startup delay

## Privacy Review

This report intentionally omits real call-session ids, room ids, participant ids, local
home-directory paths, tokens, prompt text, and private conversation content.
