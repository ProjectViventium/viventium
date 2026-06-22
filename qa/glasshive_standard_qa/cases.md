# GlassHive Standard QA Cases

## Case ID Convention

Use `GH-STD-NNN` for durable cases and `GH-STD-UC-NNN` for natural user use cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| GH-STD-001 | `48_GlassHive_Workstation_Sandbox_Runtime.md#glasshive-standard-qa` | User gets a grounded current-fact answer or an honest retrieval failure class. | Direct UI, direct MCP, LibreChat MCP | Manual/browser plus provider-health checks | PARTIAL/PASS 2026-05-23; direct MCP and LibreChat passed, direct UI parity remains a release-complete gap. |
| GH-STD-002 | Same | User uploads a public-safe PDF/workbook/binary fixture and opens/downloads a validated file output without type downgrades or surprise downloads from the default file link. | Direct UI, direct MCP, LibreChat MCP, artifacts | Manual/browser plus artifact/path tests | PASS 2026-05-27 for direct UI host and sandbox upload materialization plus no forced artifact/download response; PASS 2026-05-25 for default open-preview link, explicit download link, signed-link kind separation, text/binary/image/XSS artifact regressions; PASS 2026-05-24 for MCP artifact traversal and upload materialization. |
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
| GH-STD-013 | Same | Durable authenticated View / Steer short refs can reopen retained workspaces while raw signed tokens and active sessions remain bounded. | Short refs, signed tokens, watch UI, websocket/session stream | Automated/API/browser timing tests | PARTIAL 2026-06-20; local regressions cover default non-expiring `/r/{ref}`, auth gate, wrong-user rejection, fresh session-cookie minting after token expiry, configured short-ref TTL, legacy-row migration, and runtime-created/UI-resolved shared-state behavior. Full browser/live timing rerun pending. |
| GH-STD-014 | Same | Users can save default worker and effort preferences without affecting other users, and MCP plus Glass Drive UI apply the same per-profile effort policy. | Direct UI, MCP, API, DB/state | Automated/API/MCP/browser tests | PASS/PARTIAL 2026-06-19; automated API/MCP/UI tests and live MCP preference smoke passed, multi-browser two-real-user UI proof remains client-specific. Additional local regression scope includes Codex `none` parity and Claude `max` projection to runtime env from both MCP and Glass Drive UI, and the Glass Drive UI selector exposes Codex `none`. |
| GH-STD-015 | Same | Metadata-block firewall drift is detected automatically after deployment. | Azure VM, Docker worker network, systemd timer/logs | Scheduled probe plus alert | PASS/PARTIAL 2026-05-24; stricter hourly systemd probe passed live and distinguishes blocked endpoints from probe-runtime failure, with external alert transport still deployment-specific. |
| GH-STD-016 | Same | Standalone status/wait tools report the newest worker result instead of stale failed context, without hiding the requested run outcome. | Direct MCP, LibreChat MCP, worker runs/artifacts | Automated MCP test plus live conversation RCA | PASS 2026-05-24 locally and on a live enterprise deployment for stale-run wait regression and requested-run outcome preservation. |
| GH-STD-017 | Same | Deployment default worker profile is honored when the caller omits `profile`, and legacy `backend=openclaw` metadata never overrides the selected worker profile/runtime. | UI, MCP, API, worker runtime, provider route, logs | Automated default-path API/MCP/UI tests plus live worker smoke | PASS/PARTIAL 2026-06-19; prior live default-path smoke passed, and local regression scope now includes direct API omitted-profile creation, legacy blank project defaults in the built-in UI, alias reprofile runtime refresh, and live log routing from current profile instead of stale backend/runtime metadata. |
| GH-STD-018 | Same | Failed long-running worker tasks report a structured failure class, completion waits do not mislabel still-running work as failure, fresh user-facing artifacts are delivered even if the provider disconnects or the worker I/O capture closes after creation, and retryable work can be explicitly continued in the same workspace without overfitting the prompt or recursively bloating continuation instructions. | Direct MCP, LibreChat MCP, worker runtime, DB/state | Automated failure-class/wait/continue tests plus user-grade browser QA | PASS/PARTIAL 2026-06-22; local approval scope passed for host wait/continue, failure-class regressions, timeout/transcript metadata, evidence-check failure recovery guard, local browser wait/control fixture, and provider-backed Codex plus Claude host browser wait/continue. Cloud/deployment/LibreChat live reruns remain deployment gates. |
| GH-STD-019 | Same | Host-default deployments still honor explicit sandbox/Codex Workspace requests and preflight or safely recover missing/incompatible host runtime substrate before creating dead work or asking the user to fix global state. | Direct MCP, LibreChat MCP, API, DB/state | Automated MCP/API tests plus user-grade browser QA | PARTIAL 2026-05-27; missing-CLI preflight exists, version-mismatch/managed-recovery browser QA pending. |
| GH-STD-020 | Same | Long prompts keep their full context when delegated, host-side orchestration checks stay out of worker blocker criteria, same-conversation wait/status recovers omitted ids safely, View / Steer is surfaced around long waits, and waiting/browser watching does not overload local/cloud resources. | Direct MCP, LibreChat MCP, tool payloads, logs/process state, Workspaces/watch browser polling | Automated MCP tests plus browser/resource QA | PASS 2026-05-25 locally for MCP contract tests, browser LibreChat launch/wait/result flow, View / Steer before wait, Workspaces inspection, artifact links, callback link sanitization, efficient 5-second wait polling, and state-aware Workspaces/full-watch browser polling backoff. PASS/PARTIAL 2026-06-16 on an approved enterprise deployment: live MCP schema/tool descriptions were patched to match disabled host-native workers and a signed-in browser smoke completed through the configured workspace worker with View / Steer and file preview evidence; broad cloud soak remains separate. |
| GH-STD-021 | Same | Every GlassHive file-delivery response uses a preview/open link as the primary user link and an explicitly labeled raw download link only as a secondary action; enterprise preview-page buttons remain signed. | Callbacks, direct API, signed links, MCP artifact tools, LibreChat-rendered links | Automated API/MCP contract tests plus browser click/no-download QA | PASS/PARTIAL 2026-06-22; local callback/link ordering regressions plus seven-file local preview/download browser proof passed. Live enterprise rerun remains a deployment gate after release pinning. |
| GH-STD-022 | Same | Host assistants delegate sparsely and faithfully: real goals, constraints, files, MCP/tool capabilities, and tool results are passed through without invented plans, fake MCP usage, forced artifacts, or provider-specific overfit. | LibreChat MCP, direct MCP, bootstrap files, worker prompts, logs/DB | Automated MCP/prompt tests plus browser user QA | PASS/PARTIAL 2026-05-27; automated contract tests, direct MCP anti-bluff, post-restart direct UI host run, direct UI host/sandbox upload, Prompt Workbench source/dry-run, schedule preflight/recovery, and logs/DB checks passed; LibreChat browser dispatch and live connected-account broker happy path are blocked by local model auth and MS365 MCP timeouts. |
| GH-STD-023 | Same | Capacity and callback guardrails prevent runaway cloud cost while giving the host a useful next step. | API, MCP, runtime DB/state, logs, enterprise deployment config | Automated API/MCP tests plus live synthetic quota/callback probes | PASS 2026-05-31 on an approved enterprise GlassHive deployment: active quota returned structured `glasshive_worker_quota_exceeded` with owner-scoped `available_workspace_options`, 900-second retry guidance, no sandbox/profile-switch advice, and no synthetic leftovers; a runaway callback row was retained as `dead_lettered` instead of retrying. |
| GH-STD-024 | Same | Master first-delivery wildcard deep-work document QA proves GlassHive can accept wildcard input, perform spectacular complete deep work, and deliver wildcard text/files/document formats without overfitting to one prompt or file type. | LibreChat MCP, direct MCP, direct UI, host/workstation workers, generated artifacts, logs/DB | Manual/browser/computer QA, Claude/Codex CLI comparison, artifact validation, native skill/browser-extension readiness, public-safe research notes | PASS/PARTIAL 2026-06-22; previous direct MCP/API and workspace document runs remain valid, and local fixture now validates Markdown, CSV, HTML, PDF, XLSX, DOCX, and PPTX artifact paths without overfitting. Remaining gaps are full deep-work PPTX/file-input variants, authenticated LibreChat full master prompt rerun, direct UI rerun, live Telegram dedupe rerun, brokered connected-account happy-path rerun after OAuth recovery, and export/recall sanitization. |
| GH-STD-025 | Same | GlassHive public MCP/API/UI payloads expose short link refs and compact status/launch/wait results without leaking raw signed tokens, stale backend labels, or internal IDs unless diagnostics are explicitly requested. | MCP, API, callbacks, preview pages, UI/WebSocket logs, worker profile metadata | Automated API/MCP/UI tests plus browser/log QA | PASS/PARTIAL 2026-06-22: local short-ref/redaction fixture, public-safety scan, compact payload regressions, and browser `/w/{ref}` checks passed. Release durability remains PARTIAL until the nested GlassHive source state is committed/reconciled and a clean parent pin/release branch is verified. |

