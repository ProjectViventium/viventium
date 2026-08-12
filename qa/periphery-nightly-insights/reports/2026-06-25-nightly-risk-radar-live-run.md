# 2026-06-25 Nightly Risk Radar Live Run QA

<!-- qa-evidence-exempt: Historical focused live-run record retained as supporting evidence; later reports own complete user-path traceability. -->

## Summary

Result: `PASS` for the requested nightly risk/blind-spot/opportunity artifact generation path.

The first real run after the fix completed through the live Workbench -> GlassHive -> scheduler
callback path and produced one valid private `risk_radar` `.md` plus `.json` sidecar pair. The
Workbench periphery endpoint returned sanitized metadata only, with one artifact and zero invalid
sidecars.

This does not add conscious-chat surfacing. The artifact remains private unless a future approved
read/surfacing path retrieves it.

## RCA

Before this fix, Phase 0 had a metadata reader but the built-in nightly prompt still only asked for
scratchpad and memory proposal output. The worker completed successfully, but it had no explicit
contract to create `periphery/risk_radar/YYYY/MM/*.json`.

Fix:

- Added a compact private periphery block to the built-in Workbench nightly prompt.
- Required one `risk_radar` sidecar pair per run, including an honest low-signal/no-result artifact
  when strong evidence is missing.
- Kept the boundary: no saved-memory key, no main prompt injection, no raw private conversation text
  copied into the sidecar.
- Added regression tests proving the template carries the sidecar contract and Workbench seeding
  reconciles the prompt into the scheduler task.

## Real Run Evidence

- Live Workbench definition after restart: active built-in nightly prompt contained
  `periphery/risk_radar/YYYY/MM`.
- Live scheduler task after restart: task prompt contained `periphery/risk_radar/YYYY/MM`.
- Manual scheduled run: completed.
- GlassHive health after completion: `0` active, `0` queued, `0` callback pending, `0` callback
  delivering.
- Worker exit code: `0`.
- Scheduler DB row: `completed`, executor `glasshive_host`, no `error_class`, private detail present,
  callback payload captured.
- Periphery metadata endpoint after completion: `artifactCount=1`, `invalidCount=0`.

Sanitized artifact metadata:

- `moduleId`: `risk_radar`
- sidecar: `20260625T143421Z.risk_radar.json`
- markdown: `20260625T143421Z.risk_radar.md`
- `markdownExists`: `true`
- `generatedAt`: `2026-06-25T14:34:21Z`
- `staleAfter`: `2026-07-02T14:34:21Z`
- `sourceRefCount`: `3`
- content counts: observations `3`, risks `4`, blind spots `2`, opportunity costs `3`,
  opportunities `3`, what-would-make-this-wrong `3`, when-to-surface `4`, proposed actions `4`,
  memory proposal refs `1`

Raw sidecar body, raw memory proposal body, raw source refs, local paths, account ids, and private
conversation content are intentionally omitted from this public-safe report.

## Automated Evidence

Ran:

- `uv run --with pytest --with pyyaml --with fastapi --with httpx --with croniter --with pydantic python -m pytest tests/release/test_prompt_workbench.py -q`
  - Result: `84 passed`
- `uv run --with pytest --with pyyaml --with fastapi --with httpx --with croniter --with pydantic python -m pytest tests/release/test_scheduled_glasshive_prompts.py -q`
  - Result: `13 passed, 5 skipped`

Focused coverage:

- Built-in nightly template includes the private risk-radar sidecar path and required JSON fields.
- Built-in nightly seeding reconciles an old scratchpad-only prompt into the scheduler task.
- Valid sidecar plus matching markdown returns sanitized metadata.
- Invalid JSON, module/path mismatch, missing required fields, missing markdown companion, user-level
  schedule rejection, and cross-user forbidden access are covered.

## User-Facing QA

Prompt Workbench now shows the periphery artifact metadata in the scheduled prompt detail view.

Actual Chrome profile QA:

- Opened Prompt Workbench in the user's active Chrome profile.
- Selected `Subconscious Deep Thought`.
- Verified the `Periphery Artifacts` panel is visible.
- Verified the latest `risk_radar` sidecar is visible with generated time, confidence, severity,
  source count, markdown-present state, stale-after date, relative `.json`/`.md` paths, and content
  counts.
- Confirmed the panel exposes metadata/counts only; raw artifact text, source refs, memory proposal
  bodies, local absolute paths, and account data are not shown in this public QA evidence.

Synthetic edit QA:

- Created a temporary Workbench private schedule.
- Opened it through a real browser Workbench session.
- Updated title and prompt body, clicked `Save`, observed a successful patch, verified the refreshed
  list/detail reflected the update, then deleted the synthetic schedule.

Evaluation QA:

- Ran one no-live Workbench eval preview.
- Result: selected one synthetic eval case, return code `0`, private eval output available.

Sync note:

- The nightly scheduled prompt and periphery artifact are visible and usable.
- The Workbench sync sidebar still reports one separate `main.conscious_agent` source/live conflict.
  That is protected prompt-bundle drift, not the periphery artifact surface. It was not pushed or
  pulled during this QA pass.

Computer/browser observation found a separate live voice-tab GlassHive demo failure:

- A user-requested Yahoo Finance GlassHive demo failed because the model provider rejected an
  unsupported `reasoning.effort` value for the selected Codex model.
- This is not the nightly periphery path; the nightly run completed successfully.
- It should become its own GlassHive host-worker/provider-config QA item if that demo path is in
  scope next.

## ClaudeViv Review

- Claude auth check returned `CLAUDE_OK`.
- Structured Opus review was attempted first but produced no JSON artifact before it was interrupted
  after an extended quiet wait.
- Structured Sonnet review was attempted as a smaller-model fallback but also produced no JSON
  artifact before interruption.
- No Claude recommendation is treated as evidence for this pass. The acceptance claim rests on local
  tests, live runtime evidence, DB/log inspection, API metadata, browser QA, and public-safety scans.

## Remaining Gaps

- No conscious-agent on-demand artifact reader/surfacing flow has been implemented yet.
- No private snapshot harness/model eval corpus has been implemented yet.
- Old/stale local scheduled-run residue still needs separate cleanup classification.
- The voice-tab GlassHive demo/provider-config issue is separate from this nightly fix.

## Public-Safety Review

- [x] No raw private prompt, scratchpad, memory proposal, or risk-radar body copied here.
- [x] No account email, local absolute path, credential, callback secret, or raw DB payload copied
  here.
- [x] Evidence is expressed as statuses, counts, filenames, run classes, and sanitized metadata.
