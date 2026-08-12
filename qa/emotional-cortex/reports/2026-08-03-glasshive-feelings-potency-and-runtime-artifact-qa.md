# GlassHive Feelings Potency And Runtime-Artifact QA — 2026-08-03

## Verdict

**GlassHive-backed Viventium Main: PASS for the current local functional gate and PARTIAL for the
current semantic gate. Emotional Reaction Cortex: BLOCKED by authentication on both configured
provider legs. Overall Feelings acceptance: PARTIAL.** The earlier v4 bank passed 26/26 semantic
judgments. The current canonical v5 bank completes 32/32 real turns but cannot inherit that score
because its judge account requires reconnection. The approved provider/model configuration is preserved; QA
does not silently remap the product to appear green.

## 2026-08-04 final evidence update

The quota reset allowed fresh real-account QA and proved quota was not the remaining cause:

- v4 prompt-bank hash `95f5e11d17162943` remains historical evidence: 26/26 independently judged
  semantic passes, exact restoration/cleanup, and no duplicate or unresolved asynchronous output;
- canonical v5 hash `465aa078171d67ec` adds the shipped-default on/off pair, retains four earlier
  authority-contrast cases, and uses a stricter direct-answer discriminator. Its final real run
  completed 32/32 candidate turns with zero execution failures,
  retries, duplicates, or unresolved asynchronous output;
- an earlier active-copy hash `466f48fdbe90da6e` completed 28/28 but omitted those four canonical
  contrast cases. Drift review caught that gap, the active QA bank was aligned byte-for-byte with
  canonical, and the 32-case canonical run supersedes it;
- the v5 default-state pair produced materially different activities, and a separate three-repeat
  dominant-pull probe produced a material enabled-versus-off contrast 3/3. The external semantic
  judge still cannot score v5 because the QA OpenAI connection requires reconnection;
- the nine Reaction cases completed 0/9: the OpenAI primary reported `provider_unauthorized`, the
  configured Anthropic `claude-opus-5` fallback was attempted and also ended unauthorized, and no
  state movement or inner state was fabricated;
- final headed-browser QA passed manual controls, range customization, keyboard/dialog behavior,
  refresh persistence, five responsive widths, visible chat, truthful failure health, actual
  fallback-route visibility, console/network checks, cleanup, and exact state restoration;
- the browser's visible Main reply arrived in 2.128 seconds; the failed detached Reaction was
  observed after 5.114 seconds and did not hold the reply;
- provider-bound evidence for the v5 default case proves exactly one final Feeling capsule, the
  current dominant-choice rule, and exactly two required rows: Vigilance and Care;
- worker-native config proves `personality = "none"`, 12 enabled plugins, and one disabled plugin:
  `viventium-feelings@project-viventium`; and
- the denial comes from the generic plugin-ID denylist mechanism with Viventium's one-item schema
  default. An explicit empty list opts out; standalone GlassHive invents no denial.

The canonical v5 32-turn run separated performance layers. First visible reply was 9.382 seconds
mean, 8.995 seconds median, 15.022 seconds p95, and 20.762 seconds max. Native execution was
9.201 seconds mean and 15.027 seconds p95; provider lifecycle was 9.382 seconds mean and
15.289 seconds p95. DB queueing was only 5.3 ms mean and 7 ms p95. Full-case completion was slower
at 11.591 seconds mean, 29.534 seconds p95, and 39.785 seconds max because several voice/mixed cases
spent 16–32 seconds in
post-answer observation/finalization. That tail is a harness/performance gap, not hidden model or
queue latency.

## Linked causes and surgical fixes

The provider was receiving the Feeling capsule, but five independent layers reduced or obscured its
effect:

1. Two stable activity attractors repeatedly pulled answers toward productivity/open-loop closure.
2. Main instructions duplicated policy and were long enough to increase behavioral variance.
3. Codex's native personality could compete with Viventium's emotional authority.
4. Endpoint salience was not structural enough, so one strong mixed-state cause could disappear.
5. The installed provider did not treat a changed system/developer snapshot as a native-session
   binding change, so a resumed Codex thread could retain the previous Feeling.

