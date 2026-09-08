# Connected tools and search

## User promise

Main and supported clients can use the owner's authorized tools and current-information search and
can explain whether a result is empty, unavailable, blocked, or successful.

## Cross-client access

- **GOV-027:** Supported non-LibreChat agents and clients discover and use Scheduling and GlassHive
  cognition from server and tool contracts alone.

## Requirements

- Tool availability is the intersection of saved configuration, endpoint support, audience,
  authorization, and approval. A model or worker never gains capability from prose alone.
- Every connection is owner-scoped. OAuth denial, expiry, revocation, quota, and reconnect remain
  distinct and produce one useful next action.
- Search distinguishes successful empty results from provider unavailable, timeout, rate limit,
  missing auth or configuration, rejected request, unsupported setup, and missing local
  prerequisites.
- Current-fact lookup uses an available authorized fallback when the primary search route fails; it
  never reports operational failure as evidence that nothing exists.
- Runtime exposes typed capability and results. Models choose semantically when and how to use them;
  no prompt-keyword intent router is allowed.

## Owners and QA

- Tool configuration and brokerage: nested LibreChat agent/tool services and MCP configuration
- Local search runtime: configured SearXNG and Firecrawl services
- QA: `qa/mcp-tooling/`, `qa/mcp-oauth/`, `qa/connected-accounts-handoff/`, `qa/web-search/`, and
  `qa/web-search-telegram/`

The detailed tool and search contracts below retain their current capability and failure rules.

## Detailed contracts

- [MCPs](../07_MCPs.md)
- [Open Source Web Search](../10_Open_Source_Web_Search.md)
