# Viventium v0.5 user surface

## Screen job

Let the user continue one conversation by typing, uploading, recording an audio note, or calling.

## Default hierarchy

1. Conversation.
2. Composer.
3. Feelings state.
4. Account bubble.

Nothing else persists.

## First run

```text
Install Viventium
        |
Choose one AI account
        |
Chat
```

- Install is one confirmation.
- Install changes directly into Connect. There is no progress bar, staged delay, or “all set” screen.
- Provider connection is one direct sign-in action.
- Successful connection opens chat immediately.
- Optional channels, view choices, imports, and advanced settings wait until later.
- A failed connection stays on the same step and shows one repair action.

## Main chat

```text
                         [account]
                     [Steady]

                  conversation

             [+]  Message...  [call] [mic/send]
```

- The main column is centered and capped for reading.
- Before the first message, a centered `Top of mind` stack turns through five recent priorities, thoughts, decisions, and updates. Selecting the note advances it; hover or focus pauses it; reduced motion keeps one static note.
- User messages use a quiet filled bubble. Viventium answers are cardless.
- Upload opens a small local menu and then shows the selected file in the composer.
- An empty composer shows audio note. Typed content replaces it with Send.
- Call keeps chat visible and adds a compact live-call dock above the same composer.
- The dock is one slender row: live state and time, Call, Wing, Listen-Only, microphone, and End.
- Camera and screen sharing are absent. Chat is the live caption and transcript surface.
- The call button visibly stretches into the island and contracts back into the button.
- Voice provider choices stay in Advanced settings and never add a call-start step.

## Account bubble

The first click shows only:

- account email;
- Connect;
- Update;
- View;
- Log out.

Connect opens a centered sheet with exactly two tabs:

1. AI providers.
2. Channels.

View contains Appearance and Advanced. Advanced reveals New chat, Search, Workers, Cortex Editor, and recent conversations. It does not change the Connect inventory.

Workers shows parallel work beside the chat. Cortex Editor is the single user surface for shaping or creating a cortex. Prompt Workbench, sandbox, model, and tool internals do not become separate navigation.

## Status bar V

```text
Chat
Call
Advanced
-----
Quit
```

The app has no Start or Stop command. Opening the app means it is running.

## Feelings

- One compact plain-language label and one living soul are always visible. The label becomes Thinking, Listening, Feelings paused, or Feelings off when system state must be explicit.
- Click opens the full Feelings dashboard with the same soul enlarged beside the inner-state line.
- The top switch is exactly `Spectrum | Prompts`.
- Spectrum contains exactly `Now | Baseline | Trail`.
- Now and Baseline preserve all nine fixed bands, both comparison markers, recent movement, semantic poles, direct editing, inclusion, and active return half-life.
- Baseline includes Grounded, Candid, Warm, and Curious profiles and identifies manual edits as Custom.
- Trail records and persists time, band, before-to-after movement, strength, and cause for typed changes. It does not store message text.
- Prompts shows the live nine-band Feeling capsule, Reaction instruction, `Always | When relevant | Off`, `All speaking work | Main only`, all five stable prompt ranges, and optional private additions.
- Inner-state wording and reaction health remain separate. Health moves through Ready, Pending, Applied, Paused, and Off without claiming a live service is healthy. Pause keeps state and freezes both return movement and top motion.
- Privacy and controls expose Reset Now, Pause or Resume, Erase Feelings, and global power.

## Connection inventory

The Channels list groups familiar destinations by use. Less common endpoints stay in a collapsed Other group; Advanced does not change this list.

- Personal: Telegram, WhatsApp, WhatsApp Cloud, Signal, iMessage, SMS, Email, LINE, SimpleX.
- Work: Slack, Discord, Microsoft Teams, Google Chat, Mattermost, Matrix.
- Regional: WeChat, WeCom, DingTalk, Feishu, QQ, Yuanbao.
- Home and alerts: Home Assistant, ntfy.
- Other: IRC, Webhook, API, Agent to Agent, Raft, Buzz, Photon.

The AI list leads with subscription sign-in. API and infrastructure providers remain available lower in the same tab without entering the chat surface.

## Required states

- Install: ready, immediate Connect.
- Provider: available, connected, failed, retry; optional `connectSlow=1` exists only to review the loading state.
- Chat: empty, composing, sending, replying, complete.
- Upload: menu, selected, removed, unsupported.
- Audio note: recording, paused, cancel, send.
- Call: morphing, connecting, listening, Call, Wing, Listen-Only, muted, ended.
- Update: available, updating, current.
- Advanced: off, on, persistence after reload.
- Workers: active and complete parallel work.
- Cortex Editor: choose and create with name and purpose.
- Feelings: Spectrum, Prompts, Now, Baseline, Trail, edit, return, profile, half-life, inclusion, reaction, scope, privacy, pause, off, and persistence after reload.

## Responsive rules

- Under 860 px, the app uses one full-width column with compact gutters.
- Sheets become full-height surfaces.
- The composer keeps all primary actions at least 44 px.
- The Advanced sidebar becomes an overlay and closes after navigation.
- Menus remain inside the viewport and scroll when necessary.
