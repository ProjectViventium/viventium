# Handoff — GlassHive Claude-Code Worker, Connected-Accounts, Broker Fixes

Date: 2026-05-29
Engagement: audit + remediation of the prior "Codex session" GlassHive capability-broker work,
then switching the GlassHive worker to Claude Code and proving result quality + speed like a user.
Hard constraint throughout: **local only — nothing pushed or changed on any cloud / enterprise VM.**

This doc is the single source of truth for the engagement: every decision, learning, change (why /
where / how / what), the current state, what's next, and the gotchas that will bite the next person.

---

## 0. TL;DR

- **Connected accounts stay UNDER GlassHive** (broker/worker or the dedicated hand-off agent), never as
  direct provider tools on the main agent. Reaffirmed and enforced.
- **GlassHive worker is now Claude Code** (`claude-code`, sonnet-4-6) by default — codex weekly credits are
  exhausted and Claude is ~2.5–3.4× faster here. Set durably (config + runtime preference), enterprise-safe.
- Found and fixed **two real interop bugs** that blocked the Claude worker: (1) macOS Keychain auth
  ("Not logged in") and (2) MS365/Outlook unreadable for strict MCP clients (`structuredContent`).
- Measured the Claude worker like a user: **88–144s** (vs codex **301s**), both inboxes, prioritized +
  actionable. Timing is the agentic loop, not startup.
- **Diagnosed** two quality issues the user raised (workspace_wait result noise; a dropped real item) and
  designed **universal** (non-overfit) fixes — instruction/contract level. **Not yet implemented** (awaiting go).
- Enterprise (AITP/Maisy/Panorad) uses docker workers + provider-route auth, not Keychain — both fixes are
  compatible; the local default does not leak there.

---

## 1. User decisions (governing constraints — do not re-litigate)

1. **Connected accounts under GlassHive only.** Google / MS365 must be reached via the GlassHive
   broker/worker or the dedicated hand-off agent — never as direct provider MCP tools on the main Viventium
   agent. (A direct-tools attempt was tried and explicitly **rejected**; reverted.)
2. **No low-tier models.** Never GPT-mini / Haiku-class. Use Opus/Sonnet-tier or frontier models. (Sonnet-4-6
   is acceptable — not low-tier.)
3. **Results quality is the core metric, not just speed.** Recorded verbatim in `01_Key_Principles.md` §0 and
   `AGENTS.md`: *"outcome = Quality (Intelligence, Relevance, Usefulness, Alignment) + Performance (Fast,
   Smooth, Reliable) are the core metric of the viventium project that we must always evaluate in tests, QA,
   development, design."*
4. **PARITY, not routing rubrics.** Do **not** hardcode "quick rundown → hand-off; full sweep → worker."
   Both paths must independently meet the metric on their own AI. The Main Agent / user decide the *shape*;
   GlassHive's job is **truth and completeness**; the worker's intelligence decides the shape. Do not impose
   ranking/urgency/schema rubrics on the worker — pass user adjectives through and trust the worker's path.
5. **Codex credits exhausted → use Claude.** Temporarily switch the GlassHive worker to Claude Code CLI;
   measure metrics for the comparison. Revert to codex when credits return.
6. **Claude Code is the default/preferred GlassHive worker going forward** (this turn's explicit decision).
7. **Enterprise must stay respected + reliable**, but **no cloud changes** — only verify rules / compatibility
   / features for enterprise and make sure local fixes don't break it.
8. **Claude owns QA.** Drive browser / playground / logs / Mongo QA directly; don't hand manual re-testing
   back to the owner.
9. **Take down local Viventium if needed** to gather real data, evidence, logs, real user use cases.
10. **Store learnings / values / decisions in docs** so they don't drift across sessions (this doc + the
    requirement/QA docs below).
11. **Prefer instruction-level / surgical fixes** over runtime heuristics; never overfit to a specific MCP,
    provider, prompt, or one machine.

---

## 2. My learnings (root causes, measurements, mechanisms)

### 2.1 The Claude-code worker auth failure was an env-strip, not setsid or Keychain access
- Symptom: claude-code GlassHive worker exited in ~15–20 ms with `"Not logged in · Please run /login"`.
- The macOS `claude` CLI uses **login-Keychain OAuth** (`Claude Code-credentials-*` items), resolved **by
  user**. The GlassHive host runtime builds the worker subprocess env from a small allowlist (`_host_env`)
  that **dropped `USER`/`LOGNAME`** → claude couldn't resolve its Keychain item → "Not logged in".
