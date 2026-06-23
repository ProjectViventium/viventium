# Key Coding Principles for Viventium

**Purpose**: This document serves as the definitive reference for all AI assistants working on this codebase. These principles must be followed in every interaction to ensure consistent, high-quality development.

---

## 🎯 Core Development Principles

### 0. The Core Outcome Metric (always evaluate)

**outcome = Quality (Intelligence, Relevance, Usefulness, Alignment) + Performance (Fast, Smooth, Reliable)**
are the core metric of the viventium project that we must always evaluate in tests, QA, development, design.

- This is the lens for every path, feature, agent, and flow. Never evaluate Performance (speed/latency)
  in isolation — a faster result that is less intelligent, relevant, useful, or aligned is a regression.
- **Parity, not routing rubrics.** Where multiple execution paths can serve the same request (e.g. an
  in-process hand-off agent and a GlassHive worker), each must independently meet this metric. Do not
  hardcode a rubric like "quick request → path A, thorough request → path B"; let the AI (Main Agent and
  the worker) decide intelligently, and make every path produce truthful, complete, useful, fast results.

### 1. Beautifully Simple and Efficient
- **Do not overcomplicate things** - Seek elegant, efficient solutions
- Study the codebase, components, and research web for inspiration to identify the most beautiful and efficient way to implement features
- Code must be user-friendly for other engineers and developers
- Make code dynamic - **avoid hardcoding things**
- **MOST IMPORTANTLY**: **SEPARATION OF CONCERNS PRINCIPLE MUST BE FOLLOWED AT ALL TIMES** to maintain a clear modular design so the project does not turn into entangled spaghetti code

### 2. Documentation First
- Document steps in `.md` format in `docs/` folder
- Ensure compatibility and easiness for other developers to edit and extend code without headache
- When developing new features: create unit tests, run them, analyze failures, and make necessary adjustments

### 2.1 Repository Boundary Discipline
- `viventium_core` is the product/public-facing engineering surface
- the dedicated private companion repo is the only place for personal state, private prompts, private docs, backups, snapshots, machine-specific runtime data, and explicit user-approved secret-bearing transfer files
- the dedicated enterprise deployment repo is the only place for deployment-as-a-service code, enterprise overlays, and operator runbooks
- the private and enterprise companion repos may live locally either beside `viventium_core` or under its root for unified-workspace convenience, but when nested they must remain separate git repos, ignored by the main repo, and excluded from every public export or tracked public surface
- a plain same-named folder is not a valid private boundary; a `<private-companion-repo>` or `<enterprise-deployment-repo>` only counts when it is the root of a separate git repo or worktree
- If a file is not required to install, run, test, document, or release the v0.4 product surface, it does not belong in the tracked public-facing repo roots or any publishable export generated from them
- credentials, passwords, tokens, and secrets that appear in chat are transient secrets:
  - use them only for the immediate local task
  - do not restate them in docs, tests, commits, QA artifacts, support notes, or second-opinion prompts
- When in doubt:
  - personal / confidential / owner-specific / machine-specific -> private repo
  - deployment / infra / customer-ops / enterprise-only -> enterprise repo
  - installer / CLI / canonical config / tests / docs / launch wrappers / product code -> `viventium_core`

### 2.2 Canonical Config Discipline
- End-user configuration must converge on one human-facing source of truth:
  - `~/Library/Application Support/Viventium/config.yaml`
- Service-local `.env` files and YAML fragments are generated artifacts, not hand-maintained sources of truth
- Legacy repo-local `.env*` files are compatibility inputs for the private owner workflow only and must not become the public install story
- If a private machine-transfer or restore workflow needs explicit secrets, keep those files only in the private companion repo and document the exception there

### 2.3 Auth and Upgrade Discipline
- Do not drift into generic LibreChat credential behavior when Viventium has a documented product rule
- Provider auth precedence must stay:
  - user connected account first when supported and available
  - explicit API key from canonical/generated runtime env next
  - otherwise show a clear action to connect the account or provide the key
- Do not silently seed or expose models that the current configured auth mode cannot actually use
- Local installer and runtime health checks must be honest about mixed-mode dependencies:
  - if a feature still needs Docker Desktop in a nominally native install, say so before startup
- `bin/viventium upgrade` is the canonical path for refreshing a local install:
  - pull the current branch
  - detect/install new prerequisites in one batch
  - refresh pinned components
  - recompile generated runtime files
  - rerun doctor before restart

### 2.3.1 Shipped Artifact and Pin Discipline
- A source fix is not shipped just because the tracked file changed.
- When a feature is delivered through a nested component, compiled `dist/` output, prebuilt helper, shipped binary, or pinned component ref, release readiness requires all relevant surfaces to match:
  - tracked source change
  - nested component commit, when applicable
  - parent pin/manifest entry such as `components.lock.json`
  - compiled/prebuilt delivery artifact and any source hash that validates it
  - live installed or running artifact used in QA
- Source-level inspection is insufficient for these cases:
  - verify the installed helper bundle, shipped binary, or compiled runtime that the product actually runs
  - do not assume source correctness implies artifact correctness
- If a nested component or shipped artifact changed, verify the parent pin and the installed artifact together before claiming release readiness

### 2.3.2 Continuity and Restore Discipline
- Continuity incidents must be decomposed before fixing them. At minimum, classify which of these surfaces is failing:
  - chat history
  - saved memory
  - recall / RAG corpus
  - schedules / background tasks
  - auth / provider state
  - restore / backup state
- Recall/vector state is derived state, not canonical truth.
- Restore and upgrade paths must be continuity-aware:
  - do not silently trust rolled-back recall/vector state
  - rebuild, invalidate, or block stale derived continuity surfaces until they are proven current again

### 2.4 Installer and QA Discipline
- A clean-machine install must be proven through the public product paths only:
  - `./install.sh`
  - `bin/viventium upgrade`
  - `bin/viventium start`
- Do not "save" a broken test machine with hand edits inside App Support, local component trees, Mongo, or service state and then claim the installer works
- If a nested component change is required for installer correctness on private branches, the shipped private snapshot must also be refreshed:
  - component source
  - the shipped component snapshot manifest
  - `components.lock.json`
- Per-machine integrations must come from canonical config or approved transfer presets, not from reusing the developer machine's live tokens:
  - example: Telegram bot tokens must be machine/environment-specific when concurrent bot sessions would conflict
- Installer acceptance is not complete until the product is validated from another device or machine over LAN/public origin where relevant:
  - API/config inspection alone is insufficient
  - real browser QA must confirm the visible surface, login flow, provider picker, connected-account actions, and remote call routing
- For helper apps, prebuilt binaries, and compiled runtime bundles, QA must prove the live installed artifact:
  - verifying source code or the local repo tree alone is not enough
