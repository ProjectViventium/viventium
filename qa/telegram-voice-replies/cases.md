# Telegram Voice Replies QA Cases

## Case ID Convention

Use stable `TGVOICE-NNN` IDs for telegram voice replies cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `TGVOICE-001` | Telegram voice replies use the selected STT/TTS path and fall back with honest visible copy. | User-visible behavior matches source, docs, persisted state, and logs | Telegram voice note/reply, transcript, audio output | `tests/release/test_telegram_transcription_error_contract.py` plus user-grade QA when visible | NOT YET RUN (cataloged 2026-05-17; next feature run required) |
| `TGVOICE-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | NOT YET RUN (cataloged 2026-05-17; next feature run required) |
| `TGVOICE-003` | Telegram voice replies must sanitize TTS artifacts in parity with the Modern LiveKit voice path while preserving selected-provider voice controls. | Telegram audio does not speak raw citation ids, source labels, links/domains/emails, unknown tags, or unsupported provider markup. | Telegram voice note/reply, always-voice text reply, proactive callback audio, selected TTS provider payload | `tests/test_tts.py`, `tests/test_bot_stream_preview.py`, `tests/test_librechat_bridge.py`, `tests/test_voice_preferences.py` | 2026-05-22 PASS for automated provider-payload and sanitizer parity; live Telegram send remains user-path follow-up |
| `TGVOICE-004` | Telegram voice-note and always-voice replies are text-mode turns with optional audio delivery, not LiveKit voice-call turns. | The user gets the main text-mode answer plus audio when enabled, while LibreChat receives `voiceMode=false` and no Voice Call LLM override is applied. | Telegram voice note/reply, always-voice text reply, LibreChat Telegram route payload/logs | `tests/test_bot_stream_preview.py`, `tests/test_voice_preferences.py`, `tests/test_librechat_bridge.py`, `surfacePrompts.spec.js` | 2026-05-30 PASS for automated payload/prompt-mode regression coverage; live Telegram post-change send remains follow-up |

## `TGVOICE-001` - Core User Flow

- Requirement: Telegram voice replies use the selected STT/TTS path and fall back with honest visible copy.
- Risk covered: implementation, docs, and user-visible behavior drift apart.
- Preconditions: local Viventium runtime or the specific feature harness is available with synthetic, public-safe data.
- Steps:
  1. Exercise the feature through the real user surface, not only a unit test.
  2. Compare the visible result with source code, generated/runtime config, logs, persisted state, and the owning requirement doc.
  3. Capture a public-safe report with expected result, forbidden result, evidence, residual risk, and follow-up.
- Expected result: the feature behaves as documented and every supporting layer agrees.
- Forbidden result: backend logs, mocks, source inspection, or model completions are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, generated/runtime state summary, and docs/case links.
- Automation: `tests/release/test_telegram_transcription_error_contract.py` plus any narrower feature tests discovered during implementation.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## `TGVOICE-002` - Public-Safe Evidence Record

- Requirement: public QA artifacts must be reproducible and free of secrets, personal data, local paths, raw IDs, and private screenshots.
- Risk covered: a useful local QA run cannot be safely reviewed or published.
- Preconditions: a dated QA report is created for this feature.
- Steps:
  1. Review the report and related diffs for local absolute paths, account identifiers, tokens, raw logs, raw DB rows, private chats, and screenshots with private content.
  2. Keep raw/private evidence outside the public repo and summarize only public-safe counts, statuses, hashes, and conclusions.
  3. Link the report back to this case and the owning requirement doc.
- Expected result: the public report proves the behavior without leaking private/local data.
- Forbidden result: a report includes private transcripts, account identifiers, raw runtime dumps, local home paths, tokens, or secret-bearing command lines.
- Evidence to capture: public-safety scan result and link to the sanitized report.
- Automation: public-safety pattern scan plus relevant release tests.
- Last run: NOT YET RUN (cataloged 2026-05-17; run on each new public report).

## `TGVOICE-003` - TTS Artifact Parity Across Providers

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`
- Risk covered: Modern LiveKit voice cleans a TTS artifact class, but Telegram voice replies still
  speak the same artifact or strip provider controls incorrectly.
- Preconditions: Telegram TTS utility tests can run with synthetic provider clients; a live
  Telegram account/bot can be used for user-path QA when available.
- Steps:
  1. Send or simulate Telegram voice-note, always-voice text, and proactive callback audio paths.
  2. Include synthetic assistant text with bare internal citation ids, source/reference labels,
     markdown links/images, raw URLs, bare domains, emails, unknown angle tags, bracket stage
     directions, and spaces before punctuation.
  3. Verify OpenAI and ElevenLabs payload text strips all provider-control markup and structural
     stage directions.
  4. Verify xAI payload text preserves documented xAI controls but strips Cartesia-only controls and
     undocumented stage directions.
  5. Verify Cartesia payload text preserves Sonic-3 controls and sends matching emotion config.
  6. Verify local Chatterbox payload text preserves only `[laugh]`, `[sigh]`, and `[gasp]` while
     stripping unsupported SSML/markup.