- Codex is immune: its auth is a portable file (`~/.codex/auth.json`) the runtime copies into the worker.
- Isolation matrix (proven, not guessed): full env + `start_new_session=True` (setsid) **works**; stripped
  env fails **with and without** setsid; adding `USER` alone fixes it. So **setsid was a red herring**; the
  env strip was the cause.
- The macOS helper is a GUI/`LSUIElement` app (user Aqua session → Keychain access), so its child runtime
  has Keychain access; the original failure was the env strip alone. The fix is therefore the complete fix
  for the helper-launched runtime.

### 2.2 MS365/Outlook was unreadable for the Claude worker due to MCP `structuredContent` shape
- Symptom: `expected record, received array at structuredContent` on every `list_mail_messages` call;
  Outlook silently missing from the Claude worker's result.
- Root cause: the broker route returned `structuredContent: result` unconditionally. MS365 returns an
  **array**, but MCP requires `structuredContent` to be a JSON **object**. Claude's **strict** MCP client
  rejected it; codex's **lenient** client tolerated it — which is exactly why **only codex ever got Outlook**.
- No broker tool advertises an `outputSchema`, so `structuredContent` is optional. Fix: emit it only for
  plain objects; arrays/scalars ride in the `content[0].text` block (codex already consumes that).

### 2.3 Claude-worker performance: it's the agentic loop, not startup
- For a representative 128 s run (claude-code sonnet-4-6, host): **~100 s model inference across 11 agentic
  turns** + **~28 s tool execution** (broker → Gmail/Outlook + workspace setup) + **~0 s spawn** (host).
- Metrics from the run: `duration_ms 128450`, `duration_api_ms 100407`, `num_turns 11`,
  `output_tokens 5975`, `cache_read 267332`, `cache_creation 35816`.
- 88–144 s spread across 3 runs is driven by **prompt-cache warmth** and **output verbosity** (see 2.4),
  not cold/warm container state (host spawn is ~0 s; the Main Agent dispatches a *fresh* worker per request
  — it did not auto-`workspace_continue` even on "check again").

### 2.4 Prompt-cache + output verbosity (plain)
- **Prompt-cache:** the worker context (system prompt + CLAUDE.md + `.mcp.json` + tool defs + accumulated
  tool results) is large (~267 K tokens here). Anthropic caching lets each turn *read it from cache* rather
  than reprocess it. Warm (re-run within ~5-min TTL) → mostly cache hits → faster; cold (first run / expired)
  → cache *creation* (full processing) → slower. Most of the 88-vs-144 gap.
- **Output verbosity:** wall-time is dominated by *generating* tokens (sequential decode). More reasoning +
  longer report + more tool-call args = more output tokens = slower. The 88 s run simply wrote less.

### 2.5 Worker → Main-Agent result: noise + a completeness blur (the user's two worries, root-caused)
- **Noise:** the `workspace_wait`/`workspace_status` MCP result returns ~25 fields **plus three full
  run-record dumps** (`run`, `requested_run`, `latest_run`) wrapping the actual answer (`output_text` is one
  small field). That is plumbing noise to the Main Agent (opus handled it, but it's real, worse for lighter
  models).
- **Completeness:** the worker self-truncated to "top priorities" and the Main Agent surfaced that verbatim,
  so a **real pending reply** (an Outlook intro-follow-up) never reached the user. Root cause is a
  division-of-labor blur: the worker decided *shape* **and** dropped *items*.
