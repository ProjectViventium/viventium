<!-- qa-evidence-exempt: legacy sanitized RCA/QA note retained for historical context; current acceptance must use cases plus a fresh v2 report. -->

# 2026-06-10 Connected Accounts Handoff Editor Selector QA

Status: **PASS** after fix.

## Scope

Verify the operator-visible LibreChat Agent Builder path for the re-enabled Connected Accounts
handoff:

- Main agent has one handoff edge to Connected Accounts.
- Agent Builder > Advanced > Agent Handoffs visibly resolves that selected handoff target.
- The `/api/agents` list feeding the selector includes Connected Accounts for the signed-in user.

## Escaped Failure

Real browser reproduction initially showed:

```text
Agent Handoffs
Beta
1 / 10
Select agent
Select agent
Add agent
Add handoff agent
```

Mongo already had the Connected Accounts agent and the main edge pointed to it. Runtime chat handoff
QA passed because the graph can load the target by stable agent id. The editor failed because its
selector resolves names through the signed-in user's `/api/agents?requiredPermission=1` list, and
that list did not include Connected Accounts.

## Root Cause

The provisioner created a user ACL row by hand with `principalId` stored as a string. The permission
service builds the current user principal as a Mongo ObjectId, so the private Connected Accounts
agent did not match `findAccessibleResources`. Public/source agents still appeared through public
ACLs, which hid the mismatch until the private handoff target had to be rendered in the selector.

## Fix

- `viventium_v0_4/LibreChat/scripts/viventium-provision-connected-accounts-agent.js`
  now uses the canonical `grantPermission` service for both:
  - `ResourceType.AGENT` / `AccessRoleIds.AGENT_OWNER`
  - `ResourceType.REMOTE_AGENT` / `AccessRoleIds.REMOTE_AGENT_OWNER`
- The provisioner deletes stale string-principal rows for this agent before writing canonical
  ObjectId-principal grants.
- The provisioner was rerun against the local QA DB.
- `viventium_v0_4/LibreChat/viventium/source_of_truth/local.viventium-agents.yaml` now owns the
  `Main_To_ConnectedAccounts` edge and the target agent under `handoffAgents`.
- `viventium_v0_4/LibreChat/scripts/viventium-sync-agents.js` now exports edge targets into
  `handoffAgents`, pushes `handoffAgents`, and grants canonical `agent` plus `remoteAgent` ownership
  when it creates source-owned agents.
- The browser QA script now checks the visible selected handoff combobox text, not only whether
  `Connected Accounts` appears somewhere in the section.

## Verification

Commands run:

```bash
node --check viventium_v0_4/LibreChat/scripts/viventium-provision-connected-accounts-agent.js
node --check viventium_v0_4/LibreChat/scripts/viventium-sync-agents.js
node scripts/viventium-provision-connected-accounts-agent.js
node --check qa/connected-accounts-handoff/scripts/handoff_editor_browser_qa.cjs
VIVENTIUM_QA_ALLOW_LOCAL_JWT=1 node qa/connected-accounts-handoff/scripts/handoff_editor_browser_qa.cjs
uv run --with pytest --with pyyaml python -m pytest tests/release/test_productivity_activation_source_of_truth.py::test_connected_accounts_handoff_is_source_owned_and_read_only tests/release/test_productivity_activation_source_of_truth.py::test_agent_sync_preserves_handoff_targets_and_canonical_acl_grants -q
node scripts/viventium-sync-agents.js push --dry-run --agent-ids=agent_viventium_connected_accounts_95aeb3
```

The source-sync dry run selected the Connected Accounts handoff agent from `handoffAgents` and did
not need to touch live state. A temporary pull/export probe also preserved one `handoffAgents` entry
and the `Main_To_ConnectedAccounts` edge target.

DB evidence after provisioning:

- Connected Accounts has two owner ACL rows: `agent` and `remoteAgent`.
- Both rows store the user principal as ObjectId, not string.

Browser/API evidence after fix:

```text
Agent Handoffs
Beta
1 / 10
Select agent
Connected Accounts
Add agent
Add handoff agent
```

The remaining `Select agent` text is the unrelated Background Cortex selector above the handoff
section or a hidden combobox label, not the selected handoff row. The stricter browser assertion
also inspected visible comboboxes between `Agent Handoffs` and `Agent Chain`:

```text
Connected Accounts
Add handoff agent
```

The selected handoff combobox text was exactly `Connected Accounts`.

`/api/agents?requiredPermission=1` returned status 200, count 23, included Connected Accounts, and
listed it first after the provisioner update.

A cropped local screenshot of only the handoff selector region was saved under
`output/playwright/connected-accounts-handoff/`. The screenshot is ignored local QA output and is
not part of public evidence.

## Residual Risk

This report covers the visible editor selector path that escaped the prior runtime QA. It does not
rerun the full chat handoff or calendar mutation boundary because those were already covered earlier
on 2026-06-10; keep `CA-HANDOFF-014` in the acceptance set for future provisioning or ACL changes.

Second-opinion review was run with a GPT fallback reviewer because Claude credits were unavailable.
The review found three gaps: source-of-truth drift, the same raw ACL pattern in the general sync
create path, and a weak browser assertion. All three were addressed before this report was finalized.
