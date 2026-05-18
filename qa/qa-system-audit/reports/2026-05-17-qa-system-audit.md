<!-- qa-evidence-exempt: legacy or audit-style report; supersede with the standard run-report template on next rerun. -->
# QA System Audit - 2026-05-17

## Summary

Viventium has the right QA philosophy in place: `qa/README.md`, `01_Key_Principles.md`, `AGENTS.md`,
templates, release tests, and several mature feature QA folders already encode the core rule that
user-facing behavior needs user-grade evidence, not just logs or unit tests.

It is not yet perfectly organized or complete. The current QA system is strong in principle but uneven
in execution: feature traceability is incomplete, many QA folders are still legacy, release tests are
not consistently tied to cases, several requirement docs do not link to QA owners, and some local QA
records live in ignored paths that can make a local checkout look healthier than a fresh clone.

The path of least resistance is not a heavyweight process. The fix is a thin traceability spine:

`feature -> requirements doc -> QA folder -> case IDs -> automated tests -> user-grade evidence -> latest result -> known gaps`

That spine should be enforced by one small script or release test and kept visible in
`docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md` or a dedicated QA traceability index.

## Scope and Method

### Sources inspected

- Agent instructions: `AGENTS.md`, `CLAUDE.md`.
- QA principles: `qa/README.md`, `qa/_templates/`, `qa/_migration.md`,
  `docs/requirements_and_learnings/01_Key_Principles.md`,
  `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`.
- QA records: top-level `qa/<feature>/` folders, case catalogs, reports, ignored result folders.
- Automated checks: `tests/release/`.
- Prior audit output: `qa/documentation-implementation-audit/`.

### Checks run

```bash
uv run --with pytest --with pyyaml python -m pytest \
  tests/release/test_qa_operating_contract.py -q
```

Result: **5 passed**.

Other evidence gathered:

- QA folder inventory: **41** top-level QA feature areas; **29** are missing `README.md` or `cases.md`,
  and **30** are missing at least one target `README.md` / `cases.md` / `reports/` element.
- Requirement docs inventory: **28** docs under `docs/requirements_and_learnings/`, many with no
  direct `qa/` link.
- Release test inventory: **48** release test files; only two literally name QA case IDs, and only
  three reference any `qa/` path.
- `qa/results/README.md` is required by `tests/release/test_qa_operating_contract.py`, but `qa/results/`
  was ignored by `.gitignore`, so the required file was local-only unless force-tracked. This audit
  adjusted `.gitignore` so the public README can be tracked while timestamped raw result folders stay
  ignored.
- Ignored `qa/results/` files contain local absolute paths in historical local result summaries; they
  are ignored, but the public/private rule should make their status explicit.

## What Is Good

- `qa/README.md` is a real operating contract, not a placeholder. It names folder shape, required case
  metadata, user-grade QA, regression selection, public-safety rules, and external evaluation practice.
- `01_Key_Principles.md` has a production QA discipline section that matches the QA README.
- `AGENTS.md` already tells agents to use `qa/` as the acceptance/evidence source of truth, update
  cases, run user-grade QA, save public-safe results, and avoid backend-only signoff.
- `tests/release/test_qa_operating_contract.py` prevents the most important substitution failure:
  logs, DB rows, API responses, source inspection, model completions, and unit tests are supporting
  evidence, not replacements for visible/detail/persistence/wording checks.
- Some feature folders are genuinely strong:
  - `qa/background_agents/` has cases, browser harnesses, coverage matrix, eval prompt bank, and
    several real browser evidence reports.
  - `qa/prompt-workbench/` has a rich case catalog and recent real Chrome/Playwright-style UX reports.
  - `qa/meeting-transcript-memory/` has cases, eval harnesses, live-browser reports, and evidence
    boundaries.
  - `qa/stable-dev-runtime/`, `qa/self-healing/`, `qa/feature-request/`, and `qa/bug-report/` have
    clear cases tied to recent local implementation QA.
  - `qa/release-readiness/` has a concise release gate and case IDs.

## Major Findings

### `QASYS-002` - Feature-to-QA traceability is incomplete

Severity: **P1**

