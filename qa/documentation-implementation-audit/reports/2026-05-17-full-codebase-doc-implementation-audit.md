<!-- qa-evidence-exempt: legacy or audit-style report; supersede with the standard run-report template on next rerun. -->
# Full Codebase Documentation / Implementation Audit - 2026-05-17

## Status As Of 2026-05-17 Final QA-System Repair

This report is the pre-repair audit that found the background-agent governance and prompt-registry
source-of-truth failures. Those specific release-test failures were repaired later on 2026-05-17 and
are superseded by `qa/qa-system-audit/reports/2026-05-17-local-runtime-and-qa-repair.md` and
`qa/qa-system-audit/reports/2026-05-17-claude-final-review-summary.md`, which record `54 passed` for
the targeted source-of-truth suites and `587 passed, 3 skipped` for the full release suite in the
current local checkout. The nested LibreChat commit/pin boundary still must be handled before a
public PR or release claim.

## Summary

This audit traced the public Viventium checkout across the parent repo, active nested component repos,
source-of-truth docs, release tests, QA folders, selected runtime metadata, and ignored local artifact
boundaries. It found substantial drift between high-level docs, config schema/examples, release tests,
and the current LibreChat source-of-truth bundle. The highest-risk issue is that the background-agent
governance and prompt-registry release suites are failing against the current source tree.

No product code was changed in this pass. The output is this public-safe QA report and the reusable
cases in `qa/documentation-implementation-audit/`.

## Scope and Method

### Sources inspected

- Parent repo docs, scripts, tests, QA folders, config schema/examples, installer/runtime scripts, and
  macOS helper source/build references.
- Nested repos under `viventium_v0_4/`: LibreChat, GlassHive, MCPs, modern/legacy playgrounds,
  LiveKit/voice pieces, OpenClaw/Skyvern, and supporting component repos.
- Runtime-facing docs under `viventium_v0_4/docs/` and feature truth under
  `docs/requirements_and_learnings/`.
- Safe runtime evidence only: ignored-log presence, selected log metadata, SQLite schema/table counts,
  and git status/pin state. Raw log lines, DB rows, account identifiers, message IDs, tokens, and
  local runtime paths were not exported.

### Checks run

```bash
uv run --with pytest --with pyyaml python -m pytest \
  tests/release/test_productivity_activation_source_of_truth.py \
  tests/release/test_background_agent_governance_contract.py -q
```

Result: **13 failed, 20 passed**.

```bash
uv run --with pytest --with pyyaml python -m pytest \
  tests/release/test_prompt_registry.py -q
```

Result: **1 failed, 20 passed**. This additional failing suite was found by the Claude second-opinion
pass and reproduced by Codex.

```bash
uv run --with pytest --with pyyaml python -m pytest \
  tests/release/test_config_compiler.py \
  tests/release/test_no_runtime_nlu.py \
  tests/release/test_qa_operating_contract.py \
  tests/release/test_project_boundary_contamination.py -q
```

Result: **102 passed**.

```bash
uv run --with pytest --with pyyaml python -m pytest \
  tests/release/test_qa_operating_contract.py -q
```

Result after adding this audit folder: **5 passed**.

Other evidence gathered:

- Local markdown link scan, excluding ignored/private/runtime folders: **32 missing local markdown
  targets** using strict markdown-link syntax. Claude's second pass found this is conservative:
  backtick-cited file paths are common in this repo and expose many more missing references.
- `components.lock.json` comparison against nested component HEADs: listed component pins match local
  HEADs, but several nested repos are dirty and/or behind their configured origins.
- Parent public tree inventory: docs, scripts, tests, QA folders, active app surfaces, and component
  boundaries were sampled and mapped.

## Product Parts and Expected Behaviors

