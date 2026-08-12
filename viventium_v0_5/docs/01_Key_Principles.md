# Viventium V0.5 Key Principles

> **Status:** proposed V0.5 product constitution under product-owner review. Adapted from the
> current Viventium principles; it is not approved or shipped runtime truth.

## 1. The outcome is quality plus performance

`outcome = Quality (intelligence, relevance, usefulness, alignment) + Performance (fast, smooth, reliable)`

Speed that makes the answer worse is a regression. A path through Codex, Claude, ChatGPT,
GlassHive, LibreChat, or a future local agent must be useful on its own rather than relying on a
hardcoded routing rubric to hide weak paths.

## 2. Own the person-specific layer, not the model race

Viventium does not rebuild frontier models, generic chat, browsers, computers, connectors, or agent
harnesses that better-funded ecosystems already improve. It owns the continuity that must survive a
change of model, harness, interface, and provider:

- a sovereign view of the person's Life;
- an editable Character and emotional baseline;
- portable cortices and automation doctrine;
- permissioned context assembly and provenance;
- mutual-context handoff and verified return;
- visible state, activity, correction, and deletion.

If a native host can own a capability without breaking that continuity, the native host keeps it.

**Scope gate:** a Viventium-owned capability ships only when it makes person-specific continuity
survive or compound across a model, host, interface, or device change. If it does not, reuse the
native capability or leave it out.

## 3. Local-first, open-format, provider-independent

Life and Brain Pack are local, inspectable, exportable, and usable without one vendor. Credentials,
runtime databases, caches, logs, indexes, and hidden reasoning are not portable brain files. Cloud
processing is an explicit execution choice, not an ownership transfer.

## 4. Life is truth; Brain Pack is behavior

- `Viventium/Life/` is the human-readable personal world model: accepted facts, source-linked
  evidence, projects, communications, episodic summaries, decisions, current views, and insights.
- `Viventium/Brain_Pack/` is portable behavioral doctrine: Character, cortex definitions,
  automation definitions, permissions, surfacing rules, and evals.
- Application Support and the operating-system keychain hold runtime state and secrets.

No file projection silently replaces its authoritative source. No credential belongs in either
portable folder.

## 5. Know broadly; load selectively

The best AI knows the person deeply, but every turn should receive only the smallest relevant,
authorized slice. Viventium maintains whole-world coverage through source inventories, health,
provenance, summaries, indexes, and nightly delta processing—not by injecting the whole Life folder
into every prompt.

## 6. Permission, provenance, and state must be visible

A user should always be able to answer:

- What can Viventium see?
- Why is it using this information now?
- Where did this claim come from?
- What is running, waiting, blocked, or stale?
- What did it change?
- How do I pause, correct, export, or remove it?

The interface uses ordinary language first and offers professional evidence one level deeper.

## 7. The main experience is presence, not another inbox

Messaging apps, voice, and native agent apps remain first-class interfaces. The local Viventium app
is the control and visibility plane: CONNECT, CHARACTER, MIND, and AUTOMATIONS. Chat inside MIND is
a useful direct doorway, not the definition of the product.

Presence is continuous across those destinations. A person can drop in or out, remain in listen-only
or Wing Mode, ask Viventium to speak only when useful, or mute immediately. A call is not another tab
or a disposable session that makes Viventium feel absent before and after it.

## 8. Cortices are cognition, not extra personas

The main agent can answer quickly while specialist cortices activate and work independently.
Cortices are evidence producers with explicit activation, context, capabilities, surfacing, and
evaluation contracts. Their internal lifecycle does not become noisy second-chat theatre.

## 9. GlassHive is a mutual-context mission bridge

Delegation carries the complete visible, authorized task context—not hidden reasoning or secrets.
The worker receives a bounded mission, can ask and receive attributable updates, and returns
evidence, deliverables, status, and a receipt. The main agent evaluates the real work before
speaking for it.

## 10. Night work compounds carefully

