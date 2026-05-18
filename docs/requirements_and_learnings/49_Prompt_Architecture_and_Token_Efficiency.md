# Prompt Architecture and Token Efficiency

**Document Version:** 0.3
**Date:** 2026-05-07
**Owner:** Viventium Core
**Status:** Phase 0 baseline and pre-compaction hardening in progress on local critical branch
**Scope:** Main Viventium prompt, surface prompts, MCP/server instructions, background cortex
activation/execution prompts, Phase B follow-up/NTA prompts, memory-context injection, and prompt
observability.

## Executive Summary

Viventium should stop treating the main agent system prompt as the place where every product rule,
tool manual, surface instruction, and operational workaround accumulates. The main prompt should
remain the conscious identity and decision policy. Capability-specific cognition should be advertised
by the owning MCP server, tool schema, surface prompt, memory/recall layer, or cortex pipeline.

This is not a string manipulation project. The supported direction is:

1. Improve prompt ownership and separation of concerns.
2. Give the model clearer, better-scoped context at the layer where it makes the decision.
3. Use structured AI decisions for follow-up surfacing and silence.
4. Add token/prompt observability before compaction so changes are evidence-driven.
5. Gate all changes with exact-model side-by-side evals and live/source drift checks.

Runtime code must not infer user intent from prompt text, provider names, agent names, schedule
names, tool substrings, or user-visible phrases. Model-owned decisions should be made from explicit
instructions, structured metadata, tool schemas, MCP instructions, and visible context.

ClaudeViv review conclusion:

- Approve the direction with surgical edits before implementation.
- Do not begin main-prompt compaction until MCP instruction ownership, prompt observability, and
  exact-model eval baselines exist.
- Prefer provider-native structured output for follow-up decisions; do not parse free-text JSON as
  the primary contract.
- Make drift gates fail closed, matching agent-sync discipline.

## Implementation Log

### 2026-05-15 Prompt Workbench Two-Way Sync

Added the first standalone local Prompt Workbench at
`viventium_v0_4/prompt-workbench/`. The workbench is intentionally outside the LibreChat fork and
does not introduce a prompt database. It imports the existing prompt registry, config/source
rendering, agent-sync helper, prompt-frame dashboard reader, git history, and exact-model eval
harness.

The workbench keeps three prompt states visible:

| State | Owner | Workbench rule |
| --- | --- | --- |
| Source | `viventium_v0_4/LibreChat/viventium/source_of_truth/prompts/` and source YAML | Edits create reviewed source drafts only; generated App Support runtime files are never authoring surfaces. |
| Live | LibreChat Mongo agent records managed by Agent Builder and `viventium-sync-agents.js` | Live changes are protected. Pull/compare surfaces drift before any import or push. |
| Evaluated | `qa/prompt-architecture/evals/prompt-bank.json` plus exact-model eval run outputs | Runs and reports are tied to prompt hashes; raw eval evidence stays private. |

Sync classification is ledger-backed and public-safe:

- `synced`: rendered source instructions match live instructions.
- `live-ahead`: live changed since the last reconciled live/source hash.
- `source-ahead`: source changed since the last reconciled live/source hash.
- `conflict`: both sides changed or there is no safe baseline for an overwrite.

The private workbench ledger lives under
`~/Library/Application Support/Viventium/private-user-data/prompt-workbench/sync-ledger.json`. It
stores ids, hashes, source commit, live version, and eval run references, not raw private prompt
text. Drafts also live under that private workbench directory and require an idempotency token from
the reviewed diff before they can be applied.

Two-way sync behavior:

- LibreChat Agent Builder edits are detected through the existing compare/pull path. Clean one-section
  live edits can become a markdown draft. Multi-section or ambiguous edits must go through manual
  target selection. Public prompt safety scanning runs before any public markdown draft can be
  applied; private-looking content is refused from the public prompt tree.
- Workbench/markdown edits write source drafts only. Pushing live uses
  `viventium-sync-agents.js push --prompts-only --dry-run` first, then a reviewed push only when the
  UI supplies the matching review token for the current dry-run.
- Conflicts block automatic import/push. The user must choose keep-live/import, keep-source/push, or
  manual merge.

The first UI implements the required operator surfaces: Prompt Flow Dashboard, Prompt Atlas, Prompt
Detail with Monaco, Live Drift Board, Eval Designer/Results, prompt-frame observability, and a
LibreChat integration panel that describes the minimal managed-agent badge contract. Promptfoo is
available only as a secondary local adapter from the canonical Viventium eval bank.

The supported local lifecycle entrypoint is `bin/viventium prompt-workbench <open|start|stop|status>`.
It builds the local bundle when needed, starts the FastAPI/static workbench on a loopback port, and
stores only PID/port/url metadata under App Support prompt-workbench state. The macOS helper's
`Advanced > Prompt Workbench` submenu calls that CLI. This keeps workbench lifecycle separate from
the Viventium stack: stopping Prompt Workbench must not stop LibreChat, Mongo, native services,
voice, or the running user-facing runtime.

### 2026-05-16 Prompt Workbench Usability And Eval Clarification

The Prompt Workbench must make the safe next action obvious when source/eval drafts are waiting.
Eval preview and live push operate on applied source only, so pending source or eval drafts block
those actions. The UI now routes blocked top-level actions to the relevant draft review surface
instead of presenting inert `Apply draft first` buttons. Stale source drafts whose target file
already matches the reviewed draft can be resolved idempotently without rewriting source; eval-bank
drafts that are semantic no-ops or formatting-only churn are refused.

