# GlassHive Standard QA Cases

## Case ID Convention

Use `GH-STD-NNN` for durable cases and `GH-STD-UC-NNN` for natural user use cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| GH-STD-001 | `48_GlassHive_Workstation_Sandbox_Runtime.md#glasshive-standard-qa` | User gets a grounded current-fact answer or an honest retrieval failure class. | Direct UI, direct MCP, LibreChat MCP | Manual/browser plus provider-health checks | PARTIAL/PASS 2026-05-23; direct MCP and LibreChat passed, direct UI parity remains a release-complete gap. |
| GH-STD-002 | Same | User uploads a public-safe PDF/workbook/binary fixture and downloads a validated file output without type downgrades. | Direct UI, direct MCP, LibreChat MCP, artifacts | Manual/browser plus artifact/path tests | PASS 2026-05-24 for MCP artifact traversal and upload-materialization regressions; broader upload/download PASS 2026-05-23. |
| GH-STD-003 | Same | User schedules a GlassHive task from raw LibreChat/MCP paths without depending on Scheduling Cortex-only behavior. | Direct MCP, LibreChat MCP, scheduler/runtime state | Manual/browser/API | PASS 2026-05-23 after the GlassHive scheduler tool allowlist/routing fix. |
| GH-STD-004 | Same | User resumes named/favorited workspaces with preserved files/browser state after stop/restart/idle termination. | Direct UI, LibreChat MCP, workspace desktop/browser, DB/state | Manual/browser plus lifecycle tests | PARTIAL 2026-05-23; idle-resume and retained data passed through direct MCP, full LibreChat named/favorite workflow remains. |
| GH-STD-005 | Same | Three current, representative wildcard agentic tasks pass without hardcoded prompt or tool heuristics. | Direct UI, direct MCP, LibreChat MCP | Manual/browser plus code review for no overfit | PARTIAL 2026-05-23; direct MCP wildcard/profile smoke passed for available local profiles, full three-surface set remains. |
| GH-STD-006 | Same | Enterprise access/security requirements are proven with real user paths and supporting evidence. | UI, MCP, API, artifacts, signed links, logs, DB | Automated tests plus Playwright/API probes | PASS 2026-05-24 after deployed OAuth gate, signed-link browser QA, artifact traversal regression, and token-log redaction checks. |
| GH-STD-007 | Same | Efficiency, performance, idle/paused/max-duration reaping, and workspace/worker quotas are measured and enforced. | UI, MCP, API, worker lifecycle, logs, DB | Automated tests plus timing/quota probes | PASS/PARTIAL 2026-05-24; profile allowlist guardrail and deployed retained-workspace cost posture passed, broad cloud load/perf remains a scale follow-up. |
| GH-STD-008 | Same | Professional GlassHive UX stays aligned, spacious, scrollable, and field-stable. | Direct UI, watch/takeover, workspace hive, mobile viewport | Playwright/browser QA | PASS 2026-05-24 after local and deployed browser QA for Workspaces hive, completed labels, toggles, two-column layout, and multiline steering. |
| GH-STD-009 | Same | Claude/ClaudeViv review confirms or challenges the evidence-backed conclusion. | Review-only model pass | `claude-review-json.sh` or documented fallback | PASS/PARTIAL 2026-05-23; review completed and follow-ups were applied or recorded. |
| GH-STD-010 | Same | Provider secrets are not left in persistent workspace shell files or post-run takeover context. | Worker bootstrap, View / Steer shell, logs, workspace files | Automated mode tests plus live secret-file probe | PASS 2026-05-24 for run-only secret files, owner-only modes, and live post-run absence; active-process shared-key risk remains a documented broker/virtual-key follow-up. |
| GH-STD-011 | Same | Cloud workers cannot reach Azure metadata endpoints. | Docker worker network, VM firewall, logs | Live container/network probe or guardrail inspection | PASS 2026-05-24; live Docker worker-network probe and scheduled drift probe passed. |
| GH-STD-012 | Same | Invalid default worker/profile config fails loudly instead of silently switching users to a different worker. | MCP, direct UI, config compiler/runtime env | Automated config tests | PASS 2026-05-24 for MCP and direct UI default-profile fail-loud regressions. |
| GH-STD-013 | Same | Signed View / Steer link lifetime and active session lifetime are both enforced without blocking fresh owner-scoped recovery links. | Signed links, watch UI, websocket/session stream | Automated/API/browser timing tests | PASS/PARTIAL 2026-05-24; sign-time TTL cap, active websocket close, persisted deadline reuse, fresh-link reopen after expiry, and old expired-link rejection passed locally; live expired-row fresh-link recovery passed in Edge. Browser close-copy polish remains client-specific. |
| GH-STD-014 | Same | Users can save default worker and effort preferences without affecting other users. | Direct UI, MCP, API, DB/state | Automated/API/MCP/browser tests | PASS/PARTIAL 2026-05-24; automated API/MCP/UI tests and live MCP preference smoke passed, multi-browser two-real-user UI proof remains client-specific. |
| GH-STD-015 | Same | Metadata-block firewall drift is detected automatically after deployment. | Azure VM, Docker worker network, systemd timer/logs | Scheduled probe plus alert | PASS/PARTIAL 2026-05-24; stricter hourly systemd probe passed live and distinguishes blocked endpoints from probe-runtime failure, with external alert transport still deployment-specific. |
| GH-STD-016 | Same | Standalone status/wait tools report the newest worker result instead of stale failed context, without hiding the requested run outcome. | Direct MCP, LibreChat MCP, worker runs/artifacts | Automated MCP test plus live conversation RCA | PASS 2026-05-24 locally and on a live enterprise deployment for stale-run wait regression and requested-run outcome preservation. |
| GH-STD-017 | Same | Deployment default worker profile is honored when the caller omits `profile`. | UI, MCP, API, worker runtime, provider route | Automated/default-path MCP launch plus live worker smoke | PASS/PARTIAL 2026-05-25 UTC on a live enterprise deployment; default-path MCP launch omitted `profile`, resolved to `codex-cli`, completed through the validated Responses route, and cleanup terminated the QA worker. |