- Both are **universal** (not MS365/Google/prompt-specific). The fix keeps PARITY but separates
  **truth+completeness** (worker surfaces the complete actionable set; don't silently drop a real item) from
  **shape** (the Main Agent — which now has injected memory + conversation context — does the concision and
  drops already-done items). That yields the focused output the user liked **without** missing real items.

### 2.6 Enterprise (AITP / Maisy Dev / Panorad) deployment model
- Enterprise runs **docker** workers (`host_worker.enabled` is forced false when azure-enterprise is on) with
  **provider-route auth**: Codex→Azure OpenAI Responses, OpenClaw→Portkey, Claude→Anthropic/Portkey API key
  (`ANTHROPIC_API_KEY`/`ANTHROPIC_BASE_URL`). **Not** macOS Keychain.
- Enterprise default worker is `codex-cli`; allowlist `codex-cli,openclaw-general`. **Claude-code is installed
  but deliberately not advertised** because the Anthropic/Portkey credential currently returns invalid-key.
- Source: `/Users/adri/Documents/AITP/Projects/GlassHive/CURRENT_STATE_AND_EXPECTATIONS.md` (client-private;
  do not copy names/domains/resource IDs into public GlassHive docs).

### 2.7 Repo / process learnings
- Three git repos are in play (see §5). The **GlassHive repo** (`viventium_v0_4/GlassHive`) is full of the
  prior Codex session's **uncommitted** work; my one-line auth fix is layered on top and must not be bundled
  with that unowned work (see §4.3).
- The GlassHive runtime is launched by the macOS helper (GUI session). When relaunched from an interactive
  shell it inherits Keychain access; relaunching by hand risks broker-secret drift (the broker/callback
  secrets are deterministic, sourced from `runtime.env`).
- Agent-prompt changes carry the A/B/C drift landmine (live bundle vs tracked source vs repo changes) —
  never blind-push; review drift first.

---

## 3. Measured results (the deliverable)

Same query, `any new emails today?` / `top priorities today`, host workers, both inboxes; timing from the
GlassHive runs table.

| | Hand-off (claude-opus, in-process) | Worker — codex gpt-5.4 | Worker — claude-code sonnet-4-6 |
| --- | --- | --- | --- |
| Worker duration | ~40 s | 301 s (5m01s) | **88–144 s (~2 min, 3 runs)** |
| Providers read | Gmail + Outlook | Gmail + Outlook | Gmail + Outlook *(after fix 2.2)* |
| Quality | prioritized; occasionally compresses a detail | complete + verbatim, verbose | complete, prioritized, action-items surfaced, honest about gaps |
| Speed vs codex | — | baseline | **~2.5–3.4× faster** |

Conversation comparison (user-facing): **A** = GlassHive worker (`c/77f81066…`) — focused, dropped
already-done items (user preferred this). **B** = non-glasshive hand-off (`c/350ef01a…`) — complete but
verbose (surfaced already-done items: a signed agreement + a reschedule the user already did). See §2.5.

---

## 4. All changes — why / where / how / what

### 4.1 Committed — parent repo (`…/viventium`, branch `claude/glasshive-audit-fixes`)
- `ab88dee` **config-driven default worker profile + enterprise-compat note**
  - WHY: make Claude-code the durable default locally without breaking enterprise.
  - WHERE: `scripts/viventium/config_compiler.py` (resolver + env emit), `config.schema.yaml`,
    `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`.
  - HOW/WHAT: compiler reads `integrations.glasshive.host_worker.default_worker_profile` (default
    `codex-cli` = no change for unset configs) and emits `GLASSHIVE_DEFAULT_WORKER_PROFILE`. Runtime fails
    closed if a default isn't in `GLASSHIVE_ALLOWED_WORKER_PROFILES`, so enterprise can't inherit an
    unadvertised worker. Doc records enterprise compatibility of both bug fixes. 106 compiler tests pass.
- `2f758df` **document claude-code worker measurement + two interop fixes** (the §3 table, switch mechanism,
  cold/warm, the two bugs) in `48_GlassHive…` + QA cases `CA-HANDOFF-007/008/009` and the durability gate in
  `qa/connected-accounts-handoff/cases.md`.
- Earlier in the engagement (context): `026e4d7` memory-injection + recall design; `7c8b700` Core Outcome
  Metric + PARITY; `6b48099` results-vs-speed measured comparison; `2cab2e1` latency breakdown correction;
  `e5e130e` speed levers + cost controls; `c9dfcc1` connected-accounts handoff QA.

### 4.2 Committed — LibreChat fork (`viventium_v0_4/LibreChat`, branch `claude/glasshive-audit-fixes`)
- `d5a92d28` **broker: emit `structuredContent` only for objects** (fix MS365 reads for strict MCP clients)
  - WHERE: `api/server/routes/viventium/glasshiveCapabilities.js` (`tools/call` handler) +
    `api/server/routes/viventium/__tests__/glasshiveCapabilities.spec.js` (array → omit `structuredContent`,
    data in text). WHAT: see §2.2. Verified live (Claude read Gmail + Outlook) + 7/7 route tests.
- Earlier (context): `f95ab379` inject the run's memory into the worker bundle (Quality parity, broker spec
  19/19); `ef464d92` fix spurious gpt-5.4 error bubble (`response.output is not iterable`) via startup
  monkey-patch; `9c0c8927` broker F3 hardening (bound provider tool calls → clean degraded blocker);
  `99b82b02` provision the read-only Connected Accounts hand-off agent + main handoff edge; `0fa88cb3` revert
  of the rejected direct-tools experiment; `4c29b725` pre-audit baseline checkpoint of the Codex-session work.