Eval behavior is split into two human-facing modes:

- **Preview**: validates which eval cases would run, records a public-safe selection summary, makes
  no model call, and must not be presented as model performance.
- **Live exact-model run**: calls the canonical exact-model harness and is the path that records
  performance against prompt hashes.

The Eval Designer must default to all eval cases linked to the selected prompt across families and
surfaces. Creating or editing eval cases creates a reviewed `eval-edit` draft against the canonical
eval bank, never a direct source write, and the patch should stay focused on the target case instead
of reformatting unrelated cases. The create-new-case form must remain responsive to real browser
click and keyboard input; form text is read at save time so typing does not create source writes or
intermediate draft churn.

The former `Frames` tab is now `Prompt Traces`. A prompt trace is local metadata about a prompt run:
surface, model/provider, assembled layers, token estimates, and routing/decision metadata. The
public-safe UI must explain that concept plainly and must not expose raw private prompt text or
transcripts.

### 2026-05-14 Voice Latency Prompt-Budget Learning

Live voice latency RCA showed that a simple spoken turn can still carry a large assembled prompt
frame because voice preserves the same main agent, memory, recall, MCP, tool, background-cortex, and
surface-prompt contracts as text chat. That is a parity requirement, not accidental dead weight.

The fix direction is therefore **not** a voice-only context budget that silently removes memory or
agent instructions for calls. A voice-only budget would make voice behavior diverge from web chat
unless it was explicitly designed, disclosed, eval-gated, and documented as a product mode. The
least-risk path is shared prompt ownership cleanup:

- keep prompt-frame telemetry on the decisive voice paths so layer size, layer hashes, selected
  provider/model, and voice flags are visible without logging raw private text
- reduce duplicated main-prompt material at the shared source layer, not by cutting only the voice
  runtime path
- move tool manuals and capability details to MCP/server/tool schemas that already own those
  capabilities
- keep provider-specific voice markup in the surface prompt and shared voice capability contracts
- use provider/runtime prompt caching or prewarm where supported before deleting behaviorally
  important context
- prove every reduction with exact-model evals plus real browser/LiveKit QA

This preserves the user-visible rule: Viventium voice calls are the same agent with the same memory,
permissions, background agents, and truth boundaries unless a future product requirement explicitly
creates a different mode.

### 2026-05-09 Local QA Baseline Evidence

Ran a local QA baseline pass against the active local stack and QA account after prompt
registry, MCP-instruction ownership, Wing, telemetry, and eval-harness fixes. This is useful
engineering evidence, but it is not a public release signoff by itself: raw prompts, transcripts,
runtime logs, browser state, and connected-account artifacts remain private and must not be
published. Public release readiness still requires sanitized diffs, committed nested component
state, parent pin agreement, and a final review-only pass.

- Exact-model prompt bank: local run completed the selected bank with semantic-judge pass counts
  recorded in private evidence. Treat the public summary as a sanitized local baseline, not as raw
  reproducible model-output evidence.
- Native Chrome/Playwright surface QA: local run covered web, scheduler, Telegram gateway, voice
  gateway, Wing, and Listen-Only metadata routes with public-safe summaries only.
- LiveKit playground QA: local QA-owned call-session behavior was checked in Chrome. Public docs
  intentionally do not include raw account/session artifacts.
- Telegram bridge QA: exercised the local Telegram gateway path and the Python Telegram bridge
  renderer through QA-owned synthetic mappings without sending a real owner Telegram message.
- Prompt-frame telemetry post-patch smoke: current prompt frames cover main assembly/runtime,
  cortex activation/execution, run creation, and Phase B follow-up with `unknown_layer_names=[]`
  and populated source/runtime/compiler hashes.
- Prompt observability dashboards were regenerated in public-safe form; private full-text dashboard
  output is local-only and must stay outside public commits.

Residual limits from this closure pass:

- The QA account has Microsoft 365 connected, but Google Workspace was not connected in the local
  token store at signoff time. Google-specific read-only behavior therefore remains covered as an
  auth/availability-path check, not as a live Google-data retrieval proof.
- The Telegram `@Computer` proof deliberately used the local gateway/bridge and QA synthetic
  mapping. A true owner-originating Telegram client message was not sent because that would mutate
  the owner chat/account and conflict with QA-account isolation.
- Full Phase B provider-native structured decisioning and main prompt compaction remain future
  gates. The current branch creates the prompt source of truth, observability, eval harness, MCP
  ownership groundwork, and surface fixes needed before compaction can safely proceed.
- Claude and ClaudeViv review required two scope clarifications:
  - The branch is not Git-reviewable until the parent and nested LibreChat working-tree changes are
    committed locally; public reports currently describe local working-tree state.
  - The current prompt-bundle drift check proves live bundle vs source bundle parity, not the full
    future A/B/C runtime/source/compiled config gate.
- Pre-existing Phase B fallback text heuristics remain and must be explicitly retired or bounded in
  the structured-decisioning phase: lexical overlap insight dedupe and question-sentence stripping.

### 2026-05-09 Strict Eval Gates And Wing Surface Correction

Added stricter no-mock eval quality gates after review showed that API completion and semantic
judging were still not enough to defend prompt changes:

- Exact-model and native-surface evals now fail when distinct cases collapse to the same visible
  answer unless the duplicate is an intentional silence/suppression case or a structured runtime
  hold that later resolves with delayed/cortex evidence.
