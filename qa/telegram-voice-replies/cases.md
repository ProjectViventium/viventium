# Telegram Voice Replies QA Cases

## Case ID Convention

Use stable `TGVOICE-NNN` IDs for telegram voice replies cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `TGVOICE-001` | Telegram voice replies use the selected STT/TTS path and fall back with honest visible copy. | User-visible behavior matches source, docs, persisted state, and logs | Telegram voice note/reply, transcript, audio output | `tests/release/test_telegram_transcription_error_contract.py` plus user-grade QA when visible | PARTIAL/PASS 2026-07-14: real always-voice text/xAI output passed; post-change voice-note input/STT remains unrun |
| `TGVOICE-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | PASS 2026-07-14: dated public report passed the evidence-template validator and targeted public-safety scan |
| `TGVOICE-003` | Telegram voice replies must sanitize TTS artifacts in parity with the Modern LiveKit voice path while preserving selected-provider voice controls. | Telegram audio does not speak raw citation ids, source labels, links/domains/emails, unknown tags, or unsupported provider markup. | Telegram voice note/reply, always-voice text reply, proactive callback audio, selected TTS provider payload | `tests/test_tts.py`, `tests/test_bot_stream_preview.py`, `tests/test_librechat_bridge.py`, `tests/test_voice_preferences.py` | PASS/PARTIAL 2026-07-15: 51/51 provider-payload boundaries plus prior real xAI Telegram delivery; real non-xAI delivery remains partial |
| `TGVOICE-004` | Telegram voice-note and always-voice replies are text-mode turns with optional audio delivery, not LiveKit voice-call turns. | The user gets the main text-mode answer plus audio when enabled, while LibreChat receives `voiceMode=false` and no Voice Call LLM override is applied. | Telegram voice note/reply, always-voice text reply, LibreChat Telegram route payload/logs | `tests/test_bot_stream_preview.py`, `tests/test_voice_preferences.py`, `tests/test_librechat_bridge.py`, `surfacePrompts.spec.js` | PASS 2026-07-11 for real always-voice text delivery plus automated voice-note/text payload coverage; real post-change voice-note input remains a separate STT follow-up |
| `TGVOICE-005` | Telegram text-mode audio turns expose exactly the selected TTS provider/model control contract and shared Feelings expression rule without switching to LiveKit voice mode. | Expressive xAI, Cartesia, and Chatterbox replies can use one fitting supported control without the user asking; restrained/Feelings-off/OpenAI/ElevenLabs `eleven_turbo_v2_5`/unknown routes stay unmarked; visible text is clean; model-specific Eleven v3 tags never leak to v2.5. | Telegram voice-note/reply, always-voice text reply, LibreChat Telegram route payload/logs, metadata-only provider rendering events, prompt layers, Prompt Workbench | shared provider/model contract, `surfacePrompts.spec.js`, `telegram.spec.js`, `tests/test_librechat_bridge.py`, `tests/test_tts.py`, exact-model prompt bank | PARTIAL 2026-07-15: real xAI positive/calm/negative delivery passed on 2026-07-14; neutral Cartesia syntax, full provider/model contract, provider-matrix fixtures, structural marker validation, and privacy-safe provider-boundary telemetry pass automated checks; dynamic OpenAI/Eleven side-channel rendering and new non-xAI exact-model/audible paths remain open ([report](../emotional-cortex/reports/2026-07-14-feelings-activation-and-telegram-acceptance.md)) |
| `TGVOICE-006` | Optional Telegram text audio is model-selected per answer through the shared `{SKIP_VOICE}` contract. | Copy/read/edit-first artifacts stay complete in text without wasting synthesis time; ordinary or explicitly requested spoken replies still receive audio. | Main turn, proactive callback, persistence, TTS, Preferences, Prompt Workbench | shared JS/Python grammar, persistence tests, bot/callback/TTS tests, exact-model prompt bank | PASS/PARTIAL 2026-07-22: real Telegram main-turn skip/conversation/explicit-speech paths, logs, DB, Workbench, and automation pass; proactive real-surface and future-channel parity remain partial |
| `TGVOICE-007` | The Main Agent may create a small number of natural Telegram bubbles with `{MSG_BREAK}` while preserving one logical answer. | A conversational reply can arrive as two or three complete beats without fragment bombardment, duplicate history, duplicate audio, or artifact splitting. | Streaming preview, main turn, proactive callback, persistence, Telegram transport, Prompt Workbench | shared grammar, split-token streaming test, bot/callback/persistence tests, exact-model prompt bank | PASS/PARTIAL 2026-07-22: real two-bubble delivery, one final audio, one clean stored turn, reopen, and automation pass; proactive and attachment-plus-split paths remain partial |

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
- Last run: PARTIAL/PASS 2026-07-14. Real always-voice text replies passed selected xAI TTS,
  clean visible text, audio delivery/playback, fallback/telemetry, and DB/log correlation. Real
  post-change voice-note input/STT remains a separate partial gate.

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
- Last run: PASS 2026-07-14. The current Feelings/Telegram report passed the v2 evidence-template
  validator, `git diff --check`, and a targeted scan for personal paths, account identifiers, and
  credential-shaped content.

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
     Verify a complete paired square wrapper for a documented xAI wrapping control is
     canonicalized to official angle grammar for xAI synthesis, while unpaired/unknown wrappers
     are stripped and neither form reaches visible Telegram text.
  5. Verify Cartesia payload text preserves Sonic-3 controls and sends matching emotion config.
  6. Verify local Chatterbox payload text preserves only `[laugh]`, `[sigh]`, and `[gasp]` while
     stripping unsupported SSML/markup.
  7. Verify OpenAI `gpt-4o-mini-tts` receives the shared neutral, env-overridable `instructions`
     side channel, while `tts-1`/`tts-1-hd` omit the unsupported field; neither route receives
     inline emotion tags.
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
- Last run: PASS 2026-07-14 for real always-voice text mode plus automated text/voice-note payload
  coverage. Real post-change voice-note input/STT remains a separate follow-up.

## `TGVOICE-005` - Text Mode Audio Provider Prompt Parity

- Requirement: `docs/requirements_and_learnings/03_Telegram_Bridge.md`
- Risk covered: Telegram requests an audio attachment but the LLM never sees the selected TTS
  provider's supported speech markers because `voiceMode=false` bypasses the voice prompt.
- Preconditions: Telegram bot bridge and LibreChat Telegram route tests can run with synthetic
  payloads; live Telegram send/listen can be used when an external bot message is acceptable.
- Steps:
  1. Simulate a Telegram voice-note or always-voice text turn with `telegramAudioRequested=true`.
  2. Verify the bridge request carries `voiceMode=false`, `viventiumSurface=telegram`,
     `viventiumInputMode=text` or `voice_note`, and `telegramAudioRequested=true`.
  3. Verify the LibreChat Telegram route injects the saved Speaking route `voiceProvider`.
  4. Verify the Telegram audio-output prompt includes the shared feeling-expression rule plus
     exactly one configured provider dialect: xAI speech tags, Cartesia Sonic-3 SSML-like syntax
     rendered from neutral capability placeholders, Chatterbox markers, or plain/unknown no-markup.
  5. Send expressive synthetic turns without asking for voice, emotion, markup, or controls on xAI,
     Cartesia, and Chatterbox; run restrained xAI/Cartesia, Feelings-off xAI, plain-TTS, and unknown-
     provider negative cases.
  6. Verify visible Telegram display strips provider-control markup while capable TTS receives the
     supported control. Verify the metadata-only `[VoiceRendering][telegram]` event records
     provider/model capability, primary/fallback role, compatible/stripped counts, and no
     prompt/user/synthesis text.
  7. Include the escaped high-Play, low-Mood, high-Connection history fixture. Its raw response must
     use valid xAI provider grammar, and a paired square-wrapper slip must still retain the same
     model-selected control through structural canonicalization rather than losing expression.
- Expected result: Telegram stays in text mode, gets audio delivery, and the model receives the
  selected TTS provider speech-control contract for the audio output path. Expressive capable
  routes use the smallest fitting control without user begging; restrained, Feelings-off, plain,
  and unknown routes remain unmarked.
- Forbidden result: Telegram sets `voiceMode=true`, omits the saved `voiceProvider` on audio turns,
  asks the model to use unsupported tags, requires an explicit user request before expression, adds
  a tag to every capable reply, accepts malformed/provider-crossed syntax as valid eval evidence,
  exposes private text in structural telemetry, or shows provider tags in visible Telegram text.
- Evidence: `qa/emotional-cortex/reports/2026-07-14-feelings-activation-and-telegram-acceptance.md`
- Last run: PASS 2026-07-16 for the escaped high-Play owner-path replay plus the prior always-voice
  xAI positive, calm, and negative turns. The new replay produced one valid raw xAI wrapper, one
  compatible TTS control, zero incompatible/stripped controls, a clean visible bubble, and a
  delivered 7-second voice note. Raw/TTS
  control counts were `2/0/2`, every visible bubble was clean, all three audio files delivered, and
  native Telegram playback was started for the positive file. Prompt-frame telemetry classified the
  audio-output instruction as `surface_prompt` with zero unknown layer/characters. The exact-model
  matrix passed expressive xAI 5/5, restrained xAI 5/5, Feelings-off xAI 3/3, and plain TTS 3/3;
  On 2026-07-16, 54/54 focused TTS tests cover xAI, Cartesia, Chatterbox, OpenAI, and
  ElevenLabs sanitization/capability boundaries, including OpenAI instruction-field support by
  exact model.
  The Workbench bank also covers Cartesia positive/restrained, Chatterbox relief,
  unknown-provider, and the exact xAI history regression. LiveKit call audio, real voice-note
  input, and real non-xAI Telegram delivery remain partial gates.

## `TGVOICE-006` - Smart Optional Audio

- Requirement: `docs/requirements_and_learnings/03_Telegram_Bridge.md`
- Risk covered: the optional text-audio preference creates long, wasteful audio for emails, code,
  tables, and other read-first artifacts, or a control leaks into display/history.
- Preconditions: `Voice replies` and `Smart voice for text` are enabled; synthetic public-safe
  prompts and runtime evidence are available.
- Steps:
  1. Ask for a copy-ready synthetic email without naming the control.
  2. Verify the complete text arrives, no audio arrives, and the preference remains enabled.
  3. Ask for ordinary warm conversation and verify one audio attachment still arrives.
  4. Explicitly ask to hear a short reminder and verify audio is not skipped.
  5. Repeat through proactive callback automation and inspect persisted assistant content.
  6. Compare Prompt Workbench source/compiled/live lineage and exact-model positive/negative evals.
- Expected result: the agent semantically selects optional audio; `{SKIP_VOICE}` is never visible,
  spoken, or persisted; skipped TTS is recorded structurally without private text.
- Forbidden result: runtime keyword/length classification, missing full text, raw control markup,
  audio after a skip, or suppression after an explicit request to hear the answer.
- Automation: `tests/release/test_delivery_controls_contract.py`, Telegram bot/callback/TTS tests,
  LibreChat persistence/prompt tests, and the `telegram_smart_delivery` prompt-bank family.
- Evidence: `qa/telegram-voice-replies/reports/2026-07-22-smart-delivery-controls.md`
- Last run: PASS/PARTIAL 2026-07-22; the local Telegram main turn, logs, persistence, Prompt
  Workbench, and focused automation pass. Real proactive delivery and future-channel adapters remain
  partial.

## `TGVOICE-007` - Natural Message Boundaries

- Requirement: `docs/requirements_and_learnings/03_Telegram_Bridge.md`
- Risk covered: robotic one-bubble delivery, tag leakage during streaming, fragment bombardment,
  duplicate persistence/audio, or semantic breaks inside copy-ready artifacts.
- Preconditions: synthetic public-safe Telegram user flow and persistence/log access are available.
- Steps:
  1. Ask for a short friendly response with two natural conversational beats without naming the
     control.
  2. Verify the answer uses zero or one sensible break, never tiny fragments.
  3. Ask for an email, code block, and compact list; verify they remain intact.
  4. Exercise a deterministic split-token stream where `{MSG_BREAK}` spans chunks.
  5. Verify at most three semantic bubbles, one persisted assistant turn, and at most one audio
     attachment on the final bubble.
  6. Refresh/reopen the real surface and confirm the clean answer remains stable.
- Expected result: natural conversation may use multiple complete bubbles without changing answer
  meaning, history ownership, or audio count.
- Forbidden result: raw/partial controls, more than three semantic bubbles, fake typing delays,
  duplicate history turns, repeated audio, or an artifact split at semantic controls.
- Automation: `tests/release/test_delivery_controls_contract.py`, split-token bot tests, callback
  delivery tests, LibreChat persistence tests, and the `telegram_smart_delivery` prompt-bank family.
- Evidence: `qa/telegram-voice-replies/reports/2026-07-22-smart-delivery-controls.md`
- Last run: PASS/PARTIAL 2026-07-22; a real short response arrived as two complete bubbles with one
  final audio attachment and one clean stored assistant turn. Real proactive delivery and
  attachment-plus-split interaction remain partial.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Telegram Voice Replies. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `TGVOICE-UC-001` | On Telegram voice note/reply, transcript, audio output, verify that telegram voice replies use the selected STT/TTS path and fall back with honest visible copy. | owning requirement for `TGVOICE-001` / `TGVOICE-001` | Telegram voice note/reply, transcript, audio output | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to TGVOICE-001. | User-visible behavior matches source, docs, persisted state, and logs | PARTIAL/PASS 2026-07-14: real always-voice text/xAI delivery passed; voice-note input/STT remains unrun |
| `TGVOICE-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `TGVOICE-002` / `TGVOICE-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to TGVOICE-002. | The user sees an honest setup, retry, or degraded-state result for TGVOICE-002; no fake success is accepted. | PASS 2026-07-14: current report records run/not-run boundaries and passes the v2 template/public-safety gates |
| `TGVOICE-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `TGVOICE-002` / `TGVOICE-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to TGVOICE-002. | TGVOICE-002 remains correct after the persistence or parity step and final wording matches evidence. | PASS 2026-07-14 after final report and docs updates |
| `TGVOICE-UC-004` | Hear a Telegram voice reply or always-voice text reply that includes synthetic citations, source labels, links, emails, unknown tags, provider controls, and bracket stage directions in the assistant text. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `TGVOICE-003` | Telegram bot audio plus provider-payload test harness | TTS payload captures, voice route cache, Telegram display text, runtime logs, sanitized QA report | Telegram audio receives speech-safe provider-appropriate text with no raw artifacts; visible text hides voice-control markup; capable providers keep only their documented controls. | 2026-05-22 PARTIAL/PASS: automated provider-payload parity passed; live Telegram audio send/listen not rerun |
| `TGVOICE-UC-005` | Send a Telegram always-voice text message and a Telegram voice note, then confirm the answer uses Telegram text mode while still sending audio. | `docs/requirements_and_learnings/03_Telegram_Bridge.md` / `TGVOICE-004` | Telegram bot plus LibreChat Telegram route logs/payload | Bot kwargs, route request metadata, Telegram visible text/audio, persisted assistant message | LibreChat sees `voiceMode=false`; input mode is `text` or `voice_note` as appropriate; Telegram audio is delivered when enabled. | PASS 2026-07-11 for real always-voice text; real post-change voice-note/STT input remains follow-up |
| `TGVOICE-UC-006` | Send natural positive, calm, and negative Telegram messages without asking for emotion or markup while xAI is the saved TTS route. | `docs/requirements_and_learnings/03_Telegram_Bridge.md` / `TGVOICE-005`, `EMO-036` | Telegram Desktop, LibreChat/Telegram logs and DB, Prompt Workbench | Raw marker counts, prompt-frame metadata, clean visible text, TTS bytes/timing, delivered/played audio, Feelings-off/plain negative cases | Fitting xAI controls reach TTS and telemetry for expressive moments but not the bubble; the calm turn and Feelings-off/plain routes remain unmarked | PASS 2026-07-14 for real xAI positive/calm/negative delivery plus repeated expressive/restrained/off/plain exact-model boundaries; broader real-provider parity PARTIAL ([report](../emotional-cortex/reports/2026-07-14-feelings-activation-and-telegram-acceptance.md)) |
| `TGVOICE-UC-007` | With Smart voice for text enabled, request a copy-ready synthetic email, ordinary conversation, and an explicitly spoken reminder. | `docs/requirements_and_learnings/03_Telegram_Bridge.md` / `TGVOICE-006` | Telegram Desktop, Prompt Workbench | Visible text/audio, clean persisted message, voice-decision log, prompt lineage, exact-model eval | Email stays complete and text-only; conversation and explicitly spoken reminder still receive one audio attachment; no controls are visible | PASS 2026-07-22: all three real Telegram Desktop paths matched visible delivery, sanitized logs, and persistence evidence ([report](reports/2026-07-22-smart-delivery-controls.md)) |
| `TGVOICE-UC-008` | Ask for a friendly two-beat reply, then a copy-ready artifact, and reopen the chat. | `docs/requirements_and_learnings/03_Telegram_Bridge.md` / `TGVOICE-007` | Telegram Desktop, logs, DB/history | Bubble count/content, final audio attachment, one persisted logical turn, refresh/reopen result | Natural beats may split into at most three complete bubbles; artifacts stay intact; one clean turn persists with at most one audio | PASS/PARTIAL 2026-07-22: real main-turn split, intact email artifact, reopen, logs, and persistence pass; proactive and attachment-plus-split paths remain partial ([report](reports/2026-07-22-smart-delivery-controls.md)) |