The project has many feature requirements docs, but the link from each feature doc to QA ownership is
inconsistent. Some features have excellent QA, some are covered indirectly by broad runtime folders,
and some have no obvious QA owner.

Examples:

- `02_Background_Agents.md` maps well to `qa/background_agents/`.
- `49_Prompt_Architecture_and_Token_Efficiency.md` maps to `qa/prompt-architecture/` and
  `qa/prompt-workbench/`.
- `03_Telegram_Bridge.md` has many related QA folders, but the mapping is fragmented across runtime,
  media, detached API, local bot API, voice replies, settings latency, and web-search Telegram.
- `06_Voice_Calls.md`, `14_Voice_Latency_and_Memory_RCA.md`, and `34_Voice_Chat_LLM_Override.md`
  span multiple QA folders, but there is no single voice coverage index that says which cases cover
  which requirement.
- `08_Citation_Rendering.md`, `09_Agent_Streaming_Usage.md`, `16_Branding_and_Assets.md`,
  `21_No_Response_Feature.md`, and `29_Red_Team_Cortex.md` do not have clearly direct QA ownership.
- `07_MCPs.md` is broad, but `qa/mcp-oauth/` is a single incident-style file without the standard
  README/cases/reports shape.

Fix:

1. Make `45_Runtime_Feature_QA_Map.md` the complete traceability index, or create
   `qa/feature-traceability.md` and link it from `45`.
2. For every requirement doc, add a small **QA Ownership** section:
   - owning `qa/<feature>/`
   - required case IDs
   - automated release tests
   - user-grade surface
   - latest result and known gaps
3. Keep detailed cases in `qa/<feature>/cases.md`, not duplicated in the requirement doc.

Why:

- It keeps the system simple while making the answer to "what proves this works?" obvious.

### `QASYS-003` - Folder shape is still legacy-heavy

Severity: **P1**

`qa/_migration.md` honestly tracks many legacy gaps, but the migration has not been completed. The
current inventory found many folders missing `cases.md`, `reports/`, or both.

Examples of folders still missing standard structure:

- Installer/config/continuity: `installer-resilience`, `installer-piped-bootstrap`,
  `installer-wait-taglines`, `config-compiler-memory`, `config-compiler-xai-models`,
  `continuity-ops`, `conversation-recall-rag`, `memory-continuity`, `memory-hardening`.
- Telegram/voice: `telegram-detached-api-stability`, `telegram-document-attachments`,
  `telegram-local-bot-api`, `telegram-media-downloads`, `telegram-media-prereqs`,
  `telegram-settings-latency`, `telegram-voice-replies`, `voice-call-hardening`,
  `voice-streaming-first`, `voice-turn-taking`, `web-search-telegram`.
- GlassHive: `glasshive_host_workers`, `glasshive_steer`, `glasshive_watch_desktop`,
  `glasshive_workspaces`.
- Prompt architecture: `qa/prompt-architecture/` has reports/evals but no `cases.md`.

Fix:

1. Do not mass-convert everything in one noisy sweep.
2. For P1/P2 active surfaces, add a thin `cases.md` first with only the existing known cases and known
   gaps.
3. Move future dated reports into `reports/`.
4. Keep `qa/_migration.md` as a burn-down list with status, not just a static backlog.

Why:

- This avoids stupid overcomplication while removing the biggest developer-friction problem: nobody
  should have to guess where to put evidence or how to rerun a case.

### `QASYS-004` - The full-view evidence rule exists, but is not consistently recorded per feature

Severity: **P2**

The hard rule is present in the central QA docs:

`real browser prompt/action -> visible UI outcome -> expanded/detail states -> refresh or persistence check -> backend/log/DB confirmation -> final wording check`

The full-view checklist already exists in `qa/_templates/run-report.md`. The gap is that dated feature
reports do not consistently use those headings. Many feature folders also do not have case catalogs
that force every relevant feature to record:

- source/code inspection
- nested repo/pin/artifact inspection when relevant
- generated config/runtime artifact inspection
- visible UX/browser/computer/Telegram/voice/CLI outcome
- expanded/detail state
- persistence/reload
- logs and DB confirmation
- public-safety review
- final user-facing wording check

