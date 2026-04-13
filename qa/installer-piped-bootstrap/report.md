# Installer Piped Bootstrap QA Report

## Date

- 2026-04-08
- 2026-04-13 follow-up

## Build Under Test

- Branch: `feature/installer-resilience-public-review`
- Scope: clean public-review branch state for the installer stdin-reattachment fix
- Verification reference:
  - `git rev-parse HEAD`
  - use the checked-out branch revision that contains this report

## Steps Executed

1. Shell syntax validation:
   - `bash -n bin/viventium`
2. Release regression coverage:
   - `python3 -m pytest tests/release/test_cli_upgrade.py -q`
3. Pre-fix failure repro against an isolated temp clone using the public piped-bootstrap shape:
   - `cat /path/to/viventium/install.sh | env VIVENTIUM_REPO_URL=/path/to/viventium VIVENTIUM_INSTALL_DIR=<temp> VIVENTIUM_APP_SUPPORT_DIR=<temp> bash`
4. Post-fix PTY acceptance through the release harness:
   - extracted and executed `reattach_stdin_from_tty_if_available` under a real PTY while stdin was redirected from a pipe
   - executed an isolated fake-repo `bin/viventium install --no-start` run under the same PTY shape and verified both wizard and preflight inherited a TTY
5. Follow-up repro against the published website bootstrap shape:
   - `curl -fsSL https://www.viventium.ai/install.sh | bash`
   - confirmed the published `main` still crashed inside `questionary.select(...).ask()` with
     `prompt_toolkit` raw-mode `OSError: [Errno 22] Invalid argument`
6. Current-branch acceptance under the same piped bootstrap shape:
   - piped a shell wrapper into `bash` that `cd`'d into the current tree and ran `./install.sh`
   - confirmed the shared installer UI emitted `Interactive terminal UI unavailable; falling back to plain prompts.`
   - confirmed the installer reached the plain numbered setup prompt instead of aborting
7. Post-publish acceptance against the live website bootstrap:
   - reran `curl -fsSL https://www.viventium.ai/install.sh | bash` from a fresh temp directory after
     publishing `main`
   - confirmed the freshly cloned published build emitted the same fallback note
   - confirmed the published installer reached the plain numbered setup prompt instead of aborting

## Evidence

### Automated Results

- `bash -n bin/viventium`
  - passed
- `python3 -m pytest tests/release/test_cli_upgrade.py -q`
  - `24 passed in 12.75s`
- `uv run --with pytest --with pyyaml pytest tests/release/test_installer_ui.py tests/release/test_wizard.py tests/release/test_install_summary.py tests/release/test_config_compiler.py tests/release/test_public_bootstrap_manifests.py tests/release/test_background_agent_governance_contract.py -q`
  - `112 passed`

### Repro And Acceptance Result

- Before the fix, the piped bootstrap crashed at:
  - `Choose an option [default: 1]:`
  - `EOFError: EOF when reading a line`
- After the fix, the PTY regression harness proved the owning CLI behavior instead of relying on a
  published clone:
  - the new CLI helper changed stdin from `pipe` back to `tty`
  - the isolated `install --no-start` harness reported `wizard-stdin-tty=1`
  - the isolated `install --no-start` harness reported `preflight-stdin-tty=1`
- On April 13, 2026, the published public bootstrap still exposed a second boundary bug:
  - stdin was no longer the blocker, but `questionary` still crashed while attaching raw terminal
    control after the install had already reached interactive mode
  - the failing stack terminated in `questionary.select(...).ask()` with `prompt_toolkit`
    `OSError: [Errno 22] Invalid argument`
- The current-branch fix moved that ownership into the shared `InstallerUI` wrapper:
  - all interactive prompt entrypoints now catch runtime `questionary` failures
  - the installer prints one fallback note
  - the installer continues through plain prompts instead of aborting
- After publication, the live website bootstrap matched the current-branch acceptance result:
  - the freshly cloned published build emitted the fallback note
  - the freshly cloned published build reached the plain numbered setup prompt cleanly

## Findings

- Piped bootstrap readiness has two separate contracts:
  - the public CLI must reattach stdin from the controlling terminal before interactive prompts run
  - the shared installer UI must still survive runtime `questionary` raw-mode failures after that
    reattachment
- With both layers in place, no blocking issue remains in the piped-bootstrap installer path.

## Residual Risks

- Truly headless runs without a controlling terminal still need the documented preset-based
  non-interactive path.