| Part | Primary owners | Expected behavior / product contract | Current doc state |
| --- | --- | --- | --- |
| Public installer and CLI | `install.sh`, `bin/viventium`, `scripts/viventium/` | Install, configure, compile, doctor, bootstrap, upgrade, start/stop, snapshot/restore, reset, workflow commands, helper install, dev-runtime/dev-env | Deep docs exist, but high-level architecture/system docs are stale/incomplete |
| Config compiler and wizard | `config.schema.yaml`, examples, `scripts/viventium/config_compiler.py`, `scripts/viventium/wizard.py` | Canonical App Support config compiles into runtime files; schema/examples/docs agree | Schema/examples/docs drift from compiler and tests |
| macOS helper | `apps/macos/ViventiumHelper/`, prebuilt helper artifacts | User-facing installed runtime entrypoint/status helper, with source/prebuilt hash discipline | Documented in installer docs; not well represented in systems map |
| LibreChat fork | `viventium_v0_4/LibreChat/` | Web UI/API, agent orchestration, MCP loading, background cards, memory/recall, source-of-truth prompts/agents, voice route wiring | Rich docs exist, but active YAML currently fails governance tests |
| Agent source of truth | `viventium_v0_4/LibreChat/viventium/source_of_truth/` | Prompts, tool contracts, model routing, activation fallbacks, cards, and prompt refs own agent behavior | Several documented/tested contracts are not satisfied by current YAML |
| Prompt Workbench | `viventium_v0_4/prompt-workbench/`, `qa/prompt-workbench/` | Local prompt drafting/edit/eval/sync review surface with protected-source drift checks | Implemented and QA'd, but not fully reflected in runtime implementation index |
| Voice gateway and voice playground | `viventium_v0_4/voice-gateway/`, `agent-starter-react/`, `livekit/`, `cartesia-voice-agent/` | Voice calls, STT/TTS providers, turn-taking, listen-only/wing behaviors, user experience latency | Voice docs are broad; source-of-truth voice model route currently conflicts with release test |
| Telegram Viventium | `viventium_v0_4/telegram-viventium/` | Telegram bridge, local Bot API, media download, STT inheritance, detached API stability | Feature docs/QA exist; README links point to missing historical docs |
| Telegram Codex | `viventium_v0_4/telegram-codex/` | Codex-oriented Telegram bridge/runtime | Present but weakly covered by high-level architecture docs |
| GlassHive | `viventium_v0_4/GlassHive/`, `scripts/viventium/workflows/` | Workflow runtime, host/native workers, callbacks, self-heal, feature request, bug report command surfaces | Requirements doc exists; systems map and implementation index underrepresent it |
| MCP components | Google Workspace, MS365, YouTube transcript, scheduling, openclaw bridge, code interpreter | Connected tool availability through configured source-of-truth, OAuth, and compiled runtime config | Individual docs exist, but high-level cross-component map is incomplete |
| Remote access | Cloudflare/Tailscale/NetBird/custom-domain docs and CLI hooks | Supported external access paths with public/private boundary clarity | Requirement doc exists; not prominent in architecture/systems index |
| Memory/recall/continuity | memory hardening, recall/RAG, snapshot/restore, continuity audit | Chat history, saved memory, recall corpus, schedules, auth/provider state, restore/backup remain distinct | Good deep docs/QA exist; defaults and schema still conflict in places |
| Public/private boundary | docs, `.gitignore`, release tests, QA contract | No secrets, personal data, runtime state, local paths, or private artifacts in public exports | Guardrails are strong; ignored local artifacts exist and must stay out of exports |
| QA/release harness | `tests/release/`, `qa/` | Reusable synthetic cases and dated reports prove public release surfaces | Strong, but coverage is uneven across feature docs |

## Findings

### `DOCIMPL-004` - Background-agent governance is currently failing

Severity: **P0 / release blocker**

The background-agent source-of-truth release checks fail against the current LibreChat source tree.
This is not a theoretical documentation issue: it is the repository's own governance contract saying
the current source does not match the documented/tested behavior.

Observed mismatches include:

- MS365 and Google background activation configs are missing the expected `activation.fallbacks`
  chain.
