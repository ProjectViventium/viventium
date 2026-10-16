# Local models through native harnesses

Status: experimental integration tested on 14 October 2026; not an installed Viventium feature.

This document owns the reusable interpretation and integration guidance from the local-model
research. [The dated host-worker report](../../qa/glasshive_host_workers/reports/2026-10-14-xperfect-local-models.md)
owns measurements, candidate identity and execution results. The
[GlassHive contract](../requirements_and_learnings/capabilities/glasshive.md) still owns delivered
provider and worker behavior. This research does not change the approved product architecture.

## What works

An isolated xPerfect candidate used Qwen3.6 through Ollama with the existing native harnesses:

- Main, also called Queen, answered and read real files through Codex and Claude Code.
- A Codex worker, also called a bee, completed a real file task after an explicit coordinator
  dispatch. Its result resumed Main and remained visible after a browser reload.
- The implementation reused the coordinator, worker store, native tools and harness sessions.
  It added configuration and route validation, not another planner, scheduler or protocol relay.

This is narrower than a fully local Viventium installation. The candidate was not merged into the
active component, pinned, built or installed. Claude worker/result-return parity, full local
speech, the smallest supported laptop and other operating systems remain untested in this run.

## One endpoint is enough for integration

Ollama is a model server; Qwen is a model family; Codex and Claude Code are execution harnesses.
Several harness sessions can use one local endpoint. Native integration does not require one
server or a separate copy of the model for every agent.

Concurrent agents and concurrent model generation are different. Agents may perform file or tool
work while another agent requests inference. If the selected server can generate only one answer
at a time, another model request waits. Harness orchestration does not remove that queue.

The tested Ollama version forced the tested Qwen architecture to one slot even with parallelism
set to two. This is a version/model serving restriction observed in the logs, not proof that all
sparse models are inherently serial. Changing that setting did not fix this profile. A successful
single-runner fix was not completed.

Two runners using the same model were tested as a capacity workaround. They were not required for
the integration and are not a selected default. They add memory demand and still missed the
foreground response goal. Prefer the smallest native serving configuration that passes both
quality and responsiveness; do not build a custom inference scheduler from this finding.

## Separate integration, quality and delivery status

| Label | Meaning |
| --- | --- |
| Native integration passed | The named harness and model completed the observed task with real tools. It does not establish every model, worker profile or deployment. |
| Quality or performance failed | The specified case was executed and missed its expected result. It does not mean the entire serving engine is unusable. |
| Not tested / not qualified | Required evidence is absent. Do not report this as a measured failure. |
| Installed / shipped | Source, component pin, built artifact and running product agree, with the required real user proof. The experimental result does not establish this. |

The natural background-work request failed: Main did the work itself, created no coordinator goal
and described it as background work. Explicit tool-directed dispatch passed. Both facts must stay
visible. A forced tool call is not proof of natural delegation, and no keyword rule should be added
to make that one prompt pass.

The report's overall `PARTIAL` refers to the wider local/offline-light objective. It does not erase
the successful integration. Short warm replies and model-only first-token benchmarks also do not
establish Main responsiveness during a real worker task or delivered speech latency.

## Experimental configuration boundary

The evaluated candidate introduced these runtime settings. They are not release setup commands:
a checkout without the corresponding local-inference implementation does not support them.

| Setting | Candidate behavior |
| --- | --- |
| `WPR_LOCAL_MODEL` | One exact installed model ID; enables the explicit local route. |
| `WPR_LOCAL_BASE_URL` | Loopback server origin; default `http://127.0.0.1:11434`. |
| `WPR_LOCAL_CONTEXT_WINDOW` | Declared context; default `65536`, not proof that all context sizes were tested. |
| `WPR_DEFAULT_WORKER_PROFILE` | Existing native choice: `codex-cli` or `claude-code`. |
| `WPR_LOCAL_WORKER_BASE_URL` | Optional mission endpoint for the same exact model; diagnostic capacity option, not a default requirement. |

New ordinary and automatically reserved workers saved their exact model, endpoint and context.
Resume and duplication retained that route. Local mode rejected cloud account/subscription
bindings, incompatible profiles and conflicting model choices rather than silently falling back.
The final Claude settings and final native launch environment were checked, not only an early
environment helper. Existing cloud defaults remained when the option was unset.

Model selection does not grant host execution, file, computer or network authority. Existing
operator policy, run-scoped capabilities and server-side scope checks still apply. A model server
on loopback may itself proxy a remote model; verify resident weights, disable cloud features and
test the required network boundary before claiming offline operation. Local cognition alone does
not prove local STT/TTS or a complete offline app.

## How to repeat useful qualification

Use the [host-worker cases](../../qa/glasshive_host_workers/cases.md#ghhost-027---native-local-main-and-worker-route)
and the profile in the dated report. Keep a private instance, state directory and model cache;
do not restart a shared runtime for a benchmark.

1. Record server and harness versions, exact model/quantization/digest, context and serving layout.
2. Test Main, real file tools and each advertised worker harness. Check the actual artifact.
3. Test an ordinary delegation request as well as an explicit coordinator control. Verify accepted
   work, result return, visible details and reload; do not count work done in Main as a worker pass.
4. Ask a new question while the worker is actually running. Measure completed replies separately
   from useful streaming text, load time and audible speech.
5. Test missing input, unavailable endpoint, permission refusal, route persistence and the precise
   offline boundary. Keep unsupported, rejected, timed out and not-run cases distinct.

No model or serving engine is selected as the default from these bounded samples. Use a newer
native version or another model only after checking its actual harness path; do not infer success
or failure from a different model, a raw API fixture or a small-model benchmark.

## Primary references

- [Codex local-provider options](https://learn.chatgpt.com/docs/cli/reference)
- [Ollama with Codex](https://docs.ollama.com/integrations/codex)
- [Ollama with Claude Code](https://docs.ollama.com/integrations/claude-code)
- [Ollama local-only controls](https://docs.ollama.com/faq#how-do-i-disable-ollama-cloud-features)
- [Qwen3.6 model card](https://huggingface.co/Qwen/Qwen3.6-35B-A3B)
- [Qwen3.8 model card](https://huggingface.co/Qwen/Qwen3.8-27B)

References describe native interfaces. The dated report, not an upstream capability claim, owns
what this project actually tested.
