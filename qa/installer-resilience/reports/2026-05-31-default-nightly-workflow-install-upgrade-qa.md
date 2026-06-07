<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# 2026-05-31 Default Nightly Workflow Install/Upgrade QA

## Scope

Verify the supported local install and upgrade contract for the default nightly workflow:
GlassHive, Prompt Workbench, active Workbench nightly reflection, memory hardening, worker CLI auth,
generated runtime env, first-admin schedule seeding, install-summary visibility, and public/private
safety.

## Requirement Links

- `docs/requirements_and_learnings/01_Key_Principles.md`
- `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`
- `docs/requirements_and_learnings/11_Scheduling_Cortex.md`
- `qa/installer-resilience/cases.md` `INST-003`
- `qa/prompt-workbench/cases.md` `PW-029`
- `qa/scheduling-cortex/cases.md` `SCHED-010`
- `qa/memory-hardening/cases.md` `MEMHARD-005`

## Product Contract Checked

The minimal path of resistance is:

1. User runs the one-line install and chooses Express/Easy, or later runs `bin/viventium upgrade`.
2. Canonical config enables GlassHive, Prompt Workbench, active nightly reflection, and memory
   hardening by default.
3. Preflight requires one signed-in local worker CLI: Codex or Claude.
4. Generated runtime fills a missing worker profile from the signed-in CLI while preserving an
   explicit user-selected worker profile.
5. Prompt Workbench seeds `Subconscious Deep Thought` for the first resolved local admin user.
6. The nightly delivery path is:
   scheduled prompt -> filled placeholders -> GlassHive run -> callback -> scheduler ledger ->
   Workbench shows completed.

## Evidence

- Express/Easy config build: GlassHive enabled, Prompt Workbench enabled, nightly seed active,
  memory hardening enabled, empty `operator_user_email`, no owner-specific account string.
- Upgrade-shaped legacy config: default-nightly reconciler enabled the same defaults once.
- Worker profile simulation:
  - Codex-ready with no explicit profile -> `codex-cli`.
  - Claude-ready with no explicit profile -> `claude-code`.
  - Explicit `claude-code` remains `claude-code` even when Codex is detected.
  - No signed-in worker -> defaults still enabled but no worker profile; preflight blocks with a
    single action to sign into Codex or Claude.
- Memory provider is intentionally not inferred from the worker CLI. Worker CLI auth proves the
  GlassHive host worker can run; memory hardening provider selection remains explicit or follows
  configured LLM auth through the config compiler.
- Generated env simulation included:
  - `START_GLASSHIVE=true`
  - `GLASSHIVE_HOST_WORKERS_ENABLED=true`
  - `GLASSHIVE_DEFAULT_WORKER_PROFILE=claude-code` in the Claude-ready scenario
  - `START_PROMPT_WORKBENCH=true`
  - `VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_ENABLED=true`
  - `VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_ACTIVE=true`
  - `VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_EXECUTOR=glasshive_host`
  - `VIVENTIUM_MEMORY_HARDENING_ENABLED=true`
  - `VIVENTIUM_MEMORY_HARDENING_USER_EMAIL=` empty
  - `VIVENTIUM_MEMORY_HARDENING_CONFIGURED_PROVIDER=` empty, proving the worker CLI did not pin
    the memory provider
- Local auth probe evidence was checked only as readiness state:
  - Codex CLI login status: ready.
  - Claude CLI login status: ready.
  Raw account values were not written here.
- Claude review found four implementation gaps after the first pass. Confirmed fixes:
  - auto worker profile is now fill-only and preserves explicit user choices.
  - malformed Claude auth status fails closed.
  - worker CLI auth detection is shared by preflight and the defaults reconciler.
  - multi-admin/ambiguous first-admin seeding logs an operator-visible setup warning.

## Commands Run

- `python3 -m py_compile scripts/viventium/default_nightly_routines.py scripts/viventium/preflight.py scripts/viventium/config_compiler.py scripts/viventium/install_summary.py viventium_v0_4/prompt-workbench/backend/prompt_workbench/app.py viventium_v0_4/prompt-workbench/backend/prompt_workbench/scheduled_prompts.py`
  - PASS.
- Focused default-nightly slice:
  - `40 passed`.
- Owning release-suite group:
  - `tests/release/test_default_nightly_routines.py`
  - `tests/release/test_wizard.py`
  - `tests/release/test_preflight.py`
  - `tests/release/test_config_compiler.py`
  - `tests/release/test_cli_upgrade.py`
  - `tests/release/test_install_summary.py`
  - `tests/release/test_prompt_workbench.py`
  - Result after Claude-driven fixes: `365 passed`.
- Public-safety regression:
  - `tests/release/test_qa_results_public_safety.py`
  - Result: `1 passed`.

## Result

PASS for source, generated-runtime, installer/upgrade harness, preflight auth handling, install
summary, and synthetic Workbench first-admin seeding.

Remaining release gate: this was not a destructive fresh install on a separate clean Mac. A final
public release signoff should still run `./install.sh` on a clean machine and open the Workbench UI
after the first account is created, then correlate the visible schedule row with Scheduler and
GlassHive state.

Known setup limitation: automatic nightly seeding is proven for the normal first local admin path.
If multiple admins exist before Workbench can resolve a unique schedule owner, the runtime must not
guess a personal owner; that multi-admin ambiguity needs an operator-visible setup notice before it
can be called fully release-complete.

## Public Safety

This report intentionally omits raw account emails, local home paths, tokens, raw prompts,
transcripts, callback payloads, browser screenshots, and private runtime logs.
