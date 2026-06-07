# Telegram Bridge - Requirements, Specs, and Learnings

## Overview

Telegram messages must route through the main LibreChat Agents pipeline by default. Responses
stream back to Telegram through the existing bridge.

## Core Requirements

- Telegram users receive complete responses or a clear error if the agent or voice stack disconnects.
- Connection loss mid-response must not leave users hanging on a partial holding message.
- Retry should be user-initiated to avoid duplicate tool actions.
- Telegram bot-token setup must stay truthful and reject malformed tokens.
- Telegram must differentiate voice-note input vs text input and forward that mode to LibreChat.
- Telegram media transcription failures must surface as explicit media errors, not as transcript text,
  and must not be forwarded into LibreChat as if the user said them.
- Telegram text responses should use robust Telegram HTML generated from standard Markdown. Telegram
  voice-note and always-voice audio replies are still text-mode responses with an audio attachment
  on top; they must not switch the LibreChat turn into LiveKit voice-call mode.
- Background follow-ups must preserve the same formatting rules as the main response.
- Telegram must mirror LibreChat UX for new features, including scheduled prompts and background
  follow-ups.
- Telegram must mirror direct-action worker completion delivery. When a LibreChat turn starts a
  GlassHive worker, the callback receiver must persist both the same-conversation web callback and
  a durable Telegram delivery row. The bot may use in-turn polling as a fast path, but late worker
  results must still be claimed from the delivery ledger and sent automatically in the same
  Telegram chat after the original poll window ends or after a bot restart.
- Telegram must deliver LibreChat message attachments back to the Telegram user.
- Detached/local launches must not leave Telegram pointed at a dead LibreChat localhost origin after
  frontend dev-server exits or launcher-side supervision gaps.
- Detached/local launches must recover the LibreChat API when the real API child dies even if an
  npm/nodemon parent process is still alive.
- Local Telegram-to-LibreChat API traffic should default to explicit IPv4 loopback
  (`127.0.0.1`) to avoid localhost address-family ambiguity during restart windows. Status must
  treat Telegram as degraded when the bot process is alive but the configured LibreChat API origin
  cannot be reached.
- Successful LibreChat stream jobs must remain available briefly after completion so Telegram retry
  or resume can recover the final event. A late reconnect after a completed response must not become
  a synthetic generic connection error just because the generation job was deleted immediately.

## Public-Safe Implementation Notes

- Use the same product truth in Telegram and the web UI.
- Keep browser-facing URLs honest.
- Keep auth and token handling provider-specific and explicit.
- Do not embed private machine names, private paths, or owner-only debugging notes into the public
  contract.

## Telegram Voice and Call Behavior

- Voice-note transcription must use the Telegram bridge STT provider. By default,
  `integrations.telegram.stt_provider` is empty and Telegram inherits the configured global voice
  STT provider, including local Whisper/whisper.cpp. The compiler must not silently remap local
  Whisper to OpenAI, AssemblyAI, or any hosted provider just because Telegram is a long-running
  ingress process. Hosted providers are explicit Telegram overrides only.
- Voice-note and video-note download/transcription failures must return one clean Telegram error and
  stop before chat submission.
- Voice-note and video-note transcription must share the same non-blocking serialized local-STT path
  whenever Telegram uses local Whisper, whether inherited from the global voice route or explicitly
  configured for Telegram. The bot must not run local native STT concurrently inside the polling
  process.
- Drift guardrail: do not "harden" Telegram by changing the omitted STT provider to OpenAI,
  AssemblyAI, or another hosted route. Reliability hardening for inherited local Whisper belongs in
  serialization, startup/preflight checks, decoder validation, and honest error reporting, not in a
  hidden provider remap.
- Telegram's hosted Bot API cannot download files above its platform limit, so oversized Telegram
  media must fail honestly unless the install is configured to use a local Telegram Bot API server.
- Voice replies must use a compatible TTS provider/key pair.
- Telegram voice-note replies must use the same saved Speaking route as the modern voice
  playground. The LibreChat Telegram route resolves `resolveUserVoiceRoute(...)` for the linked
  user and returns that route to the bot; the bot must treat Cartesia variants as voice IDs
  (Megan/Lyra), not as Sonic model names. Cartesia model selection is Sonic-3-only.