- Cold-start behavior must be treated as part of product quality:
  - honest progress and timeouts for first-build Docker paths
  - honest health checks during first package builds
  - no false "healthy" claim before the actual user-facing surfaces respond

### 2.5 Incident Learning and Drift Prevention Discipline
- When a bug exposes a gap between source, docs, runtime behavior, QA, or user-visible wording, the
  fix must capture the learning in the owning feature document and, when non-trivial, in `qa/`.
- Root-cause notes must explain the full causal chain:
  - trigger
  - transformation path
  - user-visible failure
  - precise owning fix
  - why similar drift is prevented for future users
- Do not treat "code changed" as "problem solved":
  - run the relevant automated checks
  - verify the live or shipped artifact when the feature depends on a running worker, generated
    config, compiled bundle, nested component, or prebuilt output
  - record residual risks and any runtime QA that still remains
- If a user reports that a live/local flow still fails after an earlier fix, treat that report as
  new evidence. Reopen logs, DB/runtime state, code, docs, and generated artifacts before claiming
  the failure is explained.
- Debug instrumentation must reveal the decisive truth without leaking secrets or private data:
  - exact payload text should be logged with safe escaping when formatting is the suspected issue
  - credentials, private identifiers, local absolute paths, account emails, call-session ids, and
    private transcript content must stay out of public docs and QA artifacts
- Second-opinion reviews are used to challenge a grounded proposal, not to replace investigation:
  document what was validated, what gaps were found, and what follow-up was completed.
- User-facing error copy is part of product truth. If the underlying failure is rate limit, auth,
  missing key, provider outage, local runtime unavailable, or unsupported configuration, the message
  must say the correct class of problem instead of a generic service failure.
- On any user-facing agent route, a recoverable provider failure before visible assistant text is
  produced should retry exactly once through the configured fallback route when one is valid. If no
  fallback is configured or the fallback also fails, the user-visible result must be a concise,
  actionable provider-class blocker; it must not expose raw LangChain/internal troubleshooting text
  as the assistant answer.
- Retrieval/tool failures must never be laundered into "nothing exists." For web search and other
  evidence tools, distinguish successful-empty results from provider unavailable, timeout, rate
  limit, auth/config missing, request rejected, and unsupported configuration. For named-entity,
  contact, date, event-detail, or current-fact lookups, one failed search is an escalation trigger:
  check the configured provider health, including Docker-backed local services when relevant, and
  use an available browser/computer/local-delegation fallback before stopping.
- Communication must be efficient and specific: summarize what was changed, how it was verified,
  what was pushed or left local, and what still needs live QA, without dumping raw logs or private
  machine details.
- Delegated agent/workspace work must preserve the user's full intent. When handing work to
  GlassHive, another worker, a scheduler, or any long-running background system, do not replace the
  request with a thin paraphrase. Pass the full available task, success criteria, constraints,
  examples, links, file references, exclusions, and background context through the structured fields
  that own that delegation. Use summaries only as labels or titles, not as the worker's complete
  instruction.
- GlassHive workers are general intelligent workers, so less is more. Host assistants and MCP tool
  descriptions should provide the user's actual goal, constraints, files, connected MCP/tool
  capability context, and explicit success conditions, then trust the worker to choose the path.
  Do not manufacture project goals, rubrics, provider lists, output artifacts, or workflow steps
  just because a prior QA prompt happened to need them.
- For brokered MCP/tool delegation, the host is a faithful courier, not the planner. It must pass the
  user's request through with factual available context, verified tool results, and brokered
  capability grants; it must not predict which connected provider, account, MCP, tool, output format,
  or workflow the worker should use unless the user explicitly specified that choice or current
  tool evidence proves it. The design assumption is that users and host applications can connect
  unpredictable MCPs, so GlassHive must expose capabilities and let the general worker decide.
- GlassHive/MCP observability must be honest without being raw. Persisted MCP/tool-call rows should
  remain visible and inspectable in user-facing chat surfaces as concise product-language rows with
  safe task/status/artifact summaries. Hide raw invocation code, internal worker/run IDs, provider
  plumbing, and acknowledgement guidance unless the user explicitly asks for diagnostics; do not
  hide the fact that a tool or worker was used.
- GlassHive chat rendering must treat hidden/accessibility/copy text as user-facing for privacy and
  polish. Visible link labels can look clean while offscreen live regions or serialized Markdown
  still contain signed artifact/watch URLs, tokens, raw IDs, or stripped filename text. QA must
  inspect DOM/accessibility text in addition to the visual bubble, and renderers/bridges must avoid
  exposing signed URLs or raw Markdown source unless diagnostics are explicitly requested.
- MCP tool schemas and descriptions are capability contracts too. Runtime-aware server instructions
  are not enough if the callable parameter descriptions still advertise a disabled or unavailable
  substrate. When host-native workers, worker profiles, browser/computer capability, model effort,
  or file-access modes are enabled/disabled by config, the generated MCP schema/descriptions and
  server instructions must agree with the same live config before a host app reconnects.
- Worker substrate configuration must be verified against the actual provider route, not generic
  model-family assumptions. If a CLI accepts a broad effort/capability vocabulary but the deployed
  OpenAI-compatible route supports only a subset, the deployment must declare that subset and the
  runtime must clamp through the configured fallback before launch with observable logs/telemetry.
  Unsupported provider settings are infrastructure/configuration failures, not evidence that the
  worker's intelligence should be reduced or that prompts should over-specify a workaround.
- Hosted worker model rollout belongs to the route the worker process actually uses. A newer model
  deployed in another account, resource group, subscription, provider project, or local config does
  not help GlassHive unless the active worker endpoint and deployment name point at it. Before
  changing defaults, prove the active route with a direct provider probe and at least one real
  worker run that records the selected model and effort.
- Provider quota/capacity is part of the worker substrate. If a long deep-research or document run
  fails because the active route rate-limited tool/model calls, do not remove the deep-work
  requirement or lower worker intelligence as the "fix." Classify it as capacity/config evidence,
  adjust the active route or deployment quota responsibly, and rerun the same user-level QA path.
- Worker effort is part of the native substrate, not a decorative prompt hint. When MCP, UI, or direct
  API accepts a worker-type effort such as Codex `high`/`xhigh` or Claude `max`, the runtime must
  project it through structured bootstrap/config and prove the generated worker command/provider
  request actually used it. Prompt-only effort text is acceptable only for worker types that have no
  native effort surface.
- Host prompts must not downshift GlassHive's ordinary work by habit. If the user did not ask for a
  cheaper/faster pass, omit the per-run `effort` field for normal bounded tasks and let the saved user
  preference or deployment default own the baseline. Explicitly choose Codex `high`/`xhigh`, Claude
  `max`, or the configured equivalent for deep research, critical analysis, coding, comparison,
  large transformations, or executive-quality deliverables.