Fix:

1. Keep `qa/_templates/run-report.md` as the canonical checklist.
2. Reference the template from every active feature README.
3. Add a small release test that checks new/updated `qa/*/reports/*.md` files include required
   headings such as visible outcome, persistence/reload, backend/log/DB confirmation, and final
   wording check, with an explicit exemption marker for non-runtime audit reports.
4. Add specialized evidence checklist bullets to feature `cases.md` only when the feature needs
   surface-specific nuance.
5. Use the real user loop appropriate to the surface:
   - browser: Playwright or equivalent
   - desktop/computer: Computer Use or native helper QA
   - Telegram: real bot send/receive plus delivery ledger
   - voice: actual call/playground plus transcript/latency
   - installer/CLI: public command plus installed/running artifact
   - MCP/tool: model-visible tool contract plus auth/result/failure copy

Why:

- The rule is powerful, but only if reports force the evidence into the same shape every time.

### `QASYS-005` - Automated tests are not consistently linked to cases/results

Severity: **P2**

Release tests are useful, but they mostly live as technical checks rather than named QA cases. A grep
showed only a subset of `tests/release/` files reference QA docs or case IDs.

Good examples:

- `tests/release/test_prompt_workbench.py` asserts Prompt Workbench QA coverage includes `PW-004`.
- `qa/release-readiness/cases.md` links `REL-004` to a browser-visible background-agent harness.
- `qa/background_agents/cases.md` links ACT cases to visible browser QA expectations.

Gaps:

- Almost no release tests protect product behavior while naming the requirement doc, QA case ID, or
  owning QA folder. Claude's second-opinion pass found only two literal case-ID references and only
  three release tests with any `qa/` path reference.
- Many cases list automation as prose or historical result rather than a stable command.
- A failing release test does not always tell a maintainer which user-facing contract it protects.

Fix:

1. Add a lightweight convention, not a framework:
   - top of each release test file: `QA_OWNER = "qa/<feature>/cases.md"` or a short comment
   - specific high-value tests name a case ID in test name/comment/docstring
2. Add a release test that verifies every `tests/release/test_*.py` has either:
   - a `QA_OWNER` marker, or
   - a documented exception for low-level helper-only tests.
3. Update case catalogs to include exact command names for automation-backed cases.

Why:

- This gives maintainers context without turning tests into paperwork.

### `QASYS-006` - Agent instructions are partly stale and point to missing QA paths

Severity: **P1**

`AGENTS.md`, `01_Key_Principles.md`, and `qa/README.md` carry the key QA principles. `CLAUDE.md`
is lean and useful, but its quick doc map references several missing QA files, including:

- `qa/launch_readiness.md`
- `qa/result_artifact_standard.md`
- `qa/web_app_core_surface.md`
- `qa/voice_playground_and_remote_calls.md`
- `qa/mcp_oauth_and_productivity_integrations.md`
- `qa/telegram_end_to_end.md`

It also references a missing `docs/requirements_and_learnings/35_OAuth_Subscription_Auth.md`.

Fix:

1. Replace stale `CLAUDE.md` quick-map entries with real folders:
   - `qa/release-readiness/README.md`
   - `qa/modern-playground-voice/README.md`
   - `qa/telegram-runtime/README.md`
   - `qa/mcp-oauth/` after that folder gets a README/cases file
2. Add one shared sentence to agent instructions rather than duplicating long checklists:
   - "For user-visible changes, follow `qa/README.md` full-view evidence: use the feature like a user
     and compare visible UX with code, logs, DB, generated artifacts, docs, nested repos, and
     persistence before claiming done."
3. Extend `test_qa_operating_contract.py` or a docs link test to include `CLAUDE.md`.

Why:

- Agents should route to the living QA contract, not stale per-surface docs that no longer exist.

### `QASYS-007` - Some QA records are local-only or ignored while tests expect them

Severity: **P0 / clean-clone release blocker**

`tests/release/test_qa_operating_contract.py` requires `qa/results/README.md`, but `.gitignore`
ignored `qa/results/`. In this checkout, the file existed locally and the test passed; in a clean
clone, that file would be absent unless force-tracked.

