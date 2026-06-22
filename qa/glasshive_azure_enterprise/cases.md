# GlassHive Azure Enterprise Cases

## GH-AZ-001: Enterprise Auth Fails Closed

- Requirement: `GLASSHIVE_ENTERPRISE_MODE=true` requires service auth and an authenticated user
  assertion for all non-health routes.
- Expected: `/health` succeeds; `/docs`, `/ui`, MCP/API routes, artifacts, takeover, and terminal
  websocket reject missing token or missing user assertion.
- Forbidden: unauthenticated project/worker inventory, OpenAPI docs, UI, or artifact access.
- Evidence: API status codes plus middleware/unit test output.
- Last run: PASS on 2026-05-23 live approved enterprise dev deployment: `/health` returned `200`,
  public browser traffic redirected to Microsoft sign-in, service-authenticated API/MCP worked, and
  missing service token on `/v1` redirected to OAuth instead of exposing data. A follow-up runtime
  hardening test now rejects enterprise startup when the signed-link HMAC secret is missing or
  reused as the MCP/API service token.

## GH-AZ-002: User And Tenant Ownership Isolation

- Requirement: GlassHive derives owner from authenticated context in enterprise mode and ignores
  caller-supplied `owner_id`.
- Expected: User A can create/list/resume/download only User A work; User B receives empty lists or
  404/403 for User A ids; same alias under different users does not reuse the same worker.
- Forbidden: cross-user worker resume, artifact download, UI/watch access, or project/run leakage.
- Evidence: two-synthetic-user API test plus browser QA report.
- Last run: PASS on 2026-05-23 live approved enterprise dev deployment: same-user run fetch returned
  `200`, cross-user run/project/worker fetch returned `404`, and identical aliases under two
  synthetic users produced distinct owner-scoped workers.

## GH-AZ-003: Upload And Artifact Download

- Requirement: LibreChat upload metadata projects files into the worker workspace, and artifacts are
  downloadable only through owner-scoped routes.
- Expected: uploaded file appears under `uploads/`; generated artifact lists with a download URL;
  path traversal is rejected; file download has correct content; enterprise `source_path` upload
  materialization requires a server-signed source token tied to tenant/user.
- Forbidden: download outside workspace, `.git` download, cross-user artifact access, or caller-
  supplied absolute source paths under a shared upload root.
- Evidence: API test, local worker filesystem inspection, browser upload/download flow.
- Last run: PASS on 2026-05-23 live approved enterprise dev deployment for direct MCP upload
  projection and owner-scoped artifact download: synthetic upload headers materialized under
  `uploads/`, generated artifact download returned exact content, and traversal returned `400`.
  PASS on 2026-05-24 live approved-client logged-in chat QA: the chat model used GlassHive
  `uploaded_files`, the worker materialized the file under `uploads/`, generated a synthetic
  roundtrip artifact with exact marker content, signed artifact download returned `200`, missing
  token returned `401`, and traversal returned `400`.

## GH-AZ-004: Idle Compute Reaping

- Requirement: idle workspaces stop compute automatically to reduce cloud cost while preserving
  workspace/home state.
- Expected: idle ready/paused worker compute is terminated after threshold; running/queued workers
  are not killed; state becomes resumable; lifecycle audit events are recorded once per compute
  release cycle; repeated reaper passes skip already-released paused compute until resume/start.
- Forbidden: deleting workspace data, killing active work, leaving no audit event, or repeatedly
  emitting `worker.paused_compute_terminated` for the same already-released paused worker.
- Evidence: idle reaper unit test, local Edge/Playwright worker page, DB events, and resume smoke.
- Last run: PASS automated on 2026-05-27: runtime regression proves released paused compute is
  durably marked, second reaper pass is idempotent, resume clears the marker, and workspace state is
  preserved. Live cloud rollout was not performed.

## GH-AZ-005: User-Level Browser QA

- Requirement: local LibreChat integration must expose GlassHive as a usable enterprise worker
  surface with no LibreChat application-code changes.
- Expected: synthetic user can connect MCP, upload a file, delegate work, download output, run
  public deep research, open/take over the worker, stop/resume, refresh, and see clear missing-key
  errors.
- Forbidden: broken connection loop, dead links, cross-user contamination, raw secrets, or private
  paths in public evidence.
