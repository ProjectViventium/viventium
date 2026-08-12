# Viventium V0.5 Product Experience

## Product structure

### Design milestone under review

The architecture, brand language, and four-destination product model remain proposed until the
product owner explicitly approves them. The review artifacts carry the language across MIND,
CONNECT, CHARACTER, AUTOMATIONS, and the persistent presence layer. They are design artifacts, not
a claim that the V0.5 runtime exists.

The desktop app has four destinations and no generic prompt-library clutter:

| Destination | Primary question | Default content |
|---|---|---|
| **MIND** | What is Viventium saying and feeling with me now? | One continuous conversation, current Emotional State, Emotion Trail, and relevant reaction |
| **CONNECT** | What can Viventium use, and is it on? | Recognizable sources, confirmed account, enable/disable, and Connect or Change |
| **CHARACTER** | Who is Viventium with me? | Personality, Nature baseline, emotional range, speaking provider/voice; advanced STT and provider controls |
| **AUTOMATIONS** | What works while I am away? | Readable cycles and instructions, night work, approvals, history, interruption and results |

The Feelings Spectrum is one reusable module. CHARACTER uses it to edit Nature and permitted range;
MIND uses it to show the live Current state and reaction trace. The canonical nine-band order is
Energy, Mood, Drive, Curiosity, Vigilance, Care, Connection, Openness, and Play.

The ordinary product hierarchy is deliberately narrower than the architecture. MIND is conversation
plus live Feelings. CONNECT is a list of things that are on, off, connected, or need attention.
CHARACTER is the complete relationship instrument. AUTOMATIONS is a readable work list. Internal
plumbing appears only when it blocks one of those tasks.

## Persistent presence layer

Presence belongs to the app shell, not to a fifth destination:

- **Drop in / drop out** joins or leaves the live voice relationship without navigating away.
- **Stay listening** keeps the session present and responds when directly engaged.
- **Only when useful** is the human-facing Wing Mode: ambient speech defaults to silence unless
  Viventium has a clear, additive reason to contribute.
- **Mute** is always one action away and visibly overrides every listening mode.
- The current microphone, listening, speaking, muted, reconnecting, or unavailable state follows the
  person across MIND, CONNECT, CHARACTER, and AUTOMATIONS.
- **Use from anywhere** is available to every user as an ordinary on/off and add-device experience.
  The default UI never mentions domains, DNS, certificates, ports, tunnels, or transport providers.

## Onboarding

Only three steps are shown:

1. **CONNECT:** connect at least one frontier account for main thinking, connect Groq for activation
   detection, and add any life sources or channels the person wants.
2. **CHARACTER:** choose a starting character and voice; excellent defaults allow immediate use.
3. **READY:** open MIND or continue in a connected messaging or voice surface.

Permissions are requested in context, at the moment their value is clear. Nonessential connections
are always skippable.

## CONNECT interaction contract

CONNECT is a calm source list, not a marketplace grid or an integration console.

- **Find everything** is the primary setup action. GlassHive inspects the browsers, applications,
  and visible accounts the person explicitly allows, reports progress, and can be stopped.
- Discovery never connects by itself. Findings open in a review list where the person can select
  accounts and then choose **Connect selected**.
- Categories organize the list; On and “Needs you” filter it.
- Every service supports several accounts. The service row expands to separate named account rows;
  each has its own enable/disable control and Change action, followed by **Add another**.
- Every row shows the recognizable source, confirmed account identities when connected, and one
  Connect or Change action. Freshness appears only when it needs attention.
- Most connections use one focused sheet: choose a signed-in browser or installed app → confirm the
  visible account/username → Connect.
- Email uses a deliberately flat all-in-one form: email address, one connection-method choice,
  detected signed-in browsers or installed mail apps, confirmed account, and Connect. It has no
  wizard and no routine scope/destination lecture.
- Connection methods use human names and recognizable provider/application logos. Terms such as
  MCP, OAuth, API, browser automation, or IMAP may appear only in advanced explanation.
- The preferred route uses native host integrations or mature adapters. Signed-in browser,
  export/folder, and minimal official API routes are fallbacks.
- “Inboxes” may remain a connection category because people connect email inbox accounts, but the
  data lands canonically in `Life/Communications/Email/`.