- GlassHive worker capability projection is additive. Broker grants, scoped MCP files, worker-local
  config, model-provider settings, and launch flags must not strip the selected worker type's native
  skills/capabilities such as browser, computer/desktop, shell, file, MCP, and local app control.
  If a deployment intentionally locks a worker down, that must be an explicit configuration decision
  with preflight/QA coverage, not the default path. Because the host AI and user can ask for unknown
  future work, the runtime gives the worker its full truthful capability surface and lets the worker
  decide how to use it.
- Browser/computer capability must be understood as the selected worker's native product surface, not
  as only an MCP inventory item. Claude Code may expose Chrome and computer use through its own
  interactive CLI surfaces; Codex may expose Browser, Chrome, and Computer Use through app/plugin
  surfaces and worker-local config. GlassHive should project, preflight, and document those native
  capabilities truthfully, and treat missing/disabled capabilities as runtime configuration evidence
  rather than proof that the worker should never use a browser or computer.
- GlassHive worker-native skills/plugins are capability inventory, not host-authored workflow.
  Bootstrapped host and workspace workers must be told which native skill families and CLI/browser
  surfaces are expected for their type, and the runtime/image must provision those capabilities
  where license and mode allow. Claude Code and Codex browser-use extensions in workspace images are
  part of the substrate expectation: managed policy, profile installation, and connected bridge
  state must be tested separately. Workers should choose these skills/extensions when relevant and
  should not be forced into any prompt-specific skill, provider, file format, or rubric.
- GlassHive workspace native browser/computer work follows **The Golden GlassHive Rules**, the named
  `GH-WNBC-001` through `GH-WNBC-007` rules in
  `48_GlassHive_Workstation_Sandbox_Runtime.md`: less-is-more delegation, faithful capability
  context, additive native projection, browser/computer as native worker surface, isolated workspace
  bootstrap, no residual warning UX, and user-grade native capability QA.
- Deploy UI/client assets only with their matching backend/shared-package contract unless the
  compatibility boundary is explicitly proven. A client-dist-only overlay can be valid for a narrow
  static fix only after a real browser smoke proves the composer, model selector, MCP/tools row,
  message send, tool result, and artifact/file path still work. If an overlay breaks the visible app,
  roll it back immediately and classify the full-image build/publish blocker separately.
- GlassHive data in and data out must be exact. The host application must pass real uploads, file
  references, MCP grants/capabilities, retrieved context, and tool results without pretending they
  exist or were used. If data, auth, files, or MCP access are unavailable, the delegation should
  preserve that fact so the worker can choose a fallback or report a concrete blocker.
- GlassHive file handoff should stay simple and literal. Materialize allowed files into the
  worker-accessible workspace, mention the full accessible path in the prompt/bootstrap context, and
  let the worker decide how to use it. Do not replace this basic path contract with prompt-specific
  CLI arguments, hidden attachment heuristics, or guessed file access.
- GlassHive live surfaces must be truthful, not just link-shaped. A `/watch/{worker}?surface=desktop`
  URL means the primary surface remains the live workstation desktop; completed files are explicit
  result actions/status, not replacements for the requested desktop frame. `view_available` means
  the noVNC/browser substrate is actually reachable, and callback delivery means the user-facing
  chat conversation was updated so the result can surface after refresh, not merely that an outbox
  row was marked delivered.
- Delegated workers must receive a universal completion contract. Before reporting completion, the
  worker must compare the actual result against the user's request, success criteria, constraints,
  files/artifacts, visible state, or tool results when applicable; continue or remediate when the
  result does not satisfy the request; and report a specific blocker only when it cannot complete the
  task. This contract must stay capability-general and must not encode one QA prompt, one file type,
  one provider, or one host application as special runtime behavior.
- The universal completion contract must be injected at the command/run boundary for every worker
  runtime, not only written into project files. Docker/workstation Claude, host Claude, Docker/host
  Codex, and OpenClaw must all receive the same self-check and `FINAL REPORT:` requirement in the
  instruction actually sent to the CLI.
- When the user's request calls for a document, report, deck, client deliverable, or other shareable
  work product and no technical/source format was requested, the worker's primary user-facing output
  should be a polished ordinary end-user artifact such as PDF, Word, PowerPoint, spreadsheet, or an
  equivalently professional format chosen by the worker. Markdown, HTML, or source files can be
  supporting artifacts, but they are not enough as the default primary deliverable for that class of
  work unless the runtime cannot create the professional artifact and reports that blocker.
- Keep host/application orchestration checks separate from worker deliverable gates. For GlassHive,
  requirements such as which MCP tool was selected, whether the chat surfaced the View / Steer link,
  callback delivery, wait/status polling cadence, and post-run inspection from the host UI belong to
  the host assistant/operator QA layer. Preserve those checks as context, but do not make a sandbox
  worker fail a completed file/browser/research/code task just because it cannot observe the host
  chat UI from inside its workspace.
- Worker substrate failures are harness/runtime failures before they are user tasks. If a worker
  cannot start because of missing or incompatible local prerequisites, credentials, sidecars, tools,
  or runtime versions, the harness must classify the failure, try configured safe recovery or routing
  such as a managed dependency, alternate available profile, or sandbox/workstation mode when that
  does not contradict the user's request, and only then ask the user/operator for action with the
  exact blocker. Do not make "install a global tool on your machine" the first visible recovery when
  a managed or sandboxed path is available.
- Host-native worker CLIs must be preflighted against current supported stable floors and required
  native capability flags before a run is created. A stale or capability-stripped `claude`, `codex`,
  or `openclaw` binary is a substrate issue, not evidence that the worker is unintelligent. When a
  safe documented updater exists, use or surface that updater; when the mutation is global or unsafe,
  fail closed with exact recovery guidance instead of launching a degraded worker.
- GlassHive runtime facts must stay mode-scoped. Host-native binary overrides, desktop/browser
  affordances, and local-app assumptions belong only to host workers; workspace/sandbox workers must
  resolve their CLIs and tools inside their own container image and home/config. Likewise, projected
  state/workspace paths are observability and persistence facts, not proof that a Docker container,
  process, browser, or worker substrate exists. Verify the real substrate before reusing it, and make
  missing substrate a classified runtime failure rather than a user-task failure.

### 2.6 Production QA Operating Discipline
- `qa/README.md` is the QA operating contract. Every developer and AI agent must treat it as the
  source of truth for QA folder shape, case metadata, run reports, public-safety rules, and
  user-grade acceptance.
- Full-view evidence is the hard gate for non-trivial feature, bug, runtime, installer, and release
  work. The evidence chain must tie:
  `feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`.
