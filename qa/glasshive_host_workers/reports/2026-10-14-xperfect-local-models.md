# Native xPerfect local-model QA — 2026-10-14

## Summary

- Result: PARTIAL for the full local/offline-light objective. Native integration passed in bounded
  cases; natural delegation and foreground latency failed their cases.
- Build/source under test: private isolated xPerfect source snapshot based on
  `5124d13cba0d7809fc7098c92344983fc340ffd4`, with experimental local-route changes. File identities
  are recorded below; this is not an upstream commit or a published implementation.
- Runtime/artifact under test: separate loopback xPerfect API/UI, native Codex/Claude children and
  private Ollama processes. No active Viventium runtime, component pin or installed artifact changed.
- Environment: local macOS development on Apple M5 Max, 128 GiB unified memory. This host does not
  establish an 8–16 GiB laptop profile. OS cache and other host activity were not fully controlled.
- QA mode and authorizing instruction: blast-radius; optional local Main/worker integration,
  bounded benchmarks and offline boundaries, without disturbing concurrent voice work.
- Selected cases and causal relevance: `GHHOST-027` exact local route, `GHHOST-028` delegation and
  availability, `GHHOST-029` serving/offline limits. These directly exercise the new route.
- Deferred / unselected cases (NOT RUN): installed Viventium activation, complete offline speech,
  Claude bee/result parity, all retained modules, compaction, smallest hardware and other OSs.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `GHHOST-027` | PARTIAL | Both Main harnesses read real files; Codex bee wrote the correct report; 242 affected tests passed. | Claude bee/result parity and installed delivery were not run. |
| `GHHOST-028` | FAIL | Explicit dispatch completed a real goal and result wake; natural browser request created zero durable goals. | Main did the natural task itself and called it background work. Foreground completion during workers took 5–15s. |
| `GHHOST-029` | PARTIAL | Server slot logs, native compatibility failure, restricted-caller inference and refused tools/startup. | No single-runner concurrency fix or full offline acceptance was completed. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Supporting evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `GHHOST-UC-027` | Ask the local Main to inspect a file, then inspect a helper's completed work. | Native Codex/Claude and xPerfect browser | PARTIAL | Correct file answers; Codex helper result card, expanded result and reload persisted. | Exact saved endpoints/model; real report bytes; native launches and affected tests. | Claude bee/result parity and installed surface. |
| `GHHOST-UC-028` | Ask for background work naturally and keep chatting. | xPerfect browser and native coordinator | FAIL | Natural request ran in Main with no work card; final text falsely called it background work. | Zero coordinator goals for that request. Separate explicit control produced a goal, helper, file and resumed Main. | Reliable natural delegation and sub-2s foreground response. |
| `GHHOST-UC-029` | Use local inference under the selected server and network policy. | Native CLI/file tools and private API startup | PARTIAL | Restricted caller answered honestly that file tools were unavailable. | Local inference ran; external caller connection was refused; nested sandbox errors blocked tools and full startup. | Working protected tool/runtime path; whole-app offline and speech. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: optional native local inference for Main and workers.
- Requirement: [GlassHive provider, native harness and truthful result contracts](../../../docs/requirements_and_learnings/capabilities/glasshive.md),
  interpreted for this experiment by the [local-model research owner](../../../docs/research_and_future_plans/05_Local_Models_and_Native_Harnesses.md).
- Use case / QA case: `GHHOST-UC-027`–`029` / `GHHOST-027`–`029`.
- Expected result: exact selected local model, real authorized tools/work, correct durable result,
  available Main and wording consistent with observed execution.
- Actual evidence: native launches, real synthetic file, browser details/reload and persisted goal,
  run and worker-result state were compared. The natural request and latency did not meet the goal.
- Remaining gap: natural behavior, responsiveness, protected offline operation and installed parity.

## Measurements and serving profiles

Tested model: `qwen3.6:latest`, Qwen3.6-35B-A3B Q4_K_M, with 65,536 configured context tokens.
Weight digest: `d372de8e934898a59e6ccfabc3368474711384d8f1fd4d22d87a3f0a45400cdc`.
Tested server: Ollama 0.40.2. A newer 0.40.4 release was identified but not tested.
Codex and Claude used their installed native CLIs; exact CLI versions were not retained in the
sanitized result, which limits reproducibility. Do not infer a current-version guarantee.

All times below are completed replies/runs, not streaming first text, p95 or speech latency.
Different histories and host activity prevent a controlled speed ranking.

