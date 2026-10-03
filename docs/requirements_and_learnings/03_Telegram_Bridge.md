# Telegram Bridge - Requirements, Specs, and Learnings

## Overview

Telegram messages must route through the main LibreChat Agents pipeline by default. Responses
stream back to Telegram through the existing bridge.

The separate `telegram-codex` native relay defaults to `gpt-6.1-sol` with `high`
reasoning effort on new and resumed turns. Its generated settings and native CLI arguments
must agree. Explicit supported model and effort settings remain available; this relay does
not select the main Viventium Telegram bridge's model.

## Core Requirements

- Telegram users receive complete responses or a clear error if the agent or voice stack disconnects.
- Connection loss mid-response must not leave users hanging on a partial holding message.
- Transport recovery resumes the existing accepted work and saved reply automatically; it must not
  rerun tool actions. Starting execution again remains a distinct, authorized Retry action.
- Telegram bot-token setup must stay truthful and reject malformed tokens.
- Telegram must differentiate voice-note input vs text input and forward that mode to LibreChat.
- Telegram media transcription failures must surface as explicit media errors, not as transcript text,
  and must not be forwarded into LibreChat as if the user said them.
- Telegram text responses should use robust Telegram HTML generated from standard Markdown. Telegram
  voice-note and always-voice audio replies are still text-mode responses with an audio attachment
  on top; they must not switch the LibreChat turn into LiveKit voice-call mode.
- Telegram's Markdown-to-HTML renderer must gracefully degrade markdown tables into readable
  Telegram rows because Telegram does not support table rendering and workers may still return
  compact tabular summaries.
- Nested supported Markdown inside block quotes must render as the intended Telegram HTML and must
  never expose internal formatter placeholders such as `PH0` or `PH2`.
- Background follow-ups must preserve the same formatting rules as the main response.
- Telegram must mirror LibreChat UX for new features, including scheduled prompts and background
  follow-ups.
- Telegram replies must send `ReplyContextV1` as a bounded typed descriptor. Quoted text and
  extracted quoted-document evidence are untrusted reference data and must never be concatenated
  into the new user-authored message. Core resolves assistant ownership from the authenticated
  owner, current chat, and durable outbound Telegram message-ID receipt. Unknown or foreign
  provenance yields `cannot verify`; it must never produce an authorship denial or spoof claim.
- Core resolves that descriptor when it admits the turn, and the typed result becomes the turn's
  `reply_context`. A retained (prepared) input takes the replied message from its own durable
  ingress preparation, so its first admission and every replay present the same quote. The
  adapter's descriptor of that same message may only add text it extracted from a quoted document.
  Without a receipt, Telegram's own sender data decides whether the quote is the owner's, another
  participant's, or unknown. Each receipt maps a Telegram message to the message it presented, so a
  reply to a late addition names the addition and a reply to the answer names the answer. The route
  used to ignore the adapter's descriptor entirely, so Main received no quote at all, even when its
  answer happened to be right from history.
- A quote stays with its own input:
  - When Telegram reports the passage the user selected (`message.quote`), that passage is the
    quote, not the whole replied message; the preparation saves it.
  - The ready record keeps the text the adapter extracted from the input's quoted document, by
    Telegram file ID, so an identity-only continuation or replay presents the same quoted facts
    as the first admission.
  - Each source segment carries its own typed quote. When a deferred quoted input joins a newer
    input's turn, Main receives one quoted-evidence capsule per quoted input it owns, labelled
    with the same S-number as the rapid source selection. The native delegation contract still
    carries source text only.
  - Telegram's additive (`response_only`) invocation owns its current input and every input
    that no committed invocation authors. The rapid source selection lists the owned sources with
    their turn S-numbers, and Main receives each owned input's quote.
    - A claim only reserves a revision. The claim that first admits a source marks its
      `authoring_revision` provisionally.
    - A revision authors sources only at its request's generation handoff: after admission and
      every request step that can fail, just before its input binds to the stream. Its job first
      stores the final context, then the commit is recorded. At that commit, each source's author
      is the earliest committed revision that carried it, else the committing revision.
    - The commit takes over every earlier revision without a commit, which can then never commit.
    - A refused commit removes the job and returns the claim.
    - A commit whose replies are lost is reconciled from the ledger. If its outcome stays unknown,
      it is relinquished and retried, never read as a refusal.
    - A binding or started receipt that fails after the commit gives the authorship back.
    - These facts live in the logical turn's author ledger, which outlives the turn's retirement.
      So a winner still owns a reservation it fenced after another conversation replaces the turn,
      and the new conversation never authors the old one.
    - A revision claimed before the ledger existed is an author only while its job exists. A bare
      reservation is fenced, and its sources belong to the winner. Retiring the turn keeps that
      disposition in the ledger.
    - A delivery's coverage marks each source its revision authored. An input not bound to its
      own started stream settles only through the answer that authored it. So an author that
      never ran cannot leave its input silently settled: the input is re-driven, or it records
      the honest `source_input_uncovered` failure.
    - The rule covers three shapes. An input deferred before any claim belongs to the combined
      answer. So does the input of a reservation that loses its admission race. An input whose
      earlier revision committed stays with that invocation.
    - Before this rule, the consumer dropped every earlier quote in `response_only`, so the
      combined answer took newer figures from history (S0942). Claim-time marks alone then
      mistook a reservation for an author. A commit recorded before its job context, or lost
      with a retired turn, made the same mistake. So did one recorded before request steps that
      could still fail, and one whose lost reply was taken as a refusal.
- For a session-backed conversation provider, the resolved `ReplyContextV1` must travel in the
  bounded invocation-local turn-context channel immediately with the current user turn. Storing it
  only in mutable bootstrap/developer instructions is insufficient because a resumed native
  session can keep its earlier developer authority. The reply capsule outranks time, Active Work,
  source selection, owner-Main history, and stale visible ancestry when those sources conflict.
