# ANTI-008 Version-10 Voice Acceptance Preflight — 2026-08-11

## Result

`BLOCKED`. No real voice acceptance turn was started.

The selected isolated QA API and Web app were unavailable after the host interruption. Their
supported start path requires the shared-checkout API build, which rewrites
`viventium_v0_4/LibreChat/packages/api/dist/index.js`. Local production currently has a nodemon
process watching that same checkout, so the build would restart production. The acceptance run
stopped rather than mutating a shared artifact, disturbing production, or treating surviving voice
sidecars as proof that the selected app was ready.

## Preflight And Guarded Cleanup Evidence

- The source-of-truth `surface.voice.call` prompt is active at version `10`. Its tracked-file
  SHA-256 is `59a30a6fb2df87fb564027ad892fe7348c4292447c7cd934bac010bae1e8b9ba`.
- The compiled prompt body inspected before the outage had SHA-256
  `0cd04b4de4a714d3466f90a08e58838917d191f398f39bf351d500fe79f08299`; the containing compiled
  bundle had SHA-256 `b84be085350e729741ce5d1cd583406f6b1cb4f2706acf9fa495aebe7407867b`.
  It carried the required boundary: unsolicited lookup/tool work stays off the immediate live-call
  path, while an explicit lookup remains evidence-gated, interruptible, and cancellable.
- The voice-worker source SHA-256 was
  `24484282bdc60d3d2b83eef5ceb44b2c007e408295faa3d4fd33158c0cb26696`. A pre-outage process check
  matched the selected checkout, but that process evidence cannot substitute for a fresh active
  artifact check after the selected app became unavailable.
- Before the outage, the voice health endpoint returned `200`, and its capability inventory showed
  the configured local/cloud STT and TTS routes with one optional provider unavailable. This is
  supporting historical evidence only; provider health was not reclassified after the failed app
  restart.
- Final supported status reported the selected frontend and API as `Starting`; exact listener
  inspection found zero listeners on the selected API, Web, Scheduler, and Prompt Workbench ports.
  Modern Playground and LiveKit sidecars still had listeners, but they are not acceptance proof
  without the selected signed app and API.
- A separately authorized, fixture-scoped cleanup removed exactly four synthetic call-session rows
  older than 60 minutes and one exactly correlated stale running task. It removed zero users,
  messages, or conversations. The post-check found zero active calls, zero active voice tasks, and
  zero protected-user delta.

## What Was Not Run

- No signed browser call, model request, microphone input, synthesized test audio, or audible
  playback.
- No two-turn warm-up, ten short controls, ten high-stakes controls, or latency distribution.
- No explicit official lookup, connected barge-in cohort, visible Cancel action, or recovery turn.
- No linked-chat refresh, persisted content-part comparison, or post-turn log/DB correlation.

Source inspection, hashes, health responses, status, listener state, and cleanup counts are
supporting preflight evidence. They do not replace the required user-grade audible path.

## Remaining Prerequisites

1. Give the isolated QA environment a build artifact that can be compiled or selected without
   writing a file watched by local production, or move production to a distinct immutable checkout.
2. Start the isolated environment through the supported command and prove its API, Web, Modern
   Playground, LiveKit, Scheduler, Workbench, voice worker, and search dependencies all belong to
   the selected runtime.
3. Re-prove the active prompt bundle, worker source, process identity, signed QA session, current
   provider health, and zero-active-call/task baseline after that start.
4. Establish a quiet host window with no release suite or sibling runtime load, then execute the
   prepared version-10 procedure in full: warm-ups, both measured cohorts, explicit lookup, ten
   audible interruptions, Cancel/recovery, refresh/persistence, and latency gates.

`ANTI-008` may move to `PASS` only after those real audible, browser, persistence, exclusion,
lookup, interruption, cancellation, recovery, and percentile gates all pass.

## Public-Safety Review

This report contains only synthetic counts and content-free hashes. Raw identifiers, transcripts,
screenshots, credentials, account details, machine names, and local evidence paths remain outside
the public repository.