- Telegram voice output preferences must stay aligned before and after generation:
  - `VOICE_RESPONSES_ENABLED=false` disables Telegram audio replies.
  - Telegram always remains a text-mode LibreChat surface. A voice note sends
    `voiceMode=false`, `viventiumSurface=telegram`, and `viventiumInputMode=voice_note`; it should
    receive an audio reply when voice replies are enabled.
  - `ALWAYS_VOICE_RESPONSE=true` sends `voiceMode=false`, `viventiumSurface=telegram`, and
    `viventiumInputMode=text` for text messages; it only adds Telegram audio delivery after the
    text-mode main answer is generated.
  - `input_mode` remains structural: only actual voice-note input is sent as `voice_note`; text
    messages with always-voice output still use `input_mode=text`.
- When the resolved Speaking route is Cartesia, Telegram follows the same Sonic-3 voice markup
  contract as modern calls:
  - the canonical Cartesia Sonic-3 capability contract is
    `viventium_v0_4/shared/voice/cartesia_sonic3_capabilities.json`; Telegram must not carry a
    separate emotion list or tag vocabulary
  - Telegram does not request the LiveKit voice-mode prompt; audio replies are synthesized from the
    text-mode answer after speech-safe cleanup
  - runtime must not invent emotion tags or infer emotion from user intent
  - raw LLM text with Cartesia markup is preserved for TTS
  - Cartesia-supported nonverbal markers from the shared contract are preserved, while structural
    unsupported bracket stage directions are stripped before Cartesia so they are not read aloud
  - user-visible Telegram text is sanitized so `<emotion>`, `<break>`, `<speed>`, `<volume>`,
    `<spell>`, and structural bracket stage directions do not appear
  - Cartesia `/tts/bytes` requests include both the model-authored tag in `transcript` and the same
    parsed emotion value in `generation_config.emotion`; multiple model-authored emotion regions
    are synthesized as separate WAV segments and merged
  - opt-in non-secret debugging (`VIVENTIUM_VOICE_DEBUG_TTS=1` or
    `VIVENTIUM_TELEGRAM_DEBUG_TTS=1`) may log raw LLM text, TTS text, display-sanitized text, and
    Cartesia request transcripts without API keys
  - default logs should still include non-secret structural counts for `[laughter]`,
    `<emotion>`, `<break>`, `<speed>`, `<volume>`, and `<spell>` so formatting loss can be
    diagnosed without publishing transcript content
- When the resolved Speaking route is xAI, Telegram follows the standalone xAI TTS contract:
  - the canonical xAI capability contract is
    `viventium_v0_4/shared/voice/xai_tts_capabilities.json`
  - the saved route's `tts.variant` is the xAI `voice_id`, so a user selecting `Eve`, `Rex`, or
    another xAI voice in the modern playground gets the same voice in Telegram audio replies
  - Telegram prefers `VIVENTIUM_XAI_TTS_API_KEY` for synthesis and only falls back to `XAI_API_KEY`
    for compatibility, matching the LiveKit gateway's xAI voice-key precedence
  - Telegram calls `POST https://api.x.ai/v1/tts` with `text`, `voice_id`, `language`, and a
    structured `output_format`
  - xAI inline and wrapping speech tags from the shared contract are preserved for xAI synthesis
  - Telegram must not split xAI text into generic 800-character fallback chunks because that can
    break xAI wrapping tags and create invalid concatenated MP3 output
  - user-visible Telegram text must strip xAI tags even when the model emits malformed wrapper
    syntax such as `[soft]...[/soft]` or an orphan closing tag like `[/soft]`
  - Cartesia-only tags such as `<emotion>`, `<break>`, `<speed>`, `<volume>`, `<spell>`,
    `[laughter]`, and Cartesia-only bracket aliases like `[soft laugh]` or `[gentle sigh]` are
    stripped before xAI synthesis
  - OpenAI/ElevenLabs fallbacks still strip all provider markup before synthesis
- `/call` should open the browser into the modern voice surface using a browser-facing URL.
- Raw LAN/IP browser-voice links should not be presented as a supported path unless they are
  explicitly known-good for the current deployment.