| Real path | Observed seconds | Correctness / limit |
| --- | ---: | --- |
| Codex first request | 15.18 | Correct arithmetic; about 11s model load; OS cache uncontrolled. |
| Codex warm arithmetic / recall | 0.92 / 1.51 | Correct short answers and retained facts. |
| Claude first request / warm recall | 14.24 / 1.86 | Correct short answers and retained facts. |
| Codex / Claude file read | 7.58 / 6.36 | Correct inventory total 128 and largest line value 84; Claude missed the one-sentence format. |
| Changing context | 5.77 | A 260-row historical archive followed by a correction returned the current project, amber colour and unpublished state exactly. Not a compaction test. |
| One-runner corrected worker overlap | 7.01 | Foreground answer completed while a real worker ran. The corrected fixture was in the worker's actual workspace; the earlier missing-input run was not counted as success. |
| Two-runner manual helper / foreground | 18.36 / 5.09 | Correct helper file and foreground answer. Same exact model, separate endpoints. |
| Two-runner explicit dispatch reply | 14.06 | Goal accepted and helper dispatched; this reply ended before helper completion. |
| Automatic helper run / foreground overlap | 31.38 / 15.31 | Correct report; new foreground answer completed while the helper ran. |
| Result wake | 6.44 | Existing coordinator resumed Main with the helper result; browser result persisted after reload. |
| Final natural browser request | 10.39 run time | Zero durable goals; Main wrote the report itself and falsely called it background work. |

The synthetic inventory is reproducible: Oak, 7 units at 12; Pine, 3 at 8; Birch, 4 at 5.
Expected arithmetic: 84 + 24 + 20 = 128; highest line value: Oak, 84. Seed the actual workspace
returned by the runtime, not a guessed parent folder. A correct file in a refused or unrelated
temporary location is not a pass for the requested destination.

| Serving alternative | What was tested | Interpretation |
| --- | --- | --- |
| One Ollama runner | Parallelism set to two; server logged a `qwen35moe` restriction and launched one slot. | This setting did not fix this version/model profile. One endpoint still supports multiple agents whose model requests may queue. Not a universal sparse-model limit. |
| Two Ollama runners | Same model on separate Main/mission endpoints; actual work and return succeeded. | Diagnostic capacity workaround, not required architecture or a selected default. Memory cost grew; speed goal still failed. |
| llama.cpp b11540 | Earlier raw two-slot inference worked; actual native Codex Responses request skipped namespace tools and raised a system-message chat-template error. | The tested native compatibility path failed. No compatibility fix was completed; this does not establish general engine failure. |
| Standalone MLX | Earlier Qwen3.5-0.8B controls passed 9/15; examined server lacked the needed native Responses/Anthropic interfaces. | Tiny-model quality and tested server interface limits. No full xPerfect MLX run; no general MLX failure. Ollama's MLX backend is a separate configuration to qualify. |
| Qwen3.8-27B | Earlier 10 October raw controls passed 15/15; queued foreground first text was about 7.49s. | Full xPerfect Main/bee run NOT RUN in this experiment. “Unqualified” means missing evidence, not a measured integration failure. |

Single-runner sampled peak process-tree RSS was about 26.1 GiB, with peak CPU about 204.2%.
RSS sums can double-count mappings and are not unique GPU memory. Each warm runner logged about
20.4 GiB of model allocation plus context/compute; no reliable hot two-runner total was captured.
The later idle sample had unloaded the models and must not be used as a hot-memory measurement.

## Full-View Evidence Checklist

| Evidence surface | Result / sanitized pointer |
| --- | --- |
| Requirement and use case | Linked contract, research interpretation and cases above; no new product architecture approved. |
| Code owning path | `local_inference.py`, `conversation_provider.py`, `coordinator_config.py`, `coordinator_mcp.py`, `service.py`, `store.py` and `profile_runtime.py` in the candidate runtime. |
| Docs and nested docs/repos | Candidate xPerfect `docs/host-setup.md` described experimental settings; the research owner distinguishes candidate setup from supported release instructions. |
| Scripts or harnesses | Private coordinator/worker drivers, actual native CLIs, synthetic CSV and the affected pytest suites listed below. |
| Local/external prerequisite state | Private resident GGUF weights; Ollama cloud disabled; independent state/cache and no shared-service inference. Host execution used existing operator policy, not a new model permission. |
| Logs | Native endpoint and model were traced. Ollama slot restriction and llama.cpp tool/template errors were observed. Raw logs remain private. |
| DB/state/persistence | Explicit case had a saved goal, exact worker route, completed helper run and worker-result turn. Natural case had zero goals. |
| Generated/shipped artifact | Candidate native config inspected; no component pin, build, installed artifact or active-runtime acceptance. |
| Real user path | Browser conversation, expanded Result, Complete card and reload; separate natural browser request. |
| Visual/UX comparison | Explicit completed result matched the correct file. Natural final wording contradicted the absence of delegated work. |
| Not run / blocked | Caller-only egress test did not cover the model server; protected full startup/tools failed. Full offline speech, broad module and installed parity not run. |