- Evidence: Playwright/browser report under `reports/`.
- Last run: PARTIAL on 2026-05-23 live approved enterprise dev deployment: live LibreChat logs show
  GlassHive MCP registered and initialized, direct MCP proved Codex/OpenClaw workers, upload
  projection, artifact download, takeover URL generation, and owner isolation. Fresh Playwright
  LibreChat stopped at the login form, so logged-in chat-turn/file-upload/deep-research remains
  PARTIAL until test credentials or an automatable logged-in session are available. Follow-up
  standalone plain-LibreChat MCP QA proved neutral `X-GlassHive-*` headers, upload projection,
  `workspace_status`, `workspace_wait`, and signed View / Steer/noVNC rendering on the live VM; see
  the private enterprise deployment evidence archive. The logged-in approved-client chat
  upload/worker/download/watch path is PASS on 2026-05-24 via an existing signed-in Edge session;
  see the private enterprise deployment evidence archive. Overall GH-AZ-005 remains
  PARTIAL for the full provider matrix until Claude and Portkey live-provider coverage is run with
  approved live account/key availability.

## GH-AZ-006: Approved Cloud Read-Only Dry Run

- Requirement: enterprise Azure validation must use only approved enterprise/Viventium-scoped resources and
  must not overwrite cloud state before local backup and local proof.
- Expected: subscription/tenant/resource scope is verified; relevant Azure target metadata is backed
  up locally outside the public repo; public endpoints and provider routes are probed read-only;
  cloud security/cost findings are recorded without mutation.
- Forbidden: touching other customer tenants/resources, printing secret values, restarting/updating
  live apps without approval, or using logs containing real user identifiers as public evidence.
- Evidence: Azure CLI read-only inventory, provider reachability probes, Playwright public login
  check, and sanitized report under `reports/`.
- Last run: PASS for dev deployment mutation gate and PARTIAL for production readiness on 2026-05-23:
  approved enterprise cloud backup was taken locally before
  mutation, a dedicated live GlassHive VM deployment was created/configured, and LibreChat MCP config
  was updated without app-code edits. Production readiness remains PARTIAL pending full logged-in
  LibreChat chat QA, Portkey live key, Claude credit, and final operator approval.

## GH-AZ-007: Enterprise Signed-Link, Admin, And IMDS Hardening

- Requirement: enterprise signed links, admin maintenance endpoints, and worker network egress must
  narrow service-token blast radius and protect cloud metadata.
- Expected: `GLASSHIVE_SIGNED_LINK_SECRET` is required and distinct from `WPR_API_TOKEN`; enterprise
  runtime and UI startup enforce that rule; enterprise admin endpoints return `404` unless
  `GLASSHIVE_ENABLE_ADMIN_API=true`; enabled admin endpoints still require admin/owner/operator role;
  worker containers cannot connect to Azure IMDS.
- Forbidden: signed-link HMAC fallback to the service token, member access to admin endpoints,
  publicly reachable maintenance APIs, or worker access to `169.254.169.254`.
- Evidence: runtime/UI startup validation tests, admin regression tests, live service-auth `404` for
  disabled admin endpoint, VM firewall backup, persisted Docker `DOCKER-USER` rule, and in-container
  IMDS connect test.
- Last run: PASS on 2026-05-23 live approved enterprise dev deployment and local regression suite.

## GH-AZ-008: Durable Short Links And Direct View / Steer Bootstrap

- Requirement: user-visible GlassHive payloads expose opaque short refs, not raw signed query
  strings. Workspace `/r/{ref}` links are durable by default and must open from chat by minting a
  fresh bounded worker-view session without exposing `gh_token`. Artifact `/v1/link-refs/{ref}`
  routes remain owner-scoped routes through either trusted proxy owner assertion or the active
  worker-view cookie minted for the same worker.
- Expected: a fresh View / Steer `/r/{ref}` redirects to a tokenless workspace URL and sets an
  HttpOnly worker cookie; the same ref still works after the original signed token expires when
  `GLASSHIVE_LINK_REF_TTL_SECONDS=0`; a mismatched asserted owner receives `404`; artifact refs
  without owner context receive `401`; artifact refs opened from the active Watch / Steer session
  return the preview/download surface; active watch polling refreshes the bounded worker-view cookie
  instead of aging into repeated `401`; visible text, link hrefs, copy text, API logs, UI logs, and
  websocket logs do not retain raw signed URLs or raw short-ref capabilities; repeated live polling
  reuses artifact refs instead of growing unbounded rows; worker-view opens are audited; worker
  termination revokes outstanding refs for that worker.
