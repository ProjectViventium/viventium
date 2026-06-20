<!-- qa-evidence-exempt: legacy sanitized RCA/QA note retained for historical context; current acceptance must use cases plus a fresh v2 report. -->

# 2026-06-09 Connected Accounts Handoff Re-enable QA

Status: **PARTIAL**.

## Scope

Re-enable the supported same-process Connected Accounts handoff alongside GlassHive:

- Connected Accounts: immediate read-only connected-account checks and quick updates.
- GlassHive: document generation, reports, deep research, browser/computer work, multi-step co-work,
  long-running audits, and autonomous worker tasks.

## Source And Live Config

PASS:

- Provisioner no longer has the retired default-off gate.
- Provisioner updates an existing Connected Accounts agent, not only first-create state.
- Connected Accounts live config has 22 read-only Google/MS365 tools and 0 known write tools.
- Main agent live config has 0 direct Google/MS365 provider tools.
- Main agent has exactly one `Main_To_ConnectedAccounts` handoff edge to the Connected Accounts agent.
- Live main prompt includes the quick-handoff versus GlassHive split.
- Connected Accounts instructions and edge prompt now suppress account email addresses, aliases, raw
  IDs, OAuth details, server names, and tool plumbing unless diagnostic account details are
  explicitly requested.

Sanitized live DB audit after reprovision:

```json
{
  "connectedReadToolCount": 22,
  "connectedForbiddenWriteToolCount": 0,
  "mainDirectProviderToolCount": 0,
  "connectedEdgeCount": 1,
  "connectedEdgeTargetOk": true,
  "instructionsSuppressAccountEmails": true,
  "edgeSuppressAccountEmails": true
}
```

## Automated Checks

PASS:

- `node --check viventium_v0_4/LibreChat/scripts/viventium-provision-connected-accounts-agent.js`
- `uv run --with pytest --with PyYAML==6.0.2 python -m pytest tests/release/test_productivity_activation_source_of_truth.py tests/release/test_prompt_registry.py -q`
  - Result: 47 passed.

## User-Grade Browser QA

Surface: local LibreChat web UI with a short-lived local JWT for the configured Viventium runtime
test account. Evidence is public-safe: hashes/counts/route flags only.

Run 1, before the account-email privacy hardening:

- Browser reached chat: PASS.
- Visible answer before reload: PASS.
- Visible answer after reload: PASS.
- Handoff evidence: PASS.
- Provider tool evidence: PASS.
- GlassHive evidence: none.
- Message parts: `tool_call`, `text`.
- Privacy: FAIL, visible answer included an account email address.

Fix applied after Run 1:

- Connected Accounts agent instructions and handoff edge prompt now forbid account email addresses and
  aliases unless the user explicitly asks for diagnostic account details.
- Live provisioner rerun confirmed those instructions landed in Mongo.

Post-fix reruns:

- Run 2: browser submitted prompt and created assistant error part `provider_rate_limited`.
- Run 3: browser submitted shorter prompt and created assistant error part `provider_rate_limited`.
- No post-fix visible-answer pass was possible while the provider was rate-limited.

## Result

`CA-HANDOFF-010`: **PASS**. The supported provisioner is idempotent and surgical, updates existing
agent instructions, preserves unrelated main-agent edges, grants ACL, and leaves the main agent lean.

`CA-HANDOFF-001` / `CA-HANDOFF-UC-001`: **PARTIAL**. Browser evidence proved the handoff route and
absence of GlassHive on the immediate quick-read path before the privacy hardening, but the post-fix
visible-answer rerun is blocked by provider rate limiting. Re-run the browser prompt after the rate
limit clears before declaring a current visible UX pass.

## Remaining Gaps

- Re-run post-fix browser QA and require: visible answer, refresh persistence, handoff evidence,
  provider tool evidence or exact provider/auth blocker, no GlassHive route, and no account email
  address or private message details in the visible answer.
- `CA-HANDOFF-004` write-routing remains config-proven but still needs a live browser write-request
  exercise.
