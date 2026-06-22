<!-- qa-evidence-exempt: legacy sanitized QA/RCA note retained for historical context; current acceptance must use cases plus a fresh v2 report. -->
# GlassHive Worker Capability And Delivery Story

Date: 2026-06-16

## One-Screen Story

```
User / Host AI prompt
  -> LibreChat / GlassHive MCP or UI
  -> GlassHive worker bootstrap
  -> selected worker CLI (Codex or Claude)
  -> native worker capabilities + brokered MCP/context/files
  -> worker self-review + FINAL REPORT
  -> Watch / Steer + file actions + chat callback
```

Core rule: GlassHive should give the selected worker its truthful native substrate and then stay out
of the way. The host brokers facts, files, capability grants, status, and delivery. It must not
hardcode prompt-specific workflows.

## Where Capability Awareness Is Injected

- Worker instructions and self-review contract:
  `viventium_v0_4/GlassHive/runtime_phase1/src/workers_projects_runtime/bootstrap.py`
  lines 29-89.
- Native skill/capability inventory for Claude/Codex:
  `bootstrap.py` lines 67-75.
- Workspace prompt files:
  `bootstrap.py` lines 168-188 write `AGENTS.md`, `CLAUDE.md`, and `CODEX.md`.
- Worker desktop action surfaces:
  `viventium_v0_4/GlassHive/runtime_phase1/src/workers_projects_runtime/profile_runtime.py`
  lines 853-890.
- Workstation image/runtime substrate:
  `viventium_v0_4/GlassHive/runtime_phase1/src/workers_projects_runtime/docker_sandbox.py`
  lines 142-179 and 805+.

## RCA

```
Symptom A: Watch URL asked for desktop, but user saw no usable workspace
  -> file-deliverable promotion could replace the active surface
  -> noVNC was also resetting connections because supervisor inherited mounted TMPDIR
  -> result: desktop Watch looked broken even though the worker completed

Symptom B: LibreChat result looked missing/unreliable
  -> callback outbox was delivered
  -> final message existed in Mongo
  -> conversation message-list / updatedAt metadata was not advanced
  -> result: web chat could miss the final callback after refresh/list reconciliation
```

Important distinction: the worker did produce a useful PPTX/PDF. The broken pieces were delivery and
live-surface truthfulness around the worker.

## Fixes Applied

- Watch desktop fidelity: `surface=desktop` now keeps `/desktop/{worker}` as the primary frame.
  File deliverables remain in latest-output actions instead of hijacking the frame.
- noVNC truth/self-heal: new workstation containers start supervisor services with `/tmp`, not the
  mounted worker-home temp path; runtime health checks `/core/rfb.js` and repairs noVNC before
  advertising `view_available`.
- Callback visibility: LibreChat callback persistence now touches the owning conversation after
  saving/updating a visible callback so refresh/reopen surfaces the result.

## User-Visible Proof

- Historical local QA observed Watch / Steer desktop rendering a live noVNC canvas, explicit file
  actions, and callback-visible chat text without raw tool plumbing.
- Media evidence from that run is legacy/exempt and is not current public acceptance evidence. Fresh
  release acceptance must use text/DOM summaries, logs/state, and the current case checklist.

## Tests Run

- `uv run --group dev pytest tests/test_docker_sandbox.py`
  - 30 passed.
- `uv run --group dev pytest tests/test_server.py::test_launcher_workspace_hive_static_controls`
  - 1 passed.
- `npm test -- server/routes/viventium/__tests__/glasshive.spec.js --runInBand`
  - 44 passed.
- Browser QA:
  - Watch URL opened in real browser.
  - noVNC asset `/core/rfb.js` returned 200.
  - desktop frame contained a noVNC canvas.
  - delivered file actions were visible.
  - authenticated Chrome LibreChat showed the final callback result.
  - post-restart authenticated Chrome QA: final result was visible; raw leak terms found: none.

## Updated Requirements / QA Gates

- `docs/requirements_and_learnings/01_Key_Principles.md`
  - live surfaces must be truthful; callback delivery means chat-surfaced, not only outbox-delivered.
- `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`
  - service-local noVNC temp path, noVNC health/self-heal, callback conversation touch, Watch surface fidelity.
- `qa/glasshive_watch_desktop/cases.md`
  - `GHWATCH-007` desktop surface fidelity.
  - `GHWATCH-008` noVNC health for `view_available`.
  - `GHWATCH-009` callback result surfaces after persistence.

## Operational Reload

- Completed after the source/test pass. The local GlassHive and LibreChat stack was restarted, then
  `/health`, worker live payload, noVNC asset proxy, and Watch / Steer were rechecked against the
  freshly loaded code.