Additional concern:

- Historical ignored `qa/results/` markdown files include local absolute paths. They are ignored, so
  they are not public artifacts by default, but they should not be treated as publishable records.

Fix:

1. Treat `qa/results/README.md` as a public contract file.
2. Keep timestamped `qa/results/<suite>/<timestamp>/` outputs ignored unless intentionally promoted
   through a sanitized report.
3. This audit adjusted `.gitignore` to allow `qa/results/README.md` while keeping result subfolders
   ignored.
4. Add a test that fails when a required QA contract file is ignored by git.

Why:

- QA that passes only because of ignored local files is the exact opposite of clean-clone confidence.

### `QASYS-002B` - `45_Runtime_Feature_QA_Map.md` is the main traceability gap

Severity: **P1**

`45_Runtime_Feature_QA_Map.md` maps core runtime surfaces, but it is not a full feature traceability
matrix. It omits or underrepresents:

- Voice/LiveKit and modern voice playground coverage.
- Citation rendering.
- Agent streaming usage.
- General MCPs and OAuth scope coverage.
- Web search beyond Telegram.
- Scheduling cortex as a first-class folder.
- Branding/assets.
- No-response feature.
- Red Team cortex as a feature requirement.
- Power Agents Beta / sandbox sidecars.
- LibreChat config alignment.
- Code interpreter.
- Prompt-registry sync resolver.

Fix:

1. Expand `45` into a concise matrix:
   `Feature | Requirement doc | QA owner | Cases | Release tests | User surface | Latest status`.
2. Keep detailed behavior out of `45`; link to the owning docs and cases.
3. Add "no QA owner yet" explicitly where true so gaps are visible.

Why:

- One complete map prevents future agents from creating duplicate QA folders or skipping orphaned
  requirements.

Note: this is the same underlying issue as `QASYS-002`, not a separate fix stream. It is kept here as
the concrete owner/path where the traceability repair should land.

## Feature-by-Feature QA Traceability Snapshot

| Feature area | Requirement docs | Current QA owner | Current status | Main fix |
| --- | --- | --- | --- | --- |
| Background agents / cortices | `02`, `29`, parts of `21`, `45` | `qa/background_agents/` | Strong QA structure, but current governance tests fail and reports are partly flat | Fix current P0s, keep ACT cases, move new reports under `reports/` |
| Telegram bridge | `03`, `25` | Multiple `qa/telegram-*` folders | Fragmented; many folders legacy; Telegram Codex privacy gate not documented enough | Create one Telegram coverage index and standardize active folders |
| Voice calls / LiveKit / playground | `06`, `14`, `34`, `47` | `qa/modern-playground-voice/`, `qa/voice-*` | Some strong cases, many partial/legacy reports; no single voice matrix | Add voice coverage matrix and migrate voice folders to cases/reports |
| MCPs / connected accounts | `07`, parts of `39`, `45` | `qa/mcp-oauth/` plus scattered tests | Understructured; OAuth scopes and MCP defaults lack clear QA case ownership | Add `qa/mcp-oauth/README.md`, cases, scope/default release tests |
| Citation rendering | `08` | none obvious | Orphaned | Add QA owner/cases or fold into web/chat rendering QA |
| Agent streaming usage | `09` | none obvious | Orphaned | Add streaming usage case and release test owner |
| Web search | `10` | `qa/web-search-telegram/` | Telegram-specific only; general web/browser search QA not clear | Add general web-search QA owner and config/schema tests |
| Scheduling cortex | `11`, `25` | background-agent reports and `test_scheduling_mcp_supervision.py` | Indirect ownership; no scheduling QA folder | Add `qa/scheduling-cortex/` or explicit background_agents coverage section |
| Branding/assets | `16` | none obvious | Orphaned | Add visual/assets QA owner and screenshot/public-safety expectations |
| Power Agents Beta | `18` | none obvious | Present but paused/unclear | Mark paused or add provenance/QA owner |
| Memory / recall / transcripts | `20`, `32`, parts of `06` | `qa/memory-*`, `qa/conversation-recall-rag/`, `qa/meeting-transcript-memory/` | Strong pockets, but many legacy folders lack cases/reports | Standardize memory folders and one continuity coverage map |
| No Response `{NTA}` | `21` | scattered background/voice memory cases | Indirect ownership | Add explicit case IDs where `{NTA}` behavior is protected |
| LibreChat config alignment | `37`, `39` | release tests, config QA folders | Tests exist, QA traceability uneven | Link tests to config QA cases |
| Public productization/release | `38`, `40` | `qa/release-readiness/`, `qa/privacy_publish_audit.md` | Good but partly historical | Keep release-readiness current with known current blockers |
| Installer/config compiler | `39`, `50` | installer/config/stable-dev folders | Broad coverage, many legacy folders | Add case catalogs to installer/config legacy folders |
| Remote access | `47` | `qa/remote-access/` | README/report only, no cases | Add cases and current supported-entrypoint matrix |
| GlassHive runtime/workflows | `48`, `51` | `qa/glasshive_*`, workflows folders | Workflow folders good; GlassHive runtime folders lack cases/reports | Standardize GlassHive runtime QA and CLI signature tests |
| Prompt architecture/workbench | `49` | `qa/prompt-architecture/`, `qa/prompt-workbench/` | Workbench strong; prompt architecture lacks cases; current prompt registry fails | Add prompt-architecture cases and fix registry failure |
| Stable dev runtime | `50` | `qa/stable-dev-runtime/` | Good structure and cases | Keep linked from maps and helper QA |
| Code interpreter | config/compiler docs only | none obvious | Underdocumented shipped integration | Add requirement doc/QA owner or explicit vendored-component status |

