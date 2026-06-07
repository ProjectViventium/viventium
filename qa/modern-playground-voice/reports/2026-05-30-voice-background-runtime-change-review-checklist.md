<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# 2026-05-30 Voice / Background Runtime Change Review Checklist

Status: `FIXES_IN_PROGRESS_AFTER_APPROVAL` after local review, tests, lightweight user-surface QA,
Claude review-only second opinion, and owner approval to align voice async ON.

This is the public-safe inventory for the May 30 voice latency, runtime, and background-cortex
change review. It intentionally does not copy private handoff text, private conversation content,
local account identifiers, call/session ids, message ids, local absolute paths, secrets, or raw logs.

## Scope

- Voice latency and LiveKit playground behavior.
- Main-agent voice LLM route, STT route, TTS route, and generated runtime config.
- Background-cortex Phase A / Phase B detection behavior for voice and text.
- Speculative parallel main-run behavior, abort/retry semantics, delivery, billing, and persistence.
- Conversation recall/RAG and saved-memory hot-path claims where they affect voice or chat latency.
- Config compiler, schema, docs, QA cases, generated runtime boundary, and release tests touched by
  the in-flight work.
- Public/private boundary review of new docs and QA artifacts.
- Nested LibreChat fork changes and parent-repo change coordination.

## Inputs Reviewed

| Input | Public-Safe Handling | Status |
| --- | --- | --- |
| `docs/requirements_and_learnings/01_Key_Principles.md` | Requirement baseline. | `REVIEWED` |
| `docs/requirements_and_learnings/02_Background_Agents.md` | Background-cortex contract. | `REVIEWED_PARTIAL` |
| `docs/requirements_and_learnings/06_Voice_Calls.md` | Voice contract and MPV QA owner. | `REVIEWED_PARTIAL` |
| `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md` | Generated-runtime boundary. | `REVIEWED_PARTIAL` |
| `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md` | QA owner map. | `REVIEWED` |
| `qa/README.md` | QA operating contract. | `REVIEWED` |
| `qa/modern-playground-voice/cases.md` | Voice acceptance cases. | `REVIEWED_PARTIAL` |
| `qa/background_agents/cases.md` | Background acceptance cases. | `REVIEWED` |
| Private handoff and pasted conversation supplied by the user | Used as claims to verify; raw details not copied here. | `REVIEWED` |
| Git status and diff inventory for parent repo and nested LibreChat repo | Public-safe file/path inventory only. | `REVIEWED` |

## Review Gates

| Gate | Requirement Source | Status | Notes |
| --- | --- | --- | --- |
| Quality plus performance, not speed alone | `01_Key_Principles.md` | `PENDING` | Every latency fix must preserve intelligent, useful, aligned output. |
| Public/private boundary | `AGENTS.md`, `01_Key_Principles.md` | `FIXED_FOR_NEW_HANDOFF` | The new public handoff was moved to the private records area; public QA notes keep only sanitized summaries. Older historical artifacts still need a separate repo-wide boundary cleanup. |
| Canonical config and compiler ownership | `39_Installer_and_Config_Compiler.md` | `FIXED_SOURCE_PENDING_RUNTIME_QA` | Compiler, docs, and release tests now align on voice async `true`, text async `false`, voice 690 ms, text 1300 ms. |
| Voice Call LLM ownership | `06_Voice_Calls.md` | `FIXED_SOURCE_PENDING_SYNC` | Tracked source now uses main-agent voice route `xai / grok-4.3` with `reasoning_effort: none`; live DB sync and runtime verification remain required. |
| Voice user-grade QA | `qa/README.md`, `MPV-014` | `PARTIAL` | A real browser playground typed-call path reached transcript visibility and TTS provider metrics, but the harness failed its older strict `ttsEmitCount` marker expectation; full spoken speculative/background behavior remains unproven. |
| Background browser user-grade QA | `qa/background_agents/cases.md` | `PENDING` | Text/browser behavior needs visible cards, persistence, and refresh checks. |
| No runtime NLU or hardcoded user/agent branches | `01_Key_Principles.md`, `02_Background_Agents.md` | `PENDING` | Diff must be scanned for keyword/user/agent-name branching. |
| Nested repo boundary | `AGENTS.md` | `PENDING` | Parent and LibreChat changes need separate verification and later separate commits/pins if shipped. |
| Shipped/generated artifact parity | `01_Key_Principles.md`, `39_Installer_and_Config_Compiler.md` | `PENDING` | Source-only changes do not prove installed local-prod runtime behavior. |
| Claude review-only second opinion | `AGENTS.md` | `DONE` | Opus 4.8 review-only confirmed the main findings and elevated the async/gate interaction to the highest-risk issue. Claude did not edit files. |