- Every logical assistant result delivered to Telegram must persist one transport receipt with all
  Telegram chunk IDs. This includes normal Main replies, scheduled Main results, and callbacks.
  A reply to any chunk resolves the same logical output. A transport retry resends the accepted
  result and never regenerates the AI turn.
- Telegram text length, word count, and prompt keywords must never remove the agent's configured
  tools or MCP instructions. Tool availability must follow the same structural agent, capability,
  authentication, and server-health contract as web and voice. Latency optimizations may defer bulk
  schemas, but they must preserve an eager execution gateway plus request-scoped discovery.
- Telegram must mirror direct-action worker completion delivery. When a LibreChat turn starts a
  GlassHive worker, the callback receiver must persist both the same-conversation web callback and
  a durable Telegram delivery row. The bot may use in-turn polling as a fast path, but late worker
  results must still be claimed from the delivery ledger and sent automatically in the same
  Telegram chat after the original poll window ends or after a bot restart.
- Prepared Telegram input must persist its source-message identity, conversation generation,
  preparation state, claim/lease and recovery fields through the real ingress schema. Active
  preparation has no expiry; terminal and legacy rows retain the existing expiry requirement.
  The route uses the same exported canonical-conversation and accepted-source helpers as Main.
- A permanent upload preparation failure settles every verified source claim in its media group
  through the existing intake transaction. Each original source remains retained with a typed
  failure; no partial attachment group starts a turn. Recovery reconciles older or late unadmitted
  siblings from the same owner, chat, thread, conversation, generation and source scope. A late
  member cannot become ready after its group permanently failed. Prepared or admitted inputs are
  protected, retryable groups recover together, and a failed group cannot block later intake
  settlement. A refused late member or conflicting group claim returns one non-retryable attachment
  error asking the user to resend the whole group; it must not start an assistant turn or appear as
  a generic connection error. A conflicting claim settles only its verified, live, unprepared
  primary through the existing guarded status transaction; rejected related claims are untouched.
  Recovery then closes its verified unadmitted siblings, without admitting the refused turn or
  blocking later inputs. Other owner, lease and admitted-source guards keep their own errors.
- Replay of a prepared input must retain its original owner-bound parent when the selected tip is
  that same input or its interrupted provisional response. Later corrections retain their current
  continuation parent. A saved legacy self-parent or missing provisional parent may be projected
  through its verified retained original anchor without rewriting stored history; foreign, deleted,
  missing or untrusted anchors remain refused.
- Telegram must deliver LibreChat message attachments back to the Telegram user.
  Native Main's intentionally published files follow the same contract: xPerfect records selected
  output descriptors on its canonical durable response, and Core verifies the current owner,
  conversation, message, stream, agent, turn, invocation, signed origin, MIME, length and SHA-256
  before storing a normal File attachment. Existing selected files may be published; reading or
  referring to a workspace file does not select it for export. Selected files become Telegram
  documents through the existing authorized download and document sender. A native tool render is
  local to the harness and is not channel delivery. The model persists its own requested output in
  the admitted workspace or managed `TMPDIR` when needed and selects it in the final answer;
  viewed images, screenshots, and discussed uploads remain context unless selected for delivery.
  Distinct filenames may
  contain identical bytes. The configured Core limits and existing Telegram document limit apply
  before fetching and while reading bytes. An import failure preserves useful text and persists an
  unavailable attachment receipt; the web and Telegram show an honest unavailable or size notice,
  with no fabricated File or download. Replay retains saved attachments and does not regenerate
  output. Byte-verified real-surface acceptance remains required for delivery claims.
  The selected source may be in the admitted workspace or that worker's managed `TMPDIR`.
  Arbitrary host folders do not become export roots. Explicit selection retains existing authorized
  input-file returns; automatic discovery keeps its stricter operational-folder exclusions.
  Existing traversal, private-name, symlink and hard-link checks apply to selected sources.
  Rejected selections retain a basename and typed unavailable reason, even when no file succeeds.
  Core's configured file count, per-file size and aggregate size bounds apply before import.
  A completed agent transfer retains its verified selected-file carrier, including the original
  publisher identity. It emits no intermediate attachment. The eventual successful visible final
  imports each retained publication once through the same checks and attachment path. Hidden or
  refused finals and interrupted graphs must not publish retained files.
  A consultant transfer without a usable delivery identity retains its result but omits the
  selected-file carrier. An assistant response with selected files still requires that identity;
  missing identity remains a typed failure. The host import guards are unchanged.
  Core imports verified signed artifact paths through the configured authenticated native provider
  route, while retaining the original configured public-origin validation. Public links remain
  public. The transport cannot change the grant path or bypass owner, expiry, byte or storage
  checks. A changed or unavailable provider route remains an unavailable attachment; it does not
  trigger an alternate public fetch. Transport diagnostics retain only request hash, status,
  duration and a bounded error class, without URL, headers, credentials or response body.
- Authored captions must survive native media formatting on both the current turn and retained
  history. Known inline native media uses the existing hydrated media carrier, preserving bytes and
  distinct items while avoiding exact duplicate hydration. Unknown content stays available for
  validation; owner, ancestry and authored-text checks remain enforced.
- Native conversation requests must carry the verified current upload ledger in their signed
  bootstrap, including an attachment-only turn. GlassHive resolves the original bytes under the
  authenticated owner's storage root and includes the workspace attachment paths in the current
  accepted turn. Missing or foreign bytes remain an explicit unavailable source, never an empty
  successful handoff or a path supplied by the user.
- Detached/local launches must not leave Telegram pointed at a dead LibreChat localhost origin after
  frontend dev-server exits or launcher-side supervision gaps.
- Detached/local launches must recover the LibreChat API when the real API child dies even if an
  npm/nodemon parent process is still alive.