## Natural User Use Case Checklist

QA evidence in this public repo must stay text-only unless a reviewer explicitly approves a
synthetic image fixture. Do not commit browser screenshots, screen recordings, generated user files,
or other media from live QA; keep raw visual evidence in the approved private evidence location and
summarize the visible result here.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| GH-STD-UC-001 | Ask a latest/current-events web-search question. | GH-STD-001 | Direct UI, direct MCP, LibreChat MCP | Provider health, logs, worker output, final answer, fallback classification | Clear answer with source/evidence, or clear blocked/failure class. | PARTIAL/PASS 2026-05-23; direct MCP and LibreChat passed, direct UI parity remains. |
| GH-STD-UC-002 | Upload a public-safe PDF, workbook, or other binary fixture and request a transformation that preserves the requested artifact type. | GH-STD-002 | Direct UI, direct MCP, LibreChat MCP | Upload projection, workspace files, generated artifact list, open-preview response, download response, opened output | Default file link opens a GlassHive file preview/landing page; the separately labeled download action downloads the raw file; file exists, opens, and aligns with prompt/success criteria. LibreChat deployments with shared upload storage must prove GlassHive can read the actual upload bytes, not only filename metadata or extracted text. | PASS 2026-05-27 for direct UI host and sandbox fixture upload/no forced artifact; PASS 2026-05-24 locally and on a live enterprise deployment for shared-upload materialization. |
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
| GH-STD-UC-013 | Keep a watch session open past the signed token duration, then reopen from the same authenticated short View / Steer link. | GH-STD-013 | Full-watch browser session | Session timer, websocket close, visible copy, same-link recovery, auth gate | Existing active sessions are time-bounded; raw expired signed tokens fail; the durable owner-authenticated `/r/{ref}` reopens the retained workspace and mints a fresh bounded session. | PARTIAL 2026-06-20; local regression coverage added for durable `/r/{ref}` after token expiry, unauthenticated rejection, wrong-user rejection, fresh session-cookie minting, and configurable short-ref TTL. Full browser/live rerun pending. |
| GH-STD-UC-014 | Save a default worker and effort, then launch via UI and MCP without specifying either. | GH-STD-014 | Direct UI, MCP, API/DB | Preference row, launch payload, worker profile/bootstrap env, visible default controls | Only that authenticated user gets the saved default; other users keep their own/default settings. | PASS/PARTIAL 2026-05-24; live MCP preference launch passed, two-real-user browser proof remains client-specific. |
| GH-STD-UC-015 | Restart Docker or reapply guardrails, then wait for the scheduled metadata probe. | GH-STD-015 | Azure VM/systemd | systemd timer status, service logs, alert target | Probe passes when IMDS is blocked and fails noisily if IMDS becomes reachable or the probe cannot run. | PASS/PARTIAL 2026-05-24; stricter timer/service run passed live, example OnFailure unit added, external alert wiring optional. |
| GH-STD-UC-016 | Ask "wait/check results" after a worker had an older failed run but later completed. | GH-STD-016 | Direct MCP, LibreChat MCP | Tool output, run ordering, latest artifact links, chat wording | The assistant acknowledges the requested run outcome when stale, then answers from the newest effective run and provides available artifacts; it does not summarize an older failed run as the current outcome. | PASS 2026-05-24 locally and on a live enterprise deployment. |
| GH-STD-UC-017 | Launch a workspace without specifying a worker profile, then reuse a named workspace alias with a different profile. | GH-STD-017 | MCP, direct UI, direct API, DB/logs | Worker profile selected, runtime label, provider route, output artifact, log path, cleanup state | Deployment default is used exactly; for enterprise defaults this should be `codex-cli` unless the deployment deliberately overrides it and proves the override. Alias reuse updates profile/runtime/log routing coherently, and legacy `backend=openclaw` never causes a Codex worker to be reported or inspected as OpenClaw. | PASS/PARTIAL 2026-05-25 UTC; expanded local regression coverage added 2026-06-19. |
| GH-STD-UC-018 | Ask a complex research/file task, ask GlassHive to wait for the result, observe a synthetic provider failure, then say continue/retry. | GH-STD-018 | MCP, LibreChat MCP, workspace state | Completion-wait timeout policy, failure class, retryability, original instruction preservation, continuation run id, visible chat wording, artifact links for partial files | The model waits with the configured completion timeout, reports "still running" on timeout instead of false failure, reports the real failure class when terminal failure occurs, surfaces partial artifacts when files exist, and uses `workspace_continue` to preserve the same workspace when the user asks to continue. | PASS 2026-06-22 for local approval scope: host wait/continue, failure-class, transcript metadata, evidence-failure guard, local browser control fixture, and provider-backed Codex plus Claude host browser wait/continue passed. |
| GH-STD-UC-019 | In a host-default Viventium deployment, ask the chat model to "use sandbox" or "use Codex Workspace" for a public-safe task. Separately exercise a missing or incompatible host runtime dependency. | GH-STD-019 | LibreChat MCP, direct MCP, API/DB | Tool call arguments, worker execution mode, worker/run row counts, blocked/recovery payload fields, visible chat wording | Explicit sandbox language results in `execution_mode=docker`; missing or too-old host substrate is classified before dead work is created; configured managed/profile/sandbox recovery is attempted when compatible; the assistant does not say work is running when no workspace was started and does not ask the user to change global machine state while managed recovery exists. | PARTIAL 2026-05-27; missing-CLI automation exists, version-mismatch/managed-recovery browser QA pending. |
| GH-STD-UC-020 | Give a long, constraint-heavy public-safe brief, ask GlassHive to use sandbox/Codex Workspace and wait, then inspect the MCP payload, visible chat, and resource usage. | GH-STD-020 | LibreChat MCP, direct MCP, process/log/DB state, Workspaces/watch browser pages | Tool arguments, full-context preservation, recent-dispatch fallback, View / Steer visibility, poll cadence, process list, browser network cadence | The worker receives the full available brief rather than a watered-down summary; host-side checks such as View / Steer visibility and wait cadence are verified by the host, not reported as worker blockers after deliverables are complete; wait/status uses explicit ids or same-conversation fallback; View / Steer is shown before or at least with final result; no abandoned browser/status loop overloads the machine. | PASS 2026-05-25 local browser QA with synthetic long brief, sandbox/Codex workspace, same-turn wait, artifact links, Workspaces inspection, DB/log evidence, resource snapshot, and completed-workspace browser polling backoff proof. PASS/PARTIAL 2026-06-16 enterprise browser smoke for corrected MCP schema/default workspace execution and View / Steer/file-preview evidence; not a full long-brief resource soak. |
| GH-STD-UC-021 | Click the primary GlassHive file link from a completed run, then click the explicit download action. | GH-STD-021 | LibreChat MCP callback, direct API, browser | Link labels/order, signed-token kind, response headers, browser download event, artifact open page content | Primary `Open GlassHive file` link opens a preview/landing page and does not download. Only the `Download file` action returns an attachment, and enterprise click-through does not require hidden auth headers. | PASS 2026-06-22 local API/MCP/browser QA including seven-file preview/download fixture; live enterprise rerun required after release pinning/deployment updates. |
| GH-STD-UC-022 | Ask GlassHive to use connected-account MCP/tools, deep research, or file work with ordinary user wording and inspect what the host passed into the worker. | GH-STD-022 | LibreChat MCP, direct MCP, bootstrap files, logs/DB, browser | Tool call payload, delegation audit, materialized MCP config/env/files, worker final report, artifact/open-link behavior | MCP/tool availability is advertised as capability context; the worker chooses the path; no fake MCP result, forced download, invented urgency rubric, provider checklist, or made-up success criteria appears in the worker brief or user response. | PASS/PARTIAL 2026-05-27; direct MCP anti-bluff, worker goal preservation, post-restart direct UI host run, direct UI host/sandbox upload, schedule preflight/recovery, and Prompt Workbench source checks passed; LibreChat browser dispatch and connected-account happy path blocked by local model auth and MS365 MCP timeouts. |
| GH-STD-UC-023 | Give GlassHive a wildcard input prompt or file(s), ask for deep research/work, and require a wildcard output such as text, PDF, Word, PowerPoint, or multiple files. | GH-STD-024 | LibreChat MCP, direct MCP, direct UI, host/workstation workers, generated artifacts, browser/computer validation | User prompt/input files, worker logs, generated files, opened document validation, final report, DB/run state, Claude/Codex comparison, public-safe research notes. | Worker delivers a spectacular, complete, deeply researched result in the requested or inferred format without hardcoded assumptions about input type, output type, document format, provider, or workflow. | PASS/PARTIAL 2026-06-22; local fixture validates PPTX along with Markdown/CSV/HTML/PDF/XLSX/DOCX, and host Codex/Claude smokes prove effort/profile execution. Remaining surfaces/variants are full deep-work PPTX/file-input variants, authenticated LibreChat full-prompt rerun, direct UI rerun, live Telegram dedupe rerun, connected-account happy path, and export/recall sanitization. |

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
  3. Let the worker complete autonomously using the normal bootstrap self-check harness. The worker
     must inspect its actual output and compare it with the prompt/success criteria before reporting
     completion, not merely say that work started.
  4. Click the default returned artifact/file link and verify it opens a GlassHive file
     preview/landing page rather than triggering an immediate raw download.
  5. Click the separately labeled `Download file` action, then download, open, and inspect the
     output like a user.
  6. Probe traversal/cross-user artifact access where enterprise mode applies.
  7. Verify MCP artifact tools never sign absolute, parent-relative, `.git`, or backslash traversal
     paths before returning a download URL.
  8. For PDF/DOCX/XLSX/PPTX/media/archive and other binary-preserving tasks, verify the worker
     received the original bytes in `uploads/` and did not substitute a `.txt` extraction unless the
     user explicitly asked for text extraction only.
  9. For LibreChat enterprise deployments, verify the GlassHive upload root is the same trusted
     upload storage LibreChat uses, or mark binary/PDF round-trip as blocked. Filename metadata alone
     is not sufficient evidence that the worker can read the file bytes.
  10. In shared-upload deployments, attempt to reference another user's upload path or filename from
     the prompt/tool payload and verify GlassHive does not copy those bytes into the workspace.
