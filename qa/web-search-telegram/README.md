# Telegram Web Search QA

## Purpose
Validate the real Telegram user path for web search availability and prove the owning control path:
canonical config -> compiler output -> live runtime -> Telegram-visible assistant behavior.

## Scope
- canonical `integrations.web_search` ownership in App Support config
- compiled runtime output for `runtime.env` and `librechat.yaml`
- live local SearXNG and Firecrawl health
- built-in agent runtime tool continuity for existing installs
- Telegram Desktop send -> stored LibreChat turn -> assistant tool invocation

## Acceptance Contract
1. If canonical config enables web search, the compiler must emit a live `webSearch` block and
   `interface.webSearch: true`.
2. Telegram must stop answering as if search is unavailable on the tested prompt path.
3. The stored assistant turn must show a real `web_search` invocation, not only a prompt-only
   claim.
4. Existing built-in agents must preserve live tool arrays except for runtime-disabled tools that
   are intentionally pruned by the runtime repair layer.
5. QA must distinguish a fully dead search path from a degraded scraper-only sidecar failure.

## Evidence Rules
- Keep evidence public-safe.
- Do not record private chats, tokens, personal email addresses, or machine-local secret values.
- Use synthetic probe text and repo-relative evidence paths.
