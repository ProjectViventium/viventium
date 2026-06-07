<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# 2026-05-18 Voice Settings Startup Loading QA

## Summary

The modern-playground call page could appear stuck at `Loading your voice settings...` because the
primary call button was disabled while the advisory browser voice-settings fetch was still loading.
On the observed local runtime, the first browser hit also paid a Next.js dev cold-compile cost for
the voice startup API routes, so the settings request took long enough to look like a broken page.

The fix keeps `Start chat` available while optional voice-settings display data is loading, adds
timeout bounds and Viventium-specific recovery text to voice-settings fetches, and prewarms the
modern-playground voice startup routes during launcher startup.

## Requirement Trace

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`
- Runtime doc: `viventium_v0_4/docs/VOICE_CALLS.md`
- QA case: `qa/modern-playground-voice/cases.md` / `MPV-007`
- User-visible goal: a call deep link should not look stuck before the user can start the call.

## Root Cause Evidence

- Browser evidence: a real modern-playground call deep link initially matched the reported screen,
  with `Open from Viventium` disabled and the settings area showing `Loading your voice settings...`.
- Network evidence: the browser request to `/api/call-session-voice-settings` completed
  successfully, but only after a long first-hit delay.
- Runtime log evidence: the playground dev server cold-compiled `/api/call-session-voice-settings`
  and then `/api/call-session-state` on first use. One observed cold compile for the settings route
  took about 59 seconds.
- Code evidence: `components/app/app.tsx` treated `voiceSettings.isLoading` as part of
  `canStartCall`, so optional display settings could disable the call gate.
- API evidence: both the playground proxy and `/api/connection-details` voice-settings hydration
  paths had no explicit timeout before this fix.
- DB supporting evidence: the call-session collection had active and expired records, and the
  `expiresAt` index lacked TTL cleanup. Queries for this page filter by active call-session id, so
  this is a hygiene follow-up rather than the immediate page-blocking cause.

## Changes Verified

- `agent-starter-react/components/app/app.tsx`
  - `Start chat` no longer depends on `voiceSettings.isLoading`.
  - The page now explains that voice settings are still loading while leaving the call action
    available.
- `agent-starter-react/hooks/useCallSessionVoiceSettings.ts`
  - Browser voice-settings requests now use a bounded timeout.
  - Timeout and transient load failures retry once during startup and show Viventium-specific
    recovery copy.
- `agent-starter-react/app/api/call-session-voice-settings/route.ts`
  - The proxy to LibreChat now has a bounded timeout and returns a structured timeout response.
- `agent-starter-react/app/api/connection-details/route.ts`
  - Server-side token hydration remains authoritative and now has a bounded voice-settings timeout.
- `viventium_v0_4/viventium-librechat-start.sh`
  - The launcher prewarms `call-session-voice-settings`, `call-session-state`, and
    `connection-details` after the playground answers HTTP and before the voice worker starts.
  - Prewarm failures are logged but do not fail startup, and each request is bounded so a stuck
    compile cannot hold startup for minutes.

## User-Level QA

- Real-browser reproduction:
  - Opened a synthetic active modern-playground call link.
  - Observed the reported blocked state before the fix.
  - Confirmed the long `/api/call-session-voice-settings` first-load request in browser network
    timing.
- Real-browser regression:
  - Delayed `/api/call-session-voice-settings` by 10 seconds with Playwright routing.
  - Confirmed `Start chat` was visible and enabled immediately while the settings panel still showed
    a loading state.
  - Confirmed timeout/retry recovery text was Viventium-specific and did not show raw browser
    exceptions.
- Live local stack smoke:
  - Reopened a current call deep link after the patch.
  - Confirmed the primary call action was available while the settings request was still resolving.
- Final synthetic browser smoke:
  - Opened a public-safe synthetic call link in Playwright.
  - Confirmed `Start chat` was enabled while `Loading your voice settings...` remained visible.
  - Confirmed the later recovery copy stayed Viventium-specific and the call action remained
    available.

## Automated Checks

- `uv run --with pytest python -m pytest tests/release/test_voice_playground_dispatch_contract.py -q`
  - Result: 29 passed.
- `pnpm exec tsc --noEmit` from `viventium_v0_4/agent-starter-react`
  - Result: passed.
- `bash -n viventium_v0_4/viventium-librechat-start.sh`
  - Result: passed.

## Second Opinion Review

Claude was run in review-only mode with sanitized context and no file-editing tools. Useful findings
were folded back into the fix:

- The proxy timeout now fires before the browser timeout so the structured proxy response can win
  when the proxy is reachable.
- Browser/proxy settings timeout and call-start hydration timeout now use separate env knobs.
- Server-side hydration explicitly treats abort timeout as a `null` settings result so token
  issuance can fall back to existing metadata.
- Launcher prewarm now documents why `GET /api/connection-details` is intentional.
- Launcher prewarm defaults now use a bounded `20s` per-route timeout and warn on misses.
- The dispatch wording was tightened so docs match the current code/tests: explicit LiveKit
  dispatch remains the default call-session restart-recovery path, while token-room-config-only
  dispatch is opt-in.

## Not Run / Remaining Gaps

- A full microphone join and spoken LiveKit turn was not rerun for this case. `MPV-007` targets the
  pre-call loading gate, and existing voice call launch/turn coverage remains tracked under
  `MPV-001`, `MPV-003`, and `MPV-004`.
- The launcher prewarm change takes effect after the local runtime is restarted through the
  supported launcher.
- DB TTL cleanup for expired call sessions remains a follow-up hygiene item. It was observed while
  tracing the issue, but it was not the immediate cause of the disabled call page.

## Privacy Review

This report intentionally omits real call-session ids, usernames, local home-directory paths,
tokens, prompt text, and private conversation content.
