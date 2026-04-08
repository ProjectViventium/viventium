# Installer Piped Bootstrap QA Report

## Date

- 2026-04-07

## Build Under Test

- Branch: `main`
- Working tree included local changes to:
  - `bin/viventium`
  - `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`
  - `tests/release/test_cli_upgrade.py`
  - `qa/installer-piped-bootstrap/*`

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

## Evidence

### Automated Results

- `bash -n bin/viventium`
  - passed
- `python3 -m pytest tests/release/test_cli_upgrade.py -q`
  - `24 passed in 12.75s`

### Repro And Acceptance Result

- Before the fix, the piped bootstrap crashed at:
  - `Choose an option [default: 1]:`
  - `EOFError: EOF when reading a line`
- After the fix, the PTY regression harness proved the owning CLI behavior instead of relying on a
  published clone:
  - the new CLI helper changed stdin from `pipe` back to `tty`
  - the isolated `install --no-start` harness reported `wizard-stdin-tty=1`
  - the isolated `install --no-start` harness reported `preflight-stdin-tty=1`

## Findings

- No blocking issue remains in the piped-bootstrap installer path after stdin is reattached from the
  controlling terminal before interactive install prompts run.

## Residual Risks

- Truly headless runs without a controlling terminal still need the documented preset-based
  non-interactive path.
- The public website/bootstrap URL should be rechecked after this branch is committed and published,
  because the working-tree fix is proven locally before release rather than through the already
  published clone target.