## Telegram Media Prerequisites

- Telegram voice notes and video notes are part of the supported bridge surface, so their media
  decoding requirements must be treated as first-class installer/runtime prerequisites.
- When Telegram is enabled, `ffmpeg` must be available and runnable on the host:
  - local `pywhispercpp` transcription needs it to decode Telegram's non-WAV voice-note media
  - Telegram video-note extraction already depends on it before transcription
- Presence alone is not enough. Startup/preflight must run a small ffmpeg media probe so broken
  Homebrew dynamic-library links fail honestly before Telegram is reported healthy.
- If the install needs Telegram media downloads beyond the hosted Bot API ceiling, the Telegram bot
  must be pointed at a local Telegram Bot API server instead of `https://api.telegram.org`.
- Canonical config owns that choice under `integrations.telegram`:
  - explicit external-server wiring with `bot_api_origin`, or
  - explicit `bot_api_base_url` and `bot_api_base_file_url`, or
  - Viventium-managed same-Mac server wiring under `local_bot_api`
- Path of least resistance applies here:
  - if an operator already has a supported local/external Telegram Bot API server, prefer wiring
    `bot_api_origin` (or the explicit base URLs) instead of making Viventium own another server
  - only use `integrations.telegram.local_bot_api` when Viventium must own the same-Mac server
    lifecycle itself
- Those canonical fields compile to:
  - `VIVENTIUM_TELEGRAM_BOT_API_ORIGIN`, or
  - explicit `VIVENTIUM_TELEGRAM_BOT_API_BASE_URL` and `VIVENTIUM_TELEGRAM_BOT_API_BASE_FILE_URL`
- When `integrations.telegram.local_bot_api.enabled` is true:
  - Viventium owns the local `telegram-bot-api` process lifecycle in the launcher
  - preflight must report the `telegram-bot-api` binary plus `api_id` / `api_hash` as prerequisites
  - the compiler derives `VIVENTIUM_TELEGRAM_BOT_API_ORIGIN` from the local host/port instead of
    requiring duplicate manual base-URL config
  - the Telegram bot must run in PTB local mode
  - Telegram media size policy must come from canonical config, not a hidden hardcoded default
- `integrations.telegram.max_file_size_bytes` is the canonical Telegram bridge media ceiling.
  Hosted Telegram defaults to 10 MB; managed local Bot API mode defaults to 100 MB unless the
  operator sets a different value explicitly.
- Public install flows must detect, install, and recheck `ffmpeg` automatically through preflight
  when Telegram is enabled.
- Telegram startup must fail honestly instead of reporting a healthy bridge when `ffmpeg` is
  unavailable or installed but not runnable.
- If a running bridge still encounters a non-runnable decoder, Telegram should return one clean
  media-decoder error and stop before chat submission.
- Telegram polling must be single-owner per BotFather token. Starting the bot from a second
  checkout, terminal, launch helper, or stale supervised process must fail closed before polling
  begins, otherwise Telegram's `getUpdates` API alternates conflicts between the processes and
  voice replies can be delayed or split from the text reply.
- Telegram startup/watchdog logic must reconcile the real scoped bot process list before launching:
  a pidfile-free live bot from the same checkout must be adopted back into the PID contract, and
  multiple same-checkout bot processes must be collapsed to one instead of starting an additional
  poller.
- The same-token lock must live in a durable Viventium runtime lock directory, not a temporary
  directory that the OS may clean while the process is still running.
- The macOS status-bar helper must not report the stack as simply running when Telegram is enabled
  but the live Telegram sidecar has a missing PID or a recent polling/auth runtime issue. Core web
  health can remain usable, but the helper must surface that enabled sidecars need attention.
- Telegram command/message handling must tolerate transient Bot API `getMe` timeouts without
  crashing the user turn. Reply-context fallback is allowed only when the reply sender actually
  exists; a non-reply message should continue through the normal LibreChat bridge path.
- Telegram error logs must identify failures with non-secret structural metadata such as update ID
  and message ID. They must not log raw Telegram update objects because those can include private
  message text, chat IDs, usernames, or attachments.
