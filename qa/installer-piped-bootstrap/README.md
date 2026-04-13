# Installer Piped Bootstrap QA

## Scope

Verify the public CLI keeps interactive install prompts working when the bootstrap entrypoint starts
with stdin attached to a consumed pipe but the user still has a controlling terminal.

## Requirements Under Test

- `bin/viventium install` must restore interactive stdin before launching the wizard.
- `bin/viventium install` must keep interactive stdin available for aggregated preflight prompts.
- Equivalent piped bootstrap entrypoints must no longer crash at the first setup prompt with
  `EOFError`.

## Environments

- POSIX shell with PTY support
- isolated temp repos and temp App Support directories
- local repo checkout for source-based and shell-based regression coverage

## Test Cases

1. Extract the CLI helper and prove it turns stdin back into a TTY after stdin is redirected from a
   pipe while stdout/stderr stay on a PTY.
2. Run an isolated fake-repo `bin/viventium install --no-start` harness under a PTY with stdin
   redirected from a pipe; verify both the wizard and preflight see `sys.stdin.isatty() == true`.
3. Reproduce the public bootstrap shape with `cat install.sh | bash` against an isolated temp clone;
   confirm the installer reaches the first setup prompt instead of throwing `EOFError`.
4. Validate shell syntax with `bash -n bin/viventium`.

## Expected Results

- The CLI helper restores terminal stdin successfully.
- Interactive install reaches the setup prompt normally under a piped bootstrap.
- Wizard and preflight both inherit a real TTY in the isolated install harness.
- No shell syntax regressions are introduced.
