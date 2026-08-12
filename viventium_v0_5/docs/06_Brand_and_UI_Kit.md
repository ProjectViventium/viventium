# Viventium V0.5 Brand and UI/UX Kit

> **Direction:** quiet graphite, living ink—alive, precise, warm, and never theatrical.

> **Status:** proposed V0.5 visual baseline under product-owner review. Nothing is locked until the
> product owner explicitly approves it.

## Brand promise

**Your Life. Your Mind. Your AI.**

Viventium should feel like a trusted private instrument that happens to be alive: simpler than a
professional console, more substantial than a friendly chatbot, and visibly under the person's
control.

## Visual thesis

- Warm alabaster and neutral graphite establish privacy and seriousness.
- A restrained satin-blue signal marks focus and active presence. It is never a page wash, glow, or
  substitute for hierarchy.
- Feeling-band colors appear only inside the Feeling Spectrum or their own trace.
- Fine rules, spacious typography, and deliberate alignment replace dashboard card mosaics.
- The V mark is crisp and geometric; no glowing brain, robot, orb, or generic gradient logo.
- Navigation is dimmer than the working canvas; content, not chrome, holds the highest contrast.
- Translucent material is reserved for persistent navigation and presence controls where it helps
  preserve place. Routine content remains crisp and flat.

## Tokens

| Role | Dark | Light | Use |
|---|---|---|---|
| Canvas | `#111214` | `#F5F4F1` | App background |
| Raised | `#181A1D` | `#FCFBF8` | Focused sheets and selected surfaces |
| Ink | `#F2F1EE` | `#17181B` | Primary text |
| Muted | `#96999F` | `#686B72` | Secondary text |
| Rule | `#2A2D31` | `#DFDED9` | Dividers and quiet structure |
| Presence | `#86A4F8` | `#3F5FB7` | Active, current, focused—not decoration |
| Attention | `#E4B36E` | `#A86412` | Needs action |
| Danger | `#EF8793` | `#B53D4D` | Destructive/error |

Use semantic tokens in OKLCH in production, with tested sRGB fallbacks. Default to the operating
system's light/dark setting and offer a manual override.

## Type, space, and shape

- **UI and display:** the native system sans stack. It makes Viventium feel at home on each device,
  loads instantly, and keeps the app lightweight. If a custom typeface is adopted later, it must be
  bundled locally and earn its payload through a visibly better result.
- **Technical metadata:** Geist Mono or system monospace, used sparingly for times, IDs, paths, and
  evidence.
- **Type scale:** 11, 12, 14, 16, 20, 28, 40. Body copy is normally 14/1.5. Product surfaces use
  compact optical density rather than oversized dashboard typography.
- **Spacing:** a 4px base with 8, 12, 16, 24, 32, 48, and 64px steps.
- **Radius:** 9px controls, 14px sheets, 20px rare presence surfaces. Rows remain mostly cardless;
  pills are limited to short status or segmented choices.
- **Elevation:** borders first; one restrained shadow only for a transient focused sheet.

## Interaction thesis

The default surface is readable without clicking. One action reveals one deeper layer. Complex
configuration progresses in place:

`choose a signed-in source → confirm the account → connect`

First-run discovery follows a second, equally clear rhythm:

`Find everything → watch or stop discovery → review accounts → connect selected`

The app always shows current, loading, paused, stale, denied, degraded, failed, and healthy states
honestly. Every autonomous action supports interruption, recovery, provenance, and an understandable
result.

## Motion

- 120–160ms for hover/focus/press; 200–240ms for layout or sheet transitions.
- One slow low-contrast presence breath may indicate active listening or thinking; it never glows
  fluorescently or runs when the state is idle.
- Cortex activation draws one short trace from trigger to active state to contribution.
- Respect `prefers-reduced-motion`; preserve meaning with static state changes.

## Core components

- App rail and quiet page header
- Source row and category index
- Multi-account source row with named child accounts, individual switches, and Add another
- Compact all-in-one connection sheet
- Health/freshness status with plain-language failure
- Feeling Spectrum module with a shared fixed 0–100 scale, Current, Nature, and a recorded temporal
  trail for every emotion
- Emotion Trail summary with time, change, and cause
- Cortex definition row and live activation trace
- Conversation surface with evidence and worker handoff states
- Automation row with inline cycle, instruction, delivery, result, history, and Prompt Workbench
  `{{` variable autocomplete
- Empty, loading, degraded, blocked, destructive-confirmation, and recovery states
- Persistent presence dock with quiet waveform, drop-in/out, listening policy, mute, and
  availability; it is complete in MIND and compact elsewhere so it never covers working content
- Use-from-anywhere switch and add-device sheet; networking details are absent from ordinary UI
- Professional provider, browser, channel, and application marks; never placeholder initials in a
  production-facing source list when a real mark exists

## AI-specific UX rules

