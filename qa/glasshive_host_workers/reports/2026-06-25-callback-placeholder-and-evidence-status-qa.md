# GlassHive Callback Placeholder And Evidence Status QA

<!-- qa-evidence-exempt: Historical focused regression note retained as supporting evidence; full user-path acceptance is recorded in later reports. -->

Date: 2026-06-25
Case: `GHHOST-009`
Status: PASS

## RCA

Three general defects combined in the reported chat:

1. Run evidence could classify browser accessibility node numbers such as `403 close button` as provider auth/status evidence.
2. `worker_message` accepted a blank worker id, which allowed a downstream `/workers//message` 404 instead of an immediate MCP validation error.
3. LibreChat callback persistence did not treat its own unfinished `Generation in progress.` assistant message as a replaceable placeholder. A completed callback could be saved below that placeholder while the placeholder remained unfinished.

This was not primarily a voice-model intelligence issue. The voice model exposed the weak contracts, but the durable fixes belong in GlassHive evidence parsing, MCP validation, and LibreChat callback persistence.

## Fix Summary

- GlassHive failure classification now requires structured/status/auth/rate-limit context before treating numeric `401`, `403`, `429`, `503`, or `529` text as provider evidence.
- GlassHive MCP `worker_message` now trims and validates `worker_id` and `message` before calling the API.
- LibreChat GlassHive callbacks now replace an unfinished `Generation in progress.` leaf, set `unfinished=false`, and keep the result on the current conversation branch.

## Evidence

- Targeted GlassHive regression tests passed:
  - `test_run_evidence_does_not_treat_browser_snapshot_node_ids_as_provider_status`
  - `test_run_evidence_classifies_structured_provider_auth_missing`
  - `test_run_evidence_classifies_structured_provider_rate_limit`
  - `test_worker_message_rejects_blank_worker_id_before_api_call`
- Broader affected GlassHive tests passed:
  - `runtime_phase1/tests/test_run_evidence.py`
  - `runtime_phase1/tests/test_mcp_server.py`
  - Combined result: 57 passing tests.
- LibreChat callback suite passed:
  - `server/routes/viventium/__tests__/glasshive.spec.js` with 46 passing tests.
- Local runtime was restarted and health checks passed for GlassHive API, LibreChat API, LibreChat frontend, and Modern Playground.
- Live MCP check passed: blank `worker_message` was rejected before any HTTP call.
- Live callback check passed with synthetic public-safe conversation data: the signed callback returned HTTP 200, updated the placeholder message in place, set `unfinished=false`, and preserved the current branch parent.
- Real Chrome / LibreChat visual QA passed: the synthetic conversation displayed the completed callback text and did not show the `Generation in progress.` placeholder.
- Cleanup passed: synthetic QA conversation and four synthetic QA messages were deleted after visual verification.
- One historical affected local conversation was surgically repaired after the product fix: the completed callback was reparented to the current user message and the stale placeholder row was deleted. DB sanity check showed no remaining `Generation in progress.` row or callback child under the stale placeholder; real Chrome showed the completed result without a blank spinner bubble.

## Residual Risk

Other existing old conversations that already persisted an unfinished placeholder would still be historical data unless separately repaired. The code path is fixed for new callbacks.