## Minimal Fix Plan

### Phase 1 - Make the QA spine obvious

1. Finish the `qa/results/README.md` fix by tracking the now-unignored README.
2. Update `45_Runtime_Feature_QA_Map.md` into the complete feature traceability matrix.
3. Add missing `QA Ownership` sections to requirement docs only when the central matrix is not enough.
4. Fix stale `CLAUDE.md` QA paths by routing to real QA folders and `qa/README.md`.

### Phase 2 - Enforce lightly

1. Add `scripts/viventium/qa_traceability.py` or a release test that checks:
   - every requirement doc has a QA owner or explicit "no QA owner yet"
   - every top-level QA folder has `README.md` and `cases.md`, or is listed in `_migration.md`
   - every release test file has `QA_OWNER` or an explicit low-level exception
   - required QA contract files are not ignored by git
2. Add a docs link/path check for agent instructions and QA docs.

### Phase 3 - Migrate active gaps without ceremony

Prioritize active user-facing and release-blocking surfaces:

1. background agents / prompt registry
2. Telegram runtime and Telegram Codex
3. voice/LiveKit/modern playground
4. MCP OAuth and connected-account scopes
5. installer/config/stable runtime
6. GlassHive runtime/workflows
7. orphaned feature docs such as citations, streaming usage, branding, no-response, red-team

Each migration should add only:

- `cases.md`
- a current status section in `README.md`
- a dated report for the latest meaningful run
- links to existing automation and known gaps

## Recommended Script / Test Contract

A simple `qa_traceability` check should output a table and fail only on high-signal issues:

- missing QA owner for a requirement doc
- missing `cases.md` for a non-migrated QA folder
- release test file with no `QA_OWNER` marker
- required QA contract file ignored by git
- agent instruction link pointing to a missing local path
- feature report claiming pass with no user-grade surface for a browser/Telegram/voice/user-visible flow
- stale migration backlog rows whose folders are already structurally complete
- hard-coded `qa/...` paths in tests or instructions that no longer exist
- stale `Last Run` dates for active cases, at first as a warning

Do not build a heavy test-management system. Markdown plus one checker is enough.

## Public-Safety Review

- [x] No secrets, passwords, cookies, token values, private chats, screenshots, raw logs, or DB rows.
- [x] No local absolute paths reproduced from ignored result files.
- [x] No private account identifiers, message IDs, chat IDs, session IDs, or raw provider IDs.
- [x] Ignored/local artifact concerns are summarized without copying raw content.