- Current agent execution model values differ from the documented/tested launch baseline.
- Deep Research and Support agent tool contracts do not include expected `web_search` availability.
- Confirmation, support, red-team, and main-agent instruction guard phrases are missing.
- Main-agent voice route in source-of-truth YAML uses a model that does not match the expected
  release contract.
- Activation decision subject is inline text where tests expect the prompt registry reference.
- Runtime-card guardrail language expected by tests is absent.

Primary evidence:

- Failing command:
  `tests/release/test_productivity_activation_source_of_truth.py`
  and `tests/release/test_background_agent_governance_contract.py`.
- Source under test:
  `viventium_v0_4/LibreChat/viventium/source_of_truth/local.viventium-agents.yaml`.

Required reconciliation:

1. Decide whether the docs/tests or the current YAML express the intended product truth.
2. If YAML is correct, update the requirement docs, QA map, and tests intentionally.
3. If docs/tests are correct, repair the source-of-truth YAML and any generated/live sync artifacts.
4. Re-run the failing release suites and save a dated report under the owning QA folder.

### `DOCIMPL-004B` - Prompt registry sync resolver drops included guardrails

Severity: **P0 / release blocker**

Claude's second-opinion pass found, and Codex reproduced, a third failing release suite:
`tests/release/test_prompt_registry.py::test_js_sync_resolves_full_source_agent_yaml_prompt_refs`.
The resolved main-agent instructions do not contain the expected runtime-card guardrail text.

This is related to the background-agent governance failures but has a different ownership path:

- The source prompt markdown references an included runtime-card guardrail block.
- The included block contains the expected guardrail language.
- The JS sync resolver does not preserve that `includes:` frontmatter content into resolved
  main-agent instructions.

This means fixing only the YAML or only the prompt text can leave the live-sync path able to recreate
the drift. The sync resolver and source-of-truth YAML/prompt bundle need to be reconciled together.

Required reconciliation:

1. Fix the prompt resolver so included prompt fragments are present in resolved agent output.
2. Keep the background-agent YAML/governance fix in the same release slice.
3. Re-run `test_prompt_registry.py` and the two background-agent governance suites together.

### `DOCIMPL-003` - Config schema, examples, wizard, compiler, and docs are misaligned

Severity: **P1**

The compiler implements fields that are missing from the schema, while docs/examples contain
conflicting defaults and descriptions.

Specific gaps:

- `runtime.dev_env` is implemented by `scripts/viventium/config_compiler.py` and documented in
  `config.full.example.yaml` / installer docs, but is absent from `config.schema.yaml`.
- `runtime.memory_hardening.transcripts.ignore_globs` is implemented and documented, but absent from
  `config.schema.yaml`.
- `integrations.web_search` supports provider/API fields in compiler and wizard code, but the schema
  only exposes `enabled`, and the full example does not include the complete block.
- Telegram STT schema description says omitted Telegram STT defaults to OpenAI when global voice STT
  is local, while the requirement docs and compiler expect Telegram to inherit the global local STT
  provider.
- `config.full.example.yaml` says new installs should ship `default_conversation_recall: true`, while
  the minimal example, wizard default, and tests still default it to `false`.

Required reconciliation:

1. Pick one intended default for conversation recall and update docs/examples/wizard/tests together.
2. Expand `config.schema.yaml` to match implemented public fields, or remove undocumented compiler
   fields if they are not meant to be user-facing.
3. Correct Telegram STT inheritance wording in schema docs.
4. Add regression tests that compare schema/example keys against compiler-supported keys.

### `DOCIMPL-002` - Public markdown docs have broken local references

Severity: **P1**

The local markdown link scan found 32 missing local targets after excluding ignored/private/runtime
folders and checking strict `[text](path)` markdown links. Claude's second pass confirmed this is an
undercount because the repo frequently cites files in backticks. High-impact examples:

- Root `README.md` references `.env.example`, but the file is not present.
- `docs/README.md` references missing `docs/DOC_SOURCE_MAP.md` and `docs/archive/`.
- `viventium_v0_4/docs/README.md` references missing status/feedback docs and several missing
  historical deep-dive docs.
- `viventium_v0_4/telegram-viventium/README.md` references several missing Telegram docs.
- `viventium_v0_4/LibreChat/viventium/services/librecodeinterpreter/README.md` references missing
  service docs.
- Always-loaded operator context also points at several missing QA acceptance-contract files and a
  missing OAuth/subscription requirements doc.

Required reconciliation:

1. Restore intended docs, move them to an explicit archive/private boundary, or remove/update links.
2. Mark historical/private-only references as such instead of presenting them as public links.
3. Add a markdown link check to release-readiness if public docs are in scope.
4. Treat backtick-cited file paths as first-class references after the high-impact links are repaired.

### `DOCIMPL-001` - High-level architecture and systems docs are stale

Severity: **P1**

The deep requirement docs are much stronger than the high-level architecture/systems docs. New users
following the high-level map get an incomplete and partly outdated picture.

Examples:

- `docs/02_ARCHITECTURE_OVERVIEW.md` and `docs/03_SYSTEMS_MAP.md` still describe v0.3 topology even
  though setup docs say v0.3 is not part of the target public release surface.
- `docs/03_SYSTEMS_MAP.md` lists only a thin v0.4 directory map and omits or underplays active
  surfaces such as GlassHive, Prompt Workbench, Telegram Codex, workflow commands, macOS helper,
  remote access, continuity operations, and openclaw/power-agent sidecars.
- `docs/03_SYSTEMS_MAP.md` still frames shared `.env` / `.env.local` secrets as central, conflicting
  with newer canonical App Support config and generated-runtime-file boundaries.
- `viventium_v0_4/docs/IMPLEMENTATION_INDEX.md` covers only a subset of runtime implementations.

Required reconciliation:

1. Rewrite the high-level architecture/system maps around v0.4 public product surfaces.
2. Move v0.3 material to a clearly marked historical section or archive.
3. Align shared-resource language with the canonical config/public-private-boundary docs.
4. Expand the implementation index to include installer/compiler, helper, GlassHive/workflows,
   Prompt Workbench, Telegram Codex, remote access, recall hardening, and QA owners.

### `DOCIMPL-005` - Runtime keyword guard exists outside the documented no-runtime-NLU contract

Severity: **P1/P2, depending on intended product design**

`viventium_v0_4/LibreChat/api/server/services/viventium/telegramToolGuard.js` contains a Telegram
tool-loading guard built around hardcoded keyword lists and message-shape checks. The file-level
comment explains the performance rationale, but this behavior is not clearly represented as an
approved exception in the source-of-truth docs or release tests.

Why it matters:

- The repo's core rule forbids runtime regex/keyword matching for user intent, provider selection,
  email phrasing, or productivity scope unless explicitly source-of-truth-owned.
- The existing no-runtime-NLU test focuses mostly on provider-branded regex and old helper names; it
  does not catch generic keyword gates such as `DEFAULT_KEYWORDS` / `hasToolIntentKeyword`.
- Valid user phrasings outside the list can silently skip tool loading.

Required reconciliation:

1. Decide whether Telegram tool-intent gating is an intentional documented exception.
2. If it is intentional, move the behavior to config/source-of-truth metadata and add synthetic
   positive/negative cases.
3. If it is not intentional, remove or redesign the runtime keyword gate.
4. Expand `tests/release/test_no_runtime_nlu.py` to catch this class of drift.

### Prompt architecture and Prompt Workbench status need sharper docs

Severity: **P2**

Prompt Workbench exists and has substantial QA evidence, but the runtime implementation index and
top-level systems docs underrepresent it. The prompt architecture docs also include proposed/future
rollout language alongside implemented surfaces, which makes it hard to know what is canonical today.

Residual evidence:

- `qa/prompt-workbench/` reports successful local UI and artifact-level checks.
- The same QA status notes that live exact-model evals and reviewed live sync were intentionally not
  completed in at least one recent pass.
- Nested LibreChat prompt/source files are currently dirty, including source-of-truth prompt/agent
  files and untracked prompt labels.

Required reconciliation:

1. Split implemented Prompt Workbench behavior from proposed prompt-architecture roadmap work.
2. Add Prompt Workbench to the implementation index and systems map.
3. Keep live-sync/eval limitations visible in QA status until they are actually run.

### Public/private artifact boundary is strong, but local ignored artifacts are present

Severity: **P2**

The repo has strong public/private boundary docs and guardrail tests, and the checked public tree did
not show tracked runtime log/output directories in the sampled checks. However, ignored local artifacts
are present in the working checkout and nested runtime folders.

Observed safely:

- Ignored local logs/output/runtime folders exist in the checkout.
- A Google Workspace MCP debug log exists locally with OAuth-related error metadata.
- GlassHive has ignored local runtime DBs; table names and counts were inspected, but rows were not
  exported.
- Parent `git ls-files` did not list the sampled runtime/log/output paths.

Required reconciliation:

1. Keep ignored local artifacts out of public exports and Claude/sub-agent context unless strictly
   needed and sanitized.
2. Before any public commit/push/PR, scan staged diffs and QA reports for local paths, personal
   identifiers, raw IDs, logs, and secrets.
3. Consider documenting where local runtime DB/log evidence may be summarized in public QA reports.

### `DOCIMPL-007` - Vendored/shipped component provenance is incomplete

Severity: **P1**

Claude's second pass found a stronger shipped-artifact gap than the initial audit named. Some in-tree
components look like full projects but are not separate nested repos and are not represented in
`components.lock.json`.

Examples:

- `viventium_v0_4/LibreChat/viventium/services/librecodeinterpreter/` is a full vendored service with
  its own license/build/test metadata. It is also exposed as a first-class integration through schema
  and compiler surfaces, but lacks a requirements doc, QA owner, and component pin/provenance note.
- `viventium_v0_4/MCPs/openclaw-bridge/` and `viventium_v0_4/MCPs/power-agents-beta/` are in-tree MCP
  projects without lock-file entries or clear high-level documentation. This is distinct from the
  separately pinned `viventium_v0_4/openclaw` component.

Required reconciliation:

1. Decide whether each in-tree project is public-shipped, experimental, paused, private-only, or
   historical.
2. Add component provenance/pin documentation, or convert to nested repos with lock entries where
   appropriate.
3. Add QA owners for active shipped surfaces.
4. Add a release test that flags vendored project roots lacking either a lock entry or an explicit
   vendored-component allowlist/provenance note.

### Nested repo and release readiness state needs explicit status language

Severity: **P2**

`components.lock.json` matched the local HEADs for the listed nested component repos during this audit,
which is good. But the working tree is not clean:

- The parent repo has many modified/untracked files.
- The LibreChat nested repo is dirty and ahead of its branch, including source-of-truth YAML, prompt,
  API, MCP, and voice-related files.
- Several nested repos are behind origin.

This is not automatically a defect, but it means docs or release notes should not claim a shipped or
release-ready state without separately verifying nested commits, parent pins, prebuilt artifacts, and
installed artifacts after the intended changes land.

Required reconciliation:

1. Track whether each dirty nested change is intentional, public-safe, committed in its nested repo,
   and represented by the parent pin.
2. Avoid release-ready wording until dirty/behind states are resolved or explicitly excluded.

### QA coverage is uneven across feature docs

Severity: **P2**

The QA structure is much better than a generic project, but feature coverage is not evenly traceable
from every requirement doc to cases/reports. Areas that need clearer direct QA ownership include:

- Citation rendering.
- Agent streaming usage.
- Branding/assets.
- General MCPs and scheduling cortex.
- No-response incidents.
- Power Agents Beta / paused experimental surfaces.
- Telegram Codex.
- macOS helper user flows beyond installer source checks.
- Code interpreter service.
- Telegram Codex privacy gate.
- GlassHive workflow CLI command contract.
- MCP OAuth scope defaults.