- Expected result: downloadable output opens and aligns with the input and success criteria, and the
  final worker report reflects verified completion or a real blocker.
- Forbidden result: missing upload, broken link, private path exposure, traversal access, or
  runtime code that detects this exact QA prompt, progress-only final reports, or claiming completion
  without inspecting the produced output. It is also forbidden to delete the problem
  statement by converting the user's PDF/workbook/media/archive into `.txt` when the requested task
  requires the original file type or layout-preserving output.
- Evidence to capture: upload projection, workspace file list, artifact metadata, download status,
  opened-file validation, logs, and DB/audit counts.
- Full-view evidence minimum: real upload/download/open path plus logs/DB/artifact confirmation.
- Automation: manual/browser plus artifact/path regression tests.
- Last run: PASS 2026-05-25 UTC for artifact-link regression coverage: API/header checks and
  browser QA verified the default GlassHive file link opens the preview/landing page without
  `content-disposition`, while the separately labeled `Download file` action still returns an
  attachment. PASS 2026-05-25 UTC for live LibreChat MCP PDF-byte projection, owner-scoped
  cross-upload denial, and missing-binary metadata/blocker fallback on an enterprise deployment.
  PASS 2026-05-24 for MCP artifact signing and header-upload materialization regressions; 2026-05-23
  across direct UI, direct MCP, and LibreChat MCP, including validated artifact downloads and
  traversal/cross-user probes.

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
  8. Inspect MCP/API/callback payloads and UI/API/WebSocket logs for raw `gh_token`, `gh_sig`,
     `gh_exp`, `gh_kind`, and `/v1/signed-links/{token}` leakage; visible payloads should carry
     only `/r/{ref}` or `/v1/link-refs/{ref}` short refs.
