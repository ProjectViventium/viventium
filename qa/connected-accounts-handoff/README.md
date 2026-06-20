# Connected Accounts Handoff QA

## Scope

The main Viventium agent stays lean (no direct Google/MS365 provider tools) and can reach the user's
connected Google Workspace / Microsoft 365 accounts through a dedicated **Connected Accounts**
hand-off agent via a native LibreChat handoff edge (`edges[].edgeType: "handoff"`, auto-generated
`lc_transfer_to_<agent>` tool).

This path defaults to read-only inspection for immediate connected-account checks and can perform
quick email/calendar updates only after explicit user confirmation when the relevant write tool is
present. Broad document/file permission changes and destructive file operations stay on a separately
confirmed write-capable path. GlassHive remains the owner for document generation, reports, deep
research, browser/computer work, multi-step co-work, long-running audits, and autonomous worker tasks.

This area proves the routing of that handoff: when it hands off, when it must not, which providers it
covers, that the answer returns inline with no worker plumbing, and that provider/model failures are
reported honestly.

## Owning docs / surfaces

- `docs/requirements_and_learnings/02_Background_Agents.md`
- `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`
- Provisioner:
  `viventium_v0_4/LibreChat/scripts/viventium-provision-connected-accounts-agent.js`
- Runtime fix: `viventium_v0_4/LibreChat/api/server/services/viventium/openaiResponsesOutputPatch.js`
- GlassHive broker complement: `qa/glasshive-mcp-capability-broker/`

## Quality bar

Real-browser acceptance: visible UI outcome (handoff chip + tool calls + inline answer), no error
bubble, no `View / Steer` / worker plumbing in the reply, no main-agent direct provider tools, and
confirmation-gated email/calendar write scope for the hand-off agent. Public-safe evidence only:
counts/timestamps and sanitized outcome summaries, no private message bodies, IDs, or tokens.

## Latest status

2026-06-10: current browser QA is **PASS** for the immediate quick-read path, calendar mutation
boundary, and Anthropic-to-`gpt-5.4` fallback recovery. The quick-read prompt returned an inline
provider-status answer through the Connected Accounts handoff, persisted after reload, used no
GlassHive route, and exposed no account identifiers. A neutral calendar create prompt no longer
routed to the read-only handoff, did not call a calendar write tool, and asked for explicit
confirmation/provider choice instead of saying it only had read-only access. Source-owned Anthropic
agents now carry `openAI / gpt-5.4` fallback; a built-dist initializer probe verified stale OpenAI
OAuth does not block the fallback recovery route. A real create/delete calendar smoke remains
pending explicit permission to mutate a connected calendar.

2026-06-10 follow-up: fallback reconnect error rendering is **PASS**. When a primary provider is
rate-limited and the fallback provider needs connected-account reconnect, the agent controller,
LibreChat browser error renderer, and Telegram bridge now preserve actionable reconnect guidance
instead of generic `Connection error`, `Something went wrong`, or stale rate-limit wording. See
`reports/2026-06-10-fallback-reconnect-error-rendering.md`.

2026-06-10 editor follow-up: Agent Builder handoff selector QA is **PASS**. Browser QA reproduced
the live failure where the existing `1 / 10` handoff row rendered as unresolved `Select agent`,
traced it to a string-principal ACL grant that kept Connected Accounts out of `/api/agents`, then
verified the repaired provisioner, source-owned `handoffAgents` target, sync-create ACL path, and
live DB show the selected handoff row as `Connected Accounts` in Agent Builder > Advanced. See
`reports/2026-06-10-handoff-editor-selector-qa.md`.

2026-06-10 confirmed-write follow-up: Connected Accounts confirmed email/calendar write capability
is **PASS** for configuration, wording, non-mutating browser QA, and MS365 read reachability. The
incident conversation was active on Connected Accounts and contained historical read-only refusals;
live config now gives Connected Accounts 36 tools including MS365 send/draft/calendar and Google
Gmail/calendar write tools, while broad/destructive file/mail/calendar write tools remain absent. Browser QA proved the agent
asks for confirmation/details instead of claiming read-only access, reload persistence holds, and a
harmless MS365 read call succeeds without mutation tool calls. A real send/draft smoke remains
unrun because it would mutate a connected account. See
`reports/2026-06-10-confirmed-write-capability-qa.md`.