## Natural User Use Case Checklist

QA evidence in this public repo must stay text-only unless a reviewer explicitly approves a
synthetic image fixture. Do not commit browser screenshots, screen recordings, generated user files,
or other media from live QA; keep raw visual evidence in the approved private evidence location and
summarize the visible result here.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| GH-STD-UC-001 | Ask a latest/current-events web-search question. | GH-STD-001 | Direct UI, direct MCP, LibreChat MCP | Provider health, logs, worker output, final answer, fallback classification | Clear answer with source/evidence, or clear blocked/failure class. | PARTIAL/PASS 2026-05-23; direct MCP and LibreChat passed, direct UI parity remains. |
| GH-STD-UC-002 | Upload a public-safe PDF, workbook, or other binary fixture and request a transformation that preserves the requested artifact type. | GH-STD-002 | Direct UI, direct MCP, LibreChat MCP | Upload projection, workspace files, generated artifact list, download response, opened output | Downloadable file exists, opens, and aligns with prompt/success criteria. LibreChat deployments with shared upload storage must prove GlassHive can read the actual upload bytes, not only filename metadata or extracted text. | PASS 2026-05-24 locally and on a live enterprise deployment for shared-upload materialization. |
| GH-STD-UC-003 | Schedule "in 20 minutes do X" or "on Mondays do X" through GlassHive. | GH-STD-003 | Direct MCP and LibreChat MCP | Schedule row/state, trigger logs, callback/delivery state | Schedule is accepted, persisted, and executes or is visibly pending with correct timing. | PASS 2026-05-23. |
| GH-STD-UC-004 | Name a worker/workspace, favorite it, manually customize files/browser state, stop/restart, then resume. | GH-STD-004 | Direct UI, workspace desktop/browser, LibreChat MCP | DB/state, workspace files, browser profile evidence, idle/restart events | Resume is fast enough, state persists, and the user can target the named workspace naturally. | PARTIAL 2026-05-23. |
| GH-STD-UC-005 | Research current agent/code-interpreter/OpenClaw/Codex/Claude use cases, define three quick wildcard tasks, and run them. | GH-STD-005 | Direct UI, direct MCP, LibreChat MCP | Research notes, prompts, logs, outputs, no-overfit code inspection | Representative tasks succeed or produce honest blockers without hardcoded behavior. | PARTIAL 2026-05-23. |
| GH-STD-UC-006 | Try unauthenticated, forged, wrong-user, wrong-tenant, traversal, tampered-link, and expired-link access. | GH-STD-006 | API, UI, direct MCP, artifact links | HTTP status, sanitized logs, DB/audit counts, automated security tests | All unauthorized or unsafe actions fail closed; allowed same-user actions still work. | PASS 2026-05-24. |
| GH-STD-UC-007 | Leave idle/paused/over-duration workspaces, verify compute is released, enforce quotas, then resume and inspect state. | GH-STD-007 | UI, API, worker lifecycle, logs/DB | Idle/paused/max-duration reaper events, quota env/config, limit responses, container/process state, preserved files/artifacts | Idle or abandoned compute stops, active work is capped honestly, quotas stop excess work, and workspace data remains resumable. | PASS/PARTIAL 2026-05-24. |
| GH-STD-UC-008 | Verify launcher/watch/workspace UX remains professional, spacious, scrollable, and field-stable. | GH-STD-008 | Direct UI, watch/takeover, workspace hive, mobile viewport | Playwright snapshots/evals, console logs, UI tests | Title, fields, Workspaces hive, watch/takeover controls, and constrained scrolling match the documented design. | PASS 2026-05-24. |
| GH-STD-UC-009 | Ask for visible QA review and gap analysis after Codex completes its own evidence review. | GH-STD-009 | Claude/ClaudeViv review-only pass | Prompt, sanitized review output, Codex comparison notes | Review classifies claims and any gaps are addressed or recorded. | PASS/PARTIAL 2026-05-23. |
| GH-STD-UC-010 | Ask the worker to inspect its environment after completion without exposing provider keys. | GH-STD-010 | Direct MCP, View / Steer shell, workspace files | Secret-file modes, absent secret files after run, env/log probes | No raw provider key appears in persistent shell files, post-run takeover, logs, or artifacts. | PASS/PARTIAL 2026-05-24. |
| GH-STD-UC-011 | Try to fetch Azure metadata from inside a worker. | GH-STD-011 | Docker worker network | HTTP status/timeout, firewall rules, logs | Metadata access fails closed. | PASS 2026-05-24. |
| GH-STD-UC-012 | Misconfigure default worker outside the allowlist during QA. | GH-STD-012 | MCP and UI bootstrap | Automated test output, startup/error copy | Runtime fails loudly with the default/allowlist mismatch instead of silently using another profile. | PASS 2026-05-24. |
| GH-STD-UC-013 | Keep a watch session open past the signed link duration, then reopen from a fresh GlassHive link. | GH-STD-013 | Full-watch browser session | Session timer, websocket close, visible copy, fresh-link recovery | Existing sessions are time-bounded; an old expired link is rejected; a newly minted owner-scoped View / Steer link reopens the workspace cleanly. | PASS/PARTIAL 2026-05-24; local automated websocket close, persisted deadline reuse, fresh-link recovery, and old expired-link rejection passed; live expired-row fresh-link recovery passed in Edge. |
| GH-STD-UC-014 | Save a default worker and effort, then launch via UI and MCP without specifying either. | GH-STD-014 | Direct UI, MCP, API/DB | Preference row, launch payload, worker profile/bootstrap env, visible default controls | Only that authenticated user gets the saved default; other users keep their own/default settings. | PASS/PARTIAL 2026-05-24; live MCP preference launch passed, two-real-user browser proof remains client-specific. |
| GH-STD-UC-015 | Restart Docker or reapply guardrails, then wait for the scheduled metadata probe. | GH-STD-015 | Azure VM/systemd | systemd timer status, service logs, alert target | Probe passes when IMDS is blocked and fails noisily if IMDS becomes reachable or the probe cannot run. | PASS/PARTIAL 2026-05-24; stricter timer/service run passed live, example OnFailure unit added, external alert wiring optional. |
| GH-STD-UC-016 | Ask "wait/check results" after a worker had an older failed run but later completed. | GH-STD-016 | Direct MCP, LibreChat MCP | Tool output, run ordering, latest artifact links, chat wording | The assistant acknowledges the requested run outcome when stale, then answers from the newest effective run and provides available artifacts; it does not summarize an older failed run as the current outcome. | PASS 2026-05-24 locally and on a live enterprise deployment. |
| GH-STD-UC-017 | Launch a workspace without specifying a worker profile. | GH-STD-017 | MCP, direct UI | Worker profile selected, provider route, output artifact, cleanup state | Deployment default is used exactly; for enterprise defaults this should be `codex-cli` unless the deployment deliberately overrides it and proves the override. | PASS/PARTIAL 2026-05-25 UTC. |