- Exact-model and native-surface evals now fail when async/tool-routed cases end in generic pending
  language without post-case evidence that the routed work produced a completed insight, callback,
  or honest limitation.
- Each eval record carries `hasRuntimeHold`, `pendingCortexStatuses`, duplicate-response quality
  failures, and unresolved-async quality failures so dashboards and reports cannot mistake transport
  completion for behavioral success.

Native QA history exposed a Wing Mode regression: ambient self-talk in a passive call could receive
supportive reflection instead of `{NTA}`. The fix lives in the Wing surface prompt, not runtime
intent matching: Wing now explicitly treats silence as the default and forbids emotional-support
responses to ambient personal speech unless the user directly addresses Viventium, asks for help, or
there is a clear time-sensitive/safety-critical reason to intervene.

### 2026-05-09 Prompt Source-Of-Truth Registry

Added the first tracked prompt-registry source-of-truth slice:

- Added `viventium_v0_4/LibreChat/viventium/source_of_truth/prompts/` as the Viventium-owned
  prompt source tree.
- Split the main Viventium agent prompt into prompt-registry sections and a composite
  `main.conscious_agent` include.
- Extracted global no-response, conversation recall, memory archivist, MCP server instructions,
  cortex activation/execution prompts, surface prompts, and Phase B follow-up ownership prompts.
- Added `promptRef` support for Viventium source YAML. Compiled/runtime YAML still receives plain
  strings so LibreChat's upstream shape stays intact.
- Added a prompt-registry compiler/validator with frontmatter checks, duplicate-id failure,
  include-cycle failure, public-tree private-pattern scanning, strict-variable support, and runtime
  placeholder preservation for LibreChat variables such as `{{current_user}}`.
- Added a compiled `prompt-bundle.json` output to the config compiler and a runtime
  `promptRegistry` loader for code-owned surface prompts. Runtime lookups use the boot-loaded
  bundle with inline fallbacks, not per-request Markdown reads.
- Added local prompt-frame JSONL file logging under a private observability directory when explicitly
  enabled, with CI/production refusal.
- Added a static prompt observatory dashboard generator with public-safe mode and private full-text
  mode.
- Added JS/Python promptRef parity coverage after ClaudeViv flagged future drift risk around
  `promptVars`, strict variables, and runtime-placeholder preservation.
- Added a Scheduling Cortex FastMCP-vs-registry instruction parity test so top-level MCP cognition
  does not drift between the server and LibreChat YAML surfaces.

This change does not compact the main prompt or change user-level live agent instructions by itself.
Compaction remains blocked behind real-surface frame-manifest evals.

### 2026-05-09 MCP Instruction Ownership Review

Official MCP, OpenAI, Anthropic, LibreChat, and FastMCP guidance all point to the same architecture:
tool capability knowledge should be advertised by the server/tool contract that owns the capability.
The main Viventium prompt should describe identity, policy, and orchestration, not copy external MCP
manuals into user-level agent instructions.

Claude review found one critical LibreChat-path gap: for `startup: false` MCPs,
`serverInstructions: true` could remain unresolved because startup inspection skips metadata fetch.
If that unresolved boolean reached prompt assembly, the context could lose the server instructions
or inject the literal text `true`.

Applied guardrail:

- `MCPManager.formatInstructionsForContext()` now accepts only non-empty string instructions or
  fetches server-provided instructions on demand for non-OAuth app-level MCPs.
- Resolved server instructions are cached for the manager lifetime.
- OAuth/user-specific MCP instructions are not fetched from app-level context; per-user facts must
  come through tool results or structured request context.
- Added a focused Jest regression suite covering unresolved boolean protection, lazy
  server-instruction fetch, filtering, OAuth skip, and string `"true"` handling.

This is still not permission to compact the main prompt. Remaining gates before compaction:

- GlassHive low-level tools must pass the MCP tool-description checklist.
- GlassHive server instructions need a parity or single-source test comparable to Scheduling Cortex.
- Native-surface evals must prove real tool selection and user-facing behavior after the main-prompt
  operational manuals are removed.
- The prompt-bundle A/B/C drift gate must prove live, compiled, and source prompt hashes agree.

### 2026-05-07 Local Critical Branch

Branch: `codex/prompt-architecture-critical`

Implemented so far:

- Phase 0: private backup, QA-account parity, and public-safe QA scaffold.
- Phase 1: provider-doc reference pack and prompt ownership audit.
- Phase 2: metadata-only prompt-frame telemetry around main, cortex, and Phase B follow-up paths.
- Phase 3: Scheduling Cortex and GlassHive MCP instruction ownership.
- Phase 3.5: MS365 and Google Workspace MCP instruction ownership, added after Claude review found
  productivity MCPs were still too skeletal for safe main-prompt compaction.
- Phase 4: no-mock exact-model eval harness baseline through the local QA account.

Important discoveries:

- Live eval transport completion is not enough; the harness initially completed 3 cases while
  extracting empty assistant text. The harness now parses assistant content arrays, stores raw SSE
  events only in the private evidence area, and fails non-silent cases with empty visible output.
- The first Phase 4 report overstated coverage. The harness now reports `partial_baseline` unless
  the full prompt bank runs, and it lists cases/surfaces covered.
- Source and compiled LibreChat hashes currently diverge after Phase 3.5. This is expected until
  runtime config is regenerated/reloaded, but it means live productivity MCP behavior is not yet
  proven against the new instructions.