- Expected result: fail-closed auth/scoping, no cross-contamination, and member UI exposes only
  managed user-safe links.
- Forbidden result: docs/OpenAPI/UI/artifacts/watch accessible without auth; raw VM paths, ports,
  provider endpoints, signed-token URLs, or secrets in member-visible output.
- Evidence to capture: HTTP statuses, visible UI, logs, DB/audit counts, env/config summary, timing,
  provider-secret exposure probe, metadata-block probe, and automated test output.
- Full-view evidence minimum: browser/API probes plus logs/DB and automated security tests.
- Automation: runtime/UI/config tests plus Playwright/API probes.
- Last run: PASS 2026-06-20 local automated regression for short-link payload redaction and UI/API
  log filtering; live browser/log QA remains before production-grade approval. PASS 2026-05-25 UTC
  for owner-scoped upload byte denial in live enterprise MCP.
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
  recover a workspace from the same durable authenticated GlassHive short link.
- Risk covered: a raw signed token expires and makes an authenticated old result/workspace short
  link unusable, or an already-open browser session remains usable indefinitely.
- Preconditions: signed link secret configured; `GLASSHIVE_LINK_REF_TTL_SECONDS` left at default
  `0` for durable short refs; `GLASSHIVE_MAX_WATCH_SESSION_DURATION_S` set when active watch
  sessions must be capped.
- Steps:
  1. Generate a View / Steer `/r/{ref}` short link whose underlying `gh_token` has a short TTL.
  2. Confirm unauthenticated and wrong-user opens fail before any session cookie is minted.
  3. After the underlying token expires, open the same `/r/{ref}` as the owning authenticated user.
  4. Confirm it redirects to a tokenless watch URL and sets a fresh bounded worker cookie.
  5. Keep an active watch session open past the configured watch duration.
  6. Confirm the server closes the active session or requires a fresh authenticated short-ref open.
  7. Set `GLASSHIVE_LINK_REF_TTL_SECONDS` to a positive test value and confirm the short ref then
     expires by policy.
  8. Seed a legacy pre-payload short-ref row and confirm it migrates to durable payload-backed
     resolution under the default no-expiry policy.
  9. In split runtime/UI topology, create the ref from the runtime package and open it through the
     UI package with a shared `GLASSHIVE_LINK_REF_STATE_PATH`.
- Expected result: short refs are durable and auth-gated by default; raw signed tokens and active
  sessions remain bounded; optional positive short-ref TTL expires refs deliberately.
- Forbidden result: an authenticated owner sees `Invalid or expired GlassHive workspace link` only
  because the embedded token aged out, a stolen `/r/{ref}` opens without auth, or an old browser
  session remains usable forever after session expiry.
- Evidence to capture: HTTP/websocket status, visible UI copy, and logs.
- Full-view evidence minimum: signed-link tests, authenticated short-ref tests, browser/websocket
  timing test, and artifact/download click test.
- Automation: signed-link tests now; browser/websocket timing follow-up.
- Last run: PARTIAL 2026-06-20; local short-ref regressions added for durable default, auth gate,
  wrong user, fresh session-cookie minting, configured short-ref expiry, legacy-row migration, and
  runtime-created/UI-resolved shared-state behavior. Browser/live rerun pending.

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

## GH-STD-018 - Failure Classification, Completion Wait, And Workspace Continuation

- Requirement: `48_GlassHive_Workstation_Sandbox_Runtime.md#glasshive-standard-qa`.
- Risk covered: a long-running worker fails due to provider/rate-limit/content-filter/auth/runtime
  degradation, a short completion poll is incorrectly presented as task failure, the chat says the
  task failed even when partial workspace evidence exists, or a retry starts from scratch and loses
  the user's files/state.
- Preconditions: a synthetic public-safe failed run fixture with structured CLI failure evidence;
  GlassHive MCP status/wait/continue tools enabled.
- Steps:
  1. Create or simulate a worker run that exits non-zero with structured provider failure events.
  2. Verify persisted run fields contain `failure_class`, `failure_retryable`,
     `failure_user_message`, `failure_recommended_recovery`, and redacted diagnostics; the worker
     profile/runtime label must reflect the selected runtime such as `codex-cli`, not stale
     fallback metadata.
  3. Call `workspace_status` and `workspace_wait` for that run.
  4. Call `workspace_wait` without `timeout_seconds` under a synthetic timeout policy and verify it
     uses the configured default/cap while returning "still running" rather than false failure.
  5. If workspace files exist despite the failed terminal run, verify MCP status/callback guidance
     surfaces signed artifact open links and does not say no artifacts were produced.
  6. If a fresh user-facing file was created under `artifacts/` or any workspace `index.html`
     during a provider-response/rate/runtime-I/O capture failure, verify GlassHive reports the run
     as completed with artifact links and an honest warning; verify stale files and arbitrary
     partial files outside user-facing artifact locations remain failed/retryable.
  7. Ask to continue/retry and verify the model/tool path uses `workspace_continue`, not a fresh
     launch, and that the continuation instruction preserves the original task and current
     workspace state without recursively nesting prior GlassHive continuation wrappers.
  8. Run the same behavior through local LibreChat MCP/browser before release acceptance.
- Expected result: users get clear failure copy and an explicit same-workspace continuation path
  when retryable; wait timeouts say the worker is still running and keep the View / Steer link
  available, without hardcoded branches for one prompt, user, provider label, or file type.
- Forbidden result: raw secrets in failure text, unclassified provider failures when structured
  evidence exists, a wait timeout represented as failure, automatic unbounded retry loops,
  prompt-specific runtime conditionals, or a restart from a blank workspace when the user asked to
  continue.
- Evidence to capture: tool output, DB/run fields, redacted logs, continuation run instruction
  shape, View / Steer link, and browser chat wording.