- GlassHive appears plainly under **Workers** because it performs discovery, sync, browser/computer
  work, and delegated missions. It is not disguised as a connection protocol or opaque automation.
- Success replaces the action with the confirmed account and an enabled switch. Professional
  receipts and deletion details remain available one level deeper.

## MIND layout

MIND is the emotionally compelling home and has only two dominant jobs:

- one continuous conversation occupies the primary reading column; its messages may quietly name
  their origin, but the person never switches between “Here” and Telegram versions of Viventium;
- a living emotional-state rail shows the nine Current values, Inner state, and a compact temporal
  **Emotion Trail** with time, change, and cause in the same visual language as the real Feelings
  instrument;
- cortex and worker activity appears as a quiet inline event in the conversation only when it is
  currently relevant, with one action to inspect or stop it;
- a consequential reply may carry one collapsed **Behind this reply** line that summarizes the
  Memory brought in and any active specialist. Opening it reveals one chronological receipt:
  **Context & Memory → Cortices → What changed**. It distinguishes Life sources,
  saved Memory, past conversation, transcripts, and ambient evidence instead of flattening them
  into one generic “memory” bucket;
- durable writes say **Saved to your Life** and offer correction. Inferred changes say **Suggested
  for your review** and do not become Memory until accepted. The interface never exposes hidden
  reasoning or invents Cortex-to-Cortex dialogue;
- lifecycle plumbing, source summaries, and architecture diagrams do not compete with the
  relationship.

The persistent presence control remains visible in MIND but does not compete with the conversation.
It should feel like Viventium is continuously available and softly humming, not like the person must
start a fresh call application every time.

## CHARACTER layout

- identity and speaking voice lead in one compact, previewable relationship row; the voice menu can
  select, create, or import a voice while STT and
  provider-specific controls remain under Advanced;
- the real nine-band instrument is preserved from the canonical `FeelingBandDefinition`: all nine
  Feelings are simultaneously visible on one fixed 0–100 vertical scale, with Current fill/cap,
  Nature marker, and straight recorded path inside each band; the focused inspector keeps expanded
  Current/Nature controls, exact poles and felt words; Inner state;
  Grounded/Candid/Warm/Curious Nature
  profiles; return speed; whether the emotion is Felt; five additive felt ranges; reaction
  instruction; reset, pause, and erase;
- every Feeling includes a real temporal trail so the person can see how it travelled, when it
  changed, by how much, and why; elapsed time runs from Older to Now, points are not smoothed into
  invented continuous readings, unchanged Feelings do not get invented movement, and CHARACTER
  also keeps a readable **What changed and why** list;
- first run begins off and clearly labels illustrative information as Sample. A manual state edit
  clears any stale reaction copy until the next real reaction arrives;
- all advanced emotion controls expand inline. The fundamental Current/Natural interaction never moves into
  a modal or a generic settings form;
- the raw speaking capsule is an Advanced inspection surface, not ordinary reading burden. It is
  empty when Feelings are paused or no band is Felt. Confirmed erase removes the Feeling state,
  trail, Nature changes, personal range wording, and personal Reaction Cortex configuration;
- clear separation between durable Nature, live Current, and what a selected voice can express.

## AUTOMATIONS layout

- one readable timeline/list of schedules, night workers, source sync, Morning Briefs, and delegated
  missions rather than dashboard cards;
- each row shows its cycle, next run, and enable/disable control; selecting it expands the cycle,
  instruction, context, delivery, last useful outcome, and history inline;
- the expanded instruction uses the same Prompt Workbench `{{` variables, autocomplete,
  validation, version history, and save path. AUTOMATIONS and Workbench are two views of one
  canonical scheduled-prompt object, never duplicated prompt stores;
- active GlassHive work shows mission goal, shared-context receipt, questions, evidence, status, and
  parent evaluation without exposing agent plumbing;
- interruption, approval, retry, and recovery stay visible whenever relevant.

## Prompt Workbench backlog

Keep the full Workbench for professional QA, but add an **Easy View** that answers four questions:

1. Where is this prompt used?
2. What input/context did it receive?
3. What result did it produce?
4. What changed between versions and did quality improve?

The Easy View is a source map, latest result, history, and readable diff. Editing still opens the
same canonical prompt and variables; it is not a second prompt store or a separate editor product.
