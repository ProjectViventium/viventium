# Three Telegram voice controls — local acceptance

## Summary

- Result: **PARTIAL** overall; controls, foreground delivery and restart persistence pass. Natural delayed and call-origin callbacks remain open.
- Build/source under test: the reviewed three-control Telegram and compatible Core source candidate.
- Runtime/artifact under test: the supported loaded Telegram component, Core API and scheduler recorded below.
- Environment: local development; existing linked account and selected speech routes.
- Tester: agent-operated Telegram client and playback checks with independent Opus source review.
- Related change: three audio preferences, exact callback input origin and declared-control display cleanup.
- QA mode and authorizing instruction: blast-radius; implement and test the requested Telegram audio controls.
- Selected cases and causal relevance: TGVOICE-011 and its foreground, saved-setting, model-skip and callback consumers.
- Deferred / unselected cases (NOT RUN): natural delayed/call-origin acceptance, hardware capture, endurance and universal audio quality.

## Scope Run

| Case | Result | Evidence | Limit |
| --- | --- | --- | --- |
| TGVOICE-011 controls and foreground | PASS | Reopened Telegram card, six real switch/input cases and final loaded audio | Exact settings and model skip retained. |
| TGVOICE-011 persistence | PASS | Saved values and Core agree after restart | Product missing-value defaults have fixture proof. |
| TGVOICE-011 late/call-origin | PARTIAL | Source-bound callback and restart tests | No natural delayed or call-origin result observed. |

## Natural User Use Case Checklist Run

| Use case | Natural action | Surface | Result | Visible evidence | Supporting evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| TGVOICE-011 preferences | Change the three controls, reopen, restart | Telegram Preferences | PASS | Explicit ON/OFF labels and current help | Both saved stores and loaded source agree | No new missing-value account was created. |
| TGVOICE-011 reply | Send voice or text; request text only; disable audio | Telegram chat and received audio playback | PASS | Expected text/audio or text only | STT/Main/delivery acknowledgements and decoded reply | Universal glitch-free audio is not claimed. |
| TGVOICE-011 callback | Receive the original voice worker result after newer input/restart | Deterministic callback path only | PARTIAL | Natural result not observed | Exact origin/topic checks pass | Real delayed and call-origin acceptance remains open. |

## Traceability