## GH-STD-001 - Web Search And Current Fact

- Requirement: GlassHive Standard QA mandatory case 1.
- Risk covered: the worker reports stale or invented current facts, or hides provider/search failure.
- Preconditions: configured provider/search path or explicit blocked reason; current date recorded;
  synthetic public-safe prompt.
- Steps:
  1. Run the current-fact prompt through direct GlassHive UI.
  2. Run the same class of prompt through direct MCP.
  3. Run the same class of prompt through LibreChat MCP.
  4. Compare answer, citations/evidence, logs, provider health, and fallback behavior.
- Expected result: grounded answer with current evidence, or explicit failure classification:
  successful-empty, provider unavailable, timeout, rate limit, auth/config missing, request
  rejected, unsupported configuration, or local prerequisite unavailable.
- Forbidden result: hallucinated winner/news, "nothing found" masking an operational failure, or
  direct UI/MCP/LibreChat parity drift.
- Evidence to capture: prompt date, visible result, source/fallback summary, logs, provider health,
  worker state, and any blocked prerequisite.
- Full-view evidence minimum: visible answer plus logs/provider-state comparison for all three
  surfaces.
- Automation: manual/browser plus provider-health probes.
- Last run: PARTIAL/PASS 2026-05-23; direct MCP and LibreChat MCP passed with source/evidence,
  while direct UI current-fact parity remains a release-complete gap.

