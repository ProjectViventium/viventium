<!-- qa-evidence-exempt: Generated focused browser artifact; full-view acceptance is owned by the universal continuity report. -->

# Live background-cortex fallback disclosure QA — 2026-08-09

- Status: PASS
- Surface: local LibreChat, non-admin QA account, disposable main Agent and cortex
- Cortex activated from a normal browser turn: yes
- Disconnected primary recovered through configured fallback: yes
- Fallback-produced insight persisted: yes
- Visible cortex fallback row: yes
- Expanded explanation and public failure class visible: yes
- Disclosure and cortex result survived reload: yes
- Persisted structural fields agreed with the UI: yes
- Synthetic Agents/conversation/session cleanup: verified
- Browser console errors: 0
- Account hash: f9ffb8f8a012
- Conversation hash: a4421b96bdf7

This fixture exercises a generic provider-failure boundary through the real background-cortex runtime. It does not branch on a user entity or production prompt phrase. Raw prompts, responses, provider payloads, identifiers, screenshots, tokens, local paths, and database records remain outside the repository.

The deterministic synthetic lane proves the downstream generic `primary unavailable` recovery and
disclosure contract; it is not a claim that this run reproduced a specific OAuth error variant.
Separate connected-account QA covers terminal `invalid_grant` classification.