- Local JWT fallback is useful for owner-machine QA but sensitive. It now requires an explicit
  local-only opt-in and refuses CI/production.
- Main prompt compaction remains blocked until live MCP instruction hash agreement, full
  exact-model coverage, real voice/Telegram/Wing/scheduler/listen-only runners, and browser QA pass.

Validated in local/targeted suites so far. These counts are engineering evidence, not final
public-release signoff until the branch is committed, public-safety scanned, and the parent/nested
component pins agree:

- Config compiler release tests: `76/76`
- Install summary plus eval-harness release tests: `35/35`
- Prompt-frame telemetry Jest tests: `7/7`
- Scheduling Cortex pytest suite: `83/83`
- Live QA-account exact-model baseline: `3/3` selected web cases, reported as partial baseline.

The working tree also contains unrelated pre-existing memory/transcript edits. They are out of
scope for this prompt-architecture implementation and must be reviewed/staged separately.

## Inputs And Evidence

### User-visible Viventium feedback, sanitized

A Telegram voice conversation surfaced these inefficiency themes:

- The main prompt appears to repeat GlassHive worker behavior across the main `Tools` section,
  MCP server instructions, and callback/run status rules.
- "Wait for cortex results" and live-data boundaries appear in multiple places.
- Voice mode injects provider-control detail that may be too large if included outside the surfaces
  that actually need it.
- Memory keys are behaviorally useful, especially working/context/me/signals, but older moments
  may need decay, promotion, or archival discipline.
- Full memory/context injection may be wasteful on simple live-data turns unless observability proves
  the injected material is being used.
- Listen-Only Mode and later memory hardening should treat transcripts as soft evidence, not live
  chat instructions or automatic stable memory.
- Conversation recall should prefer summaries for broad triage while preserving full transcript
  access for recent, hot, or quote-sensitive cases.

The raw conversation transcript is intentionally not copied into this public document because it
contains private user context.

### Prior verified RCA to preserve

The previous investigation verified these points:

| Area | Finding |
| --- | --- |
| Runtime/source drift | Live selected models differed from source-of-truth in thinking settings and voice route. |
| Main prompt bloat | GlassHive and Scheduling Cortex operational instructions live inside the main prompt. |
| MCP readiness gap | Scheduling Cortex has per-tool descriptions but no top-level FastMCP instruction layer. |
| Follow-up repeat bug | Phase B already shows the model the recent visible answer, but the decision contract is under-structured. |
| Observability drift | Product OpenAI `gpt-5.4` route worked through connected-account auth while status still reported "Connect OpenAI". |

Known validation from that run:

- LibreChat prompt/follow-up/NTA/surface Jest tests: `79 passed`
- Release/static governance tests: `28 passed`
- Scheduling Cortex tests: `68 passed`
- Voice gateway follow-up scheduler tests: `7 passed`
- Telegram bridge/NTA/voice preference tests: `111 passed`
- Productivity activation eval: `24/24 passed`
- Product-route probes passed for `openAI / gpt-5.4` and `anthropic / claude-opus-4-7`
- Follow-up micro-evals passed for redundant voice, new web fact, and Telegram question-only cases

Remaining validation gaps:

- Telegram preview test needed a clean import-environment rerun.
- Activation benchmark needed connected-account OpenAI support instead of env-key-only probing.
- There was no complete side-by-side exact-model prompt eval harness for the whole prompt stack.

## Current Prompt Ownership Map

| Layer | Current owner | Current issue | Proposed owner after fix |
| --- | --- | --- | --- |
| Conscious identity, style, truth, boundaries | Main Viventium agent prompt | Mostly valuable; should remain short and stable | Main prompt |
| Memory use rules | Main prompt plus memory runtime | Useful but too broad if full memory is injected every turn | Main prompt for policy; memory layer for retrieval tiers and budgets |
| Live data boundaries | Main prompt, cortex prompts, MCP/productivity docs | Repeated, but safety-critical | Compact main rule plus cortex/tool-specific grounding contracts |
| GlassHive operational behavior | Main prompt and `glasshive-workers-projects.serverInstructions` | Duplicated and long | GlassHive MCP server/tool instructions; main prompt keeps only capability boundary |
| Scheduling self-continuity | Main prompt and Scheduling MCP descriptions | Main prompt carries schedule manual and examples | Scheduling MCP top-level instructions and tool descriptions; main prompt keeps permission/purpose |
| Voice markup controls | `surfacePrompts.js` from shared provider capability JSON | Correctly capability-driven, but must prove it is only injected on voice/TTS paths | Surface prompt layer only |
| Wing Mode silence | `surfacePrompts.js` | Duplicates `{NTA}` language locally | Surface prompt references central no-response contract |
| No-response contract | `librechat.yaml` `viventium.no_response` plus local repeats | Central concept exists but repeated in some prompts | Single central contract plus surface-specific decision context |
| Phase B follow-up | `BackgroundCortexFollowUpService.js` | Good model-visible recent-response grounding; output contract still free text | Structured model decision envelope plus `{NTA}` compatibility |
| Background cortex activation | Source-of-truth activation prompts | Correct ownership; eval coverage must stay strong | Keep; add prompt-size and activation observability |
| Generated runtime config | Config compiler and runtime App Support output | Drift guard weaker for compiled `librechat.yaml` than agent sync | Add A/B/C compile drift gate |

## Model-Specific Prompting Requirements

### Claude Opus 4.7