- Full-view evidence means inspecting the real owning code, logs, DB/state/persistence, generated or
  shipped artifacts, scripts/harnesses, docs and nested docs/repos, and the real user path through
  browser/computer, Telegram, voice, installer, CLI, MCP/tool, scheduler, GlassHive, or the relevant
  surface.
- Start QA from the feature inventory and natural user use cases, not from the single symptom or
  code file in front of you. Use `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`,
  `qa/feature-user-use-case-checklist.md`, and the owning `qa/<feature>/cases.md` to list the obvious
  user actions first: happy path, first-run/empty state, missing auth/config, degraded dependency,
  retry/recovery, interruption/cancel/update, persistence/reload/restart, cross-surface parity,
  shipped artifact verification, and public/private safety.
- Treat that use-case list as a checklist. Each applicable item must be exercised like a user through
  the real product surface and marked `PASS`, `FAIL`, `BLOCKED`, or `PARTIAL` with evidence. If an
  item was not run, it remains a visible gap.
- If the real user path cannot be run, the result is `BLOCKED` or `PARTIAL`, not done. Name the
  missing path, record what supporting evidence was gathered, and do not use mocks, unit tests, logs,
  DB rows, source inspection, or another model's review as a substitute for required user evidence.
- Supporting evidence cannot replace required user-path evidence.
- Completion reports must explicitly say what was run, what was not run, what visible UX/result was
  observed, what backend/log/DB/state evidence supports it, and what mismatch or residual fix remains.
- Keep one living QA area per feature or flow:
  - `qa/<feature>/README.md` for scope, owning docs, surfaces, quality bar, and latest status
  - `qa/<feature>/cases.md` for durable case IDs, expected outcomes, forbidden outcomes, automation,
    and last-run links
  - `qa/<feature>/reports/YYYY-MM-DD-<topic>.md` for dated execution evidence and residual risks
- When touching a feature, update the relevant QA cases before or alongside the implementation and
  rerun the impacted existing cases. Do not leave the QA source of truth stale while adding one-off
  notes elsewhere.
- Every escaped defect, production miss, user-reported failure, or "we missed this in QA" lesson must
  be promoted into a reusable synthetic regression case. Preserve the behavioral shape and expected
  outcome, but remove private transcript text, personal names, account details, screenshots, tokens,
  local paths, and machine-specific state.
- User-facing behavior requires user-grade QA. For browser-visible flows, the acceptance loop is:
  `real browser prompt/action -> visible UI outcome -> expanded/detail state -> refresh or
  persistence check when relevant -> backend/log/DB confirmation -> final model/runtime wording does
  not contradict the visible state`.
- Logs, DB rows, API responses, source inspection, model completions, and unit tests are supporting
  evidence, not substitutes for any required visible-UI, detail-state, persistence, or wording step.
  Skipping the visible browser step is not acceptable for browser-visible behavior even when backend
  evidence says the operation succeeded.
- If an obvious infrastructure prerequisite is part of the feature, such as Docker Desktop for local
  SearXNG/Firecrawl, local Bot API, code interpreter, or sidecars, the QA checklist must include the
  prerequisite state. A stopped prerequisite is evidence, not an excuse to collapse the result into a
  vague product failure.
- For non-browser surfaces, use the nearest real product loop: Telegram send/receive plus ledger,
  Voice/LiveKit call plus transcript/latency, Scheduler trigger plus delivery ledger, installer/CLI
  command plus installed artifact, and MCP/tool call plus auth/tool-result/failure-copy verification.
- Mocked tests, unit tests, API checks, logs, or DB rows can support QA, but they do not replace the
  user-visible acceptance path when the product surface is visible to the user.
- Public QA artifacts must be sanitized: no secrets, private prompts, personal chats, customer data,
  local absolute paths, account identifiers, conversation IDs, message IDs, session/call IDs,
  Telegram chat IDs, Mongo `_id` values, screenshots with private content, database exports, App
  Support state, cookies, raw provider request/response IDs, stack traces with private paths, or raw
  runtime dumps. Store raw private evidence only in the approved private location and summarize
  public-safe counts, hashes, timestamps, and conclusions in `qa/`.

### 3. Study Before Acting
- **Do not make assumptions** about the codebase, components, or anything
- **You must provide proof and references** to truth in codebase and online resources to ensure you are grounded in reality and not making things up
- When requesting new features: **study the project systematically** to map it out and understand the best place to add the new feature in concert with existing codebase and behavior
- Strictly follow a modular design that is efficient, beautifully simple, does not overcomplicate things, and perfectly gets the job done
- **Avoid recreating the wheel** by analyzing the components and modules you can use that are either already in the project or can be imported

---

## 📖 Requirements & Learnings Directory

### Purpose of `docs/requirements_and_learnings/`
The `docs/requirements_and_learnings/` directory serves as the **central repository** for all key requirements and learnings across the project. This directory ensures that all feature-specific knowledge, requirements, specifications, and learnings are consolidated in one place.

### Critical Rules:

#### 1. Single Source of Truth Per Feature
- **DO NOT EVER LET THERE BE MULTIPLE DOCUMENTS FOR THE SAME FEATURE / REQUIREMENT**
- Instead: **compile, update, and add** to existing documents
- Each feature/concept should have exactly **one comprehensive document** that contains everything about it

#### 2. When Working on New Features/Projects
- **All documents in this directory must be added/updated** when working on new features or projects
- If the new feature/project has key requirements or learnings tied to a single concept or feature, they **must be documented here**
- Example: If working on background agents and how they surface results:
  - User's requirements → Document in the background agents document
  - Your learnings → Add to the same document
  - Specifications → Include in the same document
  - Use cases → Document in the same document

#### 3. Document Completeness Standard
A developer referring to a single document about a respective feature **must perfectly become up to speed** about:
- ✅ **Requirements** - What the feature must do
- ✅ **Specifications** - How it should work technically
- ✅ **Use Cases** - When and why to use it
- ✅ **Learnings** - What was discovered during development
- ✅ **Edge Cases** - Known limitations or special considerations
- ✅ **Integration Points** - How it connects with other parts of the system

#### 4. Document Naming Convention
- Use descriptive, feature-specific names (e.g., `02_Background_Agents.md`, `03_Memory_System.md`)
- Number documents for easy reference (e.g., `01_`, `02_`, `03_`)
- Keep names concise but clear

#### 5. Maintenance Responsibility
- When adding new requirements or learnings, **first check if a document exists** for that feature/concept
- If it exists: **update the existing document** - do not create a new one
- If it doesn't exist: **create a new document** following the naming convention
- Always ensure the document remains comprehensive and up-to-date

