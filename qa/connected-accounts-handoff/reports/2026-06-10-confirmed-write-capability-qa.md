<!-- qa-evidence-exempt: legacy sanitized RCA/QA note retained for historical context; current acceptance must use cases plus a fresh v2 report. -->

# Connected Accounts Confirmed Write Capability QA - 2026-06-10

## Result

PASS for the reported read-only refusal regression and for non-mutating browser QA.

PARTIAL for actual send/draft execution because no real email draft or send was performed without
explicit permission to mutate a connected account. Same-process handoff writes remain
prompt-confirmed rather than broker-token-confirmed, so the handoff tool set was intentionally
narrowed to non-destructive email/calendar writes only.

## RCA

The reported conversation was active on the `Connected Accounts` handoff agent. Mongo showed
historical assistant replies that refused MS365 sending because the handoff path was configured and
prompted as read-only-only. The broader MS365 specialist already had send/draft/calendar write tools,
but the Connected Accounts handoff did not, and the standalone Google/MS365 specialist prompts still
said to never send email directly.

This was not primarily a model rate-limit problem and not an absence of MS365 write tools globally.
There was also an operational MS365 MCP transport issue: logs showed `ECONNREFUSED` because the
Docker-backed MS365 MCP service was not running. After Docker was started and the MS365 MCP compose
service was brought up, a harmless MS365 read check succeeded.

## Changes Verified

- Connected Accounts live agent has 36 tools.
- Required confirmed-write tools are present:
  `send-mail_mcp_ms-365`, `create-draft-email_mcp_ms-365`,
  `create-calendar-event_mcp_ms-365`, `update-calendar-event_mcp_ms-365`,
  `send_gmail_message_mcp_google_workspace`, `draft_gmail_message_mcp_google_workspace`,
  `create_event_mcp_google_workspace`, and `modify_event_mcp_google_workspace`.
- Forbidden broad/destructive tools are absent:
  `upload-file-content_mcp_ms-365`, `delete-onedrive-file_mcp_ms-365`,
  `create_drive_file_mcp_google_workspace`, `delete_event_mcp_google_workspace`,
  `move-mail-message_mcp_ms-365`, `delete-mail-message_mcp_ms-365`,
  `delete-calendar-event_mcp_ms-365`, and `delete-specific-calendar-event_mcp_ms-365`.
- Main still has zero direct Google/MS365 provider tools and one Connected Accounts handoff edge.
- Main prompt no longer contains the stale read-only Connected Accounts framing.
- MS365 and Google specialist prompts no longer say `NEVER send emails directly`; they now require
  explicit user send confirmation.
- MS365 MCP service is reachable at the configured local endpoint after Docker startup.
- Review-only `gpt-5.4` second opinion flagged stale owning docs and overbroad destructive tools;
  owning docs were updated and delete/move/archive-style tools were removed from Connected Accounts.

## Evidence Run

- Exact incident DB inspection:
  - target conversation found
  - active agent was Connected Accounts
  - historical read-only refusals found
- Live provision:
  - Connected Accounts provisioner refreshed tools and ACLs
  - prompt-only sync updated Main, MS365, and Google live instructions after compare/dry-run review
- Automated checks:
  - `node --check qa/connected-accounts-handoff/scripts/confirmed_write_capability_browser_qa.cjs`
  - targeted productivity source/provisioner/public-safety tests: 6 passed
- Browser QA:
  - synthetic Connected Accounts prompt asked about future MS365 send without permission to mutate
  - visible reply asked for recipients, subject/body, and explicit approval instead of read-only refusal
  - reload preserved the result
  - stored messages contained no mutation tool calls
- Browser reachability QA:
  - synthetic prompt asked for harmless MS365 read/status verification
  - visible reply reported MS365/Outlook access reachable
  - DB tool-call evidence showed `list-mail-messages_mcp_ms-365`
  - mutation tool-call list was empty

## Residuals

- No real send/draft/calendar-create smoke was run because that would mutate connected account data.
- Google Workspace separately logged `invalid_token / Authentication required`; reconnect Google if
  Google-side quick checks or writes are needed.
- Older logs still contain prior Anthropic rate-limit and MS365 `ECONNREFUSED` entries from before
  this repair; post-repair MS365 browser reachability succeeded.
