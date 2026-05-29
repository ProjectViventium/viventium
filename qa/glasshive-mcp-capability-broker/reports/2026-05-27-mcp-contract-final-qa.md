# GlassHive MCP Contract Final QA

Date: 2026-05-27

## Scope

Validate the corrected GlassHive MCP broker contract after the escaped inbox-flow regression:

- broker/tool capability is advertised as context, not invented worker goals
- vague adjectives such as "urgent" are passed through without a private rubric
- missing user success criteria stay minimal
- content-read intent remains host-grant scoped and is not a worker-authored authorization edge
- connected-account results return inline without forced files, broken local links, or hidden config artifacts

Private browser/account evidence, raw provider output, tokens, account identifiers, and local absolute paths are stored outside this public repo under the private user-data QA folder.

## Code And Prompt Checks

- PASS: `runtime_phase1/src/workers_projects_runtime/mcp_server.py` advertises the no-invented-goals contract, the vague-adjective pass-through rule, and the host-signed content-read grant rule.
- PASS: `viventium/source_of_truth/prompts/mcp/glasshive_workers_server.md` mirrors the MCP instruction contract.
- PASS: `viventium/source_of_truth/prompts/main/truth_live_data.md` tells the main agent to pass broker/tool availability as context and trust the worker.
- PASS: requirements docs updated in `07_MCPs.md` and `48_GlassHive_Workstation_Sandbox_Runtime.md`.

## Automated Checks

- PASS: prompt registry render/parity tests: 23 passed.
- PASS: GlassHive MCP tool-description regression test passed.
- PASS: GlassHive workspace launch acknowledgement regression test passed.
- PASS: LibreChat broker/auth/callback Jest subset passed: 3 suites, 64 tests.
- PASS: Python compile check for edited GlassHive MCP server.

## Browser Flow

Prompt used: "Please check my inbox for anything urgent today across my connected accounts. Do not send, delete, archive, mark read, or modify anything."

Result: PASS.

Observed behavior:

- The main agent did not ask an unnecessary provider clarification.
- The first visible response launched `workspace_launch`.
- Launch args used minimal success criteria and preserved the explicit read-only constraints.
- Launch context included broker availability and said the user adjective "urgent" should be passed through without inventing a rubric.
- Worker bootstrap exposed the broker MCP and host-authorized content-read scope.
- Worker completed and returned the result inline in LibreChat.
- No state-changing action was reported.
- No `Download file`, `local worker link`, or hidden config path was visible in the final chat response.
- DB inspection showed the user prompt, the launch acknowledgement, and the inline final result; no forced file artifact response was inserted.

## Security Checks

- PASS: worker `.mcp.json` and Codex config used broker projection and did not contain raw Google/MS365 provider tokens.
- PASS: public chat output did not expose hidden worker config files.
- PASS: broker policy/auth Jest tests confirm worker self-asserted intent does not authorize content reads; host-signed grant scope is required.

## Claude Review

Claude review identified one high-risk wording issue: the `connected_account_content_intent` schema text overstated the flag as if it directly scoped reads. Fixed by changing the MCP/tool wording to say it is only an intent signal and that authorization still requires a host-signed broker grant with content-read scope; tests now assert the corrected wording.

Claude also flagged timing/test debt around host-busy retry and scheduled-state assertions. Those are not caused by this prompt-contract fix and remain follow-up hardening items.

## Remaining Gaps

- Prompt Workbench source visibility is covered by source files and prompt-registry render tests; the authenticated source-id endpoint returned the expected auth-protected error object rather than a source prompt body, so a manual Workbench UI diff walkthrough remains a partial item.
- Long-duration live renewal beyond the unit/Jest renewal path remains a follow-up.
- The completed pre-fix browser acknowledgement pasted a raw View/Steer URL. The MCP acknowledgement guidance now instructs future responses to use a labeled `View / Steer` link instead of a bare URL.