### Example Workflow:
```
1. Starting work on "Background Agents" feature
   → Check: Does `02_Background_Agents.md` exist?
   
2. If YES:
   → Read existing document
   → Add new requirements/learnings to it
   → Update specifications if changed
   
3. If NO:
   → Create `02_Background_Agents.md`
   → Document all requirements, specifications, use cases, and learnings
   
4. Result: One complete document that tells the full story
```

### Benefits:
- ✅ **No information fragmentation** - Everything about a feature in one place
- ✅ **Easy onboarding** - New developers can understand features quickly
- ✅ **Knowledge preservation** - Learnings don't get lost
- ✅ **Consistency** - Single source prevents conflicting information
- ✅ **Maintainability** - Easier to keep documentation current

---

## 🔍 Root Cause Analysis Methodology

### When There Are Issues:
1. **Break down the problem** to the smallest steps and things you can - small and full coverage
2. **Go to first principle thinking** and truly nail down the issue
3. **Stop assuming you have a fix and jumping to the build!**
4. **You need to have complete concrete evidence** only after you've gone through EVERYTHING
5. **Then finally refer to web** for additional context if needed
6. **LEAVE NO STONE UNTURNED**
7. When asking a second model or sub-agent to review the issue, sanitize private values whenever a placeholder will preserve the reasoning task

### Priority-Based Approach
- Address issues in priority order based on severity (Critical → High → Medium → Low)
- Create comprehensive analysis documents before implementation
- Validate, test, and explore fixes before implementing

---

## 📚 Codebase Study Requirements

### General Rules:
- **Do not overfit!** Read the documentation priority to any change for both `viventium_v0_3_py/viventium_v1` and `viventium_v0_4` (we are no longer updating v0_3, so assume features and fixes and changes are all meant for viventium_v0_4)
- Ask yourself, based on the codebase and docs, what other parallel usecases are supported? and would my plan or solution fix only this? or the full scope for various cases. 
- Based on documentation, gain the background and context before making changes
- **Do not patch** Do a full analysis of components and things that are involved so that you fix the root cause without breaking any other functionality at its root, instead of patch of patch!
- **Do Not re-invent the wheel** First, study the code base and root project files to find similar things that you can use. Second, search web, online github repositories, forums, online docs, community notes, and various things. (Because reality is... everything has already been done in many ways by many people and if you dont find exactly the trusted reliable answer, you will find close inspiration to use)
- **Study the codebase** and understand the existing logic, flow, patterns, and principles
- Make changes the proper way in full, covering edge cases
- Ensure changes are consistent with the existing codebase and principles

### Before Any Change:
- Understand existing components, patterns, and abstractions
- Identify where existing functionality can be reused
- Map out the proper integration points
- Ensure minimal changes that leverage existing code

### Runtime vs Prompt Decision Gate (MANDATORY)
- **Classify output ownership first** before proposing fixes:
  - `runtime-generated` = deterministic strings/behavior from code paths (controllers, services, dispatch, adapters)
  - `model-generated` = LLM output influenced by prompts/configuration
- **Prompt-change gate**:
  - If behavior is `runtime-generated`, fix the runtime path first
  - Prompt/config edits are allowed only when root cause is `model-generated`
- **Do not use prompt edits to suppress deterministic runtime placeholders**; fix the source code path emitting them
- **Provide a concrete causal chain** for every issue: `trigger -> transformation -> user-visible output`, with file:line references
- **Plumbing budget rule**: before adding new request fields/routes/config keys, prove existing context signals are insufficient (e.g., existing ids/metadata already flowing)
- **Cross-surface regression check**: evaluate impact across Telegram, Scheduler, LibreChat Web UI, and Voice before finalizing
- **No one-instance scheduling exceptions**: scheduled prompts must flow through one canonical generation,
  visibility classification, delivery, and ledger path. Do not branch runtime behavior on human-facing
  schedule names, prompt examples, or incident-specific labels such as "heartbeat"; use structured task
  fields or explicit metadata contracts when a schedule needs special operational policy.
- **Activation classifier rule**:
  - If a background-agent activation bug is `model-generated`, fix the user-configured activation prompt/source-of-truth first and prove it with evals.
  - Do **not** add runtime string blacklists or message-specific "if text contains X, suppress agent Y" gates for classifier false positives.
  - Runtime changes are allowed only for structural activation plumbing defects (for example: wrong context assembly, broken latest-turn extraction, missing fallback wiring, or bad scope metadata propagation). This bullet does **not** override the CRITICAL RULE below.
  - For productivity agents specifically, "reply/respond/say/return" must never be hardcoded as special-case deny words in code; the classifier prompt must distinguish chat-format instructions from real email/content actions.
  - Do **not** infer agent role from hardcoded agent names, cortex titles, or tool names when explicit config metadata can carry the intent. User systems may rename agents, replace tools, or define different specialist shapes entirely.

### CRITICAL RULE: No Hardcoded NLU in Runtime Code
- Intent detection, provider clarification, and history classification must be owned by LLM activation classifiers plus YAML-configured activation prompts.
- Runtime code must **not** use regex, substring matching, or hand-written NLU helpers on user/assistant message text to:
  - decide cortex activation
  - classify provider intent such as Gmail / Outlook / Ms365
  - pre-filter or rewrite activation history based on guessed semantics
  - create "deterministic fast paths" that bypass the activation classifier
- Allowed runtime string handling is limited to deterministic structural parsing:
  - identifier extraction such as URLs, file IDs, email addresses, or protocol strings
  - message metadata such as role, timestamp, length, attachment presence, or configured scope keys
  - message-content normalization needed to read stored text blocks safely
- If a fix requires teaching the system to understand new phrasing, the change belongs in `viventium_v0_4/LibreChat/viventium/source_of_truth/<env>.viventium-agents.yaml`, not in JavaScript.
- If classifier reliability is the issue, fix it with `activation.fallbacks` and live eval coverage, not with heuristic runtime preempts.
- Any PR that reintroduces regex or keyword NLU in runtime routing layers is a critical review block unless it proves the logic is deterministic-by-construction and not user-intent classification.

### User-Level Configurations and System Prompts
- **Do not overfit user-level designs** such as system prompts and configurations
- System prompts are not a substitute for fixing deterministic runtime behavior in backend pipelines
- Viventium is an agentic platform with a real agent builder, editable background cortex configs, and configurable activation models:
  - use those config surfaces instead of sneaking business logic into runtime code when the problem is classifier behavior
  - when a prompt/config change is made, add/update reusable QA docs and automated regression coverage so future engineers can verify the intended behavior without rediscovering it
- Before modifying or creating system prompts/configurations, **always pull the latest user-level configs** to understand current state:
  ```bash
  node viventium_v0_4/LibreChat/scripts/viventium-sync-agents.js pull
  ```