Current primary main model is Claude Opus 4.7. The prompt plan should follow these requirements:

- Be clear, direct, and specific about desired output and constraints.
- Use consistent sectioning for mixed instructions, context, examples, and variable inputs.
- Keep the core prompt outcome-oriented rather than process-heavy.
- Prefer model-visible structured context over hidden runtime heuristics.
- For tool use, move detailed "what this tool does / when to use it / caveats / response shape"
  into tool and MCP definitions.
- Verify Opus 4.7 runtime parameters:
  - use the supported thinking/effort shape for the current API path
  - do not carry removed sampling/tuning parameters into Opus 4.7 requests
  - do not carry legacy `thinkingBudget`, `max_thinking_tokens`, `extended_thinking`, or old
    extended-thinking budget fields into Opus 4.7 requests

### GPT-5.4

Current background/productivity/research routes use GPT-5.4 in live configuration. The prompt plan
should:

- Give GPT-5.4 precise completion criteria and output contracts.
- Preserve provider-appropriate `reasoning_effort`, especially `xhigh` for Deep Research.
- Avoid contradictory instructions that waste reasoning tokens.
- Use explicit grounding rules for live facts and productivity data.
- Keep tool-use expectations crisp and avoid making GPT-5.4 parse a long main-agent identity prompt
  when a background cortex only needs scope, evidence, and output rules.

### GPT-5.5

GPT-5.5 was not verified as selected in current live/source configs. Treat this section as
forward-looking only. Do not migrate prompts toward GPT-5.5 norms until an exact-model eval gate
confirms parity or improvement for the product route that will actually use it.

- Re-baseline prompts before adopting it; do not carry every legacy instruction forward.
- Prefer shorter, outcome-first prompts with explicit constraints and validation rules.
- Re-evaluate low/medium effort before escalating effort by default.
- Use evals, not vibes, to decide whether compact prompts preserve Viventium behavior.

## Proposed Prompt Fixes

### Fix 1: Add prompt-layer observability before deleting text

Before compaction, every model call should be able to log a safe prompt-frame summary:

```json
{
  "event": "viventium.prompt_frame",
  "surface": "web|telegram|voice|scheduler|cortex",
  "provider": "anthropic|openAI|...",
  "model": "model-id",
  "prompt_family": "main|cortex_activation|cortex_execution|followup|memory|scheduler",
  "layer_token_estimates": {
    "main_instructions": 0,
    "global_no_response": 0,
    "memory_context": 0,
    "conversation_recall": 0,
    "surface_prompt": 0,
    "mcp_server_instructions": 0,
    "tool_schemas": 0,
    "background_context": 0
  },
  "source_hashes": {
    "agent_source": "sha256-prefix",
    "librechat_source": "sha256-prefix",
    "compiled_runtime_config": "sha256-prefix",
    "live_installed_runtime_config": "sha256-prefix",
    "compiler_version": "version-or-sha"
  },
  "flags": {
    "voice_mode": false,
    "wing_mode": false,
    "listen_only": false,
    "primary_response_mode": false,
    "auth_class": "connected_account|env_key|none|mixed"
  }
}
```

Rules:

- Log sizes, hashes, IDs, and structural metadata, not raw private prompt text.
- Full prompt text logging may exist only behind a local debug flag and must stay out of public docs
  and QA artifacts.
- Even with full prompt debug enabled, logs must scrub Telegram chat/user IDs, voice call/request
  session IDs, conversation/message IDs, local absolute paths, and credentials. Debug logs are local
  only and excluded from public export.
- Add prompt-frame counters to QA so token regressions are visible.
- Track follow-up decision outcome (`suppress`, `surface`, `surface_after_hold`, `error`) without
  logging private transcript text.

Acceptance:

- A simple weather/web turn shows exactly which prompt layers were injected.
- A voice turn shows voice prompt layer size and provider-control marker counts.
- A GlassHive delegation turn shows MCP/tool schema size separately from main prompt size.
- A scheduled Telegram run shows scheduler prompt, follow-up prompt, and delivery classification.

### Fix 2: Define a compact main prompt contract

The main prompt should keep:

- Identity and relationship stance.
- Voice/style rules that define Viventium's character.
- Truth and live-data boundaries.
- Memory-use policy at a high level.
- Tool boundary principles, not tool manuals.
- Scheduling self-continuity permission and guardrails.
- Background cortex relationship: evidence producers, not second chat surfaces.

The main prompt should remove or shrink:

- Detailed GlassHive profile/backend/run/callback mechanics.
- Long scheduling command manuals and examples.
- Repeated direct-action/cortex silence rules already owned by `activation_policy`.
- Repeated `{NTA}` mechanics already owned by `viventium.no_response`.
- Provider-specific voice markup controls.

Proposed target shape:

```text
<identity>
You are Viv...
</identity>

<style>
Brief, direct, natural, honest...
</style>

<truth_and_live_data>
Do not invent live data. Use verified tools/cortices for live facts and connected accounts.
</truth_and_live_data>

<memory_policy>
Use visible memory context naturally. Search recall when prior-chat context is needed. Never expose
memory key names.
</memory_policy>

<tool_policy>
Use the tool whose advertised capability owns the real action. Prefer verified tool results over
memory or inference. Ask only when the structured choice is genuinely ambiguous.
</tool_policy>

<self_continuity>
You may create and evolve self-continuity schedules within documented boundaries.
</self_continuity>

<background_cortices>
Answer immediately. Cortices provide evidence. Surface only useful new information.
</background_cortices>
```

