<!-- VIVENTIUM START
Purpose: Single source of truth for LibreChat v0.8.3 configuration alignment in Viventium.
Scope: Local/source-of-truth LibreChat YAML, env parity, deferred tool mechanics, and feature recommendations.
VIVENTIUM END -->

# LibreChat v0.8.3 Config Alignment

## Purpose

This document is the single source of truth for how Viventium should use LibreChat `v0.8.3` configuration and capability features.

It covers:

- what the important `v0.8.3` / config `1.3.x` features actually are
- how `deferred_tools` works mechanically
- what is currently enabled locally
- what was changed on 2026-03-11
- what should stay on, stay off, or be enabled later

## Authoritative Sources

Official LibreChat sources used for this alignment pass:

- [LibreChat v0.8.3 changelog](https://www.librechat.ai/changelog/v0.8.3)
- [LibreChat Config v1.3.4 changelog](https://www.librechat.ai/changelog/config_v1.3.4)
- [LibreChat Config v1.3.5 changelog](https://www.librechat.ai/changelog/config_v1.3.5)
- [LibreChat deferred_tools docs](https://www.librechat.ai/docs/configuration/librechat_yaml/object_structure/deferred_tools)
- [LibreChat MCP Server Credential Variables docs](https://www.librechat.ai/docs/configuration/librechat_yaml/object_structure/mcp_settings)

Code/source-of-truth inputs used in this repo:

- clean upstream LibreChat `v0.8.3`
- Viventium frozen source commit `742660756b58e8f24e7c4c4f78798b8b5aaa2541`
- local runtime YAML:
  - `viventium_v0_4/LibreChat/librechat.yaml`
  - `viventium_v0_4/LibreChat/viventium/source_of_truth/local.librechat.yaml`

## What Was Changed On 2026-03-11

### Implemented

The local/source-of-truth config was updated to enable current LibreChat capabilities that align with Viventium goals:

- enabled `deferred_tools`
- enabled `programmatic_tools`
- enabled `context`
- added `GOOGLE_API_KEY` env parity alongside `GOOGLE_KEY` / `GEMINI_API_KEY`
- added explicit local `VIVENTIUM_CALL_SESSION_SECRET` parity, synced from the root local stack secret, so Telegram bridge auth works when the `v0.8.3` backend is started directly from the worktree

Changed files:

- `viventium_v0_4/LibreChat/librechat.yaml`
- `viventium_v0_4/LibreChat/viventium/source_of_truth/local.librechat.yaml`
- `viventium_v0_4/LibreChat/.env`
- `viventium_v0_4/LibreChat/.env.example`

### Why

The previous local YAML carried forward an older explicit capabilities list. That explicit list overrode newer LibreChat defaults and accidentally disabled features that now fit Viventium well:

- `deferred_tools` helps large MCP surfaces
- `context` matches Viventium's document-heavy workflows, OCR, and recall
- `programmatic_tools` fits Viventium's code interpreter and agent-tool orchestration direction

## How `deferred_tools` Actually Works

This is the exact mechanism, not a marketing summary.

### Conceptually

`deferred_tools` is **not** the same thing as MCP `startup: false`.

- `startup: false` delays MCP server inspection/connection at app startup
- `deferred_tools` delays whether specific tool schemas are actually bound into the model-facing tool set until they are discovered

That means your original understanding was materially correct: this feature is about avoiding immediate exposure/binding of all tools at once, especially for large MCP surfaces.

### Preconditions

For `deferred_tools` to matter, all of these must be true:

1. Global agent capability `deferred_tools` is enabled in `librechat.yaml`
2. The agent has tools selected
3. Specific tools are marked with `tool_options[toolId].defer_loading: true`
4. The run is using event-driven tool execution

For Viventium's large operational tool set, deferred discovery must remain request-scoped and usable
inside the same model invocation that discovers a tool. The fallback binding path resolves the
current event-driven tool set dynamically; it must not snapshot tools before discovery or mutate a
shared global binding that could leak one request's tools into another. `file_search` remains eager
for recall continuity. GlassHive keeps `workspace_launch`, `workspace_status`, and `workspace_wait`
eager as its stable cross-surface gateway; bulk operational schemas use
`tool_options.defer_loading: true` and MCP-owned instructions direct scoped `tool_search` discovery.
Agent compare/sync/reload must preserve `tool_options` as protected structured configuration.
Optional handoff-agent initialization failures must be isolated structurally: remove the failed
participant and its incident edges before graph compilation while preserving the main agent and
other healthy participants. A configured provider-auth fallback may retry initialization once for
structured authentication/rate-limit failures, but never for cancellation or graph/tool invariants.

Direct LibreChat startup and the full-stack launcher must share the caller-selected Python
interpreter for generated config and prompt-registry compilation. A host `python3` upgrade must not
silently bypass the dependency-complete runtime selected by the outer launcher.

### Mechanical Flow

1. **Tool registry is built**
   - `buildToolRegistry()` copies selected tool definitions into a registry and preserves `defer_loading`
   - File: `packages/api/src/tools/classification.ts`

2. **Deferred tool capability is checked**
   - `buildToolClassification()` computes `hasDeferredTools`
   - If deferred tools exist and the capability is enabled, it adds `tool_search`
   - File: `packages/api/src/tools/classification.ts`

3. **Serializable tool definitions are passed into agent initialization**
   - `initializeAgent()` stores `toolDefinitions`, `toolRegistry`, and `hasDeferredTools`
   - File: `packages/api/src/agents/initialize.ts`

4. **Agent runtime filters what gets bound**
   - In `AgentContext.getEventDrivenToolsForBinding()`, any direct-call tool with `defer_loading === true` is excluded from binding unless it has already been discovered
   - File: `node_modules/@librechat/agents/src/agents/AgentContext.ts`

5. **The model can still call `tool_search`**
   - `tool_search` is the discovery doorway for deferred tools
   - It searches the registry and returns matching tool names

6. **Discovered tools become eligible**
   - Prior `tool_search` results are parsed from history
   - Discovered tool names are tracked and their `defer_loading` behavior is overridden for subsequent turns
   - File: `packages/api/src/agents/run.ts`

7. **Message formatting preserves discovered-tool history**
   - `formatAgentMessages()` dynamically expands the valid tool set when it sees `tool_search` output
   - File: `node_modules/@librechat/agents/src/messages/format.ts`

### Practical Consequence

With `deferred_tools` enabled:

- the agent can start with a smaller directly bound tool surface
- the model uses `tool_search` to discover relevant deferred tools
- once discovered, those tools stay valid in later turns
- this is especially useful when an MCP server exposes a large number of tools
- a small stable gateway can remain eager so terse requests and follow-ups never depend on the model
  first discovering the server's primary launch/status/wait contract

### What It Does Not Mean

`deferred_tools` does **not** mean:

- "all tool metadata disappears from the system forever"
- "MCP servers are never connected until the user manually clicks connect"
- "tool execution is disabled until a full page reload"

It is a discovery-and-binding strategy, not a total removal of tool metadata from the runtime.

## Latest/Greatest Feature Surface Relevant To Viventium

These are the important current LibreChat features/config levers for Viventium.

### Interface / UX

- `interface.parameters: true`
  - exposes modern model controls like OpenAI `reasoning_effort`, Google `thinkingLevel`, Anthropic `effort`
- `interface.multiConvo: true`
  - supports multi-threaded work patterns
- `interface.memories: true`
  - aligns with Viventium memory system
- `interface.temporaryChat: true`
  - useful for short-lived, low-persistence sessions
- `interface.fileCitations: true`
  - important for trust and grounded document interactions
- `interface.mcpServers.create: true`
  - enables user-created MCP servers with trust confirmation

### Agent Capabilities

- `deferred_tools`
  - deferred discovery/binding for large tool surfaces
- `programmatic_tools`
  - exposes `run_tools_with_code` path when tools are configured for code execution
- `execute_code`
  - code interpreter path
- `file_search`
  - document retrieval / search
- `web_search`
  - external search grounding
- `actions`
  - OpenAPI / action tools
- `artifacts`
  - structured artifact generation/editing
- `context`
  - native file/context handling
- `tools`
  - baseline tool support
- `chain`
  - multi-step agent/tool chaining
- `ocr`
  - OCR/document parsing pipeline

### MCP Configuration

- `mcpServers.<name>.startup: false`
  - startup laziness for MCP connection/inspection
- `mcpSettings.allowedDomains`
  - SSRF-relevant allowlist for remote MCP endpoints
- credential variables / user vars for MCP
  - useful for user-created or env-driven MCP setups

### Model Specs

`modelSpecs.list[].preset` can carry more than endpoint/model:

- `reasoning_effort`
- `reasoning_summary`
- `thinkingLevel`
- `effort`
- `maxContextTokens`
- `artifacts`
- `tools`
- `useResponsesApi`
- `web_search`

This means model specs can be used not only for curated model menus, but also for curated default behavior profiles.

### GPT-5.6 Agent Builder Contract

As of 2026-07-09, the supported OpenAI GPT-5.6 picker family is:

- `gpt-5.6` (alias to flagship Sol)
- `gpt-5.6-sol`
- `gpt-5.6-terra`
- `gpt-5.6-luna`

The launcher publishes all four IDs for direct API-key inventories, and LibreChat's fallback catalog
carries the same list for offline/failed discovery. The ChatGPT/Codex connected-account route is a
distinct provider surface: the 2026-07-09 QA account probe accepted `gpt-5.6-sol` and
`gpt-5.6-terra`, rejected the generic `gpt-5.6` alias with an explicit unsupported-model response,
and did not resolve `gpt-5.6-luna`. Its generated inventory therefore exposes only Sol and Terra,
with Sol first. Do not silently remap a configured model. An explicit operator model-list override
remains authoritative.

Agent Builder must default a newly selected GPT-5.6 model to `useResponsesApi: true` when the field
is unset, persist that visible parameter with the agent, and apply the same default for API-created
agents. An explicit user choice remains authoritative. This follows OpenAI's GPT-5.6 guidance to use
Responses for reasoning, tools, and multi-turn workflows. Chat Completions with function tools is
compatible only at effective reasoning `none`.

The July 9, 2026 built-in model migration is a separate, evaluated source/compiler/runtime change:
the conscious agent and quality-first cortices use explicit Sol; balanced and latency-sensitive
cortices use explicit Terra; every text route uses Opus 4.8 fallback; and the voice route remains
Grok 4.3. The exact map and efforts live in `02_Background_Agents.md`. This does not add Pro mode,
persisted reasoning, Programmatic Tool Calling, explicit caching, or multi-agent orchestration.
There is no `gpt-5.6-pro` model slug; Pro is a reasoning mode.

Official sources:

- [Using GPT-5.6](https://developers.openai.com/api/docs/guides/latest-model)
- [GPT-5.6 migration guide](https://developers.openai.com/api/docs/guides/upgrading-to-gpt-5p6-sol)

### OCR / Files

- `ocr.strategy: document_parser`
  - built-in document parsing path
- `fileConfig`
  - endpoint-specific file limits and mime support

For Viventium, this matters because document-heavy workflows are a core product direction.

## Current Local Config Status

### Enabled And Recommended

- `parameters`
- `presets`
- `multiConvo`
- `memories`
- `temporaryChat`
- `agents`
- `prompts`
- `mcpServers.create`
- `webSearch`
- `fileSearch`
- `ocr: document_parser`
- agent capabilities:
  - `deferred_tools`
  - `programmatic_tools`
  - `execute_code`
  - `file_search`
  - `web_search`
  - `artifacts`
  - `actions`
  - `context`
  - `tools`
  - `ocr`
  - `chain`

### Enabled But Should Be Watched

- none at the moment in the local profile

### Intentionally Off

- `remoteAgents.use`
- `remoteAgents.create`
- `remoteAgents.share`
- `remoteAgents.public`
- `marketplace.use`
- public sharing for prompts, agents, and MCP servers

These are intentionally conservative and align with Viventium’s preference for a curated, controlled experience over broad public/distributed surfaces.

## Recommendations Aligned With Viventium Goals

### Turn On / Keep On

1. Keep `deferred_tools` on.
   - Best fit for Viventium because MCP surfaces are growing and context discipline matters.

2. Keep `context` on.
   - Viventium is document-heavy and recall-heavy. Disabling native context support fights the product direction.

3. Keep `programmatic_tools` on.
   - It is aligned with the code interpreter vision and does not force usage unless tools are configured for code execution.

4. Keep `interface.parameters` on.
   - This exposes current model tuning knobs without hardcoding them into prompts.

5. Keep `mcpServers.create` on, with trust confirmation.
   - This aligns with the MCP-first direction while preserving safety friction.

6. Keep `ocr.strategy: document_parser`.
   - Strongest local default for reliability and zero-extra-credential setup.

### Keep Off

1. Keep `remoteAgents` off for now.
   - Viventium is still optimizing core agent quality and orchestration. Remote/distributed agent surfaces add complexity before the local core is fully settled.

2. Keep `marketplace` off.
   - Public marketplace discovery does not align with the current curated/private product direction.

3. Keep public sharing for prompts/agents/MCP off.
   - Better privacy and lower accidental surface area.

### Recommended Next Alignment Step

1. Consider curated `modelSpecs` defaults instead of global hardcoding.
   - Example:
     - GPT-5 mini: low/auto reasoning for responsiveness
     - Gemini 3.1 Pro: medium `thinkingLevel`
     - Claude Sonnet/Opus: medium `effort`
   - Recommendation:
     - leave these user-selectable for now
     - only hardcode model defaults once latency/cost/quality tradeoffs are explicitly chosen

2. Consider adding one real Playwright regression for:
   - deferred MCP tool discovery flow
   - MCP OAuth connect/reconnect flow
   - artifact generation/editing flow

### Applied Hardening

- `ALLOW_SHARED_LINKS_PUBLIC=false`
  - adopted locally on 2026-03-11
  - aligns better with upstream security posture and Viventium's privacy-sensitive direction

## Key Distinctions To Remember

### `deferred_tools` vs `startup: false`

- `deferred_tools`
  - per-agent capability
  - per-tool `defer_loading`
  - affects tool discovery/binding to the model
- `startup: false`
  - per-MCP-server config
  - affects startup inspection/connection behavior

These solve different problems and should not be confused.

### Parameters UI vs Hardcoded Defaults

- `interface.parameters: true` exposes user/operator controls
- `modelSpecs.preset.*` can impose curated defaults

For Viventium, exposing the controls is the correct first move. Hardcoding defaults should come only after product decisions about latency, quality, and cost.

## Bottom Line

For Viventium on LibreChat `v0.8.3`, the best current alignment is:

- enable modern agent capabilities (`deferred_tools`, `programmatic_tools`, `context`)
- keep MCP startup laziness where it helps reliability
- keep public/distributed surfaces conservative
- expose parameter controls without over-hardcoding model behavior
- continue using explicit git-tracked YAML and env parity as the source of truth

That gives Viventium the latest useful LibreChat capabilities without drifting away from the project’s core principles of simplicity, modularity, and controlled behavior.