- This provides visibility into the inner workings of user-level agent configurations, system prompts, and related settings
- Before any push/update to live user-level agents, **always run a live-vs-source comparison** and review:
  - A = current live user-level agent bundle
  - B = tracked source-of-truth bundle
  - C = current repo/source-of-truth edits that are not yet in live
- Present the A/B/C drift to the user before syncing when there is any difference in user-managed
  fields such as instructions, conversation starters, tools, provider/model, or background cortex config.
- Treat live user edits as protected state until they are intentionally reconciled. Do **not** assume
  the tracked scaffold should automatically overwrite live user-managed config.
- If the symptom is capability availability rather than prompt text alone, inspect adjacent
  scaffold/runtime config too (for example `viventium_v0_4/LibreChat/viventium/source_of_truth/<env>.librechat.yaml`).
  Global toggles such as `interface.webSearch` can disable behavior even when the agent bundle still
  contains the expected tool entries.
- Non-dry-run sync should fail closed when reviewed live-vs-source drift still exists. Only proceed
  with an explicit acknowledgement such as `--compare-reviewed` after the A/B/C diff has been shown
  and intentionally accepted.
- When syncing agent model/provider fields into a live local Mongo surface, the sync path must honor
  the canonical generated runtime env. Do not treat the raw git-tracked bundle as the live model
  truth when the runtime compiler/seed path defines the actual assignment for that machine.
- To update user-level configs:
  1. Pull the latest configs: `viventium-sync-agents.js pull --env=<env>`
  2. Compare live vs source-of-truth vs current repo edits: `viventium-sync-agents.js compare --env=<env>`
  3. Edit the **git-tracked source-of-truth** file for clean diffs:
     - `viventium_v0_4/LibreChat/viventium/source_of_truth/<env>.viventium-agents.yaml`
     - (Snapshots are still written under `.viventium/artifacts/agents-sync/runs/<timestamp>-<env>/viventium-agents.yaml`)
  4. Push the updated configs using the **correct push mode**:
    - `viventium-sync-agents.js push --prompts-only --env=<env>` — for prompt/instruction/cortex activation changes
     - `viventium-sync-agents.js push --activation-config-only --activation-fields=prompt,model,provider,fallbacks,intent_scope --env=<env>` — for selected background cortex activation config changes
     - `viventium-sync-agents.js push --model-config-only --env=<env>` — for provider/model updates only
     - `viventium-sync-agents.js push --env=<env>` — full push (DANGEROUS, see warning below)
- `env` is set via `--env=<env>` (or `VIVENTIUM_ENV=<env>`); use the target runtime environment name for pull/push operations.
- This ensures you're working with the actual deployed configurations, not assumptions
- Canonical artifact/snapshot path conventions are documented in `docs/requirements_and_learnings/27_Artifact_Storage_Standard.md`

#### CRITICAL: Push Safety Rules (Learned 2026-02-15)
- **ALWAYS use `--prompts-only` for prompt/instruction/cortex activation changes**. This is the safe mode that skips `tools`, `model`, `provider`, and other UI-managed fields.
- **ALWAYS review `compare --env=<env>` output before push**. If live user config differs from the tracked scaffold on user-managed fields, reconcile intentionally and present that drift to the user before applying changes.
- **NEVER use default `push` (without `--prompts-only`) unless you are certain the YAML `tools` arrays exactly match the live target environment state**. Default push overwrites ALL fields including `tools`, which breaks MCP server links that were configured via the LibreChat UI. The user then has to manually re-add each MCP server one by one.
- **Why it breaks**: Default push writes 16 fields including `tools` (string arrays like `sys__server__sys_mcp_scheduling-cortex`). If the YAML was pulled at time T1 and someone changed MCP tools via UI between T1 and push at T2, the stale T1 tools array overwrites the UI changes.
- **Do not blindly overwrite live instructions or conversation starters either**. A stale scaffold can erase user-authored main-agent or background-agent prompt edits just as easily as it can erase tools.
- **`--prompts-only` safe fields**: `id`, `name`, `description`, `instructions`, `conversation_starters`, `background_cortices` (with safe merge that only touches `activation.enabled`, `activation.prompt`, `activation.confidence_threshold`, and the explicitly reviewed reliability field `activation.fallbacks`). Treat fallback changes as live runtime-behavior changes, not as copy-only prompt edits.
- **`--activation-config-only` safe fields**: only `background_cortices`, with an allowlist merge over `activation.enabled`, `activation.prompt`, `activation.confidence_threshold`, `activation.fallbacks`, `activation.model`, `activation.provider`, `activation.cooldown_ms`, `activation.max_history`, and `activation.intent_scope`. Use `--activation-fields=...` to narrow further.
- **`--model-config-only` safe fields**: only agent model/provider fields and their parameter bags
  (`provider`, `model`, `model_parameters`, `voice_llm_model`, `voice_llm_provider`,
  `voice_llm_model_parameters`, `voice_fallback_llm_model`, `voice_fallback_llm_provider`,
  `voice_fallback_llm_model_parameters`, `fallback_llm_model`, `fallback_llm_provider`,
  `fallback_llm_model_parameters`). Use this when correcting stale model drift without touching
  tools or prompts. Voice model changes that depend on provider-specific knobs, such as xAI
  `reasoning_effort: none`, must prove the parameter bag survived the sync.
- **Use `--agent-ids=...` for surgical pushes** when only a subset of background agents changed. This keeps model/prompt fixes narrowly scoped instead of rewriting the whole roster.
- **Always dry-run first**: `push --prompts-only --dry-run --env=<env>` to preview changes before applying.
- Safety UX rule for operator tooling:
  - `--help`, `-h`, and explicit usage/preview paths must be side-effect free
  - a help flag must never execute a real pull/push/write path
  - reason: sync tooling is used in high-risk configuration surfaces where one mistaken invocation can overwrite live agent state
- For activation routing/plumbing, prefer a small explicit config key such as `activation.intent_scope` over runtime title/agent-name inference.
- Runtime ownership rule for agentic systems:
  - legal: explicit config metadata (`activation.intent_scope`, selected model/provider fields, prompt text, thresholds)
  - legal: generic runtime plumbing that derives provider intent from canonical config tokens such as `productivity_<scope>` without inspecting agent names or prompt titles
  - illegal: hardcoded business logic keyed to one generated agent id, one agent title, one tool name suffix, or one specific user prompt example
  - illegal: runtime alias maps that silently treat free-form provider/tool labels (`gmail`, `google`, `outlook`, `onedrive`, etc.) as if they were valid activation scope keys when the source-of-truth config already defines canonical scope tokens
  - illegal: accepting loose provider aliases in helper-context isolation logic (`gmail`, `outlook`, `google`, `microsoft365`) when the canonical activation scope token is already available from config or a documented legacy header
  - illegal: env-override ownership rules that match cortex ids/names by substring to decide activation hold or specialist ownership when the same decision can be made from structured config metadata
  - illegal: substring-based runtime renaming of built-in agent display names (for example rewriting `Parietal Cortex` into some generic label) when the source-of-truth config already carries the intended user-facing name
  - reason: Viventium is an agent platform with user-managed agents and tools. The AI/config should stay the brain and decider; runtime code should only provide generic plumbing.