## Changed File Inventory

### Parent Repo

| Area | Files | Review Status |
| --- | --- | --- |
| Canonical config | `config.full.example.yaml`, `config.schema.yaml` | `REVIEWED` |
| Requirements docs | `docs/requirements_and_learnings/02_Background_Agents.md`, `06_Voice_Calls.md`, `32_Conversation_Recall_RAG.md`, `39_Installer_and_Config_Compiler.md`, `48_GlassHive_Workstation_Sandbox_Runtime.md`, `52_Voice_Component_Fork_Modification_Inventory.md` | `REVIEWED_WITH_ALIGNMENT_FAILS` |
| Public handoff | `docs/HANDOFF_2026-05-30_two_mode_background_detection.md` | `FAIL_BOUNDARY` |
| QA cases/reports | `qa/background_agents/cases.md`, `qa/glasshive-mcp-capability-broker/cases.md`, `qa/modern-playground-voice/cases.md`, `qa/scheduling-cortex/cases.md`, new voice reports, new STT QA area | `REVIEWED_PARTIAL_WITH_BOUNDARY_FAILS` |
| Compiler/preflight | `scripts/viventium/config_compiler.py`, `scripts/viventium/preflight.py` | `REVIEWED` |
| Release tests | `tests/release/test_config_compiler.py`, `test_preflight.py`, `test_prompt_workbench.py`, `test_scheduled_glasshive_prompts.py`, `test_voice_playground_dispatch_contract.py` | `REVIEWED_AND_RUN_TARGETED` |
| Runtime docs | `viventium_v0_4/docs/VOICE_CALLS.md` | `REVIEWED_WITH_ALIGNMENT_FAILS` |
| Voice gateway | `viventium_v0_4/voice-gateway/worker.py`, `pywhispercpp_provider.py`, added STT/turn-handling tests and benchmark script | `REVIEWED_AND_TESTED` |

### Nested LibreChat Repo

| Area | Files | Review Status |
| --- | --- | --- |
| Agent controller | `api/server/controllers/agents/client.js`, `callbacks.js`, new speculative parallel specs | `REVIEWED_AND_PATCHED_WITH_REMAINING_QA_GAPS` |
| Background policy/timing | `api/server/services/viventium/voicePhaseAPolicy.js`, `telegramTimingDeep.js` | `REVIEWED` |
| GlassHive capability broker | `api/server/services/viventium/GlassHiveCapabilityBootstrapService.js`, `GlassHiveCapabilityPolicyService.js`, `GlassHiveCapabilityBroker.spec.js` | `REVIEWED_AND_TESTED` |
| Runtime RAG/recall | `packages/api/src/agents/initialize.ts`, `packages/api/src/files/rag.ts`, `rag.spec.ts` | `REVIEWED_AND_TESTED_PARTIAL_QA` |
| Provider/model config | `packages/api/src/endpoints/anthropic/oauthSubscription.ts`, `packages/data-provider/src/config.ts`, tests | `REVIEWED_AND_TESTED` |
| Token accounting | `packages/api/src/utils/tokens.ts` | `REVIEWED_UPSTREAM_OVERLAP` |
| Scheduling cortex | `viventium/MCPs/scheduling-cortex/scheduling_cortex/dispatch.py`, dispatch tests | `REVIEWED_AND_TESTED` |

## Claims To Verify