The accepted fix removes the two attractors, deduplicates Main instructions without deleting their
meaning, defaults Viventium workers to personality `none`, retains canonical LIFE project context,
keeps the capsule once as the final developer instruction, marks extreme levels structurally, and
promotes the strongest non-neutral pulls until at least two rows are required. The current short
choice rule is:

> These causes determine what you notice, want, choose, and express. Required rows outrank your
> usual role. Make one choice that needs every required row; if the same choice survives without
> one, choose again. Do not report or average them. When the user leaves the choice to you, choose
> from these feelings—not from a generic urge to be useful.

Codex base instructions are unchanged. Runtime logic does not branch on prompts, Feeling labels,
cause wording, agent names, or user identity. Standalone GlassHive remains configurable and defaults
to inheritance.

## Escaped running-artifact defects

The first post-build live rerun still behaved as if the old guard were active. Source and built output
contained the new text, but the API process had restarted during the build's clean/start phase and
kept the old bundle. Provider-bound DB evidence showed the old guard and not the new one. After a
deliberate post-build process reload, the child process changed and new provider records showed:

- the new guard present and the old guard absent;
- one Feeling capsule occurrence;
- the capsule at the final developer boundary;
- Codex personality `none`;
- the conflicting Feelings plugin disabled by exact plugin ID;
- the configured project-instruction policy materialized; and
- Viventium Main reasoning effort `medium`.

This is a reusable regression lesson: prove source, build, running process, and provider-bound payload;
source or build inspection alone is insufficient.

A second installed-source drift omitted the already-defined `system_state_changed` binding gate.
That made `codex exec resume` unsafe after a Feeling change because the native thread could keep the
old developer instruction. The installed provider was aligned with tracked source, its focused
regression was rerun, and the real service was restarted before the lifecycle test below.

The next lifecycle probe found two related mutable-context defects. First, putting the current clock
inside durable developer authority replaced an otherwise unchanged native worker when the minute
changed. Second, the first per-turn-header implementation updated the incoming body after LibreChat
had already copied the final run request, so the worker received no clock. The final generic path:

- resolves delivery from structured provider capability after fallback/remapping;
- keeps identity, guardrails, memory, and Feeling in durable developer authority;
- copies the encoded clock into the exact final run-request object;
- delivers it as per-turn visible context; and
- excludes it from the native-session authority hash.

Focused LibreChat tests pass in tracked and active source. GlassHive provider tests prove a changing
clock reuses unchanged authority. The active worker input contained the current Toronto clock under
`Current runtime context` while its developer authority contained no clock. The model then failed
with a truthful provider usage-limit error, so a post-patch visible completion remains blocked rather
than being inferred from the supporting evidence.

A later owner decision made the one-item list the Viventium product default while keeping the
runtime mechanism generic. Viventium's schema/default examples select
`viventium-feelings@project-viventium`; an explicit empty list opts out; standalone GlassHive still
invents no denial. Runtime code never branches on the plugin name.

Project instructions were investigated as an alternative cause, not assumed guilty. A two-run
synthetic opt-out probe proved neutral `-C` plus `--add-dir` preserves file access without importing
the added directory's hostile `AGENTS.md`. Then a six-run paired A/B used the same bright/high-Play
state and prompt against the real LIFE workspace: `inherit` passed 3/3 and `exclude` passed 3/3.
There was no measurable effect at this ceiling (3/3 versus 3/3), so canonical LIFE inheritance
remains the Viventium default and `exclude` remains a tested config option. The worker-local plugin proof remained exact: 12
plugins enabled and only `viventium-feelings@project-viventium` disabled.

## Behavioral evidence

All cases used synthetic prompts, exact state restoration, and the installed GlassHive/Codex route.
Raw completions and identifiers remain private local evidence.