- Expected result: Provider-bound Telegram TTS text is speech-safe and route-appropriate; selected
  TTS provider/voice route does not drift to defaults unless the saved route is unsupported or
  missing credentials.
- Forbidden result: Telegram TTS says `turn0search4`, `Sources:`, raw URLs/domains/emails, unknown
  tags, unsupported SSML, or bracket stage directions such as `[clears throat]`; provider-specific
  controls are stripped before a capable provider can use them; public QA exposes private Telegram
  identifiers or raw private transcripts.
- Evidence: `qa/telegram-voice-replies/reports/2026-05-22-tts-artifact-parity-qa.md`
- Last run: 2026-05-22 PASS for automated sanitizer/provider-payload regression coverage and
  Claude second-opinion follow-up. Live Telegram send/listen remains PARTIAL until rerun through
  the real bot surface with public-safe synthetic text.

## `TGVOICE-004` - Text Mode With Audio Delivery

- Requirement: `docs/requirements_and_learnings/03_Telegram_Bridge.md` and
  `docs/requirements_and_learnings/34_Voice_Chat_LLM_Override.md`
- Risk covered: Telegram audio replies accidentally opt into the LiveKit Voice Call LLM override,
  voice-call prompt, or voice-call Phase A policy just because an audio reply is requested.
- Preconditions: Telegram bot tests can run with synthetic payloads; live Telegram send can be used
  for user-path QA when available.
- Steps:
  1. Send or simulate a Telegram text turn with `ALWAYS_VOICE_RESPONSE=true`.
  2. Send or simulate a Telegram voice-note turn with voice replies enabled.
  3. Verify the LibreChat bridge request carries `voiceMode=false` in both cases.
  4. Verify `viventiumInputMode=text` for always-voice text and `viventiumInputMode=voice_note` for
     voice-note input.
  5. Verify Telegram audio is still sent when the audio gate passes.
- Expected result: Telegram remains on the main text model/prompt path and receives audio delivery
  after the text answer.
- Forbidden result: Telegram sends `voiceMode=true`, activates the Voice Call LLM override, or
  suppresses audio delivery just because voice-call mode is false.
- Evidence: `qa/modern-playground-voice/reports/2026-05-30-phase-b-followup-decision-and-recall-gate.md`
- Last run: 2026-05-30 PASS for automated regression coverage; live Telegram post-change send
  remains a user-path follow-up.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Telegram Voice Replies. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `TGVOICE-UC-001` | On Telegram voice note/reply, transcript, audio output, verify that telegram voice replies use the selected STT/TTS path and fall back with honest visible copy. | owning requirement for `TGVOICE-001` / `TGVOICE-001` | Telegram voice note/reply, transcript, audio output | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to TGVOICE-001. | User-visible behavior matches source, docs, persisted state, and logs | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `TGVOICE-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `TGVOICE-002` / `TGVOICE-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to TGVOICE-002. | The user sees an honest setup, retry, or degraded-state result for TGVOICE-002; no fake success is accepted. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `TGVOICE-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `TGVOICE-002` / `TGVOICE-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to TGVOICE-002. | TGVOICE-002 remains correct after the persistence or parity step and final wording matches evidence. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `TGVOICE-UC-004` | Hear a Telegram voice reply or always-voice text reply that includes synthetic citations, source labels, links, emails, unknown tags, provider controls, and bracket stage directions in the assistant text. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `TGVOICE-003` | Telegram bot audio plus provider-payload test harness | TTS payload captures, voice route cache, Telegram display text, runtime logs, sanitized QA report | Telegram audio receives speech-safe provider-appropriate text with no raw artifacts; visible text hides voice-control markup; capable providers keep only their documented controls. | 2026-05-22 PARTIAL/PASS: automated provider-payload parity passed; live Telegram audio send/listen not rerun |
| `TGVOICE-UC-005` | Send a Telegram always-voice text message and a Telegram voice note, then confirm the answer uses Telegram text mode while still sending audio. | `docs/requirements_and_learnings/03_Telegram_Bridge.md` / `TGVOICE-004` | Telegram bot plus LibreChat Telegram route logs/payload | Bot kwargs, route request metadata, Telegram visible text/audio, persisted assistant message | LibreChat sees `voiceMode=false`; input mode is `text` or `voice_note` as appropriate; Telegram audio is delivered when enabled. | 2026-05-30 PASS automated; live Telegram post-change send remains follow-up |