| Claim | Current Status | Required Evidence |
| --- | --- | --- |
| Main agent voice LLM should be Grok 4.3. | `FIXED_SOURCE_PENDING_SYNC` | Source now declares `xai / grok-4.3` plus `reasoning_effort: none`; verify live DB and call-session voice settings after sync. |
| Voice async detection default is ON with a 690 ms budget. | `FIXED_SOURCE_PENDING_QA` | Compiler/docs/tests align; voice user-path verification is still required. |
| Text async detection default is OFF with a 1300 ms budget. | `UNVERIFIED` | Config compiler output, web chat timing logs, background card behavior. |
| Speculative parallel activation cancels and re-runs safely when a cortex activates within budget. | `FAIL/PARTIAL` | Small-seam tests pass, but the exported proof helper is not the live code path. The live code currently keys speculation from raw `requested`, not the policy-safe `enabled`, so direct-action fail-closed claims are not proven. |
| No-activation speculative path delivers exactly once and does not double-bill. | `PARTIAL` | Focused tests pass, but they cover an isolated/buffered harness while live wiring uses live-reuse streaming. |
| Memory/recall are not material latency causes after recent work. | `CONFLICT` | Fresh timing traces for memory on/off and recall on/off in chat and voice; prior evidence showed recall/RAG and memory hot-path failures. |
| Voice runtime was verified after the new changes. | `FAILED_CURRENT_EVIDENCE` | The supplied pasted handoff says voice QA was attempted but did not complete successfully after restart. |
| Opus 4.8 source and dist changes are active and safe. | `UNVERIFIED` | Source config, generated config, built dist artifact, model inventory tests. |
| `VIVENTIUM_TIMING_DEEP` and `VIV_INIT_TIMING` coexist without confusing timing evidence. | `UNVERIFIED` | Code trace and sample logs. |
| New public docs/reports are clean. | `FIXED_FOR_NEW_HANDOFF` | The new raw handoff was moved out of public docs; useful sanitized notes remain in this feature-owned report. |

## Test / QA Matrix

| Surface | Command or User Path | Status | Result |
| --- | --- | --- | --- |
| Parent diff hygiene | `git diff --check` | `PASS` | No whitespace errors. |
| Nested LibreChat diff hygiene | `git -C viventium_v0_4/LibreChat diff --check` | `PASS` | No whitespace errors. |
| Compiler tests | `PYTHONPATH=. uv run --with pytest --with pyyaml pytest tests/release/test_config_compiler.py -q` | `PASS` | 108 passed; generated runtime and LibreChat env defaults align to voice async `true`, text async `false`, voice 690 ms, text 1300 ms. |
| Main-agent voice route contract | `PYTHONPATH=. uv run --with pytest --with pyyaml pytest tests/release/test_background_agent_governance_contract.py::test_local_source_of_truth_main_agent_voice_route_uses_grok_without_reasoning -q` | `PASS` | 1 passed; source-of-truth main-agent voice route is `xai / grok-4.3` with `reasoning_effort: none` and no Anthropic `thinking` field. |
| Background governance full contract | `PYTHONPATH=. uv run --with pytest --with pyyaml pytest tests/release/test_config_compiler.py tests/release/test_background_agent_governance_contract.py -q` | `FAIL_UNRELATED` | 123 passed, 4 failed in existing prompt/fallback/source-ref governance expectations unrelated to the voice route/default changes. |
| Preflight/prompt/scheduling/voice release tests | `PYTHONPATH=. uv run --with pytest --with pyyaml --with pydantic --with croniter pytest tests/release/test_preflight.py tests/release/test_prompt_workbench.py tests/release/test_scheduled_glasshive_prompts.py tests/release/test_voice_playground_dispatch_contract.py -q` | `PASS` | 161 passed, 21 skipped. |
| Voice gateway full suite | `uv run pytest tests -q` | `PASS` | 329 passed, 20 subtests passed, 1 deprecation warning. |
| LibreChat controller/API tests | Focused Jest suites for `client`, speculative helpers, voice policy, RAG, Anthropic OAuth, data-provider config, GlassHive broker | `PASS` | Agent controller/policy 164 passed; RAG/OAuth 25 passed; data-provider config 57 passed; GlassHive broker 20 passed. |
| LibreChat API full suite | `npm run test:ci -- --runInBand --silent` under `LibreChat/api` | `PARTIAL` | Attempted twice; runner exited with code `-1` before a final summary after several early suites passed. Focused touched suites above are the reliable evidence. |
| Scheduling Cortex dispatch tests | `uv run --with pytest --with pydantic --with croniter pytest tests/test_dispatch.py -q` under scheduling-cortex | `PASS` | 51 passed. |
| Callbacks voice reasoning guard | `npm test -- --runInBand server/controllers/agents/__tests__/callbacks.spec.js` | `PASS` | 11 passed; voice-mode reasoning deltas are suppressed before emit/aggregation. |
| Voice Phase A/speculative policy focused tests | `npm test -- --runInBand server/controllers/agents/speculativeParallelDetect.spec.js server/services/viventium/__tests__/voicePhaseAPolicy.spec.js` | `PASS` | 37 passed; live speculative eligibility now honors the policy-safe `enabled` gate instead of raw `requested`. |
| Modern Playground visible load | Playwright CLI open/snapshot `http://localhost:3300` | `PASS` | Page loaded as `Viventium Voice Assistant`; voice route controls visible; Open-from-Viventium disabled without a call session. |
| LibreChat visible load | Playwright CLI open/snapshot `http://localhost:3190` | `PASS` | Login page rendered with 0 console errors and 1 warning. |
| Synthetic fake-mic voice path | `node qa/modern-playground-voice/scripts/livekit_synthetic_audio_qa.js` with public-safe short WAV | `PASS` | Modern Playground + LiveKit + worker + local STT persisted one cleaned synthetic transcript row and cleanup removed the synthetic user/session/message records. This does not cover assistant LLM/TTS/speculative background behavior. |
| Browser text/background QA | Real LibreChat browser prompt, background cards, reload, DB/log correlation | `PENDING` | Not run in this review pass. |
| Modern playground voice QA | Real playground call per `MPV-014`, assistant audio/transcript/log/DB correlation | `PARTIAL` | Post-restart typed playground call created a call, opened the page, clicked Start, toggled transcript, sent a synthetic prompt, showed transcript text, logged a non-cancelled TTS provider metric for 4 chars, and had 0 browser console errors. The harness still returned nonzero because local Chatterbox did not emit the legacy `ttsEmitCount` marker. |
| Runtime config alignment | Supported source/live compare plus direct DB check for main agent | `PASS_WITH_REMAINING_UNRELATED_DRIFT` | Source and live main-agent voice route now match `xai / grok-4.3` with `reasoning_effort: none`; the stale xAI `thinking:false` bag was removed by a dry-run-first `--model-config-only --agent-ids=<main>` sync. Remaining compare drift is limited to two unrelated background-agent empty-object/null fallback-parameter differences. |
| Current resource snapshot | Local CPU/memory/disk snapshot | `INFO` | Current matched Viventium processes were not CPU saturated. The observed failures align with fixed timeouts/config gates rather than raw host-resource exhaustion. |
| Claude review-only | Opus 4.8 max-effort second opinion | `DONE` | Confirmed async default interpretation and the `policy.enabled` safety fix. Added follow-ups: remove the unreachable legacy async branch, run an in-budget real voice activation test, build/re-scope the front-end flow-style indicator, and keep this change split from unrelated GlassHive/RAG/OAuth work. |

