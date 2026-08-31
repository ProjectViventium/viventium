# Viventium v0.5 concept

<!-- uizze:product-schema 1 -->

## Platform

web

## Stack

Static HTML, CSS, and JavaScript for concept review only. This is not a product implementation decision.

## Users

One person using Viventium as a daily personal AI through text, audio notes, and live calls.

## Product Purpose

Viventium gives the user one continuous conversation with their AI. Setup, connection, calls, channels, account care, and deeper capability support that conversation without becoming the product.

## Positioning

One app. One connection. Always on. Keep the product capability; hide its machinery.

## Operating Context

- First launch: install, connect one AI account, then enter chat. There is no simulated install wait or completion screen.
- Daily use: open chat, type, upload, record an audio note, or call.
- Occasional care: update the app, connect an account or channel, or change the view.
- Power use: enable Advanced to reveal new chat, search, conversation history, parallel Workers, and Cortex Editor.
- Ambient access: use the V in the macOS status bar to open Chat, Call, Advanced, or Quit.

## Capabilities and Constraints

- The default product surface is one centered chat.
- Persistent controls are limited to upload, call, audio note or send, the living Feelings state, and the account bubble.
- An empty conversation shows a quiet `Top of mind` note stack: the latest priorities, thoughts, decisions, and updates from the ongoing relationship. It turns automatically, pauses for reading, and never becomes a dashboard.
- A live call keeps the same conversation visible. It does not replace chat with a transcript page.
- Calls preserve Viventium's user modes: Call, Wing, and Listen-Only. One slender row keeps only mode, time, microphone, and End. The chat itself is the caption and transcript surface.
- Listening and speaking providers stay out of the call-start surface. Saved configuration remains authoritative.
- The account surface keeps the account email and Log out, and adds Update, View, and Connect.
- Connect has exactly two top-level tabs: AI providers and communication channels.
- Advanced is off by default. When enabled, it reveals only the reduced conversation sidebar, parallel Workers, Cortex Editor, and recent chat history. Prompt Workbench remains internal.
- Prompt templates, skills, bookmarks, attachment libraries, MCP terminology, provider internals, and runtime controls are not part of the default user surface.
- Viventium starts with the app and remains on until Quit. Start and Stop controls are excluded.
- The concept must include loading, success, failure, recovery, recording, call, and responsive states.
- Existing product capability is not deleted because its technical surface is hidden. Chat invokes work naturally; internal LibreChat, GlassHive, Prompt Workbench, worker, sandbox, memory, and routing machinery remains implementation, not navigation.
- The concept does not reuse LibreChat UI, LiveKit code, or previous v0.5 mockups.
- The proposed shell and current runtime release truth remain distinct. LibreChat may stay hidden behind continuous chat and Cortex Editor, GlassHive stays the worker plane, and Prompt Workbench stays mandatory internally.
- V0.5 remains one signed Apple silicon app. It does not port the product to OpenClaw or Hermes.

## Feelings Contract

- The top state combines a plain-language label with one restrained living soul. One continuous membrane reflects all nine feeling bands and moves through Resting, Attending, Thinking, Reacting, Settling, Paused, and Off. It never becomes a waveform, spinner, rainbow, mascot, or online-status dot.
- The dashboard starts with a first-person inner-state line and separate truthful reaction health.
- `Spectrum | Prompts` is the top switch. Spectrum contains `Now | Baseline | Trail`.
- Spectrum preserves all nine bands: Energy, Mood, Drive, Curiosity, Vigilance, Care, Connection, Openness, and Play.
- Every band shows Now, Baseline, recent movement, the two semantic poles, the active felt prompt, inclusion, and return half-life. Now actually decays toward Baseline from the stored update time and freezes while paused or off.
- Baseline includes Grounded, Candid, Warm, and Curious profiles plus a truthful Custom state.
- Trail records and persists typed time, band, before-to-after movement, strength, and cause without storing raw messages.
- Prompts exposes the exact active nine-band Feeling capsule, the Reaction instruction, activation, speaking scope, and five stable range prompts with optional private additions.
- Health is explicit and truthful: Ready for the local preview, Pending after a manual state edit, Applied after a simulated reaction, Paused, or Off.
- Privacy and controls include reset, pause or resume, erase, and global power.

## Brand Commitments

- Product name: Viventium.
- Mark: the existing shipped Viventium V asset, unchanged.
- Voice: brief, natural, direct, and nontechnical.
- Binding references: centered composition and the current LiveKit voice interface's calm, voice-first clarity.

## Evidence on Hand

- The current owner brief is the authority for this concept.
- Existing v0.4 product requirements define install, calls, connected accounts, Feelings, updates, and continuity behavior.
- The current official LiveKit Agent Starter shows a voice-first, multimodal control surface with a quiet monochrome canvas and a compact control dock.
- Previous v0.5 mockups and reports exist elsewhere in the repository but were not opened or reused.

## Product Principles

1. **Absolute Minimalism.** If something is not absolutely necessary, remove it, especially a user step or persistent control.
2. **One conversation.** Text, files, audio notes, calls, and visible work results stay in one continuous chat.
3. **Direct progress.** Every setup action either advances the user or explains one specific repair.
4. **Power on request.** Advanced capability stays available without teaching technical product structure to everyone.
5. **No capability loss.** Hide implementation detail; do not remove useful capability.
6. **Calm truth.** Show current state and failure clearly, without noise, false health, or hidden fallback.

## Accessibility & Inclusion

The concept must support keyboard use, visible focus, screen-reader labels, readable contrast, reduced motion, reduced transparency, and text as an alternative to voice.