## User-Grade Evidence

- Surface exercised: real xPerfect browser and native Codex/Claude local-model file paths.
- Real user path: ask a file question; inspect a completed helper, expand Result and reload;
  separately ask for background work in ordinary language.
- Visible outcome: explicit result was correct and durable; natural request exposed no work card
  and incorrectly described Main's own work as background work.
- Expanded/detail state: helper Result contained the arithmetic and highest-value item.
- Persistence/reload result: completed card, result and resumed Main answer survived reload;
  separate conversation recall also passed after reload.
- Backend/log/DB confirmation: actual report bytes, exact local route, completed helper and result
  turn matched the explicit UI; zero goals contradicted the natural request's background claim.
- Final model/runtime wording check: explicit control accurately reported dispatch/completion;
  natural request failed. A prior tool-directed dispatch blocker was fixed, not hidden as a pass.
- Substitution check: logs, DB rows, API responses, source inspection, model completions and unit
  tests supported these observations; they did not replace browser details, reload or wording proof.

## Automated Evidence

242 affected tests passed in the isolated candidate. The command, from its `runtime_phase1/`:

```sh
python -m pytest tests/test_local_inference.py tests/test_coordinator.py \
  tests/test_store_integrity.py tests/test_store_lifetime.py \
  tests/test_store_connection_reuse.py tests/test_worker_configuration.py \
  tests/test_delegation_preaccept_capacity.py tests/test_parallel_runtime_safety.py -q
```

`test_local_inference.py` belongs to the experimental candidate; its presence is not claimed in
the installed component. Coverage included exact catalog/admission, saved routes after settings
changes, duplicate/reservation persistence, final launch credential/settings conflict guards,
coordinator run-scope projection and unchanged cloud defaults when local mode is unset.

Seven failures in earlier, broader provider/profile checks reproduced with the captured original
provider/profile source files. They remain open: two incomplete voice-terminal fixtures and five
fake-process launch/version-probe fixtures. They are not seven failures in the 242 passing set,
and the wider suite is not reported green.

Public-safe candidate file SHA-256 identities:

| Candidate source | SHA-256 |
| --- | --- |
| `local_inference.py` | `d56aaea320494ac2d45ce5610b3487512787bb80045f9c0685d35992f9a8d22e` |
| `service.py` | `2ff588d5890a6954b5e097fa6708ab00976bd9d414e14cb03e7a72644279c076` |
| `store.py` | `e40de627bc22190979d1ebfab9ed55f90d6479c01c0dcf1a5f791853c0e162fd` |
| `profile_runtime.py` | `5b7220df73283a5cca408fe5ead400fd5e57f49e363edd410a7f3484b9111311` |
| `test_local_inference.py` | `f2e369cada21a212d89557b5b5cbcb85506aaf4773ee18f5b3cafbf5cb7dc722` |

Exact prompts, full manifests, raw logs, screenshots, DB/state and test output remain in a private
maintainer annex for this dated report. These content identities do not make the candidate public
or turn it into an installed release. A public source package and exact CLI-version record are
still prerequisites for complete independent replay.

## Findings

- Fixed in the candidate: exact local catalog, final cloud-binding rejection, immutable saved
  route, Claude setting precedence, trusted coordinator tool-policy projection and local background
  catalog/reservation wiring. No model prompt or runtime intent classifier was added.
- Open defects: natural delegation/wording, foreground latency, protected tool/startup compatibility
  and run-level token counters remaining zero despite provider response usage being present.
- Review: Opus 5.5 completed an initial independent review. A final refresh failed on expired
  authentication; final review sign-off is absent. Review never replaced tests or user-path proof.
- Offline boundary: caller egress policy allowed loopback and refused an external connection.
  Local inference ran, but nested native sandbox execution failed; full runtime handshake also
  failed. The model server was cloud-disabled with resident weights but was not covered by that
  successful caller-only run. Do not describe this as whole-app offline acceptance.
- Cleanup: owned test processes stopped and test ports closed. Shared model/runtime services and
  voice work were not modified. Experiment-generated source workspaces and a byte-matched temporary
  report were retained privately outside the source snapshot.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies or credential-bearing command lines.
- [x] No private prompts/chats, attachments, screenshots, personal emails, account identifiers or customer data.
- [x] No conversation, message, session/call, worker or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, private stack traces, DB exports or runtime dumps.
- [x] Private evidence summarized only with sanitized counts, hashes, dates and conclusions.