- Forbidden: chat-visible `gh_token`, expired-token error on a durable workspace ref, direct
  unauthenticated artifact download, cross-owner workspace access when identity is asserted, or
  durable refs/open tabs becoming compute leases that keep idle workers running, durable refs
  surviving explicit worker termination, or short-ref paths appearing verbatim in application logs.
- Evidence: runtime/UI short-link regression tests, browser-opened chat link, hidden copy/accessibility
  text inspection, VM/UI/API log redaction check, DB/runtime state showing idle/pause controls still
  own compute release, link-ref DB row-count/revocation checks, and `worker.view_opened` event
  evidence.
- Last run: PASS on 2026-06-20 live approved enterprise dev QA with public-safe evidence kept in the
  private enterprise deployment archive: `/r/{ref}` redirected without `gh_token`, artifact ref
  opened from the active worker-view cookie, missing/unauthenticated refs failed closed, active
  `/api/worker/{id}/live` polling refreshed the cookie, Playwright opened the final artifact with no
  console/page errors, service logs had zero `gh_token` matches in the final deploy window, and a
  follow-up hardening smoke confirmed short-ref log redaction, view-open audit, and ref revocation
  on worker termination.

## GH-AZ-009: Enterprise Launcher, Watch, And Managed Workspace UI

- Requirement: the authenticated enterprise GlassHive entrypoint must be usable like a real user
  surface, keep the documented GlassHive fields, fail closed without identity, expose non-blocking
  worker progress, and avoid raw runtime/local links for member users.
- Expected: root launcher scrolls and shows `Describe your project`, `Success Criteria`, and
  `Context`; launch redirects immediately to watch; watch shows result/detail/menu/pause-resume
  states without overlap; project workspace opens through managed enterprise links only.
- Forbidden: hidden launch controls, stacked status text, raw provider endpoints as deliverables,
  raw `localhost`/gateway/API-docs links in member UI, unauthenticated bootstrap, or cross-user
  access.
- Evidence: automated UI/runtime/config tests, OpenAPI/docs auth probes, Claude review-only
  follow-up, and Playwright browser report.
- Last run: PASS on 2026-05-23; see
  `reports/2026-05-23-launcher-watch-enterprise-qa.md`.

## GH-AZ-010: Workspace Hive Launcher View

- Requirement: the authenticated launcher must let users inspect their active workspaces without
  digging through a select control, and inactive retained workspaces must be available on demand
  without showing the project launch form in the selected workspace view.
- Expected: clicking `Workspaces` selects a real tab/view; the project launch form is hidden; active
  workspace tiles appear by default; `Show inactive` reveals paused/retained workspaces; tile actions
  can open full watch, open project, play/pause, interrupt, and steer inline. Tiles detach live
  desktop iframes when inactive and avoid polling while the browser tab is hidden.
- Forbidden: inert `Workspaces` label, hidden retained workspaces, project launch controls visible
  in the Workspaces view, raw unmanaged links, lingering live iframes after pause/idle, or tile
  actions that cannot control/steer the workspace.
- Evidence: automated UI tests, Playwright browser report, Microsoft Edge visual pass, API/runtime
  state, auth probes, and Claude review follow-up.
- Last run: PASS on 2026-05-23 after Claude follow-up fixes; see
  `reports/2026-05-23-workspace-hive-ui-qa.md`.

## Natural User Use Case Checklist

