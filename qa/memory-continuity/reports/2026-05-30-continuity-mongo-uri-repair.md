<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# 2026-05-30 Continuity Mongo URI Repair

## Scope

Public-safe follow-up for `MEMCONT-001`, focused on the recurring continuity-audit warning where
Mongo introspection was skipped because generated `MONGO_URI` was blank.

## RCA

`bin/viventium continuity-audit` read `runtime.env` and passed only `MONGO_URI` into the Mongo
continuity probe. Local native runtime generation intentionally stores the non-secret local Mongo
port and database name in `runtime.env`, while the resolved `MONGO_URI` is maintained in the
generated LibreChat service env or by launcher defaults. The audit therefore had enough generated
metadata to derive the local URI, but did not use it.

Direct Mongo checks could compensate during QA, but that violated the project rule that the owning
helper must prove the continuity gate.

## Fix

`scripts/viventium/continuity_audit.py` now resolves Mongo in this order:

1. `MONGO_URI` from `runtime.env`.
2. `MONGO_URI` from generated `runtime/service-env/librechat.env`.
3. Local derived URI from `VIVENTIUM_LOCAL_MONGO_PORT` and `VIVENTIUM_LOCAL_MONGO_DB`.

The report still stores only metadata counts/timestamps and does not print the URI.

## Evidence

- Unit regressions prove local Mongo URI derivation and generated service-env preference.
- A live continuity audit wrote a metadata manifest with status `ok`.
- The live manifest had no Mongo warning.
- Mongo continuity surfaces were available for messages and saved memory, and scheduler continuity
  metadata was captured.

## Commands

- `uv run --with pytest --with pyyaml python -m pytest tests/release/test_continuity_audit.py::test_resolve_mongo_uri_derives_local_runtime_uri tests/release/test_continuity_audit.py::test_resolve_mongo_uri_prefers_generated_service_env -q`:
  **2 passed**.
- Targeted continuity/launcher/compiler/scheduler regression slice: **18 passed**.
- `bin/viventium continuity-audit`: **ok**, no warnings.

## Status

PASS for the continuity helper Mongo-introspection gap.

Remaining continuity/RAG acceptance still requires separate user-facing recall QA when the claim is
end-to-end recall behavior rather than metadata continuity.

## Public Safety

No local URI, user identifier, raw memory text, raw message text, or local absolute path is included
in this public report.