- Local Telegram-to-LibreChat API traffic should default to explicit IPv4 loopback
  (`127.0.0.1`) to avoid localhost address-family ambiguity during restart windows. Status must
  treat Telegram as degraded when the bot process is alive but the configured LibreChat API origin
  cannot be reached.
- A saved native FINAL remains recoverable under the existing bounded recovery deadline until the
  exact Telegram logical-turn/revision delivery acknowledgement is committed. Provider completion,
  SSE publication, and replay storage are not delivery acknowledgements. Ordinary completion TTL,
  cleanup, and terminal bookkeeping must preserve an unacknowledged adapter-owned FINAL. An exact
  committed acknowledgement permits normal expiry; explicit retirement still fences stale output.
- Successful LibreChat stream jobs must remain available briefly after completion so Telegram retry
  or resume can recover the final event. A late reconnect after a completed response must not become
  a synthetic generic connection error just because the generation job was deleted immediately.
- Telegram's raw SSE follow-up listener and DB-backed follow-up poller share the compiler-owned
  `runtime.background_followup_window_s`, delivered as
  `VIVENTIUM_TELEGRAM_FOLLOWUP_GRACE_S`. They must not invent independent implicit listener
  lifetimes. An explicit zero disables ordinary automatic follow-up listeners without canceling
  Main, cortex execution, Phase B, or a separately configured GlassHive callback wait.
- `VIVENTIUM_TELEGRAM_FOLLOWUP_TIMEOUT_S` may explicitly bound a longer operator-selected total
  listener window and is limited to one day. If it is omitted, the canonical background follow-up
  window is also the total. The legacy `VIVENTIUM_TELEGRAM_INSIGHT_GRACE_S` and
  `VIVENTIUM_TELEGRAM_INSIGHT_MAX_S` inputs are deprecated standalone compatibility only and never
  override a compiler-supplied canonical window.

## Smart Messaging Delivery Controls

Problem being solved: `Smart voice for text` should not turn read-first artifacts such as drafted
emails, code, tables, or exact copy into long, wasteful audio, while conversational replies should
still feel warm and speakable. Telegram delivery should also be able to express a small number of
natural conversational beats without forcing every answer into one robotic bubble or breaking one
logical conversation turn into duplicate history.

Telegram text and optional audio are two delivery views of one Main Agent answer. The model decides
whether audio is useful and where a conversational answer has natural bubble boundaries; the
runtime only consumes the following explicit structural controls:

- `{SKIP_VOICE}` on a standalone line suppresses the optional audio attachment for that turn. The
  complete text answer is still sent. It is appropriate for read-first, copy/edit/reuse artifacts
  such as emails, code, tables, forms, and long reference material. It must not be used merely
  because a conversational answer is detailed or long, and an explicit request to hear/read/speak
  the answer takes precedence.
- `{MSG_BREAK}` on a standalone line separates complete conversational beats into Telegram
  bubbles. The agent usually emits none, may occasionally emit one, and may emit at most two so one
  logical turn creates at most three semantic bubbles. It must not split code, quotes, emails,
  documents, tables, tightly structured lists, or tiny fragments.

Both controls are case/whitespace tolerant only as standalone lines outside fenced code and block
quotes. Literal mentions in prose, inline code, fenced examples, and quotes remain user content.
Incomplete reserved control suffixes are hidden while streaming so users never see a flashing
`{MSG_` or `{SKIP_` fragment.

The clean response persists as one logical assistant turn. Delivery controls and provider voice
markup do not persist in Telegram chat history. Semantic bubbles are separate Telegram transport
messages, but they do not create duplicate conversation records or background turns. Long-message
transport splitting still applies independently. If audio is delivered, the clean logical answer
is synthesized once and attached once, to the final bubble; no fake typing delays are added.

`Smart voice for text` is the user-facing preference label for the existing
`ALWAYS_VOICE_RESPONSE` setting. Voice-note input still follows the ordinary voice-reply toggle;
`{SKIP_VOICE}` only suppresses an otherwise optional output attachment selected for the current
answer.

The canonical grammar is versioned and shared by the LibreChat/JavaScript persistence boundary and
the Python messaging adapter. Other conversational channel adapters must consume the same grammar,
caps, precedence, persistence, and observability contract rather than inventing channel-specific
tokens. This provides a parity contract without pretending that a Slack or WhatsApp adapter exists
when it is not installed. Runtime must never infer these decisions from prompt text, length,
keywords, or artifact type.