- Automation: `tests/test_profile_runtime.py` failure-classification tests,
  `tests/test_api.py` runtime/artifact recovery tests, and `tests/test_mcp_server.py`
  status/wait/continue tests.
- Last run: PASS 2026-06-22 for local approval scope. Runtime/API/MCP regressions, host
  Codex/Claude wait/continue smokes, provider-backed Codex/Claude host browser wait/continue,
  timeout/transcript metadata, continuation handling, provider-failure classification,
  fresh-artifact recovery, stale-artifact rejection, readable evidence/ledger recovery guards, and
  evidence-check failure non-recovery all passed. Local browser fixture coverage proved `/w/{ref}`
  active-run controls and refresh persistence. Cloud/deployment/LibreChat live reruns are separate
  deployment gates, not part of this local pass.

## GH-STD-019 - Host/Sandbox Capability Routing, Preflight, And Recovery

- Requirement: `48_GlassHive_Workstation_Sandbox_Runtime.md#glasshive-standard-qa`.
- Risk covered: a host-default Viventium deployment ignores explicit sandbox/Codex Workspace
  language, or a missing/incompatible host runtime substrate creates dead work, leaks confusing
  technical recovery copy, or is misreported as a normal failed user task.
- Preconditions: host workers enabled in the test deployment; at least one sandbox-capable worker
  profile; synthetic public-safe prompt; ability to simulate one missing host CLI and one too-old or
  misconfigured local runtime dependency in automated tests.
- Steps:
  1. Inspect the MCP instructions and tool descriptions for sandbox/Codex Workspace guidance,
     structured failure copy, and `workspace_status`/`workspace_wait` follow-up guidance.
  2. Run direct MCP/API tests where `execution_mode=host` and the selected host CLI is unavailable.
  3. Verify GlassHive returns `status=blocked`, `failure_class=runtime_dependency_missing`, and no
     worker/run row is created.
  4. Run a direct MCP/API or browser-visible host-worker test with an incompatible local runtime
     version or broken required sidecar. Verify GlassHive attempts configured safe recovery first:
     managed/bundled dependency, worker-local toolchain, alternate available profile, or
     sandbox/workstation mode when that does not contradict the user's request.
     Version requirements and available recovery branches must come from runtime/profile
     configuration, not hardcoded runtime constants.
  5. In local LibreChat, ask a public-safe task with "Use sandbox" or "Use Codex Workspace" and
     verify the tool call creates a Docker/workstation worker, not a host worker.
  6. Ask a follow-up "wait for results" and verify the assistant uses `workspace_wait` with the
     returned follow-up context for the active recovered run rather than `run_get`, a blocked
     preflight attempt, or a guessed answer.
- Expected result: explicit sandbox wording produces `execution_mode=docker`; unavailable host
  runtime dependencies fail closed or recover safely before persistence; incompatible versions are
  treated as harness/runtime substrate issues, not user task failures; the assistant's wording is
  honest and non-technical.
- Forbidden result: prompt-specific runtime branching, silently remapping an explicit host request,
  creating dead host worker rows before preflight, saying work is running after a blocked launch, or
  exposing raw worker/run IDs except for diagnostics. It is also forbidden to tell the user to install
  or change global machine state before configured managed/profile/sandbox recovery has been tried or
  ruled out.
- Evidence to capture: tool-call args, MCP response payload, DB worker/run row counts, visible chat
  wording, source-of-truth prompt/allowlist diff, and focused test output.
- Automation: `tests/test_mcp_server.py::test_worker_delegate_once_blocks_missing_host_cli_before_api_calls`,
  `tests/test_api.py::test_missing_host_cli_blocks_creation_before_worker_row`, and tool-instruction
  contract tests. Add coverage for too-old runtime version recovery before claiming this case
  complete.
- Last run: PARTIAL 2026-05-27; missing-CLI automation exists. Too-old runtime version recovery and
  local browser QA remain required before release or deployment signoff.

## GH-STD-020 - Delegation Fidelity, Wait Recovery, And Efficient Polling

- Requirement: `48_GlassHive_Workstation_Sandbox_Runtime.md#glasshive-standard-qa` and
  `01_Key_Principles.md#25-incident-learning-and-drift-prevention-discipline`.
- Risk covered: the host assistant compresses a complex user request into a thin summary before
  handing it to GlassHive, the assistant launches work and then loses the run because a wait/status
  call omitted ids, host-side orchestration checks are incorrectly treated as worker blockers, the
  user cannot see the View / Steer link during a long wait, or QA/status loops overload the local
  machine or cloud resources.
- Preconditions: public-safe long prompt fixture with constraints/examples/exclusions; host workers
  enabled for Viventium-style tests; Docker available only when running the browser sandbox path.
- Steps:
  1. Inspect MCP server instructions and `workspace_launch` / `worker_delegate_once` descriptions
     for explicit full-context preservation, sandbox routing, View / Steer, wait, and polling
     guidance.
  2. Launch a synthetic long-brief task and verify the tool payload preserves the full available
     request in `context`/instruction; labels may be short, but worker-facing context must not be a
     watered-down paraphrase.
  3. Call `workspace_wait` and `workspace_status` without ids immediately after launch and verify
     they resolve only the same authenticated user/conversation's recent dispatch.
     Scheduled launches are a deliberate exception: a schedule returns a schedule handle rather than
     an active dispatch, so same-conversation recent-dispatch fallback does not attach until the
     scheduled work actually starts.
  4. In enterprise simulation, switch user, switch conversation, and omit the conversation header
     after a conversation-scoped launch; verify omitted-id wait/status fails closed instead of using
     another user's or another conversation's recent worker. Also launch without a conversation
     assertion and verify it does not create a user-wide remembered fallback.
  5. Verify `workspace_wait` uses the configured efficient polling cadence as a runtime floor, so a
     caller-provided low interval cannot create an aggressive status loop.
  6. Include host-side checks such as tool selection, View / Steer visibility, wait cadence, or
     post-run inspection in the public-safe prompt context and verify the worker does not report a
     blocker after completing the requested workspace-internal artifacts.
  7. In browser QA, verify the user gets a View / Steer link before the wait when the chat protocol
     can show assistant text before the next tool call, or at minimum in the final answer, and that
     no abandoned browser/status monitor remains after QA.
     When the Workspaces hive shows many active workers, embedded live desktops may be capped to
     preserve operator/browser resources; overflow tiles must still provide status text and Full
     watch access.
- Expected result: GlassHive receives the full task, same-conversation wait recovery works without
  cross-user leakage, host-side orchestration is verified by the host rather than misreported by the
  worker, View / Steer remains discoverable, and waiting is efficient.
