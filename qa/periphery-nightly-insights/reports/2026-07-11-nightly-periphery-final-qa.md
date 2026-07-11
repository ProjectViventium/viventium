# Nightly Periphery Final QA - 2026-07-11
<!-- qa-evidence-exempt: Historical local QA format retained without retroactively inventing evidence; current release acceptance is recorded separately. -->

## Outcome

The private risk-radar pilot is implemented and its full local acceptance path is working:

`bounded private snapshot -> Workbench schedule -> GlassHive Sol/xHigh run -> paired v2 artifact -> callback/ledgers -> optional conscious-agent list/read`

The nightly body is not inserted into ordinary chat, memory writes are off, and the conscious agent
can retrieve a current artifact only when useful. A temporary provider-rate-limit block recovered;
the post-sanitizer browser, expanded-detail, refresh, log, Mongo, crash-recovery, and exact-model
checks now pass.

## What Was Actually Run

| Surface | Actual result |
| --- | --- |
| Private real-account snapshot | PASS: final run selected 120 of 1,219 available recent conversations, included 113 and excluded 7 by structured labels; 1,086 messages, 9 memories, 12 schedules, 50 scratchpads, and 11 existing lens descriptors projected. |
| Real scheduled Workbench run | PASS: the final post-restart run completed in 3m16s through visible Workbench UI. GlassHive executed `gpt-5.6-sol` / `xhigh`; callback and DB both recorded requested xHigh, effective xHigh, no fallback, and successful parent/child completion. |
| Real v2 artifact | PASS: the fresh paired JSON/markdown artifact is current, quality passed with no quality reasons, 3/3 source refs resolved, 9/9 claims grounded, zero ungrounded claims, zero verbatim evidence copies, and zero memory proposal refs. |
| Workbench browser UI | PASS: live definition shows Sol/xHigh, Memory Off, snapshot counts/status, latest completed run, and 17 indexed artifacts (5 passed, 12 legacy). The same state persisted after a stack restart and a deliberate Workbench crash/watchdog recovery. |
| Ordinary conscious chat control | PASS: normal one-sentence conversation made no periphery tool call and did not surface nightly content. |
| Explicit conscious-agent request | PASS before serializer hardening: the visible response called list then read and returned one evidence-grounded, medium-confidence item without storage details in the answer. |
| Expanded tool detail | FAIL then FIX: first browser expansion exposed raw index/storage/run/source metadata. Scheduling Cortex now returns bounded agent-safe serializers. Direct live MCP proof is 2.4 KB list + 2.8 KB read, current quality passed, 9 grounded claims, and zero forbidden storage/run/source keys. |
| Post-sanitizer browser rerun | PASS after recovery and compacting: ordinary chat made no periphery call; final explicit chat made one list plus one newest-per-module read; the answer stayed concise and calibrated; expanded cards exposed no forbidden storage metadata; refresh persisted the conversation and cards. |
| Six model-quality cases | PASS individually on exact Sol/xHigh: material signal, honest no signal, degraded source, medical humility, unlabelled QA noise, and stale correction. |
| Unified six-case repeat | PASS after the final grader change: 6/6 passed from the public command on exact `gpt-5.6-sol` / `xhigh`, zero failed cases, zero ungrounded claims, and zero verbatim private-evidence copies. The earlier usage-limit run remains correctly classified as operational evidence. |

## Root Causes And Fixes

1. **Nightly generation previously failed before useful output.** Persisted model/effort metadata and
   runtime routing could disagree, while the prompt carried too much context inline.
   Fixed with compiled Sol/xHigh precedence, fail-closed routing, projected evidence files, and a
   compact output/evidence contract.
2. **The first private snapshot lacked enough recent conversational evidence.**
   Fixed with a bounded per-user snapshot of recent conversations/messages, memories, schedules,
   scratchpads, run ledgers, and existing lens inventory.
3. **QA/test residue could distort the account corpus.**
   Fixed with private exact-id/structured labels. No runtime prompt keyword classifier and no chat
   deletion were added.