Required reconciliation:

1. Add or link owning QA folders for each requirement doc.
2. For paused or historical features, mark status and expected maintenance obligations.
3. Convert escaped incidents into synthetic public-safe cases as required by `qa/README.md`.

## Documented But Not Implemented Properly

The clearest cases are release-test-backed:

- Background agents: docs/tests expect activation fallbacks, tool availability, launch model baseline,
  voice route model, prompt refs, card guardrails, and instruction phrases that the current
  source-of-truth YAML does not satisfy.
- Config fields: docs/compiler implement `runtime.dev_env`, transcript ignore globs, and richer
  web-search config than the schema exposes.
- Telegram STT: schema prose contradicts compiler/docs/tests about inheriting local STT.
- Conversation recall default: public examples/docs/tests/wizard do not agree.
- Documentation navigation: multiple public docs promise files that are not in the current public tree.
- Prompt registry sync: source markdown includes a guardrail block, but resolved main-agent
  instructions currently omit it.

## Implemented Or Present But Not Properly Documented

- Prompt Workbench as a first-class runtime/QA surface.
- GlassHive workflow adapters and CLI commands for self-heal, feature-request, and bug-report flows.
- Telegram Codex as a distinct surface from Telegram Viventium.
- macOS helper status-bar behavior and prebuilt/source verification in top-level maps.
- OpenClaw bridge, power-agent sidecars, and other experimental/paused components as intentionally
  active, paused, or historical.
- Runtime DB-backed GlassHive callback/outbox behavior at the systems-map level.
- Live-vs-source prompt sync limitations and exact-model eval status.
- Any intentional Telegram tool-intent performance guard, if it is meant to remain.
- Telegram Codex `private_chat_only` as a documented privacy requirement and QA surface.
- Voice-gateway provider matrix, including local TTS/STT variants and checksum expectations.
- Code interpreter service provenance, config contract, and acceptance tests.

## Recommended Order of Work

1. Fix the prompt-registry resolver and background-agent source-of-truth governance drift together.
2. Reconcile `config.schema.yaml`, examples, wizard defaults, compiler fields, and docs.
3. Repair high-impact broken markdown links, starting with always-loaded operator context and public
   READMEs, then add a docs link check that also understands backtick-cited file paths.
4. Add provenance/pin/QA ownership for unpinned vendored shipped components.
5. Rewrite `docs/02_ARCHITECTURE_OVERVIEW.md`, `docs/03_SYSTEMS_MAP.md`, and
   `viventium_v0_4/docs/IMPLEMENTATION_INDEX.md` around current v0.4 product surfaces.
6. Decide the Telegram keyword guard fate and expand no-runtime-NLU tests.
7. Add missing QA owners for undercovered requirement docs.
8. Add CLI signature/scope/default parity tests for GlassHive workflows, MCP OAuth scopes, and
   Telegram Codex privacy behavior.
9. Only after the above, perform fresh clone/install, nested pin, prebuilt artifact, and installed
   artifact verification for release-readiness.

## Second-Opinion Status

Claude structured review was completed in review-only mode. The strongest additions were:

- Reproduced and elevated the prompt-registry sync resolver failure.
- Confirmed the main background-agent, config-schema, broken-link, and Telegram keyword-guard findings.
- Identified underdocumented/unpinned vendored shipped components.
- Confirmed that macOS helper prebuilt/source hash and listed `components.lock.json` component pins
  were not the problem area in this pass.

A public-safe Claude review summary is saved alongside this report.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines included.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails,
  account identifiers, or customer data included.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or
  raw provider request/response IDs included.
- [x] No local absolute paths, hostnames, machine names, App Support paths, DB exports, or raw runtime
  dumps included.
- [x] Private evidence summarized with sanitized counts and conclusions only.