Three Telegram voice controls → [Telegram contract](../../../docs/requirements_and_learnings/03_Telegram_Bridge.md) → choose reply audio and receive a natural response → [TGVOICE-011](../cases.md#tgvoice-011---three-voice-preferences) → master permission, source input and model judgment agree → recorded controls, foreground and restart evidence below → delayed/call-origin user acceptance remains PARTIAL.

## Full-View Evidence Checklist

| Evidence surface | Recorded result and limit |
| --- | --- |
| Requirement and use case | TGVOICE-011; preferences and ordinary voice/text responses. |
| Code owning path | Telegram config, voice policy, foreground renderer, callback bridge and shared speech grammar. |
| Docs and nested docs/repos | Telegram requirements, component README and compatible Core callback contract. |
| Scripts or harnesses | All-switch matrix, source-origin, display, route-lookup and persistence checks below. |
| Prerequisites | Final selected STT/Main/TTS foreground path completed; no universal provider claim. |
| Logs and DB/state/persistence | Main requests, retained settings, Core mapping and committed delivery acknowledgements agree. |
| Generated/shipped artifact | Reviewed source, frozen Telegram component and compiled API agree after supported restart. |
| Real user path and visual/UX | Actual Preferences, voice-note forwarding, clean text, audio received and played. |
| Not run / blocked | Natural delayed/call-origin results remain PARTIAL; hardware and endurance NOT RUN. |

## User-Grade Evidence

- Surface exercised: Telegram Preferences, chat, received audio and browser-backed state evidence.
- Real user path: choose audio settings, send real voice notes and text, request text only, reopen and restart.
- Visible outcome: three explicit controls, correct text/audio eligibility and clean display; final audio played to completion.
- Expanded/detail state: the existing Preferences card showed explanatory help and all selected ON/OFF values.
- Persistence/reload result: settings and Core mapping agreed after restart; reopened card retained the selection.
- Backend/log/DB confirmation: source-bound requests, frozen component identity and committed delivery acknowledgements support the observed cases.
- Final model/runtime wording check: model skip remains authoritative; foreground PASS does not certify delayed/call-origin parity.
- Substitution check: deterministic tests and review support the recorded Telegram user paths; they do not replace the missing natural callback cases.

## Automated Evidence

Retained selected evidence: 701 Core checks; 170 current Telegram checks with 79 unchanged checks retained. Counts describe the original selections, not a combined unique total. The exact recognition old/new cases and package-build limits are retained below. This formatting update ran no new product QA.

## Findings

The following original dated details are retained; reorganizing them does not change their evidence scope or result.

Date: 2026-10-27. QA mode: **blast-radius**. Owner: [TGVOICE-011](../cases.md#tgvoice-011---three-voice-preferences).

### Contract

The existing Preferences card contains **Master Switch**, **Reply Voice with Voice** and
**Always Include Voice Reply**, each with an explicit ON/OFF state. All new product defaults are ON;
explicit existing selections are preserved. The former Smart control keeps its stored Always
field, while Reply Voice is a new field.

Audio is eligible when `Master AND (Always Include OR (spoken input AND Reply Voice))`.
Always Include also permits proactive replies. Master OFF, model skip, quiet outcomes, invalid
required metadata and failed text delivery still suppress optional speech. Eligibility never
forces the model to speak.

### Deterministic evidence

- **701 selected Core checks pass**, combining current affected checks with retained, unchanged
  consumer evidence. These cover authenticated partial updates, defaults, source authority,
  original input mode, callback binding, scheduler projection and private/group/topic boundaries.
- **170 current Telegram checks pass**, with **79 valid unchanged UI/policy/state checks retained**.
  They cover the switch matrix, source-bound callbacks, skip/ranges/failure paths, display, exact
  topic routing and unchanged TTS data. Repeated runs are not added to these totals.
- The old display candidate reproduced ten bracket-recognition failures; the correction passes
  all thirteen recognition cases. Declared controls disappear while links, placeholders, URLs,
  escaped literals and code survive. A fresh-process check rejects config/client/TTS-engine
  initialization on display-only work.
- Master-off, model-skip and invalid callback results make zero Speaking-route lookups.
- The selected API package build passed. Later changes affect directly loaded JS and Python, so
  the unchanged compiled package was not rebuilt again. A broader Telegram Jest attempt exhausted
  its heap; it is not counted as passed.

### Real Telegram cases

These are synthetic inputs sent through the ordinary logged-in Telegram client. Captionless
voice notes were forwarded through the real UI; their actual voice attachments went through
selected STT, Main, text/audio delivery and persisted acknowledgements. No incoming updates or
worker results were forged.

| Case | Master / Reply Voice / Always | Actual result |
| --- | --- | --- |
| Ordinary voice note | ON / ON / OFF | Recognized speech, authored text and one received audio reply. |
| Ordinary typed input | ON / ON / OFF | Clean text only; no TTS. |
| Voice asks for text only | ON / ON / OFF | Valid structured model skip, complete text, no TTS. |
| Master disabled | OFF / ON / ON | No TTS or audio. This exposed the display-control defect repaired in the final candidate. |
| Always includes voice despite Reply OFF | ON / OFF / ON | One audio reply, as required by the broader Always option. |
| Spoken-input option disabled | ON / OFF / OFF | Text only; no TTS or audio. |

The received reply was played and downloaded from Telegram. Its exact bytes match the delivery
receipt, decode without nonfinite or clipped samples, and contain all substantive authored
clauses in local recognition. One opening sound is uncertain in recognition; exact phonetics or
universal glitch-free audio are not claimed.

### Final activation and persistence

**PASS for controls and foreground delivery.** The final candidate was loaded through the
supported full stop/start path. All changed source files, frozen runtime files and compiled API
artifacts agree; one ready Telegram poller and fresh Core/Scheduling processes use that candidate.
The saved mixed selection and Core mapping agreed after restart, before any new chat or settings
write. Reopening the same card showed all three explicit ON/OFF labels and proactive-message help.

Two additional real voice-note checks passed on this final candidate: Master OFF produced clean
visible text without TTS; after restoring Master ON, the normal spoken-input selection produced
one clean text reply and one received audio item. The final audio item was played to completion
in Telegram. Both Main requests and their delivery acknowledgements completed. The requested
selection was restored through Preferences and verified in both stores. This closes final
activation, visible wording, foreground delivery and persistence; it does not close the delayed
callback limits below.

Independent Opus 5.5 review checked the full evidence and the concrete fixes. Its final source
verdict found no material blocker; runtime and user acceptance were established separately. No
Git release or complete-system readiness claim is made.

### Limits and follow-up

- Source-bound delayed callbacks, newer-input isolation and restart metadata pass deterministic
  checks. No natural delayed callback or call-started result has been observed in this run; those
  user paths remain PARTIAL. Do not infer live parity from injected callback tests.
- Core can retain a synthesis tag in canonical text when audio was not requested. This is an
  older, separate issue. The Telegram display fix does not prove history/web/memory cleanup.
- Only explicit preference-sync tasks are serialized. In-flight private chat requests also
  refresh Core values; universal ordering is not claimed.
- Product defaults are verified with missing-value fixtures. Post-load key counts describe
  current state and cannot reconstruct all pre-upgrade missing fields.
- Core and Telegram must be activated or rolled back together for this callback-contract change.
- No models, prompts, provider credentials or worker orchestration changed. Latency benchmarks,
  provider evaluations, hardware capture and endurance tests were not part of this batch.

Raw prompts, media, screenshots, account identifiers, database rows, logs and exact artifact
identity records are retained privately. This report contains only sanitized product evidence.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies or credential-bearing commands.
- [x] No private prompts, conversations, media, screenshots, personal emails, accounts or customer data.
- [x] No conversation, message, call, chat, database or provider request identifiers.
- [x] No machine names, private hostnames, absolute local paths, raw logs or runtime dumps.
- [x] Private evidence is represented only by sanitized observations, counts, dates and conclusions.