Acceptance:

- Main prompt remains behaviorally recognizable in evals.
- Token size drops materially without reducing tool success.
- GlassHive/scheduling behavior still passes direct-action evals because capability knowledge moved
  to MCP/tool definitions, not because runtime code guessed user intent.

### Fix 3: Move GlassHive cognition to GlassHive MCP instructions and schemas

GlassHive should advertise:

- real browser/desktop/local file/local project/installed CLI capability
- host vs docker execution-mode semantics
- high-level `worker_delegate_once` default for routine tasks
- callback behavior and when not to poll
- user-facing language constraints
- attachment projection contract
- diagnostics-only plumbing fields

Main prompt keeps only:

```text
When a user asks you to do real work on their browser, desktop, local files/projects, installed
tools, or long-running worker surfaces, choose the connected execution tool that advertises that
capability. Do not answer from memory when a real action or inspection is requested.
```

Acceptance:

- `worker_delegate_once` remains selected for ordinary one-off real-computer tasks.
- The model does not expose worker IDs/run IDs unless diagnostics are requested.
- Background cortices stay silent on direct GlassHive actions unless they own separate scoped value.

### Fix 4: Move Scheduling Cortex details to Scheduling MCP instructions

Scheduling Cortex needs a top-level server instruction layer in addition to per-tool descriptions.
It should advertise:

- create/list/search/update/delete/preview capabilities
- injected user/agent identity
- timezone requirements
- default conversation policy behavior
- self-continuity permission and constraints
- `{NTA}`/silent scheduled-run behavior
- no schedule-name/prompt-text branching
- summary-safe list/search defaults
- detailed inspection tools for raw prompt/delivery state

Two migration anchors are load-bearing and must be present in Scheduling/GlassHive MCP instructions
before they are removed from the main prompt:

- Morning briefing starter schedule discipline: find/update the existing
  `template_id: morning_briefing_default_v1` schedule instead of creating duplicates.
- Explicit worker mention dispatch: `@codex`, `@claude`, and `@openclaw` are commands to choose the
  matching configured host-worker profile, not names to discuss.

Main prompt keeps only:

```text
You may use Scheduling Cortex for user reminders and your own self-continuity schedules. Use it when
the user asks you to remember, remind, check later, monitor, or continue work later. Stay inside the
documented guardrails: no external actions without user approval, and silence is valid when there is
nothing useful to surface.
```

Acceptance:

- Morning briefing update still finds and updates the starter schedule rather than duplicating it.
- Passive scheduled runs do not emit status chatter.
- User one-time reminders preserve catch-up/misfire behavior.

### Fix 5: Centralize no-response and upgrade follow-up to structured AI decisioning

The current `{NTA}` concept is correct. The improvement is to stop asking the model to output either
free text or `{NTA}` from a long prose prompt. The follow-up model should return a structured
decision first:

```json
{
  "decision": "suppress|surface|surface_after_hold|blocker",
  "visible_text": "string|null",
  "basis": "new_fact|resolved_blocker|stale|redundant|question_only|error",
  "confidence": "low|medium|high"
}
```

Transport requirement:

- Anthropic/Claude routes should use provider-native tool-use or an equivalent typed response
  mechanism so the SDK validates the decision envelope.
- OpenAI/GPT routes should use `response_format` with JSON Schema where available.
- Free-text JSON parsing is allowed only as a documented fallback path for a provider or runtime
  surface that cannot use native structured output.

Runtime validates the shape and maps:

- `suppress` -> `{NTA}` for existing suppression paths
- `surface` -> persist/speak/send `visible_text`
- `surface_after_hold` -> persist a new visible assistant follow-up after a deliberate hold or
  `{NTA}` Phase A marker. It must not edit, overwrite, or replace the Phase A message.
- `blocker` -> surface concise failure details when errors change the user outcome

This is not semantic string matching. The model decides novelty from visible recent response,
newer conversation state, and background evidence. Runtime only validates schema and preserves
backward compatibility.

Acceptance:

- The repeated-follow-up examples resolve to `suppress`.
- Background results with genuinely new facts resolve to `surface`.
- Deferred-primary/hold flows resolve to `surface_after_hold` and append a new assistant message.
- Real failures never disappear behind silence.

### Fix 6: Replace text-overlap dedupe with evidence-aware grouping

Current follow-up code contains a lexical overlap dedupe over background insights. That is not user
intent NLU, but it is still a brittle semantic shortcut in the cognition path.

Preferred replacement:

- Cortices emit structured `claim_id`, `source_kind`, `tool_call_id`, `object_id`, or `topic_hint`
  when available.
- The follow-up prompt receives grouped evidence and asks the model to decide whether groups add new
  user-visible value.
- If structured grouping is absent, pass the evidence through and let the follow-up decision model
  suppress redundancy.

Sequencing rule:

- Do not remove the existing lexical dedupe until cortex emission contracts and execution prompts
  already produce structured grouping metadata. Otherwise the previous multi-cortex amplification
  failure can return.

Acceptance:

- Multiple cortices reporting the same email/tool fact produce one user-visible continuation or
  silence.
- No runtime word-overlap threshold decides semantic novelty.

### Fix 7: Keep voice controls surface-scoped and capability-driven

Voice provider controls should stay out of the main prompt. The shared Cartesia Sonic-3 and xAI TTS
capability contracts are the source of truth for provider-specific voice markup.

Improvements:

