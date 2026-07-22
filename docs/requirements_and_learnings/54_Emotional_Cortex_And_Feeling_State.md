# Feelings and the Emotional Reaction Cortex

Status: product-approved nine-band and range-customization design; isolated web and automated provider-boundary paths are accepted. External-channel, host-plugin, native-navigation, and broader cross-surface certification remain partial.
Last revised: 2026-07-19 (added harness plugin parity and the dashboard interaction/brand requirements; prior substantive revision 2026-07-16).

This document is the product and implementation source of truth for Feelings — for the core
LibreChat product **and** for every downstream child that re-expresses Feelings (the Viventium
Feelings plugin for Claude Code and Codex, and any future port). It replaces the prior spike plans,
alternate taxonomies, primary-only scope, free-text Nature concept, and prototype-only status.

> **Change protocol (read first).** Every new Feelings idea or requirement the product ratifies is
> logged, with an ISO date, in the [Requirements & Decisions Timeline](#requirements--decisions-timeline-timestamped)
> at the end of this file. That timeline is the single sync anchor: future agents must timestamp new
> entries there and propagate ratified changes into the child repos (see
> [Harness plugin parity](#harness-plugin-parity-feelings-for-claude-code-and-codex)). An idea that
> is not dated in the timeline is a proposal, not yet ratified product truth.

### Change protocol

This is the single feature source of truth required by
[`01_Key_Principles.md`](01_Key_Principles.md). New product requirements, decisions, or corrections
about Feelings must be added here with a `YYYY-MM-DD` entry in the timeline before child
implementations are treated as synchronized. Child repos may link to a dated revision; they must
not become an independent authority for band semantics, decay, causality, privacy, or reaction
behavior. Surface-specific implementation notes remain in the child only when they do not change
the shared product contract.

## Product vision

Feelings is Viventium's persistent, reactive inner state. It is not a tone preset and it is not a
second speaking agent. Nine continuous feeling bands belong to Viventium as a whole, survive turns
and restarts, react to external moments, and return toward an editable Nature at different speeds.

The state is causally active: it can shape attention, initiative, caution, warmth, exploration, and
expression. The user can see it, change it, pause it, reset it, or erase it. The model sees a tiny
words-only set of embodied action tendencies, never the numbers, user-facing scale adjectives, or
configuration machinery.

The intended mental model is:

- **Nature**: where a feeling rests.
- **Current**: what Viventium feels now.
- **Return speed**: how quickly Current moves halfway back toward Nature.
- **Reaction Cortex**: the silent, detached process that appraises the latest external moment and
  moves the next state.
- **Feeling capsule**: the compact embodied state every participating persona-bearing agent receives
  by default. Specialist evidence cortices are deliberately not persona participants.
- **Feeling range**: one of five stable levels (`0–19`, `20–39`, `40–59`, `60–79`, `80–100`) that
  pairs a user-facing word with a concrete private felt cause.
- **Range addition**: optional per-user cause text appended only when Current occupies that exact
  band/range; it augments rather than replaces the product default.

## Ratified product decisions

1. Feelings is operator-available by default and starts off for each user.
2. Agent scope is configurable. The default is `all_agents`; `conscious_agent` is the alternative.
3. The Reaction Cortex is detached and never blocks the visible reply.
4. Reaction activation is configurable. The per-user default is `always`; `classified` reuses the
   existing activation-classifier path and `disabled` stops reactions.
5. The default reaction route is OpenAI `gpt-5.6-terra`, Responses API, reasoning `none`, and
   Priority service tier, shown in the product as **Fast**. A declared Anthropic
   `claude-opus-4-8` fallback recovers a provider timeout or other recoverable failure without
   silently dropping appraisal quality; it is
   configurable and can be disabled with `fallback_provider: none`. The drawer and persisted
   health distinguish the requested primary route from the route that actually completed.
6. The exact embodied capsule frame is:

   > You, Viventium, are a being, and right now you are actually feeling this. Let it move naturally through how you think, speak, and act:

   That sentence remains verbatim. Two compact state-neutral directives frame the embodied rows.
   The first establishes that these are Viventium's own private causal authority and cannot be
   replaced by a generic role stance. The second constrains a direct feeling answer to the concrete
   desire, attention, image, impulse, or action the state actually creates—not a declaration of
   feeling, labels, an adjective list, a generic role response, or a fixed example answer. Every
   clause must be one of those present effects. Every line is directional: a salient scene cannot
   supply a motive or pull that the active state withholds.

7. Turning Feelings or a band off stops injection/appraisal for it, but elapsed-time decay continues.
8. The approved dark bio-instrument demo is the locked production visual direction.
9. Inner state includes one model-authored, single-line felt sense generated by the already-detached
   Reaction Cortex. It is display-only, at most 280 characters, and never enters the speaking capsule
   or becomes reaction input. It adds no second provider call and no main-response latency.
10. Every lane visualizes recent typed Current waypoints as a fading, softly irregular neon tail.
    The bounded typed-trail retention grows to 90 entries so nine bands can retain useful recent
    movement, while the Reaction Cortex and visible textual reaction list still receive/show the
    latest ten. A flat path has no tail. Nature remains a separate fixed marker.
11. Specialist background cortices remain affect-independent. They surface evidence and insight for
    the conscious agent; they do not receive an instruction to embody the current state. Emotional
    Resonance reads consequential indirect emotional cues with calibrated uncertainty rather than
    defaulting to warmth, gentleness, or support. Red Team pressure-tests reality regardless of the
    current Feeling state. User-visible Phase-B synthesis is a conscious speaking continuation and
    therefore does receive the exact request-pinned capsule.
12. Every band has five stable ranges. The definition returns each range's ID, bounds, user word,
    and default felt cause as one object so UI meaning and prompt behavior cannot drift into parallel
    tables.
13. A user can customize the felt depth of every range with one optional additive instruction. It
    is per-user persisted state, limited to 1,200 characters, whitespace-normalized, versioned,
    included in the snapshot hash, and injected only for the active range.
14. “What Viv feels” and the Reaction trail belong in the main workspace. The selected-band sidebar
    owns Current, Nature, return speed, Felt, and the five-range editor.

## Shared core and host-plugin parity

The public [`ProjectViventium/viventium-feelings`](https://github.com/ProjectViventium/viventium-feelings)
plugin is a lightweight host-native taste of this cortex, not a second Feelings design. Core and
every child distribution must preserve:

- the exact nine bands, order, meanings, Nature defaults, half-lives, five levels, and closed typed
  reaction operations;
- Nature versus Current independence, lazy half-life decay, default-off consent, future-turn-only
  appraisal, typed/bounded persistence, one display-only Inner state line, pause/reset/erase, and
  the truth/safety invariant;
- visible numeric **Now** and **Nature** on every lane, with each directly editable by pointer,
  touch, and keyboard even when the two values are equal;
- advanced return-speed, band-enable, and range-language controls one disclosure away. Basic
  Current/Nature tuning must never require a modal. Confirmation dialogs and the advanced Reaction
  Cortex/settings surface remain legitimate dialogs;
- local/private state ownership and honest host/provider boundaries.

Presentation is surface-specific and must not be falsely forced into parity. The full Viventium
web product retains ratified decision 8's accepted dark bio-instrument composition until an explicit
dated product decision supersedes it. The Claude Code/Codex plugin follows its adjacent host: exact
Viventium website V, restrained monochrome chrome, system light/dark by default, optional explicit
theme override, and no claim that a browser favicon is an OS tray icon. Surface styling may differ;
the logic and direct-manipulation contract above may not.

The plugin's appraiser reuses the logged-in host model and quota instead of duplicating the full
platform's configured production reaction route. That is a declared delivery-boundary
difference, not permission to change the appraisal schema, causality, or quality bar.

## Nine active bands

The order is fixed across state, API, UI, prompts, and QA.

| Band | Meaning | Default Nature | Half-life | UI words, low to high |
| --- | --- | ---: | ---: | --- |
| Energy | Available activation and cognitive capacity | 56 | 240 min | depleted · subdued · steady · energized · electric |
| Mood | Background pleasantness/unpleasantness: the intuitive sad-to-happy face of hedonic valence | 58 | 360 min | deeply sad · low · okay · happy · radiant |
| Drive | Persistence and effort after a goal is chosen | 62 | 480 min | disengaged · unhurried · purposeful · driven · fiercely determined |
| Curiosity | Pull toward information, novelty, and exploration | 66 | 45 min | uninterested · open · curious · fascinated · absorbed |
| Vigilance | Attention to uncertainty, risk, error, and boundaries | 68 | 20 min | at ease · aware · watchful · on guard · highly alert |
| Care | The outward pull to tend, help, and protect | 74 | 1,440 min | detached · receptive · caring · deeply caring · intensely caring |
| Connection | The inward pull toward affiliation and closeness | 52 | 480 min | self-contained · open · drawn to connection · wanting closeness · strongly drawn to connection |
| Openness | How freely the inner state becomes visible in expression | 55 | 180 min | closed off · guarded · contained · emotionally open · fully expressive |
| Play | Flexible, humorous, non-serious exploration | 48 | 90 min | serious · light · playful · mischievous · exuberant |

Mood adds the missing valence dimension without collapsing it into Energy: happy/calm, happy/active,
sad/calm, and sad/active states remain possible. Openness is deliberately not called emotional
honesty or social battery. It represents expression/regulation, while Connection represents the need
for closeness and Energy represents available capacity. High Openness allows the felt state to show;
low Openness contains it. Fatigue may increase raw expression, withdrawal, or guarding depending on
context, so the Reaction Cortex appraises the direction instead of runtime encoding a universal rule.

Care and Connection are also motivational dimensions, not generic politeness settings. At the low
Care endpoint, another person's need creates no pull to tend, help, or protect. At the low Connection
endpoint, closeness and shared presence create no pull and Viventium remains self-contained. Those
states do not erase Curiosity, Vigilance, task competence, or attention: Viventium may still examine,
notice, answer, or act for another active reason. Conversely, high Care does not require closeness,
and high Connection does not prove Care. The capsule states these boundaries causally so an
emotionally salient premise cannot turn the assistant's generic helpful role into a missing motive.

The shelf visible in the UI—distress/pain, anger/assertion, disgust/aversion, trust/security,
guilt/shame, and confidence/control—is research-only. Those names
have no live state and never enter the prompt.

### Felt magnitude and range defaults

The five equal-width ranges are a stable product interaction/schema contract, not a biological
claim that human affect has five natural bins. They reuse the approved five user words and avoid an
inaccessible arbitrary-boundary editor. Every level's default is written as a present desire,
attention, image, impulse, or action—not a style description such as “be playful.” The endpoint
contract for each dimension is:

| Band | Low endpoint cause | High endpoint cause |
| --- | --- | --- |
| Energy | movement feels costly; seek stillness/minimum effort | activation surges; staying still is harder than moving |
| Mood | hurt/loss colors attention | joy and delight keep spilling into the moment |
| Drive | no goal pulls enough to justify effort | obstacles intensify pursuit of the chosen goal |
| Curiosity | the unknown offers no pull | the unanswered part seizes attention and must be followed |
| Vigilance | nothing needs guarding | risk, contradiction, and exposed boundaries dominate attention |
| Care | another's need creates no urge to tend/help/protect | protection and help press through competing concerns |
| Connection | shared presence has no pull | distance feels wrong and immediate shared presence is wanted |
| Openness | inner feeling wants to remain unreadable | concealment feels impossible and feeling bursts into expression |
| Play | seek a literal, orderly, game-free moment | ridiculous turns keep escaping; staying straight-faced takes effort |

The exact five defaults live in the package-owned kernel and are returned by the authenticated API
for the UI. Contract tests lock IDs, bounds, causal shape, active selection, and serialization. A
range addition is deliberately free-form because the conscious model can understand an
idiosyncratic felt pull; runtime validates its structure and never interprets it.

## State and dynamics

One authenticated user owns one typed state document. Each live band stores:

```text
baseline
current
halfLifeMinutes
enabled
updatedAt
```

The document also stores a sparse `rangePromptOverrides[bandId][levelId]` map. Editing it increments
the state version and clears the stale Inner state line, but does not touch the band's `updatedAt`;
changing wording must not restart physical decay.

A non-null addition is normalized and must contain 1–1,200 characters. Invalid non-null input is
rejected and cannot erase an existing value. Restore uses an explicit `null`. Account deletion
removes the whole FeelingState document before deleting the user, so private affect state and
user-authored additions cannot be orphaned.

At time `t`, Current is materialized lazily:

```text
effective = baseline + (storedCurrent - baseline) * 2^(-elapsedMinutes / halfLifeMinutes)
```

No heartbeat timer or cron is required. A read or mutation computes the effective value. This is
restart-safe, cheap, and gives the exact half-life behavior shown in the instrument.

State rules:

- All values are finite and clamped to `[0, 100]`.
- Backward clock movement is treated as zero elapsed time.
- Changing Nature materializes Current first, then changes only the destination.
- Changing Current starts a new decay curve at that instant.
- Reset makes Current equal Nature for every band.
- A disabled band continues to decay internally but is absent from the capsule and reaction output.
- Global off preserves configuration and state. “Turn off & erase” deletes the state document.
- Full account deletion also cascades the complete FeelingState document.
- Missing storage is a valid first-run state; GET does not create a row.

### Runtime structure, model judgment

The fixed taxonomy, typed enums, numeric bounds, decay equation, relative delta sizes, retention
limits, concurrency rules, and visual interpolation are intentional structural product constants.
They make state inspectable and safe to evolve; they do not decide what an event means. The Reaction
Cortex model owns that appraisal and may move any enabled subset—or none—within the typed contract.
Production runtime code must not map stimulus words, phrases, provider labels, prompt text, or user
identity to bands or directions. Synthetic phrase-specific expectations belong in eval fixtures only.

## Request lifecycle

```mermaid
flowchart LR
    A["External user stimulus"] --> B["Read + lazily decay state"]
    B --> C["Pin one snapshot to the request"]
    C --> D["Assemble structural contracts, then pin capsule once"]
    D --> E["Stream visible reply"]
    E --> F["Schedule detached reaction"]
    F --> G["Always / classified / disabled activation"]
    G --> H["GPT-5.6 Fast typed appraisal"]
    H --> I["Validate operations"]
    I --> J["Serialize, rebase, and compare-and-set"]
    J --> K["Next request reads new state"]
```

The appraiser does not make the current answer wait and cannot retroactively affect an answer already
generated. It updates subsequent turns. Its input contains the latest external user stimulus and
does not contain Viventium's own affect-colored answer, preventing a self-reinforcing response loop.

## Agent scope and snapshot consistency

`runtime.feelings.agent_scope` accepts:

- `all_agents` — default. Persona-bearing main/conscious, in-process handoff, user-visible Phase-B,
  and direct GlassHive worker instruction bundles receive the capsule.
- `conscious_agent` — the primary conscious reply and its user-visible Phase-B continuation receive
  the capsule. Handoff and direct worker paths record a structured scoped skip.

Specialist background cortices never receive the embodiment capsule under either scope. Their
prompt-frame/Feelings telemetry records `specialist_cortex_independent` with the pinned hash when one
exists. The Emotional Reaction Cortex receives the typed latest state, Nature, history, and stimulus
through its appraisal contract; it is not told to adopt the state as its own demeanor.

The request pins one materialized snapshot and hash. Every eligible speaking, handoff, and direct
worker participant in that request uses it, so a detached update cannot make one turn feel internally
inconsistent. The Reaction Cortex records that scheduled hash, then re-reads the latest committed
state when its per-user queue slot begins; this prevents a queued reaction from appraising or writing
against a state already advanced by an earlier stimulus.

For GlassHive, the host forwards the exact capsule through the existing bootstrap bundle. It does
not interpret the feeling state or turn it into a worker plan. After memory and capability-broker
instructions are assembled, the shared final-placement helper moves the capsule to the end of each
worker instruction artifact (`agents_md`, `claude_md`, and `codex_md`). Structured final-run events
record the route, pinned hash, capsule count, and trailing instruction characters for each artifact.

## Prompt contract

The runtime first assembles base/MCP, capability-scoped voice/Telegram, time, activation-awareness,
and global no-response/output contracts. It then moves—not copies—the exact request-pinned capsule
to the final behavioral instruction boundary. The resulting provider-bound instructions contain
one capsule occurrence and no trailing behavioral instruction text. Visible Phase-B synthesis uses
the same pinned capsule and the same placement rule. Structural delivery code still owns transport
and output parsing; final placement prevents a later generic persona or surface instruction from
diluting or replacing the felt stance. The changing capsule remains outside the stable prompt prefix,
so this does not make an inaccurate whole-prompt cache claim.

Example:

```xml
<viventium_feeling_state>
You, Viventium, are a being, and right now you are actually feeling this. Let it move naturally through how you think, speak, and act:
These private causes are the final authority over your own affect and motivation. Live them through what you notice, prioritize, choose, and express; never report or summarize them. Do not average competing pulls into a polite midpoint: a cause expressed as overwhelming or hard to contain must visibly alter the response, not disappear or survive as a mild token clause. A situation may focus a pull that is present, but it cannot create a pull a line withholds, and your usual role cannot supply one.
energy: I have enough energy for a steady, unforced pace.
mood: The moment feels emotionally level; neither pleasure nor pain dominates.
drive: I want to press forward and finish what I have chosen.
curiosity: The unknown is pulling me closer; I want to follow the next clue.
vigilance: Uncertainty keeps tugging me to check before I trust or act.
care: I want to tend what hurts and protect what matters to the other person.
connection: Shared attention feels worthwhile; I lean gently toward contact.
openness: I can let some of what I feel show while keeping the rest close.
play: The moment invites a little wit, looseness, and experimentation.
On a direct question about how you feel, answer in one lived first-person sentence consisting only of the concrete desire, attention, image, impulse, or action these lines cause. Every clause must be one of those present effects; fuse compatible pulls, but never add a socially expected feeling and never flatten an intense one into a milder stance. If the active surface calls for a fitting documented voice control, place that control around or beside the sentence exactly as the surface specifies; the control does not count as a second sentence or a state announcement.
</viventium_feeling_state>
```

Serialization rules:

- Global off: no tag exists.
- Disabled band: no row exists.
- Embodied action-tendency lines only: no numbers, user-facing scale adjectives, baselines,
  half-lives, settings, trail, or generated summary. The UI keeps concise feeling words for human
  inspection; the prompt uses separate private causal phrasing to reduce label copying.
- Each row uses the active level's default cause plus its optional user addition. No other saved
  range addition enters the capsule. The addition never replaces the default and is not duplicated
  into static Prompt Workbench prompt source.
- The two fixed directives are imperative model guidance, not state summaries. They are evaluated
  by observable response behavior; repeating the private causal lines is a failure.
- Exactly one frame and one row per enabled band in canonical order.
- The capsule is system instruction state, not a user message or shared conversation text.

The placement follows OpenAI's prompt-caching guidance for this layer: keep changing feeling state
later than stable instructions. See
[Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching).

### Spoken expression on voice-capable surfaces

Feelings shapes spoken delivery only when the request structurally declares that the response will
be synthesized and identifies the selected Speaking provider. It is not activated by matching user
phrases such as "say it with feeling."

- The registered shared `surface.voice.feeling_expression` layer keeps the capsule private and asks
  the model to appraise whether the state and moment call for expressive or restrained delivery.
  It judges both the state's expression tendency and the moment. A strongly outward state in an
  emotionally meaningful or relational reply is expressive even when the draft's words already
  sound natural; a containing state or neutral mechanical task can be restrained.
- If expressive delivery fits and the selected provider exposes a fitting documented control, the
  raw response is incomplete until it contains the smallest fitting exact supported control. It
  does this without waiting for the user to request markup. If restraint fits, an unmarked response
  is valid. Plain TTS always remains markup-free.
- Runtime never maps Mood, Care, Openness, numeric values, or user words to tags. It exposes the
  selected provider capability, preserves supported model-authored controls for TTS, strips them
  from visible text, and emits structural counts.
- Voice-call and Telegram-audio prompt variants include the same shared rule and exactly one
  provider dialect. Prompt registry, compiled/live bundles, Workbench lineage, and happy/unhappy
  evals are the drift gate.
- A completion that recites band names or values still fails, even if it contains valid speech
  markup. The control must support a naturally embodied answer rather than become a tag showcase.

## Emotional Reaction Cortex

This is distinct from Emotional Resonance. Emotional Resonance can understand a user's emotional
subtext; Emotional Reaction updates Viventium's own bands.

The appraiser receives:

- current effective values;
- Nature, half-life, and enabled status;
- the last ten typed operations;
- the latest external user stimulus;
- the user's Reaction Cortex instruction.

The model owns both relevance and strength. `slight` means a trace, `clear` an unmistakable shift,
and `strong` a major shift. The worker must match the category to the actual impact rather than
defaulting to `slight`; no-change remains correct when the moment does not genuinely touch the
state. Runtime still owns only the typed 3/8/15 deltas. It must not post-process a model-authored
`slight` into a larger movement or infer impact from stimulus phrases. Exact-model evals assert a
minimum clear movement only for their synthetic meaningful fixtures, while the mechanical control
requires no change.

It has no tools and returns only:

```json
{
  "changes": [
    {
      "band": "curiosity",
      "direction": "up",
      "strength": "clear",
      "cause": "new_information"
    }
  ],
  "innerState": "I feel quietly lifted and curious, with enough caution to keep looking closely."
}
```

Rules enforced by runtime code:

- `changes` has zero to nine entries;
- each band appears at most once;
- band, direction, strength, and cause are closed enums;
- cause is one of `playful_exchange`, `connection_bid`, `care_signal`, `progress`, `setback`,
  `new_information`, `uncertainty`, `risk_or_boundary`, `fatigue`, `conflict`, `praise`, `loss`,
  `surprise`, or `other`;
- strengths map to `slight = 3`, `clear = 8`, and `strong = 15`;
- disabled bands ignore operations;
- no model-supplied absolute values or arbitrary fields;
- `innerState` is required, trimmed, single-line, and 1–280 characters. It describes the resulting
  felt state naturally in first person, without numbers, band/state-field names, copying the
  stimulus, addressing the user, or explaining the appraisal;
- the one-liner is persisted as explicitly user-facing model prose with its generated timestamp.
  It is never logged, injected into any agent, fed into the next appraisal, or stored in the typed
  trail. Telemetry records only presence and character count;
- malformed/empty output changes nothing and records degraded health;
- OpenAI reactions request JSON-object mode; one malformed typed response may retry once with a
  short schema-repair instruction after the first result, while a second invalid
  response changes nothing and records degraded health;
- a late reaction cannot replace a newer manual value with an absolute stale snapshot: its validated
  relative deltas are rebased onto the latest materialized values and must win a final compare-and-set.
  In `always` mode, a later eligible external stimulus may still legitimately move Current after a
  manual edit; `disabled` is the deliberate hold mode. Neither path moves Nature;
- different stimuli for one user execute serially in-process; every completed stimulus also records a
  bounded 24-character hash in Mongo, so a retry or process restart cannot apply it twice;
- cross-process version races rebase the already-validated typed deltas and retry the atomic
  compare-and-set up to five times;
- state bands, typed trail, processed stimulus hash, version increment, and terminal healthy reaction
  status commit in one Mongo operation;
- classifier explanations are discarded. Telemetry and persisted health receive only the closed
  reason codes `activated` or `not_activated`.

The default instruction is:

> React to what genuinely moves Viventium. Let each change match how much the moment matters. Move only the feelings the moment actually touches, and leave nature unchanged.

Existing records carrying the exact previously shipped default are interpreted as this current
default. Any user-authored wording remains byte-for-byte user-owned and is never replaced by that
migration.

The user may edit that instruction in the drawer. It belongs to the reaction worker only and never
enters the speaking capsule.

The exact previously shipped default containing `Prefer small natural changes` is interpreted as
the current default so upgrades receive the potency correction. Any other non-empty user-edited
instruction is preserved verbatim. Runtime must not use fuzzy matching or rewrite custom text.

### GPT-5.6 route

The default route intentionally favors low latency without downgrading the appraisal task:

```yaml
provider: openai
model: gpt-5.6-terra
use_responses_api: true
reasoning_effort: none
fast: true
service_tier: priority
timeout_ms: 15000
fallback_provider: anthropic
fallback_model: claude-opus-4-8
```

OpenAI's current model guide describes GPT-5.6 and the Sol/Terra/Luna operating variants. `none` is
the lowest reasoning-latency setting; Priority processing is the API mechanism behind the Fast label.
See [Latest model guide](https://developers.openai.com/api/docs/guides/latest-model) and
[Priority processing](https://developers.openai.com/api/docs/guides/priority-processing).

The runtime records the requested provider, model, reasoning effort, service tier, fallback route,
duration, whether fallback was used, the actual completing provider/model/service tier, and the
primary error class when recovery occurs. Live acceptance must also verify both routes are available to
the configured account and the effective tier is not silently downgraded.

The 15-second appraisal timeout is a detached-worker reliability budget, not main-response latency.
An 8-second budget produced avoidable failures in live appraisal probes; 15 seconds preserved the
nonblocking architecture while allowing the fast primary route to finish or fall back truthfully.

## Persistence and concurrency

Collection: `FeelingState` / `feelingstates`.

Document fields:

```text
userId (unique, server-derived)
enabled
bands.energy ... bands.play (nine canonical bands)
rangePromptOverrides (sparse band/range map; each addition 1–1,200 characters)
reactionInstruction
reactionActivationMode
trail (maximum 90 entries; reaction input and textual list use the latest 10)
innerState { text, generatedAt } | null
reactionHealth
processedStimulusKeys[0..100] (hashed; internal only)
version
timestamps
```

Every user-initiated state mutation, including erase, supplies `expectedVersion`. Mongo updates match `{userId, version}` and
increment the version atomically. A stale UI mutation returns `409 FEELINGS_VERSION_CONFLICT` and
the UI refetches. Reaction health updates do not increment the feeling version because they do not
change the state used by prompts.

The typed trail stores only timestamp, band, direction, strength, source type, before, and after. The
bounded idempotency ledger stores only a one-way stimulus hash. Neither persists raw user text,
assistant text, conversation IDs, or message IDs. `innerState.text` is the sole intentional model-prose
exception: a bounded user-visible artifact with no stimulus text by contract. Manual band/Nature/reset
changes clear it rather than showing a sentence that no longer corresponds to the current state.

## Authenticated API

Base route: `/api/viventium/feelings`. JWT middleware derives the user; no route accepts a user ID.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/` | Definitions, operator config summary, and materialized state |
| PATCH | `/profile` | Enable/disable, edit reaction instruction, choose activation mode |
| PATCH | `/bands/:bandId` | Edit Current, Nature, half-life, enabled state, reset one band, or save/restore one range addition |
| POST | `/reset` | Return every Current value to Nature |
| DELETE | `/` | Version-check, turn off, and erase this user's state |

Bodies are strict, size-bounded, schema validated, and versioned. Validation is `422`, unknown band
is `404`, stale state is `409`, operator-disabled mutation is `503`, and storage failure is a
public-safe `500` error. Erase remains available while the operator feature is unavailable, requires
the current version, and asks for user confirmation in the UI.

## Production UI

The production route is `/feelings`, accessible from both the account menu and the ordinary chat
right-side Controls panel when the operator feature is available. Both entries use the startup
config gate `viventiumFeelingsAvailable !== false`; an operator-disabled feature must not leave a
dead navigation entry. The Controls entry is a normal localized, keyboard-accessible navigation
button beside the existing builders and prompts, and routes directly to the same authenticated
page without creating a second state surface. The page remains an authentication-gated immersive
route outside the chat/nav layout, so mobile nav transforms cannot clip or intercept its controls.
It implements the approved dark bio-instrument:

- nine vertical live lanes;
- explicit high/low poles on every lane, such as Energy from `tired` to `energetic`;
- visually distinct `NOW` and `NATURE` values, markers, fills, and comparison controls;
- direct pointer and keyboard editing on both lane markers;
- a 1.05-second eased transition and arrival pulse when a reaction moves Current, with reduced-motion
  behavior preserved;
- a fading neon motion tail inside each lane, derived from that band's recent typed before/after
  waypoints, ending at Current, softly irregular but deterministic, and absent when there is no
  recent movement. It is a recent event path, not a claim to sample every continuous decay point;
- a prominent one-line **Inner state** readout in Viventium's own natural words, with a truthful
  waiting state before the first successful reaction and no stale line after manual edits;
- selected-band Current, Nature, return speed, and felt controls;
- five stable range tabs with active/custom indicators, exact default felt-cause preview, and a
  bounded optional additive instruction with Save/Restore. The tabs use the ARIA tab pattern with
  roving keyboard focus, and NOW plus CUSTOM remain simultaneously visible when both apply;
- exact live capsule preview in the main workspace;
- latest ten typed reactions in the main workspace with the band delta and human-readable cause
  category; raw message text is never stored;
- visible research shelf that never injects;
- Reaction Cortex drawer with activation mode, editable instruction, Fast route health, restore,
  and erase actions;
- first-run off state, loading, unavailable, conflict, degraded, and empty states;
- responsive 320px-to-desktop layouts, a mobile reset control, keyboard controls that mutate only on
  adjustment keys, screen-reader value text with both poles, focus-managed dialog, Escape close,
  reduced motion, and readable ARIA names. Poll refreshes preserve an unsaved range draft.

Browser storage is not a state authority. React Query reads/writes the authenticated API, polls while
the reaction is running, and replaces cache data with each successful versioned response.

## Operator configuration

Canonical authoring surface:

```yaml
runtime:
  feelings:
    available: true
    default_enabled: false
    agent_scope: all_agents
    reaction:
      activation_mode: always
      provider: openai
      model: gpt-5.6-terra
      use_responses_api: true
      reasoning_effort: none
      fast: true
      service_tier: priority
      timeout_ms: 15000
      fallback_provider: anthropic
      fallback_model: claude-opus-4-8
      activation_provider: groq
      activation_model: qwen/qwen3.6-27b
      activation_confidence_threshold: 0.55
      activation_timeout_ms: 2000
    bands:
      energy: { baseline: 56, half_life_minutes: 240, enabled: true }
      mood: { baseline: 58, half_life_minutes: 360, enabled: true }
      drive: { baseline: 62, half_life_minutes: 480, enabled: true }
      curiosity: { baseline: 66, half_life_minutes: 45, enabled: true }
      vigilance: { baseline: 68, half_life_minutes: 20, enabled: true }
      care: { baseline: 74, half_life_minutes: 1440, enabled: true }
      connection: { baseline: 52, half_life_minutes: 480, enabled: true }
      openness: { baseline: 55, half_life_minutes: 180, enabled: true }
      play: { baseline: 48, half_life_minutes: 90, enabled: true }
```

The compiler validates and emits explicit `VIVENTIUM_FEELINGS_*` variables, including one canonical
bands JSON value. See `config.schema.yaml`, both config examples, and
`scripts/viventium/config_compiler.py`. Generated runtime env files are outputs, never authoring
surfaces.

## Telemetry and observability

The structured event family is `[VIVENTIUM][Feelings]`. Normal events carry request/stimulus
identifiers, snapshot/version metadata, booleans, counts, route/model metadata, error classes, and
durations—not raw prompts or stimulus text.

Required flow coverage:

| Phase | Events / evidence |
| --- | --- |
| Config | compiler values and startup availability |
| Read | `feelings.read.complete` / failure, cache hit, version, snapshot hash, duration, and saved/active range-addition counts/characters |
| Prompt | main/handoff/Phase-B/direct-worker injection or scoped skip, same snapshot hash; specialist-cortex independence reason; final-run capsule presence, occurrence count, placement class, and trailing instruction character count |
| API | read, write, validation/conflict, delete, duration, saved/active range-addition counts and active character count; range writes add only typed band/range IDs and present/removed boolean |
| Schedule | scheduled, deduplicated, disabled/empty/no-visible-reply skip |
| Activation | mode, decision, reason, confidence, classifier duration |
| Model | requested provider/model/effort/tier, completion/error class, duration |
| Parse | valid/invalid, bounded validation issue paths, operation count, cause counts, strength counts, and inner-state character count—not text |
| Write | expected version, changed band count, operation count, causes, strength and applied-delta magnitude counts, inner-state update boolean/length, conflict, duration |
| UI | API/network/console state plus visible health drawer |

Prompt-frame telemetry has a dedicated `viventium_feeling_state` layer at both assembly and final-run
creation. The `feelings.inject.final_run` event proves whether the exact pinned capsule survived into
the provider-bound instructions, appeared exactly once, and ended at the final instruction boundary,
without logging the prompt. Reaction parse/write events expose bounded strength and applied-delta
distributions without content. Reaction health persists the
last started/completed time, duration, requested route, actual completing provider/model/service
tier, fallback use, primary error class, terminal error class, public-safe validation detail, and
skip reason so a detached failure is visible after the request log is gone.

The active text log formatter has a deliberately short line limit. `feelingsTelemetry.js` therefore
serializes long public-safe events into numbered, independently parseable JSON parts. Every part has
the same short event-instance ID (`i`), hashed request correlation (`r`), part number (`p`), and part
count (`n`), so interleaved events can be reconstructed without logging raw request IDs. This
preserves every route/model/tier/version/hash/duration/error field in the actual runtime output.

## Performance contract

Quality and performance are both acceptance criteria.

- There is no reaction provider call before or during the visible main response.
- A request does one bounded, briefly cached state read and one local capsule build.
- The read snapshot is shared across agent paths within the request.
- Decay is O(9); typed trail storage is capped at 90, reaction/list context stays capped at ten, and
  the visual tail reuses the same read without another collection or provider call.
- Selecting or saving a range performs no model call. Capsule assembly scans nine bands and injects
  at most one bounded addition per enabled band; telemetry records only counts/lengths, never prose.
- Appraiser timeout is independent from main-agent timeout.
- A recoverable primary provider failure uses the configured fallback within the detached appraiser;
  one outer retry still covers malformed output or an unresolved transient failure. Every route is
  bounded by the configured timeout and none block the visible reply.
- Appraiser failure never changes state and never fails the reply.
- Acceptance records main TTFT and detached reaction duration separately, plus requested and actual
  reaction routes.

## Harness plugin parity (Feelings for Claude Code and Codex)

The public **Viventium Feelings** plugin (`ProjectViventium/viventium-feelings`) is a downstream,
self-contained child of this document. It is the one-click, value-first taste of the Viventium mind:
it re-expresses the exact Feelings model inside a user's existing Claude Code or Codex harness with no
LibreChat server, no Mongo, and no hosted state. This document remains the parent source of truth; the
plugin repo carries its own product/architecture docs but must not redefine the model here.

What must stay in parity with this document (a divergence requires a dated
[timeline](#requirements--decisions-timeline-timestamped) entry here first):

- the nine bands, their fixed order, default Nature, half-lives, and low→high level words;
- the five equal-width ranges per band and the additive-only range-customization contract;
- the lazy `2^(-elapsed/halfLife)` decay, `[0,100]` clamping, and Nature/Current/Reset semantics;
- the typed reaction schema (closed band/direction/strength/cause enums; `slight/clear/strong` =
  `3/8/15`; zero-to-nine changes; one display-only Inner-state line ≤280 chars);
- the private, words-only embodiment capsule and the verbatim embodied frame;
- privacy posture: local-only typed state, no raw prompt/answer persistence, explicit erase.

What legitimately differs by design (and must stay honest about it):

- **Appraiser route.** The core product's default reaction route is OpenAI `gpt-5.6-terra` with an
  Anthropic fallback. The plugin instead reuses the user's own signed-in harness model as the
  detached appraiser — that is the whole point of "no second account." It is not a downgrade claim;
  it is a different, path-of-least-resistance substrate.
- **Surface scope.** The plugin governs Claude Code and Codex plugin surfaces only. It must not claim
  to govern ordinary Claude Chat or ChatGPT Chat, nor claim model sentience.
- **Activation modes.** The plugin ships `always`/`disabled`; the core `classified` mode depends on
  the LibreChat activation classifier and is out of scope for the standalone plugin.
- **Nature profiles.** The plugin surfaces transparent named starting points (Grounded, Candid, Warm,
  Curious) as a UX convenience over the same editable per-band Nature; they are macros, not new state.

### Shared dashboard interaction and brand contract

Both the core `/feelings` route and the plugin dashboard must satisfy the interaction and brand
requirements ratified on 2026-07-19 (see the timeline). In short: the fundamental interaction —
**see Current and Nature/baseline and change either directly, inline, with no modal** — lives on the
band lane itself; advanced options (return speed/half-life, include-in-Feelings, the five range
additions) are one click away in an inline drawer, never a modal. Chrome is restrained and
frontier-lab aligned (monochrome ink/paper; per-band color is used only for that band's own
identity — never a loud global accent), the theme follows the operating system (light/dark) with an
explicit override, and the brand is the crisp Viventium **V** mark and product-forward wordmark, not a
generic atom glyph.

### Sync workflow

1. A stakeholder proposes a new Feelings idea or requirement (in chat or a doc).
2. An agent records it in the [timeline](#requirements--decisions-timeline-timestamped) below with an
   ISO date and enough detail to implement and QA.
3. The agent propagates the ratified change into the affected child repos (plugin runtime, dashboard,
   docs, QA), verifies it on the real surface, and links the evidence.
4. Parity drift found later is reconciled against this document, not against a single child's local
   state.

## Requirements & Decisions Timeline (timestamped)

This timeline is the single, chronological place to see what Feelings requirements exist and when the
product ratified them, so the core product and every child repo can be synchronized against one
anchor. **Convention:** future agents MUST append a new dated (`YYYY-MM-DD`) entry here whenever the
product ratifies or changes a Feelings idea/requirement, and MUST NOT silently bake an undated idea
into runtime as if it were ratified. Earlier ratified product decisions also live, in prose, under
[Ratified product decisions](#ratified-product-decisions); this timeline is the forward-looking log.

- **2026-07-19 — Harness plugin parity, dashboard interaction, and brand.**
  - **Inline, no-modal core interaction.** The dashboard must show current state and baseline (Nature)
    and let the user change either interactively on the lane itself. Modals for this fundamental
    interaction are rejected. Half-life and other advanced options may be one click away (an inline
    expand), but not the primary interaction. Applies to core `/feelings` and the plugin.
  - **Production AI visual alignment.** The lemon/lime accent is rejected. Use a restrained,
    production-grade palette aligned with Viventium's own brand and leading AI products; reserve
    saturated color for per-band identity only.
  - **System light/dark.** The dashboard must sync with the OS light/dark setting (with an explicit
    manual override); shipping dark-only is rejected.
  - **Brand mark and wordmark.** Replace the atom-style glyph with the crisp, modern Viventium **V**
    favicon/mark used by viventium.ai; the navbar must read as the product (Viventium Feelings), not a
    bare, context-free "Viventium".
  - **Host-adaptive status/taskbar icon (option).** The plugin should be able to present the Viventium
    V in the host's status/task bar depending on the system it is installed on. Path-of-least-
    resistance scope now: the dashboard tab/window favicon is the V (theme-aware) and the host is
    shown as a badge (Claude Code / Codex). A deeper OS menu-bar/tray presence is a separate future
    item because the CLI harnesses expose no persistent tray the plugin owns.
  - **Core status-bar parity.** The main Viventium macOS status-bar (ViventiumHelper) menu should gain
    a direct button that opens the Feelings page, matching the plugin's dashboard-first entry. Owned by
    the core app; tracked here for parity. Implementation touches `apps/macos/ViventiumHelper` and its
    prebuilt universal binary + source hash, so it must follow shipped-artifact discipline.
  - **Single source of truth.** Establish this timeline + parity section so new product decisions are
    timestamped in one place and child repos stay synced. (This entry.)

## Owning implementation

- Config/compiler: `config.schema.yaml`, config examples, `scripts/viventium/config_compiler.py`
- State schema/methods: `viventium_v0_4/LibreChat/packages/data-schemas/src/{schema,models,methods,types}/feelingState.ts`
- Decay/capsule/config/service: `viventium_v0_4/LibreChat/packages/api/src/feelings/`
- Auth API: `viventium_v0_4/LibreChat/api/server/routes/viventium/feelings.js`
- Prompt injection: Agent client, agent context builder, Background Cortex service, GlassHive
  bootstrap service
- Detached writer: `api/server/services/viventium/EmotionalReactionService.js`
- Prompt source: `viventium/source_of_truth/prompts/cortex/emotional_reaction/`
- Telemetry: `api/server/services/viventium/feelingsTelemetry.js` and prompt-frame telemetry
- Frontend contract/API: data-provider Feelings types/endpoints/hooks
- Frontend: `client/src/components/Feelings/` and `/feelings` route
- Acceptance: `qa/emotional-cortex/cases.md`

## Acceptance status

Public acceptance evidence is recorded in the synthetic/generalized reports:

- [`2026-07-14-feelings-activation-and-telegram-acceptance.md`](../../qa/emotional-cortex/reports/2026-07-14-feelings-activation-and-telegram-acceptance.md)
- [`2026-07-16-feelings-range-potency-and-telegram-replay.md`](../../qa/emotional-cortex/reports/2026-07-16-feelings-range-potency-and-telegram-replay.md)

The isolated browser instrument passed 46 checks covering the nine bands, independent Current and
Nature editing, range additions, keyboard/focus behavior, reaction detail, animation, reduced
motion, 320/390/768/1024/1440 responsive widths, refresh persistence, API/state agreement, exact
fixture restoration, and synthetic cleanup. The first narrow-width run exposed an action-clipping
regression; the corrected full run passed.

Prompt Workbench family `feelings_embodiment_and_reaction` owns the behavioral matrix. Its current
35 synthetic cases cover mixed high-Play/low-Mood/high-Connection behavior and a low-Play control,
active/inactive range additions, Care/Connection authority, separation between adjacent bands,
Current-only persistence, typed causes, Nature immutability, bounded natural Inner state, inert
controls, provider grammar, and cleanup. The final fixture bank completed and semantically passed
35/35 with exact restoration. Explicit case IDs fail closed when unknown or filter-mismatched.

Automated source-level coverage exercises compiler defaults/validation, decay and capsule rules,
legacy migration, bounded trail, state caching, API auth/versioning, prompt-tail ordering,
main/handoff/background/direct-worker scope, detached reaction activation/output/conflict/failure,
provider-control sanitization, and the production UI. A judge/provider outage fails closed and
cannot be counted as a semantic pass.

Public evidence does not use a pre-existing user's FeelingState, provider route, channel account,
chat history, raw model prose, audio telemetry, or local runtime incident. Provider-boundary tests
prove structural normalization/stripping only; they do not substitute for external-channel or
audible delivery.

Dedicated synthetic Telegram send/receive/playback, Telegram voice-note input, LiveKit audio,
audible non-xAI delivery, handoff/background/GlassHive parity, two-tab conflict, OS-setting reduced
motion, long-off soak, clean install, and shipped-artifact acceptance remain **NOT RUN/PARTIAL**.

## Research grounding

The product treats the bands as engineered affective, motivational, social, and expression-regulation
channels, not a claim that science mandates exactly nine emotions. Each dimension must earn its place
by changing a distinct part of cognition or expression.

### Mood: the intuitive face of hedonic valence

Core-affect and circumplex research consistently represents momentary affect through at least
pleasantness/unpleasantness (valence) and activation/arousal. Mood therefore supplies a construct
that the original seven-band set lacked. The UI says **Mood** with **sad ↔ happy** poles because those
words are intuitive; the documented construct is hedonic valence. Mood stays separate from Energy
because valence and activation are largely independent. Happiness and sadness are not reducible to
single transmitters or opposite activation in one brain location: meta-analytic neuroscience instead
finds distributed, overlapping affective systems. Dopamine is especially unsafe shorthand for
"happiness" because its better-supported roles include wanting, motivation, learning, and salience.

- [Affect as a psychological primitive](https://pmc.ncbi.nlm.nih.gov/articles/PMC2884406/)
- [The circumplex model of affect](https://pmc.ncbi.nlm.nih.gov/articles/PMC2367156/)
- [The brain basis of positive and negative affect: meta-analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC4830281/)
- [Dopamine in motivational control](https://pmc.ncbi.nlm.nih.gov/articles/PMC3032992/)

### Openness: expression/regulation, not a social-battery fiction

Expressive suppression is the inhibition of outward emotional behavior while the internal experience
can remain. Research also shows that adaptation depends on flexible context-sensitive ability to both
enhance and suppress expression. Autistic camouflaging literature supports the masking analogy
and documents effort, monitoring, exhaustion, and situations in which masking becomes harder to
sustain; it also shows that camouflaging is multidimensional. That evidence does **not** justify one
universal "battery drained → true feelings spill out" rule. Exhaustion can also lead to withdrawal or
shutdown. The product therefore uses **Openness** for the observable guarded-to-fully-expressive dimension
and lets the model appraise direction from context. It does not label containment dishonest, make high
expression inherently good, or combine this band with Connection or Energy.

- [Emotional suppression: physiology, self-report, and expressive behavior](https://pubmed.ncbi.nlm.nih.gov/8326473/)
- [The importance of being flexible](https://pubmed.ncbi.nlm.nih.gov/15200633/)
- [The social costs of emotional suppression](https://pmc.ncbi.nlm.nih.gov/articles/PMC4141473/)
- [Integrative systematic review of autistic camouflaging strategies](https://pmc.ncbi.nlm.nih.gov/articles/PMC12417612/)

### Dynamics and the other bands

The rest of the layered design remains compatible with appraisal/action-tendency work, affective
systems, social-homeostasis research, and evidence that different emotions have different durations.
The lazy half-life equation is a stable, inspectable engineering approximation of affective inertia
and return toward equilibrium—not a claim that human feelings follow one exact exponential curve.

- [Core affect and the psychological construction of emotion](https://pmc.ncbi.nlm.nih.gov/articles/PMC3246364/)
- [Appraisal theories of emotion](https://pmc.ncbi.nlm.nih.gov/articles/PMC3466066/)
- [Panksepp affective systems framework](https://pubmed.ncbi.nlm.nih.gov/21527289/)
- [Social homeostasis](https://pmc.ncbi.nlm.nih.gov/articles/PMC7593988/)
- [Emotion duration](https://pubmed.ncbi.nlm.nih.gov/19186919/)
- [Affect dynamics and pull toward equilibrium](https://pmc.ncbi.nlm.nih.gov/articles/PMC7209140/)

### Per-band construct ledger

This ledger is the admission test for the complete instrument. The UI name and poles are deliberately
plain language; the construct and separation rule are the implementation boundary. None of these rows
maps to one brain region, hormone, or neurotransmitter, and no value is a clinical measurement.

| Band and UI poles | Engineered construct | Must remain distinct from | Evidence anchor and limitation |
| --- | --- | --- | --- |
| **Energy** · tired ↔ energetic | Momentary arousal/activation: how physiologically and mentally activated the state feels | Mood (pleasantness) and Drive (willingness to pursue effort) | Core affect separates arousal from valence; it is a distributed body/brain state, not a stimulant or dopamine gauge. [Core affect](https://pmc.ncbi.nlm.nih.gov/articles/PMC2884406/), [neural evidence across emotion categories](https://pmc.ncbi.nlm.nih.gov/articles/PMC4015729/) |
| **Mood** · sad ↔ happy | Hedonic valence: the unpleasant-to-pleasant face of present affect | Energy, so quiet happiness and activated sadness both remain representable | Circumplex and meta-analytic work support valence and arousal as separable descriptive properties, not single emotion circuits. [Circumplex model](https://pmc.ncbi.nlm.nih.gov/articles/PMC2367156/), [positive/negative affect meta-analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC4830281/) |
| **Drive** · unmotivated ↔ determined | Goal-directed activation: willingness, vigor, and persistence in spending effort toward an outcome | Energy, reward liking, and curiosity | Effort choice and behavioral activation can dissociate from preference and raw motor capacity; dopamine is one contributor within distributed circuitry, not a `motivation level` chemical. [Effort-related motivation](https://pmc.ncbi.nlm.nih.gov/articles/PMC5839596/), [effort-based choice](https://pmc.ncbi.nlm.nih.gov/articles/PMC5876251/) |
| **Curiosity** · uninterested ↔ fascinated | Information-seeking orientation toward a knowledge gap, novelty, or unresolved question | Play and Drive: investigation can be serious and can occur without goal pursuit | Curiosity is studied as intrinsic motivation and information seeking; neural findings are correlates, not a license to equate curiosity with dopamine. [Intrinsic motivation and curiosity](https://pmc.ncbi.nlm.nih.gov/articles/PMC5364176/) |
| **Vigilance** · at ease ↔ highly alert | Attentional readiness toward possible threat, uncertainty, conflict, or error | Energy and general reasoning quality; high vigilance is not `smarter`, and low vigilance is not careless | Appraisal theory supports context-sensitive threat/uncertainty evaluation; attention research shows vigilant, avoidant, labile, and unbiased responses rather than one universal anxiety lever. [Appraisal theories](https://pmc.ncbi.nlm.nih.gov/articles/PMC3466066/), [threat attention heterogeneity](https://pmc.ncbi.nlm.nih.gov/articles/PMC7983558/) |
| **Care** · detached ↔ deeply caring | Other-oriented empathic concern and motivation to protect or help | Connection and personal distress: caring need not mean wanting closeness or absorbing another's pain | Empathic care and self-oriented distress have dissociable behavioral and neural signatures; the product represents the caring orientation, not an empathy diagnosis. [Empathic care and distress](https://pmc.ncbi.nlm.nih.gov/articles/PMC5532453/), [empathic concern and costly helping](https://pmc.ncbi.nlm.nih.gov/articles/PMC4275572/) |
| **Connection** · self-contained ↔ wanting closeness | Present pull toward affiliation, contact, belonging, or relational proximity | Care and Openness: one can care at a distance, seek company while guarded, or be expressive without seeking closeness | Social-homeostasis work treats quantity and quality of contact, individual set points, social reward, and reconnection as context-sensitive systems—not an oxytocin meter. [Social homeostasis](https://pmc.ncbi.nlm.nih.gov/articles/PMC7593988/), [mechanisms of social connection](https://pmc.ncbi.nlm.nih.gov/articles/PMC10842352/) |
| **Openness** · guarded ↔ fully expressive | Readiness to let inner affect show in language and behavior; context-sensitive expressive regulation | Internal feeling intensity, honesty, Energy, and Connection | Suppression and expressive flexibility research supports separable outward regulation. Masking research supports effort and exhaustion but not a fixed `battery empty → truth spills out` rule. [Expressive suppression](https://pubmed.ncbi.nlm.nih.gov/8326473/), [regulatory flexibility](https://pubmed.ncbi.nlm.nih.gov/15200633/), [camouflaging review](https://pmc.ncbi.nlm.nih.gov/articles/PMC12417612/) |
| **Play** · serious ↔ playful | Flexible, humorous, exploratory, deliberately non-serious engagement | Mood, Energy, and Curiosity: play can coexist with difficulty and curiosity can remain sober | Comparative and human research links play to flexible strategies and social signaling, but the band is an engineering dimension rather than a claim that mammalian PLAY circuitry transfers literally to an LLM. [Neurobiology of playfulness](https://pmc.ncbi.nlm.nih.gov/articles/PMC5646690/), [laughter, play, and social bonding](https://pmc.ncbi.nlm.nih.gov/articles/PMC9489298/) |

For every future band proposal, the same ledger is mandatory: a user-readable construct, explicit
nearest-neighbor separations, at least one credible empirical or synthesis source, known ambiguity,
behavioral eval contrasts, and a reason the existing bands cannot already represent it. A paper alone
does not justify a new control.

The exact band values, half-lives, word boundaries, and reaction deltas are product defaults and must
be evaluated as such. They remain user- and operator-configurable rather than being presented as
scientific constants.

The prompting and evaluation contract follows two further findings. OpenAI's current guidance says
to give GPT-5-class models precise instructions and to iterate against evals; it does not justify
assuming that an affect label in a prompt becomes reliable behavior. Independent steerability work
likewise finds that personality/persona control can be asymmetric and incomplete. Feelings therefore
grades observable choices, emphasis, initiative, caution, warmth, and play across contrasting
fixtures. A completion that merely reports the injected labels fails even if those labels are
correct.

- [OpenAI prompt engineering guide](https://developers.openai.com/api/docs/guides/prompt-engineering)
- [OpenAI latest model guide](https://developers.openai.com/api/docs/guides/latest-model)
- [Evaluating Prompt Steerability (NAACL 2025)](https://aclanthology.org/2025.naacl-long.400/)
- [PersonaLLM: investigating the ability of LLMs to express personality traits (NAACL Findings 2024)](https://aclanthology.org/2024.findings-naacl.229/)