Night workers verify source coverage, process deltas, synthesize, challenge, and propose. Useful
outputs land under `Life/Insights/`; run receipts remain separate. High-stakes conclusions and
canonical changes default to proposal. “Scan everything” means inventory-wide coverage and
change-aware processing, with periodic full audits—not wasteful rereading of every unchanged byte.

## 11. Defaults should be excellent; complexity should be earned

Onboarding is CONNECT, CHARACTER, Ready. Essential choices are obvious. Advanced STT, TTS,
permission, provider, and evaluation controls remain available without overwhelming the first run.
Core interactions are inline or in a focused sheet; settings do not become a maze.

## 12. No silent magic

Never fake a connection, tool call, source read, memory, feeling, activation, sync, or successful
worker result. Empty, unavailable, denied, stale, timed out, and failed are distinct states. Users
can interrupt automation and recover from mistakes.

## 13. Anywhere access is a consumer capability

Every supported installation must offer a secure way to reach and call Viventium away from the home
network without requiring the person to buy, own, or configure a domain or subdomain. The product
provides the link, device pairing, identity checks, revocation, and clear availability state. Custom
domains may be an advanced option, never a prerequisite.

## 14. Consumer simplicity is a hard product boundary

Viventium may be technically deep; its ordinary interface must not make the person operate that
depth. Internal routes, protocols, scopes, destinations, ports, provider plumbing, worker IDs, and
network topology stay out of the default experience unless the person is resolving a real problem.

- The default surface answers only: **what is this, is it on, which account is it, and what can I do?**
- One row should normally need one enable/disable control and one Connect or Change action.
- Connecting a personal source means choosing a browser or installed app that is already signed in,
  then confirming the visible account or username. Viventium's intelligence owns the navigation and
  extraction details.
- Technical connection methods may exist as an explicitly opened professional diagnostic layer;
  they never lead onboarding or routine use.
- Product copy is short, literal, and action-oriented. If a person must read a paragraph before a
  routine action, the interaction is not finished.
- Do not present internal architecture as product value. “Use from anywhere” is a switch and device
  action, not a networking lesson.

This is a regression gate, not a style preference. A functionally complete interface that exposes
unnecessary engineering burden fails V0.5.

## 15. MIND and CHARACTER have exact responsibilities

- **MIND** is the live relationship: channel/conversation plus current emotional state. Cortex or
  worker activity and Memory provenance appear only when they shaped a reply, inside one quiet
  turn-anchored receipt—not as another console. The receipt answers only: what Viventium was given,
  which Cortex checked it and what returned, and what changed afterward. Its visible sequence is
  **Context & Memory → Cortices → What changed**, with the collapsed line still reporting material
  source and active-Cortex counts.
- **CHARACTER** owns durable identity, voice, Nature, and the complete Feelings instrument. It must
  preserve the real nine inline Now/Nature bands; Inner state; transparent Nature profiles;
  per-emotion return speed, whether it is Felt, and five felt ranges; every emotion's temporal
  trail; reaction instruction;
  reset, pause, and erase controls. It must not replace these with a generic personality form.
- The same Feeling data can be summarized compactly in MIND and edited completely in CHARACTER.

## 16. Model roles must be obvious without exposing plumbing

V0.5 needs two distinct forms of intelligence and must label their jobs plainly:

- **Main thinking:** at least one frontier model account, initially OpenAI, Anthropic, or xAI, for the
  conscious agent and cortex processing.
- **Activation detection:** Groq provides the fast default decision about which cortices should
  wake up.

The product says those two jobs directly. It does not describe Groq as a general foundation, hide
its role inside an Advanced screen, or imply that an activation model can replace the required
frontier thinking model.

## 17. Visual quality is part of the outcome metric

The design target is current premium consumer software: modern, smooth, efficient, fast,
lightweight, and calm. Viventium must use current frontend design and accessibility practice, study
the real product surfaces it is consolidating, and validate every major theme and viewport in a
real browser.