### 4.3 NOT committed — GlassHive repo (`viventium_v0_4/GlassHive`, branch `main`) — READ THIS
- My **auth fix** is a single hunk in `runtime_phase1/src/workers_projects_runtime/profile_runtime.py`:
  `_host_env` now passes `USER`/`LOGNAME` through (added to the allowlist tuple), plus a regression assertion
  in `runtime_phase1/tests/test_profile_runtime.py`.
- It is **intentionally uncommitted** because the GlassHive repo working tree is full of the prior **Codex
  session's uncommitted work** (api.py, bootstrap.py, deliverables.py, mcp_server.py, docs, tests, a new
  `runtime_requirements.py`, etc.). Committing `profile_runtime.py` would bundle that unowned in-flight work.
- The fix **is live** (the running runtime executes the source tree) and verified. To split it out cleanly,
  the next owner can commit just the `_host_env` USER/LOGNAME line + the test assertion (e.g. via a focused
  patch) once the Codex-session work is reviewed/committed as its own unit.

### 4.4 Live config (outside any repo) — the user's install
- `/Users/adri/Library/Application Support/Viventium/config.yaml`: added
  `integrations.glasshive.host_worker.default_worker_profile: claude-code` (with a revert comment).
- Runtime per-user preference set: `PATCH /v1/preferences {"default_worker_profile":"claude-code"}`
  (owner `demo-owner`, tenant `local`) — DB-persisted, effective now.

### 4.5 Operational actions taken (no source impact, reversible)
- Temporarily removed the Main Agent's handoff edge to force the worker path for measurement, then
  **restored** it (count back to 1). Backup at `/tmp/viv_main_edges_backup.json`; helper at
  `/tmp/viv_edge_toggle.js`.
- Relaunched the GlassHive runtime + MCP from a keychain-attached shell to test the auth fix (sourcing
  `runtime.env` to preserve the deterministic broker/callback secrets). Helper script:
  `/tmp/viv_glasshive_relaunch.sh`. The runtime has since been restarted again (PIDs differ) and remains
  healthy with the fix in the source tree.

---

## 5. Current state

- **Repos / branches:**
  - parent `…/viventium` → branch `claude/glasshive-audit-fixes`, HEAD `ab88dee`.
  - LibreChat `viventium_v0_4/LibreChat` → branch `claude/glasshive-audit-fixes`, HEAD `d5a92d28`.
  - GlassHive `viventium_v0_4/GlassHive` → branch `main`, auth fix + Codex-session work **uncommitted** (§4.3).
  - Nothing pushed; all local. Feature branches chosen for easy revert.
- **Live runtime:** GlassHive runtime + MCP healthy (8766 / 8767); LibreChat backend healthy (3180/3190);
  broker fail-closed (401). Worker default = **claude-code** (preference + config). Main Agent handoff edge
  **restored** (quick reads go to the in-process hand-off; the worker path is used when delegated/asked).
- **Tests green:** broker Jest 19/19, broker route 7/7 (incl. new regression), `test_profile_runtime.py`
  (incl. new USER/LOGNAME assertion), config-compiler release 106/106.
- **Auth:** Claude-code host worker authenticates and reads both Gmail + Outlook (verified live; a later
  conversation at 20:38 UTC also succeeded after a runtime restart).

---

## 6. What's next

### 6.1 Awaiting the user's go (designed, not yet implemented — instruction/contract level, A/B/C review)
- **Auto-surface after View/Steer (no-callback LibreChat).** Add a Main-Agent instruction: *when the user
  wants the result now (a read/question), after launching call `workspace_wait` and surface in the same turn;
  for fire-and-forget background work, share View/Steer and don't block.* Intent-driven, aligns with the
  enterprise "wait only when the user asks" contract. Lives in the local main-agent prompt (e.g.
  `viventium_v0_4/LibreChat/viventium/source_of_truth/prompts/main/tools.md` or `truth_live_data.md`).