## GH-STD-002 - File Upload, Autonomous Transformation, Download, And Validation

- Requirement: GlassHive Standard QA mandatory case 2.
- Risk covered: uploads are not materialized, binary artifacts are silently downgraded to extracted
  text, artifacts are inaccessible, output is low quality, or QA overfits bootstrap instructions to
  one prompt.
- Preconditions: public-safe PDF/workbook/binary fixture; artifact download auth configured; no
  private file contents.
- Steps:
  1. Upload the fixture through each required surface.
  2. Ask the worker to redesign it into PPT or HTML with success criteria.
  3. Let the worker complete autonomously using the normal bootstrap self-check harness.
  4. Download, open, and inspect the output like a user.
  5. Probe traversal/cross-user artifact access where enterprise mode applies.
  6. Verify MCP artifact tools never sign absolute, parent-relative, `.git`, or backslash traversal
     paths before returning a download URL.
  7. For PDF/DOCX/XLSX/PPTX/media/archive and other binary-preserving tasks, verify the worker
     received the original bytes in `uploads/` and did not substitute a `.txt` extraction unless the
     user explicitly asked for text extraction only.
  8. For LibreChat enterprise deployments, verify the GlassHive upload root is the same trusted
     upload storage LibreChat uses, or mark binary/PDF round-trip as blocked. Filename metadata alone
     is not sufficient evidence that the worker can read the file bytes.
  9. In shared-upload deployments, attempt to reference another user's upload path or filename from
     the prompt/tool payload and verify GlassHive does not copy those bytes into the workspace.
- Expected result: downloadable output opens and aligns with the input and success criteria.
- Forbidden result: missing upload, broken link, private path exposure, traversal access, or
  runtime code that detects this exact QA prompt. It is also forbidden to delete the problem
  statement by converting the user's PDF/workbook/media/archive into `.txt` when the requested task
  requires the original file type or layout-preserving output.
- Evidence to capture: upload projection, workspace file list, artifact metadata, download status,
  opened-file validation, logs, and DB/audit counts.
- Full-view evidence minimum: real upload/download/open path plus logs/DB/artifact confirmation.
- Automation: manual/browser plus artifact/path regression tests.
- Last run: PASS 2026-05-25 UTC for live LibreChat MCP PDF-byte projection, owner-scoped
  cross-upload denial, and missing-binary metadata/blocker fallback on an enterprise deployment.
  PASS 2026-05-24 for MCP artifact signing and header-upload materialization regressions;
  2026-05-23 across direct UI, direct MCP, and LibreChat MCP, including validated artifact downloads
  and traversal/cross-user probes.

## GH-STD-003 - Raw GlassHive Scheduling

- Requirement: GlassHive Standard QA mandatory case 3.
- Risk covered: scheduling only works through a separate cortex path and not through GlassHive's raw
  MCP/LibreChat integration.
- Preconditions: scheduling feature enabled or explicit product gap recorded; synthetic scheduled
  prompt.
- Steps:
  1. Create a short-delay schedule through direct MCP.
  2. Create an equivalent natural-language schedule through LibreChat MCP.
  3. Inspect persisted schedule state and trigger/delivery logs.
  4. Verify execution or pending state through the user-visible surface.
- Expected result: schedule is accepted, persisted, and executed at the right time, or the product
  honestly exposes the missing GlassHive scheduling capability.
- Forbidden result: relying on Scheduling Cortex-only behavior while claiming raw GlassHive support.
- Evidence to capture: schedule state, visible copy, trigger/callback logs, and DB counts.
- Full-view evidence minimum: real schedule creation plus persisted state and delivery evidence.
- Automation: manual/browser/API.
- Last run: PASS 2026-05-23 through direct MCP and LibreChat MCP after the GlassHive scheduler tool
  allowlist/routing fix, with persisted schedule/run/artifact evidence.

## GH-STD-004 - Persistence, Favorites, Idle, And Resume

- Requirement: GlassHive Standard QA mandatory case 4.
- Risk covered: named workspaces lose state, idle termination deletes data, or UI cannot target a
  saved workspace naturally.
- Preconditions: workspace naming/favorites available or explicit UI gap recorded; idle reaper
  configured for QA; synthetic account.