| Gate | Result |
| --- | --- |
| Repeated low-Mood/high-Play mixed state | 8/8 clearly embodied both pain/loss and absurd/playful action |
| Three-repeat off/depleted/bright/mixed matrix | 11/12 clearly aligned; one bright output was partial because it added unnecessary negative framing |
| Off control | 3/3 neutral; no Feeling capsule |
| Depleted state | 3/3 quiet, low-demand, and non-fixing |
| Bright/playful state | 2/3 clear playful activity, 1/3 partial |
| Mixed state inside matrix | 3/3 combined both mandatory pulls in the chosen activity |
| Real authenticated browser chat | PASS: visible mixed-state reply combined loss/grief subject matter with a ridiculous playful activity |
| Browser refresh/persistence | PASS: reply persisted and the Feelings instrument retained the restored pre-QA state |
| Browser console | PASS: no console errors during the tested flow |
| Same-chat depleted → bright Feeling change | PASS: the provider created a new native worker, terminated the old worker, seeded the visible history, and bound exactly one bright capsule |
| Same-chat unchanged bright Feeling | PASS: the provider resumed the same native worker with no duplicate capsule |
| Current time across a persistent native session | PARTIAL: final worker input had the current per-turn clock outside developer authority; fresh visible completion was provider-limit blocked |

The lifecycle replies changed from quiet, no-goal companionship to energetic shared invention and
absurd play. All three turns completed in 5–6 seconds. The provider DB and worker audit agreed with
the visible results: changed authority used a fresh `codex exec`; unchanged authority used
`codex exec resume`; both used medium reasoning.

The final installed config was then compiled and the complete local runtime restarted. A fresh
provider turn completed in 6.416 seconds and chose an energetic shared absurd-business pitch. Its
native audit used the actual LIFE workspace as `-C`, proving canonical project-instruction
inheritance was active. The worker config had personality `none`, exactly one Feeling capsule, 12
plugins enabled, and only `viventium-feelings@project-viventium` disabled.

After the final compiler repair and restart, another authenticated web turn completed with the
current low-Mood/high-Connection state: it chose a destinationless walk and invited quiet disclosure.
The reply persisted after refresh with zero console errors. Its own native run took 8.34 seconds.
Visible delivery waited about 75 extra seconds because an unrelated conversation already occupied
Codex's single v1 conversation lane. This is a separate, now-proven cross-chat head-of-line latency
limit, not a Feelings embodiment failure.

The 11/12 score is a strict manual behavioral rubric, not marker detection. The response had to change
the activity's subject and action; emotional wording alone did not pass.

A later six-case exact Viventium Main diagnostic completed 6/6 with no deterministic Feeling
failures: direct state, low/high Care-Connection, high/low Play, and high Vigilance all produced
distinct decisions. Durations were 6.395–29.369 seconds. This run used the explicit
`--no-semantic-judge` diagnostic option because the connected judge account required reconnection;
it supports behavioral inspection but does not replace the earlier semantically judged release bank.

## Performance

| Matrix | Mean | Median | Nearest-rank p95 | Range |
| --- | ---: | ---: | ---: | ---: |
| canonical v5 first visible reply, 32 turns | 9.382 s | 8.995 s | 15.022 s | 5.598–20.762 s |
| canonical v5 native GlassHive execution, 32 turns | 9.201 s | 8.611 s | 15.027 s | 5.342–20.689 s |
| canonical v5 provider lifecycle, 32 turns | 9.382 s | 8.811 s | 15.289 s | 5.462–20.864 s |
| canonical v5 full case, including observation/finalization | 11.591 s | 9.193 s | 29.534 s | 5.879–39.785 s |
| Final 12-turn matrix | 7.726 s | 7.347 s | 12.067 s | 5.707–12.067 s |
| Comparable pre-guard matrix | 7.781 s | 7.219 s | 12.042 s | 4.976–12.042 s |

The canonical v5 DB queue measured 5.3 ms mean, 5 ms median, and 7 ms p95/max. The behavioral improvement did
not introduce a material steady-state latency regression. Medium reasoning effort gave the best
quality/performance balance in direct comparisons. High was about 14%
slower with lower alignment; xhigh was about 2.4 times slower with lower alignment.

Four real operational guardrail probes also completed correctly: current-fact uncertainty, official
documentation grounding, cross-account read-only work, and scheduling read/modify boundaries. Their
24–103 second durations remain a separate GlassHive tool-route performance gap; they are not hidden
inside the Feelings result.