- **After push, restart the target LibreChat runtime** so it reloads from MongoDB. Environment-specific deployment commands belong in the private deployment runbooks, not the public source-of-truth doc.

#### Model Governance Rule (Launch-Ready Baseline)
- Out-of-the-box Viventium background agents must stay within the current launch-ready model families unless a newer documented evaluation replaces them:
  - `anthropic / claude-sonnet-4-5`
  - `anthropic / claude-opus-4-8`
  - `openAI / gpt-5.4`
- Do not add a model picker entry or built-in agent assignment for a model that the target provider
  inventory does not expose. As of the local May 6, 2026 inventory, `claude-sonnet-4-7` is not a
  supported Anthropic model for Viventium; use `claude-sonnet-4-5` or `claude-opus-4-8` until a
  verified provider catalog and model QA update replace this baseline.
- Foundation provider rule:
  - Groq is the current launch-ready primary for activation detection under the shipped 2-second
    Phase A budget
  - Anthropic Haiku-class activation is acceptable as a fallback or alternative only when the
    benchmark for the target environment proves it fits the chosen budget
  - at least one of `OpenAI` or `Anthropic` must be configured for main/background execution on install
  - do not treat `x_ai` alone as a sufficient built-in background-agent foundation for launch-ready installs
- Do **not** silently drift back to older defaults such as `gpt-4o` or `gpt-4o-mini` just because a pull or reset changed stored config.
- The same rule applies to secondary runtime paths such as deferred/background follow-up generation:
  - if agent metadata is incomplete, the fallback must still come from the approved launch-ready families above
  - do not hide stale-model drift inside "just a fallback" code paths
- Model selection must be **environment-proven**, not wishful:
  - choose from the allowed latest families above
  - prove the chosen family actually works in the target environment with real runs
  - if one preferred provider/model is unavailable, move to another allowed latest family rather than regressing to stale models
- Before changing live agent models:
  - capture a timestamped snapshot of the pulled agent bundle
  - back up the tracked source-of-truth file
  - use `--model-config-only --agent-ids=...` for surgical updates
  - treat raw tracked source-of-truth as the default sync input; runtime-aware rewrite is opt-in only via `--runtime-aware`
- Multi-source authority rule for background-agent model work:
  - the authoritative launch baseline is the combination of:
    - the public git-tracked source-of-truth bundle
    - the latest pulled live bundle for the target environment
    - the current governance/contract tests
  - private curated snapshots are evidence and backups, not a higher source of truth
  - if the private curated file drifts away from the public/live/tested baseline, snapshot it first
    and then reconcile it back to the proven baseline instead of treating the drift as a new truth
  - reason: private drift can silently reintroduce stale provider/model assignments even when the
    public bundle, live runtime, and QA docs already agree on the correct launch-ready roster
- Contract-test rule:
  - keep a release test that validates the shipped background-agent roster, the QA catalog,
    the coverage matrix, and the signoff manifest stay in sync
  - keep a release or API test that rejects stale built-in execution or activation families before
    they can quietly return
  - keep a cross-contract check between the Python release guard and the JS runtime-model helper so
    the documented launch-ready families cannot drift apart between source-of-truth validation and
    live Mongo rewrite logic
  - keep activation-provider benchmarks honest:
    - connected-account providers must be benchmarked through the real connected-account path
    - standalone eval scripts must bootstrap the same runtime dependencies the app uses
    - when one real user is reused, per-user activation cooldown state must not bleed across
      independent benchmark scenarios
  - reason: model drift and QA drift are both launch regressions, even when the app still boots
- Inventory hygiene rule:
  - local model-picker inventories and helper/title models must also stay aligned with the current approved families
  - example: Groq inventory/title defaults should prefer the documented Llama 4 activation family, not stale Llama 3.x leftovers
  - reason: stale picker defaults and title-model entries quietly reintroduce old-model drift even when the agent source-of-truth bundle is correct
- If a required provider session drops locally (for example OpenAI account disconnects in the desktop app), reconnect the provider and then re-run the real product QA flows. Do not "fix" the situation by silently downgrading shipped agent models to stale families such as `gpt-4o`.

#### Fail-Loud Source-Of-Truth Rule
- When an operator tool needs a default bundle or schedule input, prefer explicit current
  source-of-truth files or verified reviewed artifacts only.
- Illegal behavior:
  - silently falling back to a guessed `tmp/` export
  - silently falling back to a guessed legacy `scripts/` yaml
  - silently accepting a missing reviewed artifact and then reviving stale historical config
- Legal behavior:
  - explicit operator-provided path
  - tracked source-of-truth path
  - reviewed artifact path only when the required file truly exists
  - otherwise fail loudly with a clear operator error
- Reason:
  - silent fallback is a hidden configuration fork and causes exactly the kind of stale-model,
    stale-prompt, and stale-tooling regressions this project is trying to eliminate.

#### Operator Communication Rule
- When explaining an issue to the product owner or operator:
  - translate internal names (`executeCortex`, `loadCustomConfig`, validation flags, etc.) into
    plain product language first
  - always include:
    - what happened
    - why it matters to the operator
    - recommended action
    - important alternative options and consequences when there is a tradeoff
- Internal function names are developer evidence, not user-facing explanations.

### Deployment Env Parity (LibreChat Google/Gemini)
- LibreChat's Google endpoint **requires `GOOGLE_KEY`** (or a service account) to enable Gemini models
- **When using Gemini API keys, set `GOOGLE_KEY` to the same secret as `GEMINI_API_KEY`**
- LibreChat Agents (LangChain Google provider via `@librechat/agents`) **requires `GOOGLE_API_KEY`**
  - Set `GOOGLE_API_KEY` to the same secret as `GOOGLE_KEY`/`GEMINI_API_KEY` for full parity (main agents + follow-ups)
- Keep `GOOGLE_MODELS` aligned with enabled Gemini models to avoid broken UI entries

### Deployment Env Parity (Model Lists)
- **`<PROVIDER>_MODELS` env vars take absolute priority** over hard-coded model lists in LibreChat code
- When set, `getAnthropicModels()` / `getGoogleModels()` / etc. return `splitAndTrim(process.env.<PROVIDER>_MODELS)` directly
- **When adding new models** (e.g., `claude-sonnet-4-5`), update the env var on the container — no code changes or rebuild needed:
  ```bash
  update the target runtime env so `ANTHROPIC_MODELS` includes the new values
  ```
