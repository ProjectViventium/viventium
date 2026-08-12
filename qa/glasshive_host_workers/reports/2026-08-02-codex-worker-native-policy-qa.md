# Codex Worker Native Policy And Feeling Authority QA — 2026-08-02

## Result

**PASS for the installed local Viventium product and tracked source.** Public release/commit/pin work
was not requested and remains a separate delivery step.

Viventium Codex workers now deny only the configured conflicting plugin, default native Codex
personality to `none`, carry the current Feeling authority as native developer instructions, and
replace a native session only when present authority or native policy changes. App Server was tested
and rejected for production; it remains disabled.

## Linked Root Cause

- `codex exec resume` preserves the first rollout's developer instruction. Passing a different
  `developer_instructions` value on a resume command changed launch config but did not replace the
  earlier model-visible instruction.
- Worker-local plugin config cannot clean a native session that already loaded the plugin's
  instructions. That session must be superseded at a safe turn boundary.
- Installed Codex App Server accepted experimental `thread/settings/update` calls for three changing
  developer states on one thread, including process restart/resume, but all three turns followed the
  first state. Settings metadata was therefore stale model authority.
- The official App Server documentation and installed schema also expose per-turn
  `turn/start.collaborationMode.settings.developer_instructions`. A live two-turn probe produced the
  quiet marker on turn one but ignored the changed joyful instruction on turn two. This documented
  field therefore also failed current-authority QA on the installed build.
- Developer-role `thread/inject_items` made a later state model-visible, but the API appends and
  persists the new item beside the old one. It is not current-only replacement.
- No evidence linked project `AGENTS.md` to the defect. The causal boundary was native role/state
  transport and native-session persistence. The active workspace instructions were reviewed
  privately and contained no competing personality state.

## Implemented Contract

- `plugin_denylist` accepts canonical exact plugin IDs. Suppression is written only to worker-local
  Codex/Claude native config; global user plugin config and model prompts are unchanged.
- Codex launch rereads the materialized config and fails closed unless every configured denial is
  `enabled = false`.
- Viventium compiles `codex_personality=none`; standalone GlassHive still inherits unless explicitly
  configured. `friendly` and `pragmatic` remain supported explicit options.
- The provider combines current `system` and `developer` content, deduplicates it, stores only its
  hash in session metadata, and materializes the exact snapshot as worker-local Codex
  `developer_instructions`. Higher-authority content is excluded from the user instruction.
- Present changed authority or native policy serially terminates the old worker, starts exactly one
  replacement, and seeds complete visible non-authority history. Present unchanged authority resumes.
  Absent authority on Phase B carries the pinned state forward and also resumes.
- The opt-in App Server probe now exercises the documented per-turn collaboration-mode field and
  fails closed unless both changing instructions and terminal events pass. It remains false on the
  installed build. Production stays on `codex exec` until a bounded App Server mechanism passes.

## Installed Product Evidence

- Canonical config compiled to:
  - plugin denylist: only `viventium-feelings@project-viventium`
  - Codex personality: `none`
  - App Server QA: `false`
  - Viventium host model/effort: `gpt-5.6-sol` / `xhigh`
- The supported config compiler regenerated runtime output; the installed runtime restarted from the
  active checkout and `/health` returned `200`.
- Worker-local Codex config proved:
  - the denied Feelings plugin was disabled
  - twelve unrelated installed plugins remained explicitly available
  - personality was `none`
  - current developer instructions matched the pinned provider snapshot
- Four live provider turns exercised quiet state, changed joyful state, unchanged joyful state, and a
  Phase-B turn with no repeated state. All returned the expected synthetic marker.
  - the changed-state turn terminated and replaced the first worker
  - changed, unchanged, and Phase-B turns then shared the replacement worker
  - all four persisted run instructions excluded higher-authority text
  - all requests and runs reached `completed`
- A real authenticated Viventium browser turn returned exactly `UI_GLASSHIVE_OK`. The matching
  GlassHive provider request returned `200`, persisted as completed, and used the intended host worker.
- Runtime log review showed normal startup/health and successful chat-completion requests with no
  traceback or error for the tested path.
- After the helper restarted the local stack, a fresh installed-runtime turn again returned the
  exact current-state marker. Its worker config still proved personality `none`, the one exact plugin
  denial, twelve unrelated plugin entries retained, and exact current developer instructions.

## Quality And Performance

Quality passed the relevant contract: exact outputs, native developer authority, one authoring worker,
visible-history continuity, plugin isolation, supported native personality, and real UI plumbing.

| Live path | Native/provider duration |
|---|---:|
| Initial post-change state | 3.95 s |
| Changed state with required replacement | 5.05 s |
| Unchanged state, same worker | 5.62 s |
| Phase B with absent repeated state, same worker | 4.39 s |
| Real Viventium browser turn | 6.09 s native / 6.31 s provider |
| Fresh post-restart installed turn | 6.05 s native / 6.39 s provider |
| Six-turn unchanged-state sample | 4.14 s native median / 4.39 s provider median |

The pre-change two-turn native sample was 6.61 s then 4.68 s. The post-change sample shows no detected
latency regression. In the six-turn sample all six outputs were exact, all requests completed on one
worker, provider latency ranged from 3.39–8.17 s (4.39 s median), and native execution averaged 4.59 s.
Six turns are still too few for a stable production p95 claim. The durable performance improvement is
structural: unchanged and Phase-B turns no longer pay unnecessary worker replacement/cold-start cost.
Changed authority intentionally pays one serial replacement for quality.

## Automated Verification

- Active installed checkout compiler suite: `181 passed`.
- Public checkout scoped compiler/wizard/probe suite: `175 passed`.
- Complete affected GlassHive conversation-provider and host-profile suites: PASS in both tracked and
  installed checkouts.
- Python compilation and scoped whitespace/error checks: PASS.

## Not Run / Boundaries

- The real browser response and backend persistence were verified; a post-response browser refresh
  was not needed for this runtime transport change and was not run.
- No public commit, nested-component push, parent pin update, or release artifact was created.
- No upstream issue, outreach, or socialization was performed.
- Claude review was unavailable because the local account reported its usage limit; it was not used
  as a substitute for code, config, UI, log, or DB evidence.
