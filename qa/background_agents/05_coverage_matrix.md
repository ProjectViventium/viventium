# Background Agent Coverage Matrix

## Current Matrix

| Agent | Primary Positive Coverage | Negative / Boundary Coverage | Runtime Notes |
| --- | --- | --- | --- |
| Background Analysis | `ACT-01`, `ACT-07`, `ACT-15`, `ACT-17`, `ACT-18`, `ACT-19`, `ACT-20`, `ACT-36` | `ACT-12`, `ACT-21`, `ACT-36` | Known to over-activate on some broad analysis prompts; benchmark tracks spillover explicitly. |
| Confirmation Bias | `ACT-02`, `ACT-13`, `ACT-15`, `ACT-18`, `ACT-19`, `ACT-20`, `ACT-36` | `ACT-12`, `ACT-14`, `ACT-21`, `ACT-36` | Must stay distinct from generic analysis and emotional prompts; latest-user-message control prevents stale repeated activation from history. |
| Red Team | `ACT-01`, `ACT-02`, `ACT-13`, `ACT-15`, `ACT-17`, `ACT-18`, `ACT-19`, `ACT-20`, `ACT-35`, `ACT-36` | `ACT-12`, `ACT-21`, `ACT-35` negative control, `ACT-36` | Challenge pressure should not fire on pure tool/capability requests, pure decision-method education, or stale older requests. |
| Deep Research | `ACT-03`, `ACT-36` | `ACT-12`, `ACT-27`, `ACT-36` | Shipped specialist remains capable, but main-agent auto-activation is disabled in the GlassHive broker-first local baseline. |
| MS365 | `ACT-09`, `ACT-11`, `ACT-23`, `ACT-24`, `ACT-25`, `ACT-26`, `ACT-36` | `ACT-12`, `ACT-25` negative controls, `ACT-27`, `ACT-36` | Provider-only clarification is a required regression case; source/live tool arrays must include MS365 MCP tools; in the broker-first local baseline the main agent no longer auto-activates MS365 as a background cortex. |
| Parietal Cortex | `ACT-05`, `ACT-36` | `ACT-12`, `ACT-36` | Math/statistics only. |
| Pattern Recognition | `ACT-08`, `ACT-36` | `ACT-12`, `ACT-36` | Requires multi-turn behavioral span or explicit pattern ask. |
| Emotional Resonance | `ACT-06`, `ACT-36` | `ACT-12`, `ACT-36` | Distinguish emotional disclosure from analytical strategy talk and strict output-shape work. |
| Strategic Planning | `ACT-07`, `ACT-15`, `ACT-17`, `ACT-18`, `ACT-19`, `ACT-20`, `ACT-36` | `ACT-12`, `ACT-21`, `ACT-36` | Planning/roadmap scope only; stale prior planning requests are context, not a fresh activation trigger. |
| Viventium User Help | `ACT-04`, `ACT-36` | `ACT-12`, `ACT-36` | Must not fire on generic factual, operator-diagnostic, or research requests. |
| Google | `ACT-10`, `ACT-11`, `ACT-23`, `ACT-24`, `ACT-25`, `ACT-26`, `ACT-36` | `ACT-12`, `ACT-25` negative controls, `ACT-27`, `ACT-36` | Concrete Google Workspace action required; source/live tool arrays must include Google Workspace MCP tools; in the broker-first local baseline the main agent no longer auto-activates Google as a background cortex. |

## Interpretation

- Coverage in this matrix is activation coverage, not full execution QA.
- Cases with outcome assertions (`ACT-13`, `ACT-14`, `ACT-15`, `ACT-16`, `ACT-17`, `ACT-18`, `ACT-19`, `ACT-20`, `ACT-21`, `ACT-22`, `ACT-23`, `ACT-24`, `ACT-25`, `ACT-26`, `ACT-27`, `ACT-33`, `ACT-34`, `ACT-35`, `ACT-36`, `ACT-37`, `ACT-38`, `ACT-39`) are promoted incident regressions. They
  are not satisfied by an activation-only pass; QA must verify user-visible quality, named cortex
  visibility, durable `messages.content` persistence, first-response speed, and preservation of the
  original Phase A parent answer when background cards attach.
- `ACT-21` specifically protects the configurable `activation.max_history` feature: history may
  provide context, but the latest human/user message is the activation decision subject.
- `ACT-22` protects QA observability itself: visible provider/auth environment blockers must be
  reported as blocked evidence, not as ambiguous missing-conversation failures.
- `ACT-23` protects the tool-cortex direct-action handoff: runtime hold text plus a successful Phase B
  follow-up is a continuing background workflow, not a failed provider response.
- `ACT-35` protects Red Team's decision-method stack: explicit Socratic/no-bullshit/premortem asks
  on a concrete plan activate the Red Team with method-lens output, while pure method education stays
  quiet.
- `ACT-36` protects the whole classifier topology: exact-runtime evaluation covers every cortex,
  separates semantic accuracy from provider availability/latency, and rejects sibling leakage,
  stale-turn activation, and retired activation-model defaults.
- `ACT-37` protects every cortex card against mid-turn interruption and write reordering: status
  snapshots persist incrementally, queued writes coalesce, and the final snapshot is authoritative.
- `ACT-38` protects fallback availability when a provider client ignores cancellation: the local
  per-attempt deadline, not provider cooperation, advances the fallback chain.
- `ACT-39` protects the source/config/runtime prompt boundary: registry prompt-reference objects
  must validate and resolve before use, never degrade to `[object Object]`.
- `ACT-24` protects live productivity evidence: Google/MS365 cortices must have their provider-owned
  MCP tools attached so inbox/status requests do not degrade to recall-only synthesis when auth is
  otherwise available.
- `ACT-25` protects generic plural/all-inbox requests: both productivity cortices activate unless
  the latest user message or immediate provider clarification narrows the provider.
- `ACT-26` protects Phase B fallback and metadata: provider-stage failures before tool completion
  should preserve tool metadata and retry configured fallback, while MCP/tool/auth failures remain
  non-retryable.
- `ACT-27` protects the GlassHive broker-first retirement policy: Deep Research, MS365, and Google
  remain shipped specialists but are disabled as main-agent background activations.
- `ACT-33` protects the first visible main-agent answer from raw provider plumbing: recoverable
  provider failures before visible text must use a configured fallback once or show a classified
  blocker instead of an opaque LangChain/model-rate-limit bubble.
- `ACT-34` protects the first visible main-agent answer from stream/canonical mismatch: if a user
  surface already saw Phase A text, canonical persistence must be repaired before Phase B and Phase B
  must record a silent suppressed decision rather than deterministic fallback over the visible answer.
- Productivity agents require separate execution and connected-account verification after activation.
- Provider and real-browser evidence for the current shipped activation family is recorded in:
  - `qa/background_agents/visible_cards_browser_qa_2026-05-10.md`
  - `qa/background_agents/activation_reliability_2026-04-12.md` records the Groq-first benchmark
    baseline; later VPN-related failures are provider-reachability QA issues, not a reason to
    promote xAI into the default fast path.