- Steps:
  1. Create or select a named workspace and worker.
  2. Mark it favorite when the UI supports favorites.
  3. Modify files and browser state manually through the workspace.
  4. Stop/restart GlassHive or the worker and let idle reaper run when applicable.
  5. Resume the same workspace from direct UI and LibreChat MCP.
- Expected result: saved files/browser state persist; compute is released when idle; resume is
  efficient and visibly targets the same named workspace.
- Forbidden result: cross-user reuse, state loss, slow cold start presented as instant resume, or
  hidden cost accumulation.
- Evidence to capture: workspace tile/name/favorite state, files/browser proof, idle events,
  container/process state, DB rows/counts, and resume timing.
- Full-view evidence minimum: visible workspace state before/after restart plus logs/DB lifecycle
  proof.
- Automation: manual/browser plus lifecycle regression tests.
- Last run: PARTIAL 2026-05-23; direct MCP proved idle termination with retained workspace data and
  resume, while the full LibreChat named/favorite browser workflow remains open.

## GH-STD-005 - Wildcard Agentic Compatibility

- Requirement: GlassHive Standard QA mandatory case 5.
- Risk covered: QA only covers scripted happy paths and misses realistic agentic workflows.
- Preconditions: current web research available or explicit blocked reason; configured worker
  profiles for the run.
- Steps:
  1. Research current public use patterns for Codex, Claude, OpenClaw, code-interpreter-like agents,
     and browser/computer-use workers.
  2. Define three quick tasks that cover the same complexity without private data.
  3. Run them through direct UI, direct MCP, and LibreChat MCP when relevant.
  4. Inspect outputs, logs, artifacts, and code for no hardcoded prompt/tool/provider heuristics.
- Expected result: representative tasks succeed or expose honest blockers, with no overfit runtime
  logic.
- Forbidden result: keyword/regex intent matching, prompt-specific branching, provider-label hacks,
  or tests that pass only because the QA prompt was hardcoded.
- Evidence to capture: research summary, chosen tasks, visible outputs, logs, artifacts, code search
  result, and blocked prerequisites.
- Full-view evidence minimum: three real tasks plus supporting evidence and no-overfit inspection.
- Automation: manual/browser plus `rg` inspection for suspicious new hardcoding.
- Last run: PARTIAL 2026-05-23; direct MCP wildcard/profile smoke passed for available local worker
  profiles, but the full three-wildcard set across all three surfaces remains open.

## GH-STD-006 - Enterprise Security And Access

- Requirement: GlassHive Standard QA mandatory access/security assessment.
- Risk covered: cross-user contamination, secret leakage, or unmanaged raw runtime links.
- Preconditions: enterprise mode or enterprise simulation; two synthetic users; service auth token;
  signed-link secret configured.
- Steps:
  1. Probe health vs all non-health unauthenticated routes.
  2. Create work as User A and attempt list/resume/watch/download/inference as User B.
  3. Probe forged headers, wrong token, wrong tenant, traversal, expired/tampered signed links.
  4. Probe provider-secret exposure in enterprise mode. Interactive shell startup files must not
     contain raw provider keys; if direct provider env is used, record whether the deployment uses
     per-user/virtual/brokered keys or a shared key risk exception.
  5. In Azure/cloud mode, probe that Docker workers cannot reach Azure metadata endpoints such as
     `169.254.169.254`.
  6. Attempt prompt/tool-payload escalation such as "read another user's files" by referencing an
     owner/path that does not match the authenticated assertion.
  7. Inspect UI for managed links and secret/path redaction.
- Expected result: fail-closed auth/scoping, no cross-contamination, and member UI exposes only
  managed user-safe links.
- Forbidden result: docs/OpenAPI/UI/artifacts/watch accessible without auth; raw VM paths, ports,
  provider endpoints, or secrets in member-visible output.
- Evidence to capture: HTTP statuses, visible UI, logs, DB/audit counts, env/config summary, timing,
  provider-secret exposure probe, metadata-block probe, and automated test output.
- Full-view evidence minimum: browser/API probes plus logs/DB and automated security tests.
- Automation: runtime/UI/config tests plus Playwright/API probes.
- Last run: PASS 2026-05-25 UTC for owner-scoped upload byte denial in live enterprise MCP.
  PASS 2026-05-24 after local and deployed checks. Evidence includes public OAuth gating
  for non-health routes, signed-link browser access to the workspace UI, artifact traversal
  regression coverage, VM service/log inspection with raw token access logs disabled, and a
  signed-in enterprise MCP connection verification.

## GH-STD-007 - Efficiency, Performance, Idle Reaping, And Quotas

- Requirement: GlassHive Standard QA mandatory efficiency/performance assessment.
- Risk covered: expensive idle compute, quota bypass, slow resume paths, or active work killed by
  over-aggressive cleanup.