Prompt-layer ownership and the runtime-vs-prompt boundary are also recorded in
[`49_Prompt_Architecture_and_Token_Efficiency.md`](49_Prompt_Architecture_and_Token_Efficiency.md#fix-7a-keep-messaging-delivery-intent-model-owned-and-adapter-neutral).

## Public-Safe Implementation Notes

- Use the same product truth in Telegram and the web UI.
- Keep browser-facing URLs honest.
- Keep auth and token handling provider-specific and explicit.
- Do not embed private machine names, private paths, or owner-only debugging notes into the public
  contract.

## Markdown Formatting Integrity

- Main streamed answers, scheduled/proactive messages, and background follow-ups share
  `render_telegram_markdown(...)` and the same Markdown-to-Telegram-HTML renderer.
- The renderer protects converted fragments with internal placeholders. A later block wrapper can
  contain an earlier emphasis placeholder, so restoration must resolve later/outer placeholders
  before earlier/inner placeholders.
- Escaped failure chain: nested emphasis in a Markdown block quote -> emphasis became an internal
  placeholder -> the quote became a later placeholder containing it -> forward-only restoration
  expanded the quote after the emphasis pass had already run -> Telegram stripped the NUL
  delimiters and displayed `PH<number>` as user text.
- The formatter regression gate must exercise the pure renderer, the main streamed reply path, and
  the proactive/follow-up path with synthetic nested formatting. Literal internal placeholder
  leakage is forbidden even if Telegram accepts and displays the surrounding block quote.

## Telegram Voice and Call Behavior

- Voice-note and video-note transcription must use the linked user's current saved Listening
  provider and model. The bot reads that authenticated selection alongside the independent media
  download, before recognition; an older response's cached route is not selection authority.
  Without a saved choice, the configured Telegram default applies. By default,
  `integrations.telegram.stt_provider` is empty and Telegram inherits the configured global voice
  STT provider, including local Whisper/whisper.cpp. The compiler must not silently remap local
  Whisper to OpenAI, AssemblyAI, or any hosted provider just because Telegram is a long-running
  ingress process. Hosted routes require a saved Listening choice or configured provider.
  Compiler metadata distinguishes an explicit Telegram override from an inherited default.
  Missing selection authority, provider credentials or unsupported configuration must stop
  recognition honestly; they must not choose another model or provider.
- Voice-note and video-note download/transcription failures must return one clean Telegram error and
  stop before chat submission.
  Selected hosted recognition preserves typed authentication, access, rate-limit, timeout,
  temporary-unavailable and request-rejected failures. A missing or placeholder credential is an
  authentication blocker before any request. A generic client rejection does not prove an
  unsupported model. Provider response bodies, credential samples and endpoint URLs must not
  enter transcription logs or public errors. Exact selected route/model, whole input, one request
  and owned session cleanup remain unchanged.
- Voice-note and video-note transcription must share the same non-blocking serialized local-STT path
  whenever Telegram uses local Whisper, whether inherited from the global voice route or explicitly
  configured for Telegram. The bot must not run local native STT concurrently inside the polling
  process.
- Local recognition keeps one resident model and swaps it under the existing native inference
  lock. Validate the local model on a swap, rather than hashing its complete file for each note.
  Saved OpenAI models override the legacy model default. AssemblyAI uses the selected
  streaming engine with real-time pacing of the complete note, an owned HTTP session and no
  automatic retry of already consumed PCM. Partial transcripts cannot become an authored input
  after a provider failure.
  AssemblyAI notes use the call's compiled confidence, silence and formatting settings and enable
  speaker labels. The authenticated route supplies the same bounded artifact-display keyterms
  from the linked owner's current conversation, including topics. Missing, empty or foreign
  conversations supply no keyterms; a reset uses the new conversation rather than cached hints.
  Its transcription deadline includes the decoded note duration plus the provider completion
  budget, since the streaming engine consumes the note at real-time speed.
- Nonempty, finite source PCM that is exactly zero is healthy no speech. Check the source before
  channel mixing and resampling so quiet or opposite-channel speech is not classified as silence.
  Empty, corrupt and nonfinite media retain distinct failures. A no-speech note returns one plain
  notice, cancels its preparation and invokes neither Main nor TTS. An authored caption survives
  a no-speech track. Nonzero brief, quiet and paused notes retain the complete audio.
- Local native recognition joins timestamped segments in order. Exclude a segment only when its
  valid in-bounds interval is entirely digital zero on the exact mono 16 kHz PCM consumed by the
  decoder. Unknown PCM or invalid timestamps retain native text. The shared join serves selected
  Listening and the attached-audio transcription tool. The model still receives the complete
  input; quiet/nonzero speech is never removed by this guard. False text over nonzero noise and
  inaccurate native timestamp attribution remain accuracy limits.
- Nonzero notes use the existing shared Silero speech-presence check before recognition. This
  check does not crop the note: an accepted note passes its complete original bytes and recognizer
  PCM to the selected provider. Prepare the shared detector at bot startup and reuse it. If it
  cannot start or run, return a distinct speech-detection-unavailable error; text messages remain
  usable. Code and the sealed dependencies containing Silero must be activated together.
- Content-free stage timings distinguish current route lookup, download, decode, local lock/model
  readiness and recognition. Provider markers report requested and effective model identities.
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
  - When a Telegram text-mode turn will also synthesize audio, the bot sends
    `telegramAudioRequested=true`. The LibreChat Telegram route still keeps `voiceMode=false`, but
    it injects the resolved Speaking route's `voiceProvider` so prompt layers can expose the
    selected provider's speech-control contract to the model.
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
  - every text-mode Telegram turn that requests audio composes the registered shared
    `surface.voice.feeling_expression`, `surface.telegram.audio_output`, and selected-provider
    prompt layers; Prompt Workbench must show the same source/include/eval lineage
  - when a Feelings capsule is present, the model privately appraises expressive versus restrained
    delivery from both the state's expression tendency and the moment. A strongly outward state in
    an emotionally meaningful or relational reply is expressive even when the draft already sounds
    natural; a containing state or neutral mechanical task can be restrained. After an expressive
    decision, xAI delivery is unfinished until it uses the smallest fitting exact documented xAI
    control, without waiting for the user to ask for emotion or markup; restrained delivery may
    correctly use none
  - the runtime must not map bands, values, or user phrases to speech tags. It only supplies the
    structural audio/provider capability and preserves the model-selected supported control
  - Telegram must not split xAI text into generic 800-character fallback chunks because that can
    break xAI wrapping tags and create invalid concatenated MP3 output
  - xAI wrapping controls use angle grammar such as `<soft>...</soft>`. If the model emits a
    complete paired square wrapper for a documented xAI wrapping control, such as
    `[soft]...[/soft]`, Telegram canonicalizes that same model-authored control to angle grammar
    before xAI synthesis. This is provider-grammar repair, not emotion inference. Unpaired,
    unknown, and crossed-provider controls are still stripped
  - user-visible Telegram text must strip both canonical and malformed xAI controls, including an
    orphan closing tag like `[/soft]`; repair for synthesis must never make markup visible
  - on Telegram text-mode turns that request audio (`voiceMode=false` and
    `telegramAudioRequested=true`), the raw streamed response remains available ephemerally to the
    Telegram bot for provider-aware synthesis, while the persisted assistant record and visible
    bubble remove delivery and provider voice controls. Structural marker counts provide local
    audit evidence without storing hidden control markup in chat history
  - Cartesia-only tags such as `<emotion>`, `<break>`, `<speed>`, `<volume>`, `<spell>`,
    `[laughter]`, and Cartesia-only bracket aliases like `[soft laugh]` or `[gentle sigh]` are
    stripped before xAI synthesis
  - OpenAI/ElevenLabs fallbacks still strip all provider markup before synthesis
- `/call` should open the browser into the modern voice surface using a browser-facing URL.
- `/call` requires the selected canonical agent to pass the same global Agents `USE` and resource
  `VIEW` checks as normal Agents chat before a call link is issued.
- The link carries a single-use `call_browser_launch_v1` bearer only in its fragment. The browser
  strips the fragment before a same-origin exchange, generates a 32-byte idempotency capability,
  and receives exact-session `call_browser_v1` authority. A lost response may retry with the same
  idempotency value; a different value or another browser replay is denied.
- Launch and browser capabilities are never accepted as query/body values, written to logs, placed
  in referrers, cached, or copied into public evidence. A raw call-session id is not browser call
  authority.
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
- Telegram startup readiness is bot-issued, not inferred from a Python PID:
  - the bot writes an atomic process-bound marker only after Telegram application initialization
    reaches the point where polling can start
  - the launcher and watchdog accept readiness only when the marker PID matches the live bot PID
  - optional command/description metadata refresh runs in a guarded background task; its timeout
    must not delay polling, suppress the marker, or kill an otherwise usable bridge
  - when Telegram itself is unreachable before initialization, no marker is valid and the
    watchdog must keep reporting/retrying the unavailable state without claiming success
- The same-token lock must live in a durable Viventium runtime lock directory, not a temporary
  directory that the OS may clean while the process is still running.
- The macOS status-bar helper must not report the stack as simply running when Telegram is enabled
  but the live Telegram sidecar has a missing PID or a recent polling/auth runtime issue. Core web
  health can remain usable, but the helper must surface that enabled sidecars need attention.
- Telegram command/message handling must tolerate transient Bot API `getMe` timeouts without
  crashing the user turn. Reply-context fallback is allowed only when the reply sender actually
  exists; a non-reply message should continue through the normal LibreChat bridge path.
- Reply provenance must be a bounded typed capsule, separate from user-authored text and native
  session identity. Under pressure, quoted attachment text is omitted first with explicit counts;
  ownership IDs and the current quote outrank time, Active Work, and older ancestry. Session and
  direct-fallback carriers must project the same admitted capsule and snapshot digest.
- Telegram error logs must identify failures with non-secret structural metadata such as update ID
  and message ID. They must not log raw Telegram update objects because those can include private
  message text, chat IDs, usernames, or attachments.
- Non-secret voice delivery timing logs must be available in normal runtime logs. Each voice-routed
  Telegram turn should log the gate decision, TTS start, TTS chunk duration/bytes, and Telegram audio
  send duration without logging bot tokens, API keys, raw private message text, or local paths.
- The same normal-runtime marker event must count the selected provider's dialect. For xAI it reports
  inline-tag count, wrapping-tag count, and total xAI count in addition to the legacy
  Cartesia/Chatterbox fields, so generation omission is distinguishable from display sanitization or
  TTS loss without enabling raw-text logging.
- Prompt-frame telemetry must account for `telegram_audio_output` under the canonical
  `surface_prompt` layer. A Telegram audio turn with that prompt present must report zero unknown
  prompt layers/characters; otherwise the voice instruction exists but remains an observability
  blind spot.
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
- A ledger-backed Cortex follow-up has one Telegram presenter, the durable Cortex dispatcher. The
  live insight stream and the post-stream poll leave it there, so the follow-up is always authorized
  before sending and acknowledged under the dispatcher's own lease, never under a turn-level ack.
- The dispatcher authorizes only against the turn's bound ingress row (`authorityBoundAt`), and
  general recovery leaves a Telegram gap to it only then. Every admitted turn binds that row: a fresh
  ingress before authoring, and a retained (prepared) input when its exact stream is admitted. A
  retained turn previously stayed unbound, so its late follow-up could never reach Telegram:
  recovery retried it as a stream presentation and dropped it as attempts exhausted. A continued
  admission of the same stream keeps its first binding; a row that is not this owner's source on
  that stream fails the turn closed.
- A late Cortex addition's Telegram acknowledgement is its own receipt beside the turn's Main
  receipt, in the Redis and in-memory job stores, and it names its presentation in every state,
  including a removal. It stays fenced by the exact turn, owner stream and revision, and by the
  presentation's owner, generation, claim and lease. A replay is idempotent, and a different receipt
  for the same presentation conflicts. Input newer than the turn's source withdraws the addition
  before its receipt commits, checked in the same transaction that would record it, as for Main's
  receipt. The Redis logical-turn store used to write the addition into the Main receipt's slot: an
  addition sent after a committed Main answer conflicted, so the adapter retracted it and the
  delivery was dropped as `delivery_outcome_unknown`.
- The acknowledgement route settles a Cortex receipt only for the message it presented: the
  addition's own message, delivery rows and Telegram reply mapping. It never writes, deletes or
  accepts the Main answer, never replaces the answer's reply mapping, and never takes Main's
  durable-effect path. A presentation of the parent itself (a promoted empty answer, for which the
  adapter records no Main receipt) is Main's first presentation, so its receipt also becomes Main's
  and keeps Main's persistence and acceptance.
- An idle chat (no message for `RESET_TIME`, default 3600 s) starts a new backend conversation on its
  next message. Stored conversations are unchanged, and Main continuity and saved memory are
  owner/agent-scoped, so this changes the visible thread, not what Main may know.
- The same-turn GlassHive poller and the durable dispatcher must share the same delivery ledger.
  Authenticated Telegram/voice callback polling may expose an opaque callback id to the bridge so
  the fast path can claim and mark the exact delivery row before sending. It must not legacy-send a
  callback that has a durable delivery row, because that creates one visible message from the poller
  and another from the dispatcher.
- GlassHive callback dedupe must also compare against the main streamed Telegram answer for the
  same stream, using the same Telegram-visible sanitation on both sides. If the final assistant text
  already delivered the same user-visible worker result, the callback is still a valid system event,
  but the bridge must claim and mark the delivery row as suppressed with an observability reason such
  as `already_streamed` instead of sending the same text again. If the delivery row is not visible
  yet, the bridge must wait for the row and avoid the legacy fallback for that same-text callback.
  This suppression is stream-scoped only: a different callback result, or the same words in a later
  unrelated turn, must still deliver normally.
- Generation failures keep their existing public error class through the live stream, durable
  terminal replay, and Telegram error event. The bridge uses the same typed presentation as FINAL
  and sends one non-spoken error notice. Legacy untyped callers retain their existing transport
  signature. Unknown internal diagnostics are not sent as user-facing error text.
- Provider authentication failures must surface as reconnect guidance on Telegram. They must not be
  collapsed into a generic connection error that implies Telegram or GlassHive transport is broken.
  Primary provider rate limits before visible assistant text must first pass through the main-agent
  fallback LLM contract from `06_Voice_Calls.md`. Telegram may receive a provider-rate-limit blocker
  only after no configured valid fallback is available, the fallback cannot start, or the fallback is
  exhausted. Bridge/provider errors must not be synthesized into Telegram voice notes. If a primary
  provider is rate-limited and the configured fallback provider then fails because its connected
  account needs reconnect, Telegram must preserve both facts and name the reconnect action instead
  of showing a stale rate-limit message or generic connection failure.
- For a GlassHive-backed main Agent, a native lifecycle `queued`, `waiting`, `started`, or provider
  `fallback` event is not visible assistant authorship and must not suppress recovery. A structured
  retryable quota, rate-limit, or terminal provider-response failure before visible authorship or
  an external effect uses the configured
  Agent Builder `fallback_llm_*` route exactly once. The Telegram stream and outer response stay the
  same, while GlassHive receives a distinct fallback-attempt idempotency key so it starts Claude
  instead of replaying the failed Codex request. After any authoring evidence, the provider must
  return the honest terminal blocker instead of starting a second author. Cancellation during lazy
  initialization or fallback execution must prevent or stop the fallback attempt.
- Authoring evidence is decided by delta *content*, never by delta arrival. A message or reasoning
  frame that carries no text is stream scaffolding, so it must not commit the authoring run. Both
  channels apply the same content predicate: a role-only message delta and a contentless reasoning
  frame each leave the configured fallback reachable, while the first delta carrying visible text or
  real reasoning content locks it. Gating on the reasoning event alone makes the fallback
  unreachable for every harness-routed turn, because the harness opens that channel before the
  provider has produced anything.
- Graph coordination is not an external effect. A server-owned Main-to-specialist handoff must carry
  structural effect metadata from graph ownership, independent of its generated tool name. If that
  specialist's model fails at the exact pre-authoring provider boundary without a usable status or
  code, its configured participant fallback retries first inside the same graph and turn. An
  explicitly server-declared read-only inspection is likewise replay-safe. An external mutation or
  unmarked tool remains effecting and locks provider replay fail-closed; email, calendar, durable
  work, and every other external action are never inferred safe from their names or arguments. The
  classification must be server-owned structural metadata propagated by the actual tool callback,
  never a model-supplied string, tool-name heuristic, or argument inspection. When fallback succeeds
  after the primary failed for missing provider authentication, the final turn must contain exactly
  one actionable reconnect notice and one recovered answer, with no duplicate error answer.
- Telegram SSE resume must tolerate the normal race where generation completes while the first
  stream connection is interrupted. The configured stream services should retain completed
  successful jobs for the store's short completion TTL and replay the cached final event to late
  subscribers. Truly expired or missing streams may still return a clear missing/expired-stream
  failure, but the normal completion path must not be reported as a generic connection problem.
- A GlassHive-backed Telegram turn may legitimately stay quiet while its harness uses files or
  tools. The compiled bridge defaults therefore keep the quick `/chat` request budget at 120 seconds
  but set `VIVENTIUM_TELEGRAM_SSE_READ_TIMEOUT_S=720` for the authored stream. This covers a
  ten-minute run plus transport margin without making a quiet interval look like provider failure.
- A timeout, network interruption, or SSE reconnect must reuse the same stream/idempotency key. It
  may reattach to the active native request, but it must never launch a second authoring run or send
  a late duplicate Telegram reply.
- Native conversation continuity must survive terse follow-ups such as an approval, correction, or
  pronoun that depends on the immediately preceding assistant turn. Turn-varying facts such as the
  current timestamp belong in the per-turn context delivery channel; they must not be inserted into
  durable developer/tool authority where they change the native-session snapshot and force a new
  worker on every turn. Likewise, a conversation-session provider's aggregate input usage describes
  its wider native prompt/session, not one LibreChat message. Visible-message pruning must therefore
  use locally counted message content for providers that structurally declare both
  `workspace_binding` and `conversation_session`, including when a generic adapter provider names the
  native provider through `endpoint`. Existing malformed counts must be recomputed before pruning so
  a tiny user message cannot evict the assistant question that gives it meaning.
- Transport-level bridge fallbacks must remain text-mode diagnostics, not synthetic voice replies.
  When Telegram always-voice output is enabled, the bot may voice assistant answers, but it must not
  synthesize local transport/plumbing failures such as an exhausted expired-stream retry.
- Proactive worker callbacks are one logical delivery. If Telegram voice output is enabled, text and
  audio behavior must be governed by an explicit surface policy and must never make the same worker
  completion look like two separate text completions.
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

A single image uses Telegram's photo method; albums contain two to ten images, with a single
remaining image sent as a photo. Other files use the existing document method. If Telegram rejects
a photo or album with `BadRequest`, send the original bytes and filenames as documents. Do not
resend after a timeout, network interruption, blocked bot or rate limit. A definite final rejection
is reported as not sent; an ambiguous send is reported as unconfirmed. Enforce the existing file
size bound on downloaded bytes as well as declared metadata.

When private host paths are redacted from a worker response, local Markdown citations keep their
readable label as plain text. Redaction must not leave broken link syntax or expose a private path.
A readable label is not a downloadable file; usable attachments still require the existing authorized
file delivery contract. Public source links remain intact.

Attachment delivery keeps each successful file and emits one concise notice for unavailable or
unconfirmed files. A missing or expired download response means that source is unavailable; it
does not prove why it disappeared. An interrupted Telegram send can leave delivery unconfirmed,
so the bridge must not claim the file was absent or resend it automatically. Failure notices must
not expose raw errors, private download addresses or credentials.

Inbound Telegram message attachments must follow the same shared message-file contract as the web
UI. If the active model/provider supports a file through LibreChat's native "Upload to Provider"
path, the bridge must preserve the normal raw message attachment so downstream client code can send
it provider-natively. Providers that declare both native tools and workspace binding receive admitted
files through the existing signed, owner-scoped workspace source bundle. The upload owner preserves
the exact bytes; the model decides how to inspect them. This includes regular audio/video attachments
and does not force a separate speech provider or replace the file with a transcript.
The model chooses whether to use the declared native host capability `transcribe_audio`. Its
catalog lists signed attachment IDs from the current input and the selected conversation branch.
Historical IDs come from the existing parent-chain traversal over owner-scoped Message rows, then
current owner-scoped File records; deleted, revoked, sibling-branch, and malformed references are
excluded. Current input source identities remain unchanged. The same selected IDs reach native
workspace delivery and tool grants, with current uploads retained before bounded history. Invocation
rechecks File ownership and reads original bytes through the existing storage strategy. Main and delegated workers
receive the same scoped capability. It calls the verified selected Telegram transcription runtime
and configured engine, preserving the original attachment and returning typed empty, unavailable,
auth, quota, timeout, and rejected-file outcomes. It does not download or choose another model,
create a transcript store, or decide from the user’s wording whether transcription is needed.
Transcription imports must not write Python bytecode into the sealed runtime component.
Repeated calls must pass the same code-integrity check; keep generated caches outside verified code.
Concurrent tool calls report capacity rather than loading more local models at once.

The shared web/bridge source message includes its authorized attachment snapshot before native
source capture. Later provider preparation must not add or replace that authored file list. Normal
attachment persistence must pass the source fence; real file replacement and text edits must still
reject admission through the existing digest and transaction checks.

If the file is parseable but not valid for provider-native upload on that
surface, the runtime must promote it into the context-extraction pipeline instead of storing it as
an opaque upload the agent cannot read. If neither provider-native upload nor readable
context-extraction can handle the file on that surface, Telegram must fail the turn with a clear
attachment-processing error rather than silently dropping to caption-only behavior.

Inbound Telegram file handling is surface-parity work, not a narrow extension allowlist. The bot
must accept photos, Telegram `Document` uploads, audio uploads, and regular video uploads into the
same attachment contract before the LibreChat turn starts. Voice notes and video notes remain STT
inputs; regular audio/video files are attachments unless the user explicitly sends them through the
voice-note affordance.

Trusted bridge images are already visual inputs. JPEG, PNG, and other supported image uploads must
not be rejected because a text document parser cannot extract text from them. The upload service
must persist the exact owner-scoped bytes and project them through the active provider or GlassHive
conversation bundle. A worker run receives real materialized files, not attachment placeholders.
When Telegram assigns the same filename to several album photos, durable file ID owns resolution;
filename fallback is allowed only when no durable file ID exists. Cross-owner and ambiguous matches
fail closed.

Telegram media groups/albums are one user turn. The bridge must coalesce updates with the same
`media_group_id` for the same chat/thread/user, preserve the Telegram order, choose the
caption-bearing item as the primary message when present, and forward all captured files in a single
LibreChat call. It must not dedupe files by content hash or filename, because repeated images/files
can be intentional user context. Authorization and API-key decorators must use lightweight identity
extraction only; they must not download, transcribe, or parse attachments before the real handler.

One logical attachment turn has one user-visible result. Main owns the normal answer. If a later
background-cortex result is only a Unicode/punctuation/whitespace reformating of the already visible
Main answer, it must be suppressed before Mongo persistence and Telegram delivery. This comparison
must not suppress genuinely additive content and must not be implemented as a Telegram-only filter.

Attachment capture and downstream processing failures must be visible. Telegram Bot API download
failures, size-limit failures, unsupported binaries, and document-parser/provider upload failures
must send one clear Telegram error and stop the turn before caption-only submission. The LibreChat
Telegram route returns a typed attachment-processing failure (`422` with
`attachmentProcessingError`) so the Python bridge can show the actual reason instead of a generic
server error. A declared permanent MIME rejection returns `415`, `unsupported_file_type`, and
`retryable:false`; a retained preparation records that failure and stops automatic retry. Unknown
storage/transport failures remain recoverable. Config must be rendered and the API must load it before
retrying an input rejected under an older MIME policy.

`.pptx` uploads are handled by the shared built-in `document_parser`, which extracts slide text and
speaker notes into message context for the active agent. The same parser also extracts embedded PPTX
image media and forwards those images as capped, resized vision inputs on surfaces that already
support image message parts, including Telegram and the generic Viventium gateway. This is a shared
LibreChat file-contract behavior, not a Telegram-only exception. It is not a full slide renderer:
slide layout, animations, charts stored as drawing XML, and non-image media may still require OCR,
worker analysis, or a provider/tool route that can inspect the original visual file. If a deck has no
extractable text, notes, or supported embedded image media, the failure class must be truthful.
Extraction fails closed before unbounded decompression when a presentation exceeds 5,000 archive
entries, 500 slides, 8 MiB for one XML entry, or 32 MiB of XML in total. Embedded vision extraction
also remains capped at 20 images and 12 MiB total. A limit failure is reported as an attachment
processing error; the caption must not continue alone.

### Major file-type rule

- Text-like files must extract into readable context:
  - examples: `.txt`, `.md`, `.json`, `.csv`, `.xml`, `.yaml`, code/config text
- Provider-native raw attachments must stay raw when the current runtime can truly serialize them:
  - examples: images, PDFs, Google/OpenRouter audio/video, Bedrock document types
- Trusted bridge images must preserve exact bytes and owner/file-ID identity when projected into a
  provider or GlassHive worker workspace; they do not require text extraction.
- Office/OpenDocument binaries that require OCR or a document parser must either:
  - use the configured OCR/document-parser path, or
  - fail honestly with a clear message when that extraction path is unavailable
- `.pptx` decks must extract slide text, speaker notes, and supported embedded image media through
  the shared built-in document parser before the agent run. Embedded images must be bounded before
  prompt/model injection so visual decks do not cause provider-payload failures.
- Unsupported binary/archive leftovers must not be accepted as inert message attachments.

### Fix pattern

- parse attachment events from the LibreChat stream
- download bytes through the gateway
- send images as albums when appropriate
- send non-image files as documents
- preserve provider-native message attachments and only auto-promote the non-provider-native
  parseable remainder into context extraction before the agent run
- materialize exact ordered image bytes into GlassHive conversation workspaces by owner-scoped file
  ID; never resolve a same-name album by newest filename
- preserve extracted document images as image message parts when the ingress surface supports the
  same vision contract as ordinary image uploads
- reject files that are neither provider-native nor readable through context extraction
- suppress a canonical duplicate cortex follow-up before persistence and delivery

## Evidence to Capture

- helper logs
- Telegram bot logs
- Mongo proof of the exact user and assistant turns
- attachment delivery proof when files are involved

## Logical-Turn Response Supersession

[`09_Agent_Streaming_Usage.md`](09_Agent_Streaming_Usage.md) owns the cross-surface logical-turn,
revision, adapter-capability, and delivery-acknowledgement contract. Telegram implements that shared
contract; it does not own a Telegram-only coordinator.

- A new Telegram conversation starts with provisional gateway identity, but any connected-tool or
  conversation-provider grant is signed only after LibreChat creates the durable conversation and
  response message ids. Provider refresh receives that finalized run body. A provisional `new`
  conversation or missing message id must never reach the capability broker as a valid turn scope.
- A broker-scope failure is a connected-tool authorization blocker, not evidence that the upstream
  provider rejected the owner. The visible answer must not blame WHOOP, another provider, or a web
  challenge unless an actual provider call produced that evidence.

- `LONG_TEXT` remains only a bounded pre-dispatch latency optimization. Rapid source messages stay
  distinct, ordered user segments after dispatch.
- Telegram uses `response_only` supersession. Telegram text, finalized voice-note transcripts, and
  file/clarification segments are stable on receipt. A newer source may revise only the unfinished
  assistant response/authoring for the same canonical conversation.
- Only stale assistant prose or previews are removed. Supersession never removes a user transcript,
  file source segment, accepted external effect, or accepted durable work item.
- Preview deletion failure records degraded delivery and prevents subsequent stale edits; it does
  not produce a false `Connection error. Please retry.` when the current revision succeeds.
- Pending voice transcription preserves receipt order through the existing bounded wait. Failure
  produces a truthful unavailable-transcription result while later text may continue.
- Accepted external effects and durable GlassHive/background work keep their original identity and
  continue once. A revised response may attach to or reference that accepted work, but must never
  dispatch a duplicate. Its result is delivered exactly once as current-turn context or a truthful
  completion follow-up, never as stale prose.
- The successful final send/edit is Telegram's presentation commit. Streaming previews are not.
- A pending saved-memory receipt keeps both the original source message ID and Core's current
  presentation sequence in its durable cursor. Receiver restart must preserve both, so an older
  retained input can deliver under its authorized current presentation without changing source
  identity. An uncertain Telegram send remains uncertain and is never replayed automatically.
  `test_memory_receipt_restart_retains_identity_and_worker_completion` checks this restart contract;
  the real Telegram delivery journey remains a separate acceptance gate.
- The saved-memory follow-up window starts at Main's committed presentation receipt. A confirmed
  pending or running writer retains its cursor until a terminal result, including after receiver
  restart. If Core explicitly reports no writer throughout that window and no writer was admitted,
  Telegram reports once that saving could not be confirmed and asks the user to check Memories
  before retrying. Transport errors are not evidence that no writer exists. Failed or removed Main
  presentations do not send a memory follow-up; an uncertain follow-up is never replayed.

## Parallel Work control surface

[`55_Parallel_Work_Orchestration.md`](55_Parallel_Work_Orchestration.md) owns the account-wide
Parallel Work contract. Telegram is a fast control surface, not a Telegram-only scheduler:

- the toggle updates the linked LibreChat account without a model call;
- admission, settings, and Active Work use the linked owner's operational readiness, with the same
  existing claim as Web and tool discovery. Public release certification remains separate. An outage
  preserves the saved preference and known work; it withholds new authority without cancelling work;
- Active Work consumes only opaque references and the server-returned action mask;
- Message, Steer, and Queue use short-lived user/chat-scoped prompt capabilities; Stop requires a
  confirmation; callback data never contains a raw work reference;
- every command, setting, Active Work callback, ordinary message, captioned attachment, and
  uncaptioned attachment handler uses nonblocking handoff;
- disabling new Parallel Work launches never hides or cancels work already in flight;
- provisional recoverable errors are held through the durable follow-up window and replaced by the
  recovered revision instead of committing a stale generic connection error.