- Forbidden result: prompt-specific hardcoding, runtime keyword branching, global "last worker"
  fallback, cross-user/cross-conversation recovery, invisible long waits with no eventual link,
  completed deliverables marked blocked because the worker cannot observe the host chat/UI, low-
  interval polling loops for long work, or QA scripts leaving headless browsers running.
- Evidence to capture: tool schema text, tool arguments, wait/status payloads, process/resource
  snapshot, DB/log confirmation, and browser-visible result when Docker/browser QA is available.
- Automation: `tests/test_mcp_server.py` recent-dispatch and tool-contract tests.
- Last run: PASS 2026-05-25 local. Focused automated tests passed for MCP tool contracts,
  full-context guidance, recent-dispatch wait/status recovery, and callback sanitization. A real
  local LibreChat browser run launched a sandbox/Codex workspace, showed View / Steer before the
  blocking wait, returned generated artifact links, preserved the worker-facing source brief and
  host-side success criteria in GlassHive context, completed without worker-side host-orchestration
  blockers, showed the completed workspace in the Workspaces hive when inactive workspaces were
  enabled, and used 5-second wait polling in logs. Resource inspection attributed most laptop load
  to browser/WindowServer/Docker/Codex UI processes and also found a Workspaces browser polling
  inefficiency. The UI fix was verified by Playwright: six retained tiles made one live-status
  hydration pass, mounted zero completed desktop iframes, and did not repeat retained tile live
  checks during a 16-second observation window. Cloud soak is not included in this local QA pass.

## GH-STD-021 - Artifact Link Contract Matrix

- Requirement: `48_GlassHive_Workstation_Sandbox_Runtime.md#glasshive-standard-qa`.
- Risk covered: a raw diagnostic or download endpoint is accidentally advertised as the primary
  user-facing file delivery link, causing surprise downloads or confusing files in LibreChat,
  direct MCP, direct API, or callback responses.
- Preconditions: synthetic text, binary, and image artifacts; signed-link secret configured; browser
  automation available for at least one default-link click.
- Steps:
  1. Create a completed worker artifact and inspect the callback payload.
  2. Verify callback ordering is `Open GlassHive file` first, `Download file` second, and `View /
     Steer` after the file links when present.
  3. Call `workspace_artifacts` and `workspace_artifact_download`; verify `signed_open_url` tokens
     are signed with `kind=artifact_open`, while `signed_download_url` tokens are signed with
     `kind=artifact_download`.
  4. Open text, binary/PDF-style, small image, and SVG artifacts through `/artifacts/open`; verify the
     response is `text/html`, has restrictive security headers, does not set `content-disposition`,
     escapes user-controlled text, refuses active SVG inline rendering, and shows an explicit
     `Download file` action.
  5. Open the same artifact through `/artifacts/download`; verify it is an attachment.
  6. Tamper a signed open token to change its kind/path/owner and verify it fails closed.
  7. In enterprise mode, open the preview through the configured public origin
     `GLASSHIVE_OPERATOR_BASE_URL` at `/v1/signed-links/{artifact_open}` without service headers;
     verify the glass-drive-ui proxy accepts the open token, the page's `Download file` action is
     itself a signed download link, and `View workspace` carries a worker-view token.
  8. In browser QA, click the primary file link exactly as returned by MCP/callbacks and verify no
     browser download is triggered; then click `Download file` and verify the download behavior is
     explicit.
  9. If completed output mentions an external source/check URL while also creating a user-facing
     artifact, verify the artifact remains the promoted file deliverable unless the real output is
     workspace HTML.
- Expected result: every default file-delivery response opens the GlassHive preview/landing page;
  only an explicit download action returns an attachment.
- Forbidden result: a primary result link pointing directly to `/artifacts/download`, a primary link
  labeled only as a generic file while returning an attachment, cross-kind signed-token replay,
  unescaped artifact text in the preview page, unsigned preview-page buttons in enterprise mode, a
  public proxy token-kind whitelist that accepts a kind the runtime rejects or rejects a kind the
  runtime accepts, an incidental external URL outranking the actual generated file, or a test that
  only checks link presence without clicking/opening it.
- Evidence to capture: callback text, MCP payload token kinds, open/download response headers,
  browser no-download observation, download observation, and audit/log events.
- Automation: `runtime_phase1/tests/test_api.py` artifact open/download and callback-order tests;
  `runtime_phase1/tests/test_mcp_server.py` signed open/download kind tests.
- Last run: PASS 2026-06-22 locally. API/MCP contract tests and local browser QA proved preview
  first, explicit download second, tokenless workspace links, and Markdown/CSV/HTML/PDF/XLSX/DOCX/PPTX
  artifact open/download behavior. Live enterprise rerun remains required after release pinning and
  deployment updates.

## GH-STD-022 - Sparse Delegation, MCP/Tool Fidelity, And Data I/O

- Requirement: `01_Key_Principles.md#25-incident-learning-and-drift-prevention-discipline` and
  `48_GlassHive_Workstation_Sandbox_Runtime.md#host-native-discoverability-contract`.
- Risk covered: the host assistant overfits one use case by inventing goals, success criteria,
  urgency rubrics, provider lists, downloadable files, or MCP/tool results instead of brokering real
  capabilities and letting the GlassHive worker decide.
- Preconditions: GlassHive MCP available; at least one synthetic connected-account/broker capability
  or an explicit unavailable-capability path; public-safe file/deep-research prompt.
- Steps:
  1. Launch a connected-account task with ordinary wording and inspect the MCP payload plus worker
     bootstrap files.
  2. Launch a deep-research/current-fact task and inspect whether the worker receives the full user
     request plus available tool context without a fabricated research plan.
  3. Launch a file-generation/transformation task and verify the host does not force a downloadable
     file unless the user or worker result calls for one.
  4. Inspect `AGENTS.md`, `CLAUDE.md`, `CODEX.md`, `harness-prompt.md`, and the submitted worker
     instruction for the universal completion self-check.
  5. Compare visible chat output, worker final report, artifacts, logs, and DB rows.
- Expected result: the host passes real goals, constraints, files, MCP/tool capabilities, retrieved
  context, and success conditions; unavailable data remains explicit; the worker chooses the path
  and verifies the concrete result before `FINAL REPORT:`.
- Forbidden result: fake MCP/tool usage, missing upload bytes represented as read content,
  manufactured success criteria, forced artifact/download links, provider-specific overfit,
  prompt-text intent branching, or completion without checking actual output/artifacts/tool results.
- Evidence to capture: tool schema/instructions, tool call payload, materialized bootstrap files,
  worker instruction, final report, artifact/open/download behavior when applicable, logs, DB rows,
  and browser-visible result.
- Automation: `runtime_phase1/tests/test_mcp_server.py` sparse-delegation/tool-contract tests and
  `runtime_phase1/tests/test_profile_runtime.py` prompt/preflight tests, plus browser QA.