## Working Findings

| ID | Severity | Finding | Evidence Status | Proposed Direction |
| --- | --- | --- | --- | --- |
| `VF-001` | `HIGH` | Voice async default was not aligned across compiler, docs, tests, and QA evidence. | `FIXED_SOURCE_PENDING_QA` | Owner approved voice async ON. Keep `true`, document the two-mode contract, and complete MPV-014 before claiming runtime acceptance. |
| `VF-002` | `HIGH` | Voice QA cannot be accepted as complete until a post-change user-grade playground call passes. | `CONFIRMED` | Treat current state as `PARTIAL` until `MPV-014` is rerun and logs/DB/config prove the changed runtime is active. |
| `VF-003` | `HIGH` | Main-agent voice model route was Anthropic Sonnet/stale-shaped, not the requested clean Grok 4.3 route. | `FIXED_LIVE` | Source and live DB now carry Grok 4.3 with `reasoning_effort: none`; sync was dry-runed first and applied only to the main agent model config. |
| `VF-004` | `HIGH` | Public handoff placement violated public/private boundary and single-source-doc discipline. | `FIXED_FOR_NEW_HANDOFF` | Raw handoff and owner prompt are preserved privately; public repo keeps sanitized, case-owned QA/report content. |
| `VF-005` | `MEDIUM` | Recent memory/recall latency claims conflict across handoffs. | `PRELIMINARY` | Require structured timing evidence for memory on/off and recall on/off before accepting or rejecting those bottlenecks. |
| `VF-006` | `CRITICAL` | Speculative live-reuse path bypassed the policy `enabled` gate by using raw `requested`, conflicting with direct-action fail-closed claims and tests. | `FIXED_AND_TESTED` | Live speculation now honors the resolved policy gate; ordinary voice stays async ON by default, while direct-action/tool-hold cases fail closed unless explicitly overridden. The old follow-up-only async branch was removed after Claude identified it as unreachable. |
| `VF-007` | `MEDIUM` | Config/compiler/schema/example/docs/test surfaces changed together and do not compile to one canonical runtime truth. | `CONFIRMED` | Resolve the voice async default first; then rerun compiler tests and inspect generated env. |
| `VF-008` | `MEDIUM` | Speculative tests prove exported isolated/buffered helpers, but live code uses a different streaming live-reuse branch. | `CONFIRMED` | Add tests at the actual `AgentClient` seam for live-reuse abort, no post-abort SSE/body contamination, tool-call prevention, usage reset, and Phase B persistence. |
| `VF-009` | `HIGH` | The proposed main-agent Grok 4.3 sync mechanism must preserve `voice_llm_model_parameters`; a narrow model-config-only sync may not carry the xAI `reasoning_effort: none` shape. | `CONFIRMED` | Use a sync path that includes voice model parameters, or verify after sync that live DB/provider payload contains `xai/grok-4.3` plus `reasoning_effort: none`. |
| `VF-010` | `MEDIUM` | Local Opus 4.8 model-list edits overlap newer upstream LibreChat support and are not consistently wrapped as Viventium fork modifications. | `CONFIRMED` | Prefer porting the upstream support cleanly or remove redundant local deltas during upstream merge; wrap any remaining fork-specific edits with the required Viventium markers. |
| `VF-011` | `MEDIUM` | The owner prompt asks that code flow and frontend indicate the flow style; no new frontend flow-style indicator was built in this pass. | `REMAINING_GAP` | Either build a visible public-safe indicator for blocking/speculative/redo flow, or explicitly re-scope it to a follow-up with UX requirements and tests. |
| `VF-012` | `HIGH` | Voice async default is now live, but the in-budget activation nevermind path has not been proven in a real audible voice call. | `REMAINING_QA_GAP` | Run a Modern Playground voice call where a cortex activates within 690 ms and verify no mid-audio cut, activation cards, re-run Phase A awareness, logs, and DB/state. |