- Preconditions: enterprise mode or enterprise simulation; idle/quota env configured; two synthetic
  users when quota scope is user/tenant based.
- Steps:
  1. Configure or inspect idle termination (`GLASSHIVE_IDLE_TERMINATE_AFTER_S`), paused termination
     (`GLASSHIVE_PAUSED_TERMINATE_AFTER_S`), reaper interval (`GLASSHIVE_IDLE_REAPER_INTERVAL_S`),
     max run/watch duration, max active workers per user, and max tenant/workspace limits. If the
     cap env vars are not implemented in the current build, mark that sub-check `BLOCKED` or
     `PARTIAL` instead of accepting a generic quota claim.
  2. Start a workspace, measure dispatch/spawn/resume timing, then let it become idle.
  3. Verify idle compute is released while workspace files/browser state are preserved.
  4. Pause a workspace and verify abandoned paused compute is stopped when the paused threshold is
     exceeded while files/artifacts remain.
  5. Run a synthetic over-duration task and verify `GLASSHIVE_MAX_RUN_DURATION_S` cancels it
     honestly and preserves the workspace.
  6. Attempt to exceed per-user concurrent-worker and per-tenant concurrent-workspace limits.
  7. Attempt to launch a worker profile excluded by `GLASSHIVE_ALLOWED_WORKER_PROFILES` and verify
     it is hidden from the launcher and rejected by the API/MCP runtime path.
  8. Verify queued/running/checkpoint workers are not killed by idle cleanup.
- Expected result: idle compute stops, active work is preserved, resume is efficient, and limit
  exceeded behavior is visible and honest.
- Forbidden result: idle cleanup deletes data, active work is killed, quota bypass is possible, or
  cost-relevant workspaces accumulate without visible controls.
- Evidence to capture: env/config summary, timing, worker/container/process state, DB/audit counts,
  visible quota/limit copy, max-duration cancellation evidence, paused-compute cleanup evidence, and
  automated lifecycle test output.
- Full-view evidence minimum: browser/API lifecycle path plus logs/DB and timing evidence.
- Automation: lifecycle regression tests plus Playwright/API timing/quota probes.
- Last run: PASS/PARTIAL 2026-05-24. Profile allowlist guardrails passed in automated runtime/API
  tests and deployed Workspaces showed completed/retained workers as non-active cost-managed
  workspaces; broad load/performance validation remains a scale follow-up.

## GH-STD-008 - Professional UX And Launcher Contract

- Requirement: GlassHive Standard QA mandatory professional UX assessment.
- Risk covered: drift back to cramped/basic UI, overlapping text layers, inert workspace navigation,
  hidden controls, or ad hoc field names that violate the documented GlassHive launch contract.
- Preconditions: local direct GlassHive UI running; browser automation available; at least one
  synthetic active or retained workspace when testing the hive view.
- Steps:
  1. Open the launcher in a real browser.
  2. Verify title `Define the project once. Watch the worker deliver.`
  3. Verify fields: `Describe your project`, required `Success Criteria`, optional `Context`, and
     `Workspace Type` defaulting to `Sandboxed Workspace` unless host-native workers are truly available.
  4. Open `Workspaces`, verify active and resumable tiles appear by default and inactive retained
     workspaces appear on demand.
  5. Open watch/takeover and verify workspace view gets primary real estate, controls do not overlap,
     constrained screens scroll, and Play/Pause/Interrupt placement remains efficient.
  6. Verify `Inactive Workspaces` off hides retained/completed/idle tiles; turning it on reveals
     them without calling them active.
  7. Verify wide desktop viewports fill with two readable workspace columns when enough width exists.
  8. Verify `Watch` and `Status Report` toggles independently show live workspace previews and
     latest workspace output.
  9. Verify completed work is labeled `Completed`, not idle/resume, while still allowing follow-up.
  10. Verify hive and full-watch steer fields are expanding textareas where `Shift+Enter` inserts a
      newline and `Enter` sends.
  11. Confirm a fresh sandbox desktop uses a neutral GlassHive/black idle surface and does not leak
      the upstream Selenium Grid splash wallpaper.
  12. Refresh and repeat on a constrained/mobile viewport.
- Expected result: UI remains professional, spacious, usable, scrollable, and aligned with the
  documented labels and workspace mental model.
- Forbidden result: title drift, `title`/`goal` ad hoc fields replacing documented fields, inert
  `Workspaces`, overlapping layers, non-scrolling pages, raw runtime/noVNC links as the primary
  takeover page, controls wasting workspace real estate, or upstream Selenium desktop branding
  visible in fresh worker workspaces.
- Evidence to capture: Playwright snapshots/evals, console errors, viewport dimensions, visible
  field/control state, logs, and affected UI test output.