| Case ID | Natural user action | Real surface | Supporting evidence | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- |
| GH-AZ-UC-001 | Enterprise user opens GlassHive through the authenticated enterprise entrypoint. | Browser via local auth-injecting proxy; raw backend checked separately. | Playwright snapshot, raw `/docs` `401`, proxy `/ui` `200`, backend logs. | Raw unauthenticated routes fail closed; authenticated UI loads project creation. | PASS 2026-05-22 local simulation. |
| GH-AZ-UC-002 | User creates a project and worker while a request tries to spoof another owner. | Browser UI plus API/store inspection. | Store row with `tenant-alpha` + `user-a`; worker alias `tenant-alpha--user-a--qa-research-worker`; API tests. | Ownership follows authenticated user context, not the submitted owner field. | PASS 2026-05-22 local simulation. |
| GH-AZ-UC-003 | A second user tries to list, resume, watch, or download the first user's work. | API calls with synthetic User B headers. | User B worker fetch `404`, project list empty, artifact route `404`; automated tests. | User B cannot infer or access User A workspace, worker, or artifact data. | PASS 2026-05-22 local simulation. |
| GH-AZ-UC-004 | User runs work, pauses/resumes it, opens takeover, refreshes, and checks status. | Edge LibreChat chat UI plus Playwright signed professional GlassHive `/watch/{worker}` UI plus direct OpenClaw Docker smoke. | MCP connection, callback outbox rows, professional watch page snapshot, lifecycle events, signed watch token, OpenClaw artifact download. | Worker state, latest output, events, links, and workspace files remain consistent after refresh; takeover links open the GlassHive operator UI, not the runtime diagnostic page. | PASS for Codex Docker and direct OpenClaw Docker 2026-05-22; Claude/deep-research profiles still pending. |
| GH-AZ-UC-005 | User downloads a generated file and attempts an unsafe traversal or cross-user source-path materialization. | Edge LibreChat callback link; API artifact endpoints; bootstrap regression tests. | Opaque download `200` exact body, query signed download `200`, traversal/symlink `400`, tampered/expired/mismatched opaque token `401`, user mismatch `404`, unsigned `source_path` rejection, signed same-user source acceptance. | Only owner-scoped workspace files download; traversal, cross-user access, token misuse, and unsigned shared-root source paths fail. | PASS 2026-05-22 local Edge/API/regression. |
| GH-AZ-UC-006 | Idle or manually stopped compute is released without deleting workspace state. | Edge/Playwright worker page plus automated idle-reaper regression. | `test_idle_reaper_stops_compute_but_preserves_worker`, `worker.idle_terminated` event, artifact still downloadable after reap. | Compute stops, worker remains resumable, audit events record the lifecycle change. | PASS automated and browser evidence 2026-05-22. |
| GH-AZ-UC-006B | Enterprise worker starts without copying VM host Codex, Claude, or git identity files. | Bootstrap regression test. | `tests/test_bootstrap.py` verifies no host auth/identity file copy callbacks are invoked in enterprise mode. | Workers receive only explicit bootstrap content and allowlisted provider env. | PASS 2026-05-22 automated. |
| GH-AZ-UC-007 | Operator compiles the enterprise configuration for LibreChat MCP without application code changes. | Config compiler tests and generated MCP/runtime settings. | `test_config_compiler.py`, docs/runbook sample config. | Non-localhost GlassHive URLs, service auth headers, user assertion headers, idle/provider env settings, and optional OAuth config are emitted. | PASS 2026-05-22 automated. |
| GH-AZ-UC-008 | Operator validates approved enterprise/Viventium cloud readiness without mutating cloud. | Azure CLI read-only checks plus local enterprise browser QA. | Local backup manifest/checksums outside public repo, config snapshots without secret values, public health/auth checks, provider route probes, no mutation. | Approved resources are reachable and scoped; blocked auth/config gaps are explicit; no cloud overwrite occurs. | PARTIAL 2026-05-22 approved-cloud dry run; no Azure deployment performed. |
| GH-AZ-UC-008B | User opens a chat-returned GlassHive View / Steer short link the next day or after the original signed token expired. | Browser chat link plus direct API/UI regression tests. | `/r/{ref}` redirect without raw token, HttpOnly worker cookie, artifact ref opens from the active worker-view cookie, unauthenticated ref/link probes fail closed, live poll refreshes the bounded view cookie, redacted logs/copy text, worker idle state unchanged by merely retaining the ref. | The workspace opens through a clean durable short link, artifacts remain owner-scoped, active watching does not age into `401`, and forgotten tabs/refs do not keep compute running. | PASS 2026-06-20 live approved enterprise dev QA; public-safe summary only, detailed evidence in private enterprise deployment archive. |
| GH-AZ-UC-013 | Operator deploys the approved enterprise dev VM after a local/private backup, then validates live MCP, OAuth gate, worker execution, upload/download, and cleanup. | Azure VM/Caddy/OAuth/LibreChat logs, direct MCP/API, Playwright post-auth UI tunnel, VM filesystem. | Private backup completed; health `200`; MCP initialized with 25 tools; LibreChat logs registered GlassHive MCP; Codex/OpenClaw marker artifacts downloaded; upload projection passed; cross-user access `404`; traversal `400`; UI pause/resume passed; extra QA workers terminated. | Live dev deployment works for direct MCP and post-auth GlassHive UX without cross-user contamination; public browser traffic is OAuth-gated; cost controls are configured. | PASS/PARTIAL 2026-05-23 live approved enterprise dev QA; logged-in LibreChat chat turn, Claude, and Portkey remain blocked/partial. |
| GH-AZ-UC-014 | Operator verifies post-review enterprise hardening before calling the live dev deployment reviewable. | Runtime/UI tests, live API/MCP, VM firewall, worker container. | Full API tests pass; UI server tests pass; direct MCP lists 25 tools; disabled admin endpoint returns `404`; signed-link startup validation is covered in runtime and UI; IMDS connect from active worker returns refused; health remains `200`. | Service-token blast radius is narrowed, maintenance routes are off by default, and worker containers cannot reach Azure IMDS. | PASS 2026-05-23 live approved enterprise dev hardening pass. |
| GH-AZ-UC-015 | Plain LibreChat user launches GlassHive work without Viventium callbacks, checks status, waits for completion, and opens the signed View / Steer page. | Live GlassHive MCP and Playwright signed watch page. | MCP tool list with `workspace_launch`, `workspace_status`, and `workspace_wait`; synthetic upload marker in worker output; DB/log confirmation; signed watch screenshot with no identity-provider redirect and zero console errors; forged public identity headers on signed-link routes return `401`. | GlassHive works standalone with neutral headers, optional callbacks, upload projection, no-callback status/wait, a real operator desktop page, and signed-link routes that do not trust spoofed browser identity headers. | PASS 2026-05-23 live standalone MCP QA; logged-in upgraded chat UI remains PARTIAL during concurrent client upgrade. |
| GH-AZ-UC-016 | Logged-in enterprise chat user uploads a file, invokes GlassHive MCP, waits for completion, opens Watch/Steer, and downloads the generated artifact. | Microsoft Edge logged-in enterprise chat, live GlassHive VM, Playwright signed Watch/Steer, VM DB/filesystem/logs. | Chat tool trace, worker DB row, materialized uploaded file, exact generated artifact body, signed artifact `200`, no-token `401`, traversal `400`, Watch/Steer screenshots, fallback project route member-safety/read-only screenshot, Claude review follow-up tests. | User sees a completed GlassHive worker result with View/Steer link; file content reaches the workspace via `uploaded_files`; generated artifact exists and downloads securely; idle compute stops while preserving state; fallback/dev route is authenticated, read-only for signed members, and points back to main Watch/Steer. | PASS 2026-05-24 live approved-client chat QA after Claude follow-up hardening; see the private enterprise deployment evidence archive. |
| GH-AZ-UC-009 | Enterprise user opens the root GlassHive launcher and creates work from the documented fields. | Playwright browser at local enterprise entrypoint plus raw backend auth probe. | Root snapshot, mobile scroll probe, clean console, raw backend `401`, authenticated bootstrap, automated UI tests. | User can see and submit `Describe your project`, `Success Criteria`, and `Context`; constrained screens scroll to the launch action; missing auth fails closed. | PASS 2026-05-23 local simulation. |
| GH-AZ-UC-010 | Enterprise user watches async work, expands the latest result, opens the menu, and uses pause/resume. | Playwright browser watch surface. | Watch snapshot/eval, result detail panel, menu snapshot, pause/resume state checks, console log check. | Launch is non-blocking; latest result is visible; overlay text does not overlap; one footer button reflects Play/Pause state; interrupt lives in menu. | PASS 2026-05-23 local simulation. |
| GH-AZ-UC-011 | Enterprise member opens Project workspace from Watch and verifies links stay managed. | Playwright browser project workspace through local enterprise proxy. | Reloaded project workspace snapshot/eval, runtime member redaction regression test, UI/runtime docs/openapi probes. | Project workspace opens on the same enterprise origin and contains managed watch/desktop links, not raw API docs, gateway, or localhost noVNC URLs; docs/openapi routes are closed in enterprise mode. | PASS 2026-05-23 local simulation. |
| GH-AZ-UC-012 | Enterprise user opens the workspace hive from the launcher, reveals inactive retained workspaces, and controls one without returning to the project launcher. | Playwright browser launcher and Microsoft Edge at local enterprise entrypoint. | Hive snapshot/eval, inactive toggle, Edge visual state, tile play/pause/steer actions, API live state, mobile scroll/console check, raw backend/proxy auth probes. | `Workspaces` is a selected tab/view; project launcher is hidden; inactive retained workspaces appear only after the toggle; the tile exposes Full watch, Project, Play/Pause, Interrupt, and inline steer controls; no live iframe remains on inactive tiles; raw backend shells fail closed. | PASS 2026-05-23 local simulation after Claude review fixes. |
