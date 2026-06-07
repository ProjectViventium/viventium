# Handoff: GlassHive Claude-Code Worker and Broker Reliability

Date: 2026-05-29

This public-safe handoff preserves the product lessons from the local GlassHive Claude-code worker
audit without publishing private account details, customer names, local temp paths, conversation
ids, runtime database paths, or operator-specific live state.

## Decisions

- Connected-account work remains brokered through GlassHive or the dedicated hand-off path; the main
  agent should not receive direct Google Workspace or Microsoft 365 tools as a shortcut.
- Worker routing must preserve the Core Outcome Metric: Quality plus Performance. A faster path that
  is less accurate, complete, useful, or aligned is a regression.
- Do not hardcode a rubric that sends "quick" requests to one path and "thorough" requests to another.
  Each supported path must be capable of truthful, useful, complete work on its own AI.
- Claude Code can be a valid local host-worker profile when it is explicitly configured and allowed.
  Enterprise or headless deployments must keep their own declared worker allowlists and provider auth
  model.

## Findings

### Claude-Code Host Auth

The local Claude-code worker failure was caused by stripping the user identity environment from the
host worker process. On macOS, Claude CLI subscription auth is resolved through the login Keychain and
depends on `USER` / `LOGNAME` being present. Passing those non-secret identity variables through the
host-worker environment fixes the failure without changing secret stripping.

This fix is host-worker specific. Docker and enterprise workers use their own provider-route auth
and must not inherit local Keychain assumptions.

### MCP Result Shape

Strict MCP clients reject `structuredContent` when it is not a JSON object. Some brokered provider
tools return arrays, so the broker must emit `structuredContent` only for plain objects and place
arrays/scalars in the normal text content payload. This is a universal MCP contract fix, not a
provider-specific workaround.

### Worker Result Quality

Worker output can be too noisy when status/wait calls return full run records around a small final
answer. The long-term fix is to keep diagnostic payloads behind an explicit diagnostics path and make
the default status result lean enough for the main agent to consume reliably.

Worker completeness and main-agent shaping are separate responsibilities:

- The worker should surface the complete actionable set and not silently drop real items.
- The main agent can shape, summarize, prioritize, and remove already-handled items using the user's
  current context.

This keeps GlassHive useful without turning runtime code into prompt-specific or provider-specific
routing logic.

## Public Implementation Notes

- `scripts/viventium/config_compiler.py` and `config.schema.yaml` own the source-level worker profile
  configuration.
- `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md` owns the GlassHive
  runtime and worker-behavior contract.
- `qa/connected-accounts-handoff/cases.md` owns connected-account handoff and broker QA cases.
- Runtime secrets, provider tokens, raw email/calendar/file contents, local database paths, and
  private deployment notes belong outside the public repo.

## Follow-Up Gates

- Re-run helper-managed local QA after any helper or host-worker environment change.
- Keep enterprise/headless behavior gated by explicit deployment configuration and allowlists.
- Keep broker result-shape regression coverage for strict MCP clients.
- When adding or changing worker prompts, run the A/B/C live-vs-source drift review before syncing
  user-managed agent config.