- Full-view evidence minimum: direct browser path, watch/takeover path, workspace hive path,
  constrained viewport, and supporting UI tests/logs.
- Automation: UI tests plus Playwright/browser QA.
- Last run: PASS 2026-05-24 after local and deployed browser QA. Verified `Inactive Workspaces`
  filter behavior, wide two-column tile density, stable resume hover, `Completed` labels, Watch and
  Status Report toggles, full-watch signed link access, and multiline `Shift+Enter` steering.
  2026-05-23 is superseded by the escaped issues promoted above.

## GH-STD-009 - Review-Only Claude/ClaudeViv Double Check

- Requirement: GlassHive Standard QA mandatory second opinion.
- Risk covered: Codex misses a requirement, misstates evidence, or accepts a gap as done.
- Preconditions: Codex has already produced its own evidence-backed conclusion; prompt is sanitized.
- Steps:
  1. Build a review prompt with exact docs, files, tests, runtime evidence, provisional conclusion,
     ruled-out alternatives, and claims to validate.
  2. Run Claude/ClaudeViv in review-only mode.
  3. Compare findings against repo docs/evidence.
  4. Fix confirmed gaps or record residual risks before final acceptance.
- Expected result: claims are classified as `confirmed`, `partially_confirmed`, `cannot_confirm`, or
  `contradicted`, and Codex acts on evidence-backed findings.
- Forbidden result: using Claude as a substitute for real user QA, handing it raw secrets, or letting
  it edit code by default.
- Evidence to capture: review prompt, JSON/result artifact, Codex comparison notes, and follow-up
  fixes or residual risks.
- Full-view evidence minimum: saved review artifact plus Codex reconciliation.
- Automation: `claude-review-json.sh` when available; documented direct CLI fallback if the helper
  stalls or is unavailable.
- Last run: PASS/PARTIAL 2026-05-23; `reports/2026-05-23-claudeviv-review.json` supports the
  current verdict, concrete follow-ups were applied, and release-complete gaps remain recorded.

## GH-STD-010 - Provider Secret Exposure And Post-Run Shell Safety

- Requirement: Enterprise provider secrets must not be left in persistent workspace files or
  user-facing takeover shells.
- Risk covered: a user, worker, or later resumed shell sees raw provider keys that were meant only
  for the active worker process.
- Preconditions: enterprise mode, provider env allowlist, run-only secret exposure enabled, and a
  synthetic provider key fixture.
- Steps:
  1. Launch a worker with provider credentials projected through the enterprise provider path.
  2. Verify `.glasshive/runtime.env` contains non-secret settings only.
  3. Verify `.glasshive/secret-runtime.env` and `.glasshive/secret-runtime.keys` are owner-only while
     present and absent after the worker command starts/completes.
  4. Inspect post-run takeover shell, logs, artifacts, and user-visible output for raw provider
     values.
  5. Record whether the deployment uses shared keys, virtual keys, or a host-side provider broker.
- Expected result: no raw provider key remains in persistent files, logs, artifacts, or post-run
  shell context.
- Forbidden result: raw provider keys in `.bashrc`, `.glasshive/runtime.env`, logs, artifacts, or
  completed takeover shells.
- Evidence to capture: file modes, post-run file absence, redacted env/log probes, worker result,
  and residual active-process key risk classification.
- Full-view evidence minimum: automated bootstrap test plus one live worker probe.
- Automation: bootstrap/unit tests and live worker workspace-file probe.
- Last run: PASS/PARTIAL 2026-05-24; file/shell persistence passed, active-process shared-key risk
  remains documented pending virtual keys or broker.

## GH-STD-011 - Azure Metadata Block

- Requirement: cloud Docker workers must not reach cloud metadata endpoints.
- Risk covered: a worker steals managed identity, VM metadata, or platform tokens.
- Preconditions: Azure VM deployment with Docker guardrail rules installed.
- Steps:
  1. Inspect `DOCKER-USER` rules for `169.254.169.254` and `168.63.129.16` blocks.
  2. Run a synthetic container/network probe when allowed by the environment.
  3. Restart Docker or reapply the guardrail unit and repeat the probe.
- Expected result: metadata requests from worker containers fail closed; DNS exceptions, if needed,
  are narrow and explicit.
- Forbidden result: HTTP 200 metadata response from any worker container.
- Evidence to capture: firewall rules, probe result, service status, and logs.
- Full-view evidence minimum: live cloud probe or equivalent guardrail inspection plus service
  status.
- Automation: deployment checklist now; scheduled probe is a follow-up.
- Last run: PASS/PARTIAL 2026-05-24; deployed firewall rules verified, scheduled probe remains.