- Add prompt-frame evidence proving Cartesia emotion/tag lists and xAI speech tags are injected only
  when the selected voice/TTS route needs that provider dialect.
- Consider a two-tier voice prompt after evals:
  - default: base voice rules plus primary/high-reliability controls
  - advanced: full provider capability list when expressive control is explicitly enabled or when
    the provider route requires it
- Keep runtime validation capability-driven. Runtime may preserve, sanitize, segment, and validate
  model-authored provider markup. It must not invent emotion from heuristics. xAI TTS has no
  Cartesia-style emotion parameter, so the xAI branch may only expose documented xAI speech tags and
  natural-language tone guidance.
- User-facing provider labels should stay simple even when model-facing prompt branches are precise:
  show `xAI` in voice pickers, while keeping prompt/runtime wording explicit about standalone xAI
  TTS versus the legacy Grok Voice Agent adapter.

Acceptance:

- Voice/TTS quality does not regress.
- Non-voice text turns do not carry voice provider control tokens.
- `What's up?` style whitespace preservation remains covered by voice TTS tests.
- Marker-count observability distinguishes generation omission from downstream stripping.
- If a two-tier voice prompt ships, evals must exercise every provider-control marker declared in
  the shared voice capability contract before the split is accepted.
- Provider dialects remain isolated: Cartesia prompts never leak into xAI routes, xAI tags never
  leak into Cartesia routes, and OpenAI/ElevenLabs routes prohibit provider markup entirely.

### Fix 8: Tier memory context instead of dumping everything blindly

Memory should be model-useful, not merely present.

Proposed tiers:

| Tier | Inject by default? | Purpose |
| --- | --- | --- |
| Core profile card | Yes, compact | Durable identity/preferences needed to sound continuous |
| Working/context card | Yes, bounded and fresh | Current active state |
| Signals/me card | Yes, compact | Interaction style and patterns |
| Moments | No, selected | Exact quotes or emotionally important context only when relevant |
| Drafts | Conditional | Active work/project continuation |
| Conversation recall summaries | Conditional | Prior-chat triage before full recall |
| Full raw transcript/context | Tool/explicit retrieval | Recent/hot/quote-sensitive cases only |

Model-owned retrieval stays intact:

- The model should know when to search recall or read deeper context.
- Runtime should provide tools/sections and retrieval budgets, not keyword gates.
- Listen-Only transcripts remain soft ambient evidence for memory hardening, not user-authored chat.

Memory hardener ownership:

- This document owns prompt/context injection tiers.
- Detailed hardener behavior changes such as `moments` decay, promote/archive gates, consolidation,
  transcript corroboration, and quote-sensitive raw access belong in `20_Memory_System.md`.
- If this proposal is approved, update `20_Memory_System.md` in the same implementation plan and
  cross-link the two documents instead of duplicating hardener rules here.

Acceptance:

- Simple live-data turns show reduced memory-token load.
- Recall tests still recover recent corrections and exact quotes.
- Transcript evidence cannot overwrite stable identity without corroboration.

### Fix 9: Add `librechat.yaml` compile drift gate

Agent sync already has compare/dry-run discipline. Generated `librechat.yaml` should get an
equivalent gate:

```text
A: live runtime config
B: tracked source-of-truth
C: newly compiled output
```

The gate should show:

- prompt-affecting diff
- model/provider diff
- MCP server instruction diff
- global `viventium` prompt/config diff
- memory/cortex/surface prompt diff
- hashes and token estimates

The gate must fail closed:

- Non-dry-run compile/deploy/sync operations block when live/source/compiled prompt-affecting drift
  exists and has not been explicitly reviewed.
- A follow-up acknowledgement flag may be used only after the A/B/C diff was already presented and
  accepted, mirroring the existing agent-sync compare-reviewed discipline.

Acceptance:

- No prompt/config deployment can silently leave live runtime using stale installed behavior.
- Drift between source and live voice model route is visible before sync.

### Fix 10: Fix model/status observability

Status checks must verify the same auth path the product uses.

Requirements:

- If product calls use connected-account OpenAI, readiness probes must test connected-account
  initialization, not only env API keys.
- If a provider route is configured but unauthenticated, status should identify the exact route and
  missing auth class.
- If a model probe succeeds but a UI status says "connect account", tests should fail.

Acceptance:

- `openAI / gpt-5.4` route health agrees with actual runtime product probes.
- MS365/Google MCP readiness distinguishes server started, OAuth connected, and tool call usable.

## Evaluation Plan

### Exact-model side-by-side harness

Build an eval runner that imports the real prompt builders and runs live selected routes:

- main Viventium on Claude Opus 4.7
- voice route as actually selected live
- GPT-5.4 background/productivity/research routes
- fallback routes where configured

Each prompt change must run old vs proposed prompt variants with the same sanitized inputs.

### Required eval suites

| Suite | Must prove |
| --- | --- |
| Main identity/style | Viv remains brief, natural, direct, and non-corporate. |
| Live data | No weather/news/market/email/calendar facts without verified tool/cortex evidence. |
| GlassHive | Real-computer/browser/local-file tasks select GlassHive without exposing plumbing. |
| Scheduling | Reminders, starter morning briefing edits, passive checks, and self-continuity schedules work. |
| Phase B follow-up | Redundant, stale, question-only, new-fact, blocker, and replace-hold cases classify correctly. |
| Voice | Spoken output stays natural, short, markup-safe, and TTS-safe. |
| Wing/Listen-Only | Wing defaults to silence; Listen-Only bypasses live agent/tool/memory paths. |
| Memory | Compact tiers preserve recall, exact quote recovery, and stable preference behavior. |
| Productivity cortices | Google/MS365 scopes do not fabricate outside-provider facts. |
| Token efficiency | Prompt-layer token budgets decrease without behavior regression. |

