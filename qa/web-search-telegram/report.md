# Telegram Web Search QA Report

Date: 2026-04-21
Status: pass

## Incident

Telegram reported that web search was dead. The same install had the built-in main agent still
showing `web_search` in persisted live state, which made the failure look like a Telegram or agent
sync problem even though the canonical runtime switch was off.

## Root Cause

- Canonical App Support config did not enable `integrations.web_search`, so compile output disabled
  the live search surface.
- The compiler emitted `interface.webSearch: false`, removed the top-level `webSearch` block, and
  disabled the runtime capability even though the persisted main agent still carried `web_search`.
- Existing-install startup repair preserved live tool arrays too literally. Runtime-disabled tools
  were not being pruned from preserved live arrays, which allowed stale `web_search` entries to
  persist in Mongo after the live runtime had disabled the feature.

## Fix Under Test

- Enable web search only in canonical App Support config and recompile the runtime.
- Restart the local stack through the supported launcher path.
- Repair existing-install built-in agent persistence so preserved live tool arrays keep user-managed
  state except for tools disabled by the current runtime capability gates.
- Keep the fix in the runtime repair layer rather than adding prompt hacks or Telegram-specific
  string handling.

## Automated Evidence

- Passed: `npm run test:api -- --runTestsByPath test/scripts/viventium-agent-runtime-models.test.js test/scripts/viventium-seed-agents.test.js`
- Passed: `bin/viventium compile-config`

## Live Evidence

- `bin/viventium status` after restart reported:
  - `Web Search: Configured`
  - `SearXNG: Running`
  - `Firecrawl: Running`
- `curl -fsS http://localhost:8082/` returned the live SearXNG HTML landing page.
- `curl -fsS http://localhost:3003/` returned the Firecrawl API banner.
- Local Docker disk pressure surfaced during QA while Firecrawl images were first pulling:
  - pruning unused build cache cleared the local pressure condition
  - restarting the Firecrawl compose stack after that recovery brought `http://localhost:3003`
    back up cleanly
- Telegram Desktop probe:
  - sent marker: `WEBQA_20260422T023649Z`
  - private UI screenshot was inspected and excluded from the public repo because it contained
    Telegram window/chat context
- Stored LibreChat message for that probe showed:
  - assistant `content[].tool_call.name = web_search`
  - tool args: `{"query":"latest OpenAI news today","news":true,"date":"d"}`
  - final assistant answer returned a latest-news result instead of saying search was dead

## Verdict

The reported Telegram symptom is fixed on the tested path. Canonical config now enables web search,
the runtime exposes the capability again, and a real Telegram Desktop prompt produced a stored
`web_search` tool invocation with a final answer rather than the earlier "search is dead" failure.

## Residual Risk

- Live user-managed agent drift unrelated to this incident still exists and must remain protected;
  future syncs should continue to use the A/B/C compare workflow before any broad push.