## GH-STD-012 - Default Worker Profile Fail-Loud Behavior

- Requirement: configured defaults must not silently drift to another worker profile.
- Risk covered: an operator thinks users are running one profile while the runtime silently launches
  another.
- Preconditions: `GLASSHIVE_DEFAULT_WORKER_PROFILE` and `GLASSHIVE_ALLOWED_WORKER_PROFILES`
  configured.
- Steps:
  1. Configure a valid default inside the allowlist and confirm MCP/UI use it.
  2. Configure an invalid default outside the allowlist.
  3. Confirm MCP/UI fail loudly with a clear configuration error.
- Expected result: valid defaults are honored; invalid defaults fail loudly.
- Forbidden result: fallback to another worker profile without an operator-visible error.
- Evidence to capture: automated test output and runtime error copy.
- Full-view evidence minimum: MCP and UI test coverage.
- Automation: unit tests.
- Last run: PASS 2026-05-24.

## GH-STD-013 - Watch Link And Active Session Lifetime

- Requirement: View / Steer access must remain owner-scoped and time-bounded while letting users
  recover a workspace from a freshly minted GlassHive link.
- Risk covered: a signed link expires but an already-open browser session remains usable
  indefinitely, or the server overcorrects by rejecting a legitimate fresh owner-scoped link.
- Preconditions: signed link secret configured and `GLASSHIVE_MAX_WATCH_SESSION_DURATION_S` set.
- Steps:
  1. Generate a View / Steer signed link with a short TTL.
  2. Confirm tampered/expired links fail.
  3. Keep an active watch session open past the duration.
  4. Confirm the server closes the active session or requires a fresh signed link.
  5. Confirm an old expired link is rejected and a new owner-scoped link opens the workspace.
- Expected result: sign-time expiry and active-session expiry are both enforced, and fresh
  GlassHive-generated recovery links work.
- Forbidden result: an old browser session remains usable forever after link expiry, or a fresh
  signed View / Steer link fails because a previous session row expired.
- Evidence to capture: HTTP/websocket status, visible UI copy, and logs.
- Full-view evidence minimum: signed-link tests plus browser/websocket timing test.
- Automation: signed-link tests now; websocket/browser timing follow-up.
- Last run: PASS/PARTIAL 2026-05-24; local automated session cap and fresh-link recovery passed, and
  live Edge QA opened the affected completed workspace from a fresh link after an expired
  watch-session row. Browser close-copy polish remains.

## GH-STD-017 - Deployment Default Worker Profile

- Requirement: when a caller omits `profile`, GlassHive must honor the authenticated user's saved
  default first and then `GLASSHIVE_DEFAULT_WORKER_PROFILE`; it must not silently drift to another
  worker because that route happened to be green during setup.
- Risk covered: users unexpectedly get the wrong worker/runtime, provider-route failures are hidden
  by changing defaults, or cost/security expectations differ from the documented deployment.
- Preconditions: `GLASSHIVE_DEFAULT_WORKER_PROFILE` is set, included in
  `GLASSHIVE_ALLOWED_WORKER_PROFILES`, and the provider route for that profile is configured.
- Steps:
  1. Clear or use a synthetic user with no saved worker preference.
  2. Call `workspace_launch` without `profile`.
  3. Confirm returned diagnostics or DB/runtime evidence show the configured default profile.
  4. Wait for completion or honest provider failure.
  5. If the default is `codex-cli`, verify the Responses-compatible Codex route completes a simple
     file-output task.
  6. Terminate the QA worker after evidence capture to avoid consuming active-worker capacity.
- Expected result: the configured default is used exactly, and the selected provider route either
  completes or returns an honest provider blocker.
- Forbidden result: default falls back to another profile, the failure is disguised as success, or
  the QA worker remains active after the test.
- Evidence to capture: sanitized env/default values, launch payload profile, run state, artifact or
  blocker copy, provider route class, and cleanup state.
- Automation: direct MCP smoke that intentionally omits `profile`.
- Last run: PASS/PARTIAL 2026-05-25 UTC; live enterprise default-path MCP launch resolved to
  `codex-cli`, completed, returned a View / Steer URL, and cleanup terminated the worker.

## Incident Promotion Checklist

Every missed GlassHive user-visible bug must be promoted into the reusable QA suite by doing all of
the following:

- Convert the issue into a synthetic public-safe regression case.
- Preserve the failure shape without private prompts, accounts, local paths, screenshots, or raw
  logs.
- Add both positive and negative controls when the bug involves auth, prompt/tool selection, file
  paths, uploads, artifacts, or worker lifecycle.
- Add deterministic automation when the behavior can be checked without a real external service.
- Rerun impacted Standard QA cases before claiming the fix is complete.