- Dark mode is neutral and dimensional, not an old Material-style stack of tinted cards.
- No fluorescent or neon global accent. Feeling-band color belongs to each band's own data; it is
  not the application chrome.
- Navigation recedes; working content leads. Dividers and spacing create structure before boxes,
  shadows, gradients, or pills.
- Common choices use fluid, touch-friendly segmented controls, menus, or pickers instead of rigid
  browser-default dropdowns.
- System light/dark is the default, with an explicit override and reduced-motion support.
- A prototype is still held to the production interaction and visual bar. “It is only a mock” is
  not permission to ship a generic or incomplete experience for review.

## 18. One-click setup is delegated discovery, not silent permission

CONNECT begins with **Find everything**. GlassHive uses the same browser and computer capabilities
as a strong interactive agent to discover signed-in browsers, installed applications, visible
accounts, and local sources. The person does not manually recreate an inventory the machine can
already identify.

The trust contract is strict:

1. Viventium states what it is about to inspect in one sentence.
2. The person starts discovery and can stop it immediately.
3. Findings appear as a reviewable list with account identities and connection methods.
4. Nothing is connected, enabled, or imported until the person confirms the selected findings.

This is one-click discovery followed by meaningful consent—not one-click authorization to
everything. Manual connection remains available for anything GlassHive misses.

## 19. Many accounts are normal

Email, calendars, social networks, AI providers, browsers, and channels must support several
personal and work accounts without duplicate cards or hidden account switching. A service row
expands to named account rows. Each account has its own identity, state, enable/disable control, and
Change action, followed by **Add another**.

## 20. Feelings are a history, not nine gauges

The live emotional relationship includes both the current state and the path that produced it.
MIND shows a compact **Emotion Trail** beside conversation. CHARACTER shows the trail for every
canonical Feeling, with time, movement, and human-readable cause. Missing periods remain visible as
missing; the interface never invents continuity.

Every band uses the same fixed **0–100** vertical scale so movement is comparable across Feelings.
Within a band's recorded path, the horizontal axis is elapsed time and is labeled **Older → Now**.
Recorded event points join with straight segments only where continuity is known; gaps remain gaps.
Per-emotion auto-scaling, decorative wobble, interpolated readings, or a drawn path for an emotion
that did not move are not allowed. Every visual trail keeps a readable history beside it, including
changes made by the person and resets to Nature.

The interface follows the canonical `FeelingBandDefinition` data. Compact summaries may use the
familiar **Now/Nature** markers; expanded controls use **Current**, **Natural**, **How quickly it
returns**, **Felt**, and **What changed and why**.
Engineering terms such as lane, half-life, host, or state vector do not appear in ordinary UI.

The speaking capsule exists only when Feelings are on and at least one band is Felt. Paused or
zero-Felt state produces no capsule. Personal range wording and Reaction Cortex wording are bounded,
normalized, locally persisted, and included in the confirmed Feelings erase boundary.

## 21. Automations and Prompt Workbench share one authority

AUTOMATIONS is the simple operational view of the same schedule and prompt object owned by Prompt
Workbench. Selecting an automation expands its cycle, instruction, context, delivery, latest
result, and history inline. The instruction field uses the same `{{` variable registry,
autocomplete, validation, version history, and save path as Workbench.

Viventium must never maintain a friendly automation prompt and a separate professional prompt that
can drift. Workbench remains the full evaluation surface; AUTOMATIONS is the lighter view of the
same canonical object.

## 22. Lightweight is an acceptance requirement

Premium means fast and focused, not visually or technically heavy. Prefer native typography,
semantic HTML, CSS, lightweight accessible primitives, SVG data traces, and progressive
enhancement. Do not ship an editor framework, charting framework, connector marketplace, animation
runtime, or dashboard shell when a small focused component does the job.

For the V0.5 shell, target a fast first useful view on ordinary hardware, no layout shift, no
horizontal page overflow down to 320px, interruptible autonomous work, and smooth interaction in
both system themes and reduced motion.
