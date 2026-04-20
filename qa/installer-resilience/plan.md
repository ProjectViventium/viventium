# Installer Production-Readiness Plan

Date: 2026-04-13

## Goal

Make a fresh public install on a new Mac feel aligned, current, and low-friction without requiring
owner-machine leftovers, manual Mongo surgery, or a follow-up AI debugging session.

## Confirmed issue groups

1. Fresh-install product truth can drift behind current nested product truth if the parent component
   pin is stale.
2. Existing installs can keep stale built-in prompt/runtime behavior until an explicit upgrade
   refreshes the pinned nested component checkout; startup reseeding then heals from whatever ref
   is actually checked out.
3. Connected-account chat readiness does not guarantee durable memory readiness.
4. Local conversation recall still depends on local embeddings prerequisites that may be absent on a
   new machine.
5. Cold first boot on a clean Mac is still long enough to feel broken unless the progress contract
   stays extremely honest.
6. Connected-account UI state is currently easier to verify in the browser than through a clear,
   public-safe backend/debug contract.

## Fix plan

### Phase 1. Ship current product truth reliably

1. Keep `components.lock.json` in sync with the reviewed nested LibreChat release whenever shipped
   prompt/runtime behavior changes there.
2. Add a release-gate assertion that a fresh clone/bootstrap seeds the current main-agent identity
   prompt, not a stale nested ref.
3. Add a release-gate assertion that the seeded main agent also carries the intended voice override
   bag, including `voice_llm_model_parameters.thinking: false`.

### Phase 2. Heal existing installs, not just fresh ones

1. Verify `bin/viventium upgrade --restart` always refreshes the pinned component checkout before
   the existing startup seed/upsert path runs.
2. Add a public-safe upgrade QA case that starts from a stale installed agent prompt, runs the
   supported upgrade path, and proves:
   - the nested component checkout moved to the reviewed pinned ref
   - the next startup healed the installed built-in prompt automatically
3. Surface explicit upgrade/start confirmation for both:
   - component checkout refreshed to the reviewed ref
   - built-in agents refreshed from that current source bundle

### Phase 3. Make conversation recall defaults consistent

1. Keep “recall on by default when the machine already supports the local recall path” consistent
   across:
   - base config generation
   - preset normalization
   - Easy Install
   - Advanced setup
2. Preserve explicit user opt-out when a user disables recall deliberately.
3. Add clean-machine QA for both:
   - Docker-capable path -> recall default on
   - no-Docker/no-local-runtime path -> recall clearly deferred with honest guidance

### Phase 4. Make local recall prerequisites frictionless and honest

1. Decide the supported first-run product contract for local recall:
   - either install/provision the local embeddings runtime automatically, or
   - keep recall deferred and explain the exact missing prerequisite clearly
2. If local Ollama remains the contract, preflight/status/install must agree on:
   - binary presence
   - model readiness
   - whether first boot will pull the model
3. Add a clean-machine QA case that proves the user can tell, without guesswork, whether local
   recall is already live or what exact step is still required.

### Phase 5. Close durable-memory acceptance end to end

1. Add a clean-machine QA case with a real connected model account that proves:
   - first chat succeeds
   - memory writer initializes successfully
   - the browser `Memories` panel stops showing `0% used / No memories yet`
   - `memoryentries` becomes non-zero after a memory-worthy exchange
   - a new conversation can recover the stored fact through the supported memory/recall path
2. Keep this separate from same-thread context carryover so the test proves durable memory instead
   of short-lived chat context; an in-thread `SAVED` reply is not sufficient evidence.
3. Fail release QA if connected-account chat works but durable memory remains dead.
4. Add a public-safe observability step that can confirm whether the connected-account-backed memory
   writer is truly initialized, rather than forcing QA to infer it only from UI state.
5. Add a release-gate test for the compiler -> runtime memory-writer provider contract so
   `Provider openai not supported` cannot silently ship again.

### Phase 6. Reduce first-boot friction

1. Break first boot into explicit visible stages:
   - component bootstrap
   - dependency install
   - server package build
   - client build
   - core web surfaces live
2. Investigate whether shipped prebuilt assets or cached build artifacts can remove the repeated
   long client-build wait on clean Macs.
3. Add a clean-machine timing budget report to QA so regressions in cold-start time are visible
   before release.
4. Define a numeric cold-start acceptance threshold after collecting at least three clean-machine
   baseline runs; do not leave cold-start quality as a purely subjective judgment.

### Phase 7. Make connected-account state transparent

1. Provide a public-safe backend/debug surface that confirms whether a user-scoped connected
   foundation account is actually present and usable for runtime initialization.
2. Keep that surface separate from per-user workspace OAuth so QA can distinguish:
   - model reasoning auth
   - Gmail / Google Workspace auth
   - Outlook / Microsoft 365 auth
3. Use that same surface in QA reports instead of ambiguous collection spelunking.

## Acceptance contract before calling the installer “production ready”

1. Fresh public clone in a new directory boots the current shipped prompt/runtime truth.
2. First user can register/login without UI warnings or raw auth errors.
3. `bin/viventium status` tells the truth about missing connected accounts and missing local recall
   prerequisites.
4. A connected model account enables real chat on first run.
5. Durable memory writes successfully, shows up in the user-facing `Memories` panel, and can be
   recovered from a new conversation.
6. Local recall either works on first run or is clearly deferred with exact next steps.
7. No machine-local/private data is required to make the above pass.