- Last run: PASS/PARTIAL 2026-05-27; local automated tests, direct MCP anti-bluff, post-restart
  direct GlassHive UI exact-file run, direct UI answer-shaped research/no-forced-artifact run,
  direct UI upload flows, schedule preflight/recovery, and source Prompt Workbench checks passed;
  LibreChat browser dispatch and live connected-account broker happy path remain blocked by local
  model auth/login state and Microsoft 365 MCP instability.

## GH-STD-023 - Capacity Blocking And Callback Retry Budget

- Requirement: `48_GlassHive_Workstation_Sandbox_Runtime.md#glasshive-standard-qa` mandatory case 7
  and the callback outbox bounded-retry requirements.
- Risk covered: one prompt repeatedly launches workers or retries callbacks until cloud billing is
  burned, while the host sees only a raw `429 Too Many Requests` and has no useful next step.
- Preconditions: a synthetic owner/tenant scope on a local or enterprise GlassHive deployment with
  configurable active-worker caps and callback outbox access.
- Steps:
  1. Create synthetic active workers for one owner until the configured active-worker cap is full.
  2. Attempt one additional workspace launch through the API or MCP path without starting a real
     model worker.
  3. Verify the blocked response contains `failure_class=glasshive_worker_quota_exceeded`,
     `available_workspace_options`, and no profile/sandbox switch advice. Active-worker caps may
     expose retry guidance tied to idle release; saved-workspace caps must instead say that waiting
     for idle release will not free a workspace slot.
  4. Verify the host-facing guidance tells the caller to reuse a listed workspace, ask which listed
     workspace to continue, wait for release, or ask an operator instead of relaunching in a loop.
  5. Force repeated capacity waits and verify automatic requeue stops at the configured capacity
     retry budget instead of minting unlimited wait callbacks.
  6. Seed or inspect a callback row whose stored attempt count is over the retry budget and verify it
     is retained as `dead_lettered` without another outbound HTTP attempt.
  7. Confirm synthetic projects/workers are removed and live services remain healthy.
- Expected result: quota pressure is a structured, retryable blocker with owner-scoped reuse
  options; callback replay is bounded and observable; old terminal audit rows do not create active
  backlog.
- Forbidden result: raw 429-only text, advice to switch profile/sandbox as the quota fix, automatic
  relaunch retries, cross-user workspace options, unbounded pending/delivering callback attempts, or
  synthetic QA rows left in the deployment DB.
- Evidence to capture: API/MCP payload summary, retry-after value, option count/names sanitized if
  needed, callback status/attempt summary, service health, env cap/idle settings, logs, and DB
  cleanup counts.
- Automation: `runtime_phase1/tests/test_api.py::test_worker_quota_enforced_per_user`,
  `runtime_phase1/tests/test_api.py::test_active_worker_quota_retry_after_uses_idle_release`,
  `runtime_phase1/tests/test_api.py::test_retryable_capacity_wait_has_max_attempts`,
  `runtime_phase1/tests/test_api.py::test_callback_over_budget_dead_letters_without_http`, and
  `runtime_phase1/tests/test_mcp_server.py::test_workspace_launch_returns_structured_quota_block_with_reuse_options`.
- Last run: PASS 2026-05-31 on an approved enterprise GlassHive deployment and locally. The live
  synthetic quota probe returned `429`, `glasshive_worker_quota_exceeded`, three owner-scoped reuse
  options, 900-second retry guidance, no sandbox/profile-switch advice, and zero synthetic leftovers;
  deployed API/MCP tests passed; a historical runaway callback row was dead-lettered.

## GH-STD-025 - Short-Link Payload Redaction And Compact MCP Results

- Requirement: `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`
  GlassHive short-link and compact MCP contract.
- Risk covered: raw signed tokens, stale `openclaw` backend labels, raw internal IDs, or internal
  host guidance leak through MCP/API/UI payloads, callbacks, preview pages, or logs.
- Preconditions: local GlassHive runtime or test harness with signed-link secret, one synthetic
  Codex-profile worker, and runtime/UI log capture.
- Steps:
  1. Call `workspace_launch` without diagnostics and verify the result has compact status fields,
     `result_tools`, optional short View / Steer ref, and no raw project/worker/run ids.
  2. Call `workspace_status` and `workspace_wait` without diagnostics and verify compact result
     shape, `still_running` timeout shape when applicable, and no internal guidance or raw ids.
  3. Repeat one status/wait call with `include_diagnostics=true` and verify raw lineage is present
     only in diagnostics.
  4. Generate callback, live inventory, preview, and artifact-link payloads and verify visible links
     use only `/r/{ref}` or `/v1/link-refs/{ref}`.
  5. Resolve `/r/{ref}` and `/v1/link-refs/{ref}` like a user; `/r` should set the worker cookie
     and land on a tokenless watch/project/desktop URL, while raw `gh_token` targets may appear
     only as server-side ref/open implementation details or legacy inbound compatibility.
  6. Emit synthetic API/UI/WebSocket log lines containing `gh_token`, `gh_sig`, `gh_exp`, `gh_kind`,
     and `/v1/signed-links/{token}` and verify log filtering redacts them.
  7. Create or resume a Codex-profile worker while omitting legacy `backend`, then with a legacy
     `backend=openclaw` request, and verify response metadata derives backend truth from profile and
     runtime instead of surfacing `openclaw` for Codex.
- Expected result: public payloads expose only short refs and compact status/result fields; raw ids
  are diagnostics-only; signed-token query strings and legacy signed-link token paths are redacted
  from logs; `/r` redirects leave the browser on tokenless URLs; Codex workers report `codex-cli`
  backend truth.
- Forbidden result: raw `gh_token`, `gh_sig`, `gh_exp`, `gh_kind`, `/v1/signed-links/{token}`, raw
  run/project/worker ids, host guidance, or `openclaw` backend labels in default public Codex
  payloads/logs.
- Evidence to capture: automated MCP/API/UI test output, representative sanitized payload shapes,
  browser redirect/open behavior, sanitized log excerpts, and live/cloud config revision when
  production deployment is in scope.
- Automation: `runtime_phase1/tests/test_mcp_server.py`, `runtime_phase1/tests/test_api.py`, and
  `frontends/glass-drive-ui/tests/test_server.py`.
- Last run: PASS/PARTIAL 2026-06-22. Local automated runtime/UI regressions and browser fixture
  coverage passed for short refs, compact default MCP/API shapes, diagnostics-only lineage,
  signed-query log redaction, backend/profile truth, tokenless `/w/{ref}` workspace views, and
  artifact preview/download redaction. Release durability remains partial until the nested
  GlassHive source state is committed/reconciled and a clean parent pin/release branch is verified.

## GH-STD-024 - Master Wildcard Deep-Work Document Delivery QA