4. **Artifact validation was too shallow.**
   Fixed with schema v2 snapshot binding, resolvable source refs, claim-level grounding counts,
   staleness/quality status, paired markdown validation, and a derived private index.
5. **The conscious agent could not access the new tools.**
   Fixed through reviewed A/B/C agent sync: two read-only tool IDs added, zero removed, main agent
   only, tools-only dry run first, then live pullback with zero drift.
6. **Expanded tool cards leaked internal storage metadata.**
   Fixed at the MCP serializer boundary while preserving the full artifact for Workbench validation.
7. **Old synthetic Workbench DB residue obscured current health.**
   After a private backup, explicit inactive QA definitions and their orphaned versions/runs were
   removed. Product delete now cascades. Current orphan counts are zero.
8. **The eval harness flattened provider failures.**
   It now classifies usage limit, rate limit, authentication failure, timeout, artifact missing, and
   generic model failure separately.
9. **The first safe list still encouraged redundant reads.**
   With several passing artifacts from one module, the model read each before choosing. The MCP now
   lists only the newest current artifact per module, while preserving one bounded historical entry.
10. **Filesystem modification time could choose the wrong newest artifact.**
    Artifact order now uses validated `generatedAt`; touching or restoring an old file cannot promote it.
11. **The live eval command imported the whole Scheduler runtime for three constants.**
    The prompt/schema contract now lives in one dependency-free module shared by Workbench and the
    evaluator, so the public executable works under the machine Python.
12. **Failed runtime validation could still continue into restart.**
    `dev-runtime activate-current --validate --restart` now preserves compiler failures and returns
    before stop/restart on compiler, doctor, or helper-refresh failure. A real invalid-config run
    returned 1 while the API and Workbench PIDs stayed unchanged.

## Automated Verification

- Cross-boundary release group: `393 passed`
- Scheduling Cortex: `110 passed, 6 subtests passed`
- Prompt Workbench: `103 passed`
- Config compiler/settings: `126 passed`
- Install/status summary: `56 passed`
- Memory hardening: `58 passed`
- GlassHive profile runtime: full file passed
- Periphery eval harness: `6 passed`
- Stable dev runtime fail-closed regressions: focused checks passed; real invalid-config PID check passed
- Agent tool declaration and prompt-registry parity: focused checks passed

A broader pre-existing agent-governance group still has nine failures against unrelated active
worktree changes: old provider-tool inventories/model mixes, one main-instruction phrase, and one
GlassHive prompt-extraction helper. The periphery-specific registry mismatch found in that run was
fixed. These nine are not presented as periphery regressions or silently rewritten here.

## Runtime And DB Evidence

- Built-in definition: active, `memoryWriteMode=off`, `glasshive_host`, `gpt-5.6-sol`, `xhigh`.
- Latest Workbench child run: completed in 3m16s with no retry or fallback.
- Parent nightly task: active and successful.
- Orphan Workbench versions/runs: `0 / 0`.
- Scheduling service restarted under its watchdog and returned healthy runtime identity.
- LibreChat MCP connection recovered and fetched the updated Scheduling Cortex instructions.
- Live agent bundle and tracked source match after the tools-only sync.
- Fresh compile, tracked prompt-bearing source, and active generated runtime config now report zero
  drift. Source placeholders are resolved against the compiled runtime environment before comparison,
  so expected transport/OAuth wiring matches while a wrong live MCP URL still fails closed.
- The CLI no longer labels a merely present fallback credential as `Ready`; it reports `Configured`
  until a live provider request proves validity.
- A deliberate Workbench process crash recovered through the stack watchdog with a new healthy PID.
- A failed activation validation no longer stops or restarts the currently healthy stack.

## Residual Limit

The feature acceptance path is complete. One external operational limit remains visible rather than
being misreported as product health:

1. The configured fallback credential is rejected by its provider and needs operator replacement;
   status/error wording is now honest and no credential was fabricated.