- Non-secret voice delivery timing logs must be available in normal runtime logs. Each voice-routed
  Telegram turn should log the gate decision, TTS start, TTS chunk duration/bytes, and Telegram audio
  send duration without logging bot tokens, API keys, raw private message text, or local paths.
- GlassHive callback delivery logs must include non-secret observability states: callback accepted,
  delivery enqueued, claimed, sent, failed, suppressed, retry count, and backlog age. Telegram Bot
  API token-bearing URLs must be redacted from local logs and from persisted delivery failure
  reasons.
- A callback is not successfully accepted for Telegram or voice until both the same-conversation
  callback message and the surface delivery ledger row are durable. If ledger enqueue fails after
  message persistence, the callback receiver must return a retryable failure so GlassHive retries
  rather than marking the callback delivered.
- Duplicate callback repair must be DB-backed, not process-memory-only. If a callback message was
  already persisted but the Telegram/voice delivery row is missing after a restart or partial
  failure, a repeated signed callback with the same callback id must repair the missing delivery
  row without creating a duplicate conversation message.
- Provider authentication failures must surface as reconnect guidance on Telegram. They must not be
  collapsed into a generic connection error that implies Telegram or GlassHive transport is broken.
- Telegram SSE resume must tolerate the normal race where generation completes while the first
  stream connection is interrupted. The configured stream services should retain completed
  successful jobs for the store's short completion TTL and replay the cached final event to late
  subscribers. Truly expired or missing streams may still return a clear missing/expired-stream
  failure, but the normal completion path must not be reported as a generic connection problem.
- Transport-level bridge fallbacks must remain text-mode diagnostics, not synthetic voice replies.
  When Telegram always-voice output is enabled, the bot may voice assistant answers, but it must not
  synthesize local transport/plumbing failures such as an exhausted expired-stream retry.
- Telegram GlassHive delivery dispatcher tuning is operational only:
  - `VIVENTIUM_TELEGRAM_GLASSHIVE_DELIVERY_POLL_S` controls the background delivery poll interval
    and defaults to 5 seconds.
  - `VIVENTIUM_TELEGRAM_GLASSHIVE_DELIVERY_BATCH_SIZE` controls each claim batch and is capped at
    25.
  - `VIVENTIUM_TELEGRAM_GLASSHIVE_DELIVERY_LEASE_MS` controls the claim lease and defaults to 10
    minutes, capped at 10 minutes. A lost claim must be returned as a conflict and logged as
    observability, not silently treated as a successful status update.
  - These knobs must not replace the durable delivery ledger or become correctness requirements.

## Telegram Attachments

Any file generated in LibreChat must be sent to the Telegram user as a Telegram photo/document,
not silently dropped.

Inbound Telegram message attachments must follow the same shared message-file contract as the web
UI. If the active model/provider supports a file through LibreChat's native "Upload to Provider"
path, the bridge must preserve the normal raw message attachment so downstream client code can send
it provider-natively. If the file is parseable but not valid for provider-native upload on that
surface, the runtime must promote it into the context-extraction pipeline instead of storing it as
an opaque upload the agent cannot read. If neither provider-native upload nor readable
context-extraction can handle the file on that surface, Telegram must fail the turn with a clear
attachment-processing error rather than silently dropping to caption-only behavior.

### Major file-type rule

- Text-like files must extract into readable context:
  - examples: `.txt`, `.md`, `.json`, `.csv`, `.xml`, `.yaml`, code/config text
- Provider-native raw attachments must stay raw when the current runtime can truly serialize them:
  - examples: images, PDFs, Google/OpenRouter audio/video, Bedrock document types
- Office/OpenDocument binaries that require OCR or a document parser must either:
  - use the configured OCR/document-parser path, or
  - fail honestly with a clear message when that extraction path is unavailable
- Unsupported binary/archive leftovers must not be accepted as inert message attachments.

### Fix pattern

- parse attachment events from the LibreChat stream
- download bytes through the gateway
- send images as albums when appropriate
- send non-image files as documents
- preserve provider-native message attachments and only auto-promote the non-provider-native
  parseable remainder into context extraction before the agent run
- reject files that are neither provider-native nor readable through context extraction

## Evidence to Capture

- helper logs
- Telegram bot logs
- Mongo proof of the exact user and assistant turns
- attachment delivery proof when files are involved