## Claude Review-Only Reconciliation

Claude's review was read-only on Opus 4.8. It confirmed the public/private boundary failure, the
compiler/docs/tests mismatch, the current main-agent voice route mismatch, the incomplete voice QA,
and the residual memory/recall timing uncertainty.

The strongest original finding was the compound risk between `VF-001` and `VF-006`: enabling voice
async by default arms the live speculative branch, and that branch consulted raw `requested` instead
of the policy-safe `enabled` value. After owner approval, the chosen fix was to keep voice async ON
and make the live branch honor `enabled`.

The follow-up Claude review agreed with that decision and found one cleanup worth applying
immediately: after `speculativeMode` also used `enabled`, the legacy follow-up-only async branch was
unreachable. That branch was removed. Claude's remaining hard QA ask is a real in-budget voice
activation run; the typed playground call proves the basic call/assistant/TTS path but not the
mid-voice nevermind path.

Claude also corrected one fix detail: a narrow model-config-only agent sync may not include the
voice model parameter bag. Since Grok voice needs `reasoning_effort: none`, the model-route fix must
prove the parameter shape survived source-to-live sync.

## Current Resource Snapshot

- Runtime surfaces checked: LibreChat frontend, Modern Playground, and API health responded locally.
- Current host snapshot: 10-core Apple Silicon, 32 GiB RAM, root volume about 30% used.
- Matched Viventium-related processes were not CPU saturated during the check.
- Interpretation: the confirmed failures are configuration, policy, and QA-evidence failures; the
  current evidence does not point to raw CPU/disk exhaustion as the primary bottleneck.

## Final Checklist Before Acceptance

- [x] Every changed source area reviewed or explicitly scoped out at inventory level.
- [x] Changed public docs/reports scanned for boundary leaks.
- [x] Targeted automated tests run and results recorded here.
- [x] Generated/runtime config path checked beyond source defaults for the main-agent voice route.
- [ ] Browser text/background path exercised like a user where behavior changed.
- [ ] Full audible assistant voice playground path exercised like a user where speculative/background behavior changed.
- [ ] Frontend flow-style indicator built or explicitly re-scoped.
- [x] Claude review-only pass run and reconciled against local evidence.
- [x] Proposed fixes separated into safe-now, needs-user-decision, and blocked-by-runtime-evidence.
- [x] Remaining gaps are marked `PARTIAL` or `BLOCKED`; no theoretical "done" claim.