- **Completeness without verbosity (universal).** (a) Worker completion contract: "surface the complete
  actionable set; don't pre-truncate a real pending item." (b) Main-Agent shaping instruction: do the
  concision and drop already-done items using injected memory + conversation context. Keeps PARITY ("trust
  the worker to choose the path"); only separates truth+completeness from shape.

### 6.2 Recommended (touch shared runtime / enterprise — needs enterprise QA, do not unilaterally change)
- **Trim the `workspace_wait`/`status` result noise:** gate the three full run-record dumps
  (`run`/`requested_run`/`latest_run`) behind the existing diagnostics flag → lean result by default
  (`workers_projects_runtime/mcp_server.py`, the wait/status return ~line 3436).

### 6.3 Verification gates / ops follow-ups
- **Helper-restart re-verify:** confirm a claude-code worker read after a real macOS-helper restart (largely
  satisfied by the 20:38 UTC success, but a clean helper-managed confirmation is ideal).
- **Commit the GlassHive auth hunk** as its own change once the Codex-session work is dispositioned (§4.3).
- **Codex revert path:** when codex weekly credits return, set the default back
  (`config.yaml` → `codex-cli`, and/or `PATCH /v1/preferences {"default_worker_profile":""}`). Quality + speed
  should be re-measured for codex-vs-claude at that point.
- **Enterprise claude enablement** (their op, not ours): repair/rotate the Anthropic/Portkey credential, run
  the Claude-code worker matrix, then add `claude-code` to `GLASSHIVE_ALLOWED_WORKER_PROFILES`. The
  `structuredContent` fix will benefit it; durable auth there is `CLAUDE_CODE_OAUTH_TOKEN`/API-key injection.
- **Pre-existing, lower priority** (from the original audit plan): Panorad content-read host/user gate (F4,
  document-before-cutover), specialist A/B/C drift reconciliation (F5), worker-lifecycle/orphan-container
  hygiene (F6). The `_convertOpenAIResponsesMessageToBaseMessage` variant may need the same guard as the
  patched `…Delta…` function if gpt-5.4 agents are used again (the 4 historical errors stopped after the fix).

---

## 7. Important notes / gotchas / context

- **Three repos, separate histories.** Parent commits do not deploy the LibreChat fork or the GlassHive repo.
  Commit each change in its owning repo.
- **GlassHive working tree is shared with the Codex session's uncommitted work** — never `git add -A` there;
  add explicit paths, and keep my auth hunk isolable (§4.3).
- **Agent-prompt drift (A/B/C) is a landmine** — review live vs tracked vs repo before any user-level agent
  push; that's why §6.1 is "await go," not auto-applied.
- **Secrets:** the broker/callback secrets are deterministic (`scoped_secret`) and live in `runtime.env`;
  never echo them. The Keychain Claude token was **not** extracted or persisted (verified by env-only tests).
- **Enterprise = no cloud changes.** Everything here is local; enterprise compatibility is verified by reading
  its config model, not by touching its VM.
- **Don't overfit.** All fixes are universal (env passthrough, MCP-spec result shape, division of labor) — not
  tied to MS365/Google, a specific prompt, or one machine. The runtime must not gate behavior on
  agent/provider/tool string heuristics.
- **The runtime was relaunched by hand during QA** and has since restarted; it runs the source tree, so the
  uncommitted auth fix persists across restarts. If you wipe the working tree, re-apply the USER/LOGNAME line.

### Key files
- Broker route: `viventium_v0_4/LibreChat/api/server/routes/viventium/glasshiveCapabilities.js`
- Broker service + bootstrap: `…/api/server/services/viventium/GlassHiveCapabilityBroker*.js`,
  `GlassHiveCapabilityBootstrapService.js`; memory threading in `…/controllers/agents/client.js`
- Host runtime (auth fix): `viventium_v0_4/GlassHive/runtime_phase1/src/workers_projects_runtime/profile_runtime.py`
- Worker profile resolution + wait/status shape: `…/workers_projects_runtime/mcp_server.py`, `api.py`
- Config compiler: `scripts/viventium/config_compiler.py`; schema `config.schema.yaml`; live config
  `~/Library/Application Support/Viventium/config.yaml`
- Source-of-truth docs: `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`,
  `01_Key_Principles.md` §0, root `AGENTS.md`
- QA: `qa/connected-accounts-handoff/{README.md,cases.md}` (CA-HANDOFF-001…009)
- Enterprise context (client-private): `/Users/adri/Documents/AITP/Projects/GlassHive/CURRENT_STATE_AND_EXPECTATIONS.md`
- GlassHive DB: `~/Library/Application Support/Viventium/state/runtime/isolated/glasshive/runtime_phase1.db`;
  LibreChat Mongo `mongodb://127.0.0.1:27117/LibreChatViventium`
