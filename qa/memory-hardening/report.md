# Memory Hardening QA Report

## 2026-04-25 Implementation Pass

Status: passed for implementation smoke coverage.

Public-safe checks run:

- config compiler defaults and model-governance tests passed
- runner proposal validation tests passed
- local dry-run ran against a QA account only
- local apply touched the QA account only
- owner-account counts were unchanged after the initial QA-account apply
- browser login reached the QA account and the Memories panel listed all nine memory keys
- follow-up live-local run after private backup proved Memory Archivist instruction injection and
  full-lookback coverage with redacted telemetry only

Private local artifacts, if any, stay under App Support state or the operator's private backup
directory and are not part of this report.

Notes:

- The dry-run used the launch-ready Anthropic hardening profile.
- The QA-account proposal updated `context`, `drafts`, and `moments`; `working` was not changed.
- The follow-up live-local run fed all 505 messages from 79 conversations in the 7-day lookback,
  omitted 0 messages for input-cap reasons, and applied one validated `world` key update.
- Full next-message model behavior was not exercised in browser because the local status surface
  reported foundation-model connected-account action required for the QA browser account.