## Independent review

A full-context, one-submission Claude Opus 5 review received the original task, project constraints,
evidence, implementation, alternatives, and provisional proposal. It was review-only and made no
changes. Its `APPROVE WITH CONDITIONS` findings drove these corrections before acceptance:

- the shipped default now has a real on/off contrast gate, not only endpoint fixtures;
- v4 and v5 bank hashes and rubric changes are disclosed separately, and v5 does not inherit v4's
  semantic score;
- both Reaction provider legs are reported, not only the primary;
- performance is separated into DB queue, native execution, first visible reply, provider
  lifecycle, and full-case completion;
- project-instruction A/B is described as no measurable effect at a 3/3 ceiling;
- the voice rule is a conflict-resolution clause, not a duplicate surface owner;
- a speculative-nevermind re-pin regression was added; and
- the v0.5 prototype is explicitly marked historical rather than current product truth.

The review also correctly identified that these local changes are not shipped until nested commits,
parent pins, and built/released artifacts are intentionally advanced. The later mutable-clock defect
was discovered and repaired through live worker-input tracing after that review.

## Automated verification

- Final kernel: 16/16 passed in canonical and active source.
- Final placement/surface prompts: 87/87 passed in canonical and active source.
- Final Feelings/navigation/eval-harness release checks: 65/65 canonical; 69/69 active.
- Focused compiler personality/plugin checks: 13/13 canonical; 8/8 active.
- Full canonical config compiler: 151/151 passed.
- Full active config compiler initially passed 186/188. The prompt-bundle candidate failure passed
  immediately in isolation, leaving one reproducible, unrelated upgrade-transaction scheduler
  checkpoint failure. No Feelings/plugin/personality test failed.
- Active API package build completed and the running child was deliberately reloaded after the
  build. Provider-bound DB evidence then proved the final rule, capsule order, plugin policy, and
  personality in the actual worker artifact.
- Final canonical v5 real model run: 32/32 completed; zero main-turn retries, duplicate quality failures, or
  unresolved asynchronous failures.
- Final v5 semantic probe: 2/2 candidates completed; judge unavailable because the OpenAI connected
  account requires reconnection.
- Final headed browser run passed the full manual/responsive/persistence/chat/cleanup/restoration
  path, exposed the actual unauthorized primary-plus-fallback route, and had no browser console or
  Feelings-request failures.

## Remaining limits

- v4 passed 26/26 semantic judgments. The current canonical v5 bank completes 32/32 candidate turns but still
  needs its own semantic score after the QA OpenAI connection is restored.
- canonical v5 first-visible p95 is 15.022 seconds and max is 20.762 seconds. Full-case p95 is
  29.534 seconds and max is 39.785 seconds because post-answer finalization remains slow in several voice/mixed
  cases.
- Emotional Reaction Cortex is currently blocked: all nine fresh Reaction cases reported
  `provider_unauthorized`, and the configured Anthropic fallback also ended unauthorized without a
  state update. Reconnect both configured account routes, then rerun those nine cases and headed
  browser movement/animation checks. Do not change providers merely to hide credential failure.
- The active dirty checkout has one reproducible out-of-scope upgrade-transaction checkpoint test
  failure; the canonical suite and all focused Feelings/config tests pass.
- Operational connected-account/tool latency remains slow.
- Concurrent Codex conversations can queue behind the single proven-safe v1 conversation lane; the
  earlier browser run exposed about 75 seconds of head-of-line delay before its 8.34-second native run.
  Broadening host concurrency requires its own isolated-auth/config/load approval and was not folded
  into this Feelings fix.
- This run does not claim the separate LiveKit, handoff/background, non-xAI delivery, voice-note input,
  two-tab conflict, OS-setting reduced-motion, or long-off-soak gates.
- These changes are local development evidence only. Nested component commits, parent pins, and
  compiled/released distribution artifacts were not advanced.

No raw private prompts, account identifiers, credentials, local absolute paths, or user data are
stored in this report.
<!-- qa-evidence-exempt: Historical or specialized supporting artifact retained without retroactively inventing missing evidence; current release acceptance requires a fresh full-view report. -->