### MCP tool-description checklist

Before moving capability text out of the main prompt, Scheduling and GlassHive MCP tool descriptions
must each state:

- what the tool does
- when to use it
- when not to use it
- required and optional inputs
- output shape and high-signal fields
- common failure/blocker states
- idempotency or duplicate-prevention expectations
- surface/callback behavior when user-visible output is delayed

### Observability acceptance

Prompt changes are not accepted unless QA can show:

- before/after layer token estimates
- source/compiled/live runtime config hashes
- selected model/provider per surface
- follow-up decision outcome distribution
- NTA/silence rates by surface
- tool-call selection rates for direct-action tasks
- provider-control marker counts for voice
- no raw private transcript or secret leakage in public artifacts

## Rollout Plan

### Phase 0: Documentation and logging design

- Approve this proposal.
- Add prompt-frame logging in safe metadata-only form.
- Add docs for prompt ownership and prompt-frame schema.
- Do not compact prompts yet.

### Phase 1: MCP instruction readiness

- Add Scheduling Cortex top-level MCP/server instructions.
- Audit GlassHive MCP instructions and tool descriptions against the GlassHive requirements doc.
- Apply the MCP tool-description checklist to every Scheduling and GlassHive tool that carries
  prompt-cognition responsibility.
- Add tests that direct-action behavior still works from tool/MCP visibility.

### Phase 2: Exact-model eval harness

- Build old-vs-new prompt eval runner.
- Support connected-account OpenAI paths.
- Add synthetic public-safe eval fixtures.
- Establish baseline scores and token budgets.

### Phase 3: Follow-up structured decision

- Add structured follow-up decision output.
- Use provider-native structured output as the primary transport: Anthropic tool-use or typed
  response mechanism, OpenAI JSON Schema response format where available.
- Keep `{NTA}` compatibility.
- Add evals for repeat/stale/new/blocker/replace-hold cases.
- Add cortex emission grouping metadata before removing brittle overlap dedupe.

### Phase 4: Main prompt compaction

- Move duplicated GlassHive/Scheduling detail out of main prompt.
- Keep identity, style, truth, memory, live-data boundaries, and self-continuity purpose.
- Run full side-by-side evals before syncing.

### Phase 5: Memory-context tiering

- Add prompt-frame evidence for current memory load.
- Introduce compact cards and retrieval tiers.
- Add the memory hardener decay/promote/archive proposal and tests in `20_Memory_System.md`, with a
  cross-link from this doc.
- Preserve full transcript access for hot/recent/quote-sensitive recall.

### Phase 6: Drift and status gates

- Add compiled `librechat.yaml` A/B/C prompt/config diff.
- Fix provider readiness probes to match product auth routes.
- Add CI/local QA for false provider-action-required status.

## Non-Goals

- No regex or keyword matching for user intent.
- No provider-label, agent-name, prompt-text, schedule-name, or tool-substring branching.
- No raw personal transcript copied into public docs or QA artifacts.
- No prompt compaction before MCP ownership and eval coverage exist.
- No source-only sync without live/source/generated drift review.

## Initial File Anchors

- Main Viventium prompt: `viventium_v0_4/LibreChat/viventium/source_of_truth/local.viventium-agents.yaml`
- Global Viventium prompt/config: `viventium_v0_4/LibreChat/viventium/source_of_truth/local.librechat.yaml`
- Surface prompts: `viventium_v0_4/LibreChat/api/server/services/viventium/surfacePrompts.js`
- Follow-up prompt/adjudication: `viventium_v0_4/LibreChat/api/server/services/viventium/BackgroundCortexFollowUpService.js`
- Background cortex activation/execution: `viventium_v0_4/LibreChat/api/server/services/BackgroundCortexService.js`
- Scheduling Cortex MCP: `viventium_v0_4/LibreChat/viventium/MCPs/scheduling-cortex/scheduling_cortex/server.py`
- Config compiler: `scripts/viventium/config_compiler.py`
- Agent sync gate: `viventium_v0_4/LibreChat/scripts/viventium-sync-agents.js`

## External Prompting References

- OpenAI GPT-5.5 prompt guidance: `https://developers.openai.com/api/docs/guides/prompt-guidance?model=gpt-5.5`
- OpenAI MCP/connectors guidance: `https://developers.openai.com/api/docs/guides/tools-connectors-mcp`
- OpenAI eval best practices: `https://developers.openai.com/api/docs/guides/evaluation-best-practices`
- Anthropic Claude Opus 4.7 docs: `https://platform.claude.com/docs/en/about-claude/models/whats-new-claude-4-7`
- Anthropic Claude prompting best practices: `https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices`
- Anthropic tool definition guidance: `https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools`

## Approval Questions

1. Approve Phase 0 and Phase 1 before any main prompt compaction?
2. Approve provider-native structured output as the primary follow-up decision transport, with
   text-JSON only as fallback?
3. Approve keeping memory injection tiers here while moving hardener behavior details into
   `20_Memory_System.md`?
4. Should voice advanced provider controls remain always available in voice mode, or should the
   two-tier prompt be eval-gated behind an explicit expressive-voice setting?
