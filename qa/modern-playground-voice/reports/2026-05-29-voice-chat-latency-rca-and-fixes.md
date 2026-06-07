<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# Voice + Chat Latency RCA and Fixes QA Run - 2026-05-29

## Summary

- Result: PARTIAL (P1-P4 delivered + tested; P5 foundation delivered + tested, core wiring in progress)
- Build/source under test: LibreChat fork `packages/api` + `api/server` (rebuilt dist; nodemon-loaded server)
- Runtime/artifact under test: local native runtime (api on `127.0.0.1:3180`, frontend `3190`), connected-account (Anthropic OAuth subscription) auth
- Environment: local dev gate; deep-timing instrumentation (`VIVENTIUM_TIMING_DEEP`) used during capture
- Tester: Claude (owner-delegated QA)
- Related change: evidence-based latency RCA + P1 opus-4.8 support, P2 OAuth fast path, P3 thinking telemetry, P4 non-blocking recall verify, P5 speculative-detection foundation

## Root cause (evidence-based; disproven hypotheses recorded)

Method: surface-neutral per-turn deep timing added across init/memory/recall/provider stages, plus a
direct, faithful Anthropic call (connected-account token, Claude Code system + OAuth betas,
`maxRetries=0`) that bypasses all app overhead to isolate model vs our-path latency.

Proven NOT the cause (stop chasing):
- Saved memory + conversation recall: in-app first-token ON vs OFF was effectively identical
  (~3.12s vs ~3.10s). Memory read ~1ms; recall init ~50-80ms when the RAG sidecar is healthy.
- Input/tool/prompt mass: a direct call with ~6,300 input tokens reached first token FASTER than the
  same call with ~22 tokens. Tool/prompt trimming does not move TTFT.
- "Switch the main model to a lighter one for speed": on this subscription, direct first-token for
  the larger model (~1.0s) was FASTER than the lighter one (~1.3-2.5s, with cold spikes). A
  model-swap-for-speed makes it worse.

Confirmed, ranked:
1. Reasoning/effort on chat: direct A/B showed thinking adds ~0.9-1.25s before the first SPEAKABLE
   token; with high effort + a large system prompt, one turn reached ~15s of pre-speech reasoning.
   (Owner resolved by config: main agent thinking disabled; voice already exempt.)
2. Cortex activation-detection gate: blocks the first token for ~0.6-1.3s on text chat under a 2s
   budget (`VIVENTIUM_CORTEX_DETECT_TIMEOUT_MS`, default 2000). Targeted by P5.
3. Raw subscription TTFT floor (~1.0s larger model) — not our wiring; only per-turn credential
   decrypt + a near-expiry refresh were ours.
4. Intermittent multi-second spikes: a second account with a broken refresh_token caused a
   synchronous OAuth-refresh fan-out across main + cortex inits (one failing network round-trip per
   init). The primary account's token was valid. Targeted by P2.
   (The `response.output is not iterable` stream error was already fixed upstream of this work;
   the failing `google_workspace` MCP is off the turn critical path.)

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `LAT-P1-opus48` | PASS | model picker + agent run; direct probe first-token ~1.07s; live completion streamed; no `ILLEGAL_MODEL_REQUEST` | Added `claude-opus-4-8` to endpoint inventory + token maps (1M context / 128k out); governance contract suite unaffected |
| `LAT-P2-oauth-fastpath` | PASS | 107 anthropic specs + 4 new (3 broken-token inits -> 1 fetch); live smoke clean | Non-blocking near-expiry refresh + negative-cache; preserves "preserve current token" persist contract; flag `VIVENTIUM_ANTHROPIC_OAUTH_FAST_PATH` (default-on) |
| `LAT-P3-thinking-telemetry` | PASS | `node -c` OK; `callbacks.spec.js` green in full api suite | `model_first_thinking_delta` pairs with `model_first_delta` (gap = reasoning time); gated by deep timing |
| `LAT-P4-recall-verify-nonblocking` | PASS | 21/21 rag specs (3 new: hang->`<1s` source-only; fast->verify+cache; flag-off->blocking); live smoke clean | Short-deadline race + cached verified-ids + background refresh; healthy sidecar still synchronous (invariant preserved); flag `VIVENTIUM_RECALL_VERIFY_NONBLOCKING` (default-on) |
| `LAT-P5-foundation` | PASS | 27 unit tests + full api regression (3141 tests) green; client.js +118 additive (OFF byte-identical) | Flag + fail-closed direct-action gate + commit/abort decision primitives; original isolation seam VERIFIED broken (would double-bill) and not shipped |
| `LAT-P5-core-wiring` | IN PROGRESS | isolated-worktree implementation with no-double-bill proof obligations | Separate handler set + isolated stream sink (late-recovery pattern) + dedicated abort controller |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `LAT-UC-001` | Send chat "hello", memory+recall ON vs OFF | Browser chat (3190) | PASS | Reply both states; ~no first-token delta | deep-timing first-delta ~3.10-3.12s both | none (root cause is elsewhere) |
| `LAT-UC-002` | Run a completion on an opus-4.8 agent | Browser chat (3190) | PASS | Streamed reply, no model error | agent model=`claude-opus-4-8`; validateAgentModel accepted | none |
| `LAT-UC-003` | Chat turn through connected-account after OAuth fast-path change | Browser chat (3190) | PASS | Clean reply, no auth error | error log: no new OAuth/anthropic errors | none |
| `LAT-UC-004` | Chat turn exercising transcript recall verify after non-blocking change | Browser chat (3190) | PASS | Clean reply | transcript verify ran through non-blocking helper | none |
| `LAT-UC-005` | Voice call latency end-to-end with new fixes | Voice playground (3300) | BLOCKED/PARTIAL | not re-run this pass | prior voice traces; voice reasoning already disabled in config | run after P5 + a durable deep-timing flag |

## Traceability

- Feature: voice/chat first-token latency + connected-account reliability
- Requirement: remove architectural/avoidable delays without forking surface behavior (parity) and without breaking the connected-account or recall-correctness contracts
- Use case: a simple chat/voice turn should not pay seconds of avoidable wait
- QA case: `LAT-P1..P5` above
- Expected result: measurable removal of avoidable waits (recall block, OAuth fan-out) + new model support + telemetry, all flag-gated and regression-clean
- Actual evidence: unit suites (anthropic 107+4, rag 21, P5 27, full api 3141) green; live smokes clean; direct probe isolation
- Remaining gap: P5 core wiring (single-delivery/no-double-bill proof in progress); voice end-to-end re-run; durable deep-timing flag for before/after capture

## Regression cases promoted
- OAuth fan-out: `oauthSubscription.spec.ts` — N broken-token inits must produce 1 fetch (no fan-out).
- Recall degraded sidecar: `rag.spec.ts` — hung sidecar must return within the short deadline (source-only), not block.
- Speculative detection gate/decision: `speculativeParallelDetect.spec.js`.

## Notes / residual risk
- All four shipped fixes are additive + behind default-on/revertable flags; OFF paths verified byte/behavior-identical.
- Public-safety: this report contains only timings, counts, flags, and conclusions — no tokens, account identifiers, conversation/message IDs, or private content.