- Requirement: `48_GlassHive_Workstation_Sandbox_Runtime.md#glasshive-standard-qa` and the
  first-delivery client expectation captured verbatim below.
- Source expectation, verbatim:

```text
w.  are going to devise one category of tests based on what my client really needs out of the first delivery of this version of glass Hive and that's basically where we create a a document file. whether it's a PDF, Microsoft word or a PowerPoint, it will be one of the wild card factors and then we want to make sure that the worker is able to deliver. absolutely spectacular and most complete deep research work just like you would get from chatgpt or Claude cowork. and we get it as a document... format? wild card... the point of this test is to have simplified one QA prompt. which has variety of file input or maybe just user text prompt input, text output or maybe also file(s) output, and deep work inside. with variations. so first, record this as the master QA since we already have standards glasshive QA and keep it exactly as I said... it's input (wildcard) deep work, output (Also type and format wildcard), so tests or development don't get overfitted to just one thing, because again... this is about supporting any prompts or requests user would/might have. so yeah.. document this expectations and requirements without paraphrasing and broken telephone, test it as it... identify current state and user facing issues... such as Claude CLI vs codex CLI delivered quality of work. do.deep research of how these tools work for actually users and even computer use test them on this computer to compare results. consult with Claude max effort
```

- Risk covered: the first GlassHive delivery optimizes for one fixed prompt, one file type, one
  provider, one worker profile, or one artifact path, while real users expect open-ended deep work
  with unpredictable inputs and outputs.
- Preconditions: public-safe synthetic subject matter; at least one host or workstation worker
  profile available; document validators/viewers available for the generated output type; internet
  research or a clearly recorded blocked search prerequisite when current/deep research is required.
- Wildcard dimensions:
  1. Input: no file, one text prompt, one public-safe source file, or multiple public-safe files.
  2. Work: deep research, synthesis, analysis, comparison, recommendations, cited evidence,
     document composition, and worker self-check.
  3. Output: text-only answer, one generated file, multiple generated files, or a document artifact.
  4. Format: PDF, Microsoft Word, PowerPoint, HTML, Markdown, or another format explicitly requested
     or intelligently chosen by the worker.
  5. Worker: compare available local worker-type baselines such as Codex CLI and Claude CLI when
     configured, but treat them as reference baselines rather than a fixed definition of the wildcard.
- Steps:
  1. Select one simplified public-safe master prompt family whose variables are randomized or
     manually varied across input type, requested work depth, output count, and document format.
     A first-delivery acceptance run must exercise at least two variants, and a release-complete run
     must exercise at least three variants, so this cannot become one memorized golden prompt.
  2. Run the prompt through the real GlassHive surface being accepted, starting with LibreChat MCP
     for first-delivery user value, then direct MCP/UI where relevant.
  3. Run the same class of prompt directly through the available local Claude CLI and Codex CLI
     baselines, with their native capabilities enabled, to compare delivered quality and capability
     use without GlassHive stripping or over-orchestrating the worker.
  4. Verify in/out fidelity: user request/input files -> host/MCP payload -> worker instruction ->
     worker output -> user-visible response and artifact links must preserve the actual target,
     constraints, file references, and success condition.
  5. Verify capability projection: the selected worker receives truthful native capabilities for its
     type, such as browser/computer/MCP/file/shell/local-app control when available, and any missing
     capability is explicit instead of silently hidden. When browser/computer use is relevant, record
     extension policy, installed/enabled browser profile state, and connected CLI/app bridge state as
     separate evidence.
  6. Let the GlassHive worker choose the method. Do not inject a fixed provider list, file plan,
     citation template, slide count, section count, or success rubric unless the user prompt says it.
  7. Open the produced artifact(s) like a user. For PDF/DOCX/PPTX, verify the document opens,
     contains substantive deep work, preserves requested format, and is not a renamed text file.
  8. Inspect the worker final report, logs, DB/run state, materialized input files, artifacts,
     generated links, and any browser/computer-use evidence.
  9. Compare quality across GlassHive and direct worker-type baselines: depth, relevance,
     completeness, evidence handling, formatting, visual/professional polish, performance, and
     whether the worker self-corrected obvious gaps.
  10. Record current user-facing issues without converting them into prompt-specific rules.
- Expected result: GlassHive delivers a complete, high-quality deep-work result in the requested or
  intelligently selected output format; generated documents open successfully and read like a
  professional coworker/researcher produced them. When the request asks for, or clearly implies, a
  document/report/deck/client deliverable and the user did not request a technical/source format, the
  primary user-facing artifact is a polished ordinary end-user document/work product such as PDF,
  Word, PowerPoint, spreadsheet, or an equivalently professional format chosen by the worker;
  Markdown/HTML/source files may accompany it but are not the only default deliverable unless the
  worker reports a concrete runtime blocker. The worker uses its own available intelligence,
  tools, browser/computer capability, and MCPs without host over-planning; the result satisfies the
  project outcome metric of Quality (Intelligence, Relevance, Usefulness, Alignment) plus Performance
  (Fast, Smooth, Reliable).
- Forbidden result: a hardcoded prompt detector; PDF/DOCX/PPTX-only assumptions; a fake or empty
  document; a renamed `.txt` file pretending to be a document; shallow summary work when deep work
  was requested; Markdown/HTML/source-only first delivery for a requested/implied professional
  document/report/deck/client deliverable without an explicit user format choice or concrete runtime
  blocker; forced artifacts when text output is enough; missing artifact links; raw tool
  plumbing in user output; host-injected plans/provider lists/rubrics that the user did not ask for;
  silently stripped native worker capabilities; or claiming completion without opening/validating the
  produced files.
- Evidence to capture: exact synthetic prompt and randomized variables, sanitized source fixture
  summary, worker profile/version/capability summary, browser-extension policy/profile/bridge status
  when applicable, generated artifact metadata, open/validation result, in/out fidelity trace,
  host-courier/no-overplanning check, final report, logs/DB/run state, comparison notes for direct
  worker-type baselines vs GlassHive, and public-safety scan.
- Automation: start with a manual/browser/computer QA report; then add reusable harness coverage for
  artifact creation/opening, file-type validation, no-overfit source scan, worker final-report
  presence, and side-by-side worker profile comparison.
- Last run: PASS/PARTIAL 2026-06-22. Local fixture validates the professional artifact matrix,
  including PPTX, without changing runtime behavior for one prompt or one file type. Host Codex
  xhigh and host Claude max smokes prove current effort/profile execution for small public-safe
  runs. Full deep-work PPTX/file-input variants, authenticated LibreChat full master prompt rerun,
  direct UI rerun, live Telegram dedupe rerun, connected-account happy path, and export/recall
  sanitization remain open before full first-delivery signoff.

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