- **Also update the environment-specific deploy template** to keep the hosted config in sync with live state
- Key env vars: `ANTHROPIC_MODELS`, `GOOGLE_MODELS`, `XAI_MODELS`, `OPENAI_MODELS`
- Hosted environment-specific model rollout details live in the private deployment documentation.

---

## 🔧 Open Source Project Handling

### VIVENTIUM Modifications Tracking
- This project is based on multiple open source projects
- **All changes to open source projects must be tracked** with comments wrapping (must also include detailed explanation of the change and reason behind it and its purpose and feature so when we are applying these changes onto a new version of the original repositories, we would have full context and background there):
  ```
  VIVENTIUM START
  Description of change / feature 
  Explanation of the approach / the why 

  [your changes]
  VIVENTIUM END
  ```

  - Note: if the file is created by us and was not originally in the repository, the VIVENTIUM START comment should only be at the top / beginning of the file, and hennce if you create a new file in the projects, ensure top of the file has the full VIVENTIUM START and documentation text there. On the otherhand, if you see a file starts with VIVENTIUM comment at the top, then you must not put VIVENTIUM START / END commants in the middle of that file.

- **Prefer creating new files and packages** rather than modifying many places that will cause a lot of merge conflicts

### Upstream Changes Management (IF USER SPECIFICALLY REQUESTS UPDATING FROM UPSTREAM)
- **NEVER pull code changes directly** - upstream makes radical huge changes
- **Instead**: Pull their changes into a branch, test they work and run pure
- **Then**: Let the AI plan a list of all the VIVENTIUM START/END comments in our own code
- **One by one**: Bring all changes to the new codebase
- **NO GIT COMMANDS TO POP CHANGES** or some shit like that which can be very risky

---

## 🚫 Critical Don'ts

### Never:
- ❌ Recreate the wheel
- ❌ Make assumptions without evidence
- ❌ Deviate from existing components and patterns
- ❌ Pull upstream changes directly
- ❌ Use risky git commands (pop, force push, etc.)
- ❌ Hardcode values
- ❌ Overcomplicate solutions
- ❌ Skip studying the codebase first
- ❌ Modify many places in open source code (causes merge conflicts)

### Exception (Explicit User-Approved Private Secrets)
- If the user explicitly requests committing secrets for a private repo workflow, document the exception in `docs/requirements_and_learnings/04_Git_Private_Workflow.md` and confirm the repo is private.

### Always:
- ✅ Study open source projects well and their src code
- ✅ Use as much as what's already there
- ✅ Make minimal changes for beautifully simple results
- ✅ Track VIVENTIUM modifications with comments
- ✅ Create new files/packages for major changes
- ✅ Test thoroughly before implementation
- ✅ Document your approach


---

## 📋 Testing Requirements

### When Developing New Features:
- Create unit tests for the new feature or module
- Run tests yourself and observe the results
- If tests fail, analyze the failure and make necessary adjustments
- **Make sure test files are in an organized folder and not all over the place!**
- Update or create the owning `qa/<feature>/README.md` and `qa/<feature>/cases.md`
- Add dated QA run evidence under the feature QA folder before claiming user-facing completion
- Follow existing test organization patterns:
  - Backend tests: `viventium_v0_3_py/viventium_v1/tests/`
  - Unit tests: `viventium_v0_3_py/viventium_v1/tests/unit/`
  - Integration tests: `viventium_v0_3_py/viventium_v1/tests/integration/`

---

## 🔄 Suggested Approach for Fixes

### Implementation Workflow:
1. **Create comprehensive analysis document** (e.g., `docs/VIVENTIUM_ISSUES_ANALYSIS.md`)
2. **Identify root causes** using first principles thinking
3. **Prioritize issues** by severity (Critical → High → Medium → Low)
4. **Explore, test, validate** fixes before implementation
5. **Leverage existing patterns** - use existing functions/components rather than recreating
6. **Implement minimal changes** that solve the problem elegantly
7. **Test thoroughly** before considering complete
8. **For service-level/performance issues, capture before/after runtime evidence** (logs + timings + active revision/image IDs) in the relevant `docs/requirements_and_learnings/` feature document so future sessions do not need to rediscover the same facts


---

## 📝 Summary Checklist

Before making any change, ensure:
- [ ] Read relevant documentation for both `viventium_v0_3_py/viventium_v1` and `viventium_v0_4`
- [ ] Studied existing codebase, patterns, and components
- [ ] Identified existing functionality that can be reused
- [ ] Understood the root cause (if fixing an issue)
- [ ] Classified issue as `runtime-generated` vs `model-generated`
- [ ] Documented trigger -> transformation -> user-visible output with file:line references
- [ ] Confirmed prompt/config edits are used only for model-generated issues
- [ ] Reused existing context signals before adding new plumbing (fields/routes/config)
- [ ] Checked behavior impact across Telegram, Scheduler, Web UI, and Voice
- [ ] Updated the relevant `qa/<feature>/README.md` and `qa/<feature>/cases.md`
- [ ] Promoted any escaped/user-reported defect into a synthetic regression case
- [ ] Ran impacted existing QA cases, not only the new happy path
- [ ] Tied feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap
- [ ] Inspected full-view evidence: code, docs/nested docs, scripts/harnesses, logs, DB/state or
      persistence, generated/shipped artifacts, and the real user path for every affected surface
- [ ] Marked any unrun required real user path as BLOCKED/PARTIAL instead of claiming completion
- [ ] For user-visible browser behavior, completed the real-browser loop: visible UI, expanded/detail
      state, persistence where relevant, backend/log/DB confirmation, and non-contradictory final wording
- [ ] Confirmed logs, DB rows, API responses, source inspection, model completions, or unit tests were
      not used as substitutes for the required user-visible QA path
- [ ] Planned minimal changes that leverage existing code
- [ ] Wrapped VIVENTIUM modifications with START/END comments
- [ ] Created/updated tests for new features
- [ ] Documented approach in `docs/` folder
- [ ] Kept personal/private files out of the product-facing repo and moved them to the private companion repo when appropriate
- [ ] Kept deployment-only files out of the product-facing repo and moved them to the enterprise deployment repo when appropriate
- [ ] Preserved `~/Library/Application Support/Viventium/config.yaml` as the canonical end-user config source
- [ ] For service-level fixes, documented before/after telemetry and deployed revision/image IDs
- [ ] Ensured separation of concerns
- [ ] Avoided hardcoding values
- [ ] Made code dynamic and extensible

---

**Remember**: These principles exist to maintain code quality, prevent technical debt, and ensure the project remains maintainable. Follow them consistently in every interaction.