- Disclose when a result is generated, inferred, stale, or awaiting verification.
- Keep ordinary connection copy minimal; make access detail available one level deeper when it is
  consequential or needed for recovery.
- Keep human takeover and cancel visible during autonomous work.
- Never equate autonomous discovery with consent to connect. Discovery is interruptible; the
  account review is the authorization boundary.
- Explain which feedback changes only this result, the current state, or future behavior.
- Never represent model confidence with fake numerical precision.
- Keep provenance and evidence close to consequential claims.
- Memory and Cortex visibility belongs in one reply-anchored receipt. Its collapsed line reports
  only material context and active work; its detail answers what was provided, what the specialist
  returned, and what changed. The visual sequence is **Context & Memory → Cortices → What changed**.
  It is not a brain graph, activity dashboard, or hidden-reasoning view.

## Accessibility and implementation baseline

- Target WCAG 2.2 AA, including visible/non-obscured focus, 24px minimum pointer targets, reflow,
  accessible authentication, keyboard parity, and no color-only status.
- Use semantic HTML and accessible headless primitives such as Base UI, Radix Primitives, or React
  Aria; avoid a heavy visual component kit that dictates the brand. Use Motion only for meaningful
  presence/state transitions and respect reduced motion.
- Announce discovery progress and completion through a restrained ARIA live region. Implement
  Prompt Workbench variable suggestions as an accessible combobox with keyboard selection, and
  retain a readable text alternative for every visual Feeling trail.
- Use container queries for reusable Feelings, cortex, and receipt modules.
- Treat View Transitions as progressive enhancement, not a core dependency.

## Current official references

- [Apple design principles](https://developer.apple.com/design/human-interface-guidelines/design-principles)
- [Apple onboarding guidance](https://developer.apple.com/design/human-interface-guidelines/onboarding)
- [Apple generative AI guidance](https://developer.apple.com/design/human-interface-guidelines/generative-ai)
- [Apple materials guidance](https://developer.apple.com/design/human-interface-guidelines/materials)
- [WCAG 2.2](https://www.w3.org/TR/WCAG22/)
- [Vercel AI SDK 7](https://vercel.com/blog/ai-sdk-7)
- [Linear 2026 UI refresh](https://linear.app/changelog/2026-03-12-ui-refresh)
- [Base UI accessibility](https://base-ui.com/react/overview/accessibility)
- [Motion accessibility](https://motion.dev/docs/react-accessibility)
- [Tauri 2 capabilities](https://v2.tauri.app/security/capabilities/)
- [Tailwind CSS 4](https://tailwindcss.com/blog/tailwindcss-v4)
- [React 19.2](https://react.dev/blog/2025/10/01/react-19-2)

## Rejected baseline and forward gate — 2026-07-28

The first V0.5 dark prototype was rejected by the product owner. Its green global accent, tinted-card
stack, generic Character controls, rigid selects, verbose source details, and networking-oriented
Anywhere Access surface did not meet the V0.5 product or quality bar. Screenshot evidence from that
version is historical only and must never be described as an approved or locked brand baseline.

Every replacement candidate must demonstrate, before owner review:

1. neutral premium light and dark themes with no neon global accent;
2. a complete CHARACTER surface derived from the live Feelings instrument;
3. MIND as conversation plus Emotional State;
4. source connection as enable/disable, signed-in browser/app choice, and account confirmation;
5. Groq visibly labeled Activation detection and a frontier account visibly required for Main thinking;
6. use-from-anywhere without networking vocabulary;
7. real-browser review at 320, 768, 1024, and 1440 pixels, including keyboard, reduced motion,
   persistence, and visual inspection.

## Living-mind composition — revision 3

The V0.5 product candidate uses one continuous **living ledger** rather than a field of independent
dashboard cards. Hairline rules, aligned rows, controlled negative space, and restrained blue focus
carry hierarchy. Working content should feel like one calm personal instrument whose state is
continuously moving underneath it.

- MIND combines one conversation with Emotional State, its recent trail, and a collapsed-by-default
  **Behind this reply** receipt wherever Memory or a Cortex materially shaped a response.
- CONNECT makes one-click GlassHive discovery the first action, then reveals service accounts as
  child rows instead of duplicating a service card for every identity.
- CHARACTER follows the actual live Feelings grammar: one fixed 0–100 nine-emotion instrument,
  Current fill/cap, Nature marker, typed recorded path, Inner state, exact state capsule, readable
  reaction trail, and one focused inspector for the selected Feeling.
- AUTOMATIONS expands one row in place and reuses the Prompt Workbench schedule and variable model.
- Presence never becomes a fifth page. Its full listening policy belongs in MIND; it compacts while
  the person inspects a reply receipt and on task-heavy pages. On phones the compact control lives
  in app chrome, never over Feeling values, evidence, fields, or actions.
