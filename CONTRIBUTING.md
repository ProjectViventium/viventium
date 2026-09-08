# Contributing to Viventium

Start with the [contributor setup](docs/04_SETUP_GUIDE.md#contributor-setup). It covers the supported
toolchain, test dependencies and pinned component bootstrap. Then follow the
[isolated runtime quickstart](docs/requirements_and_learnings/50_Stable_Dev_Runtime.md#contributor-quickstart)
to run your checkout without replacing an existing daily installation.

## Find the owning flow

Read the [project contract](AGENTS.md) and [key principles](docs/requirements_and_learnings/01_Key_Principles.md).
Use the [capability map](docs/README.md#capabilities-and-acceptance) to find the relevant requirement
and [QA journey](qa/catalog.yaml). Follow the trigger through configuration, compiled output,
runtime code and the visible result. The [systems map](docs/architecture/systems-map.md) identifies
component boundaries.

Managed components are separate repositories with their own instructions and dependencies.
Check `git rev-parse --show-toplevel` before editing. Component source, parent pins and built/running
artifacts must agree for a delivery claim. Starting a development environment does not promote
source changes into the installed app.

## Make and verify a change

1. Create your working branch from the current project base.
2. Make the smallest coherent change in the owning component. Reuse existing mechanisms; models
   own semantic judgment and runtime code owns structure, authority, persistence and recovery.
3. Run the relevant regression checks with the component's documented environment. For a root
   compiler change, after completing contributor setup:

   ```sh
   .venv/bin/python -m pytest tests/release/test_config_compiler.py -q
   ```

4. Exercise the affected user journey in the isolated runtime. Check the result, relevant failure
   and recovery state, and persistence. Follow the [QA contract](qa/README.md); record missing
   prerequisites separately from passing checks. Run broader checks when the change affects them.
5. Update the owning requirement or runtime document when behavior changes. Keep one source of
   truth; link to existing procedures and retain requirement IDs.
6. Review the diff for unrelated edits, secrets, private data and machine-specific paths before
   committing. Keep private logs, screenshots and user prompts outside public repositories.

Prompt changes follow the existing [Prompt Workbench contract](docs/requirements_and_learnings/49_Prompt_Architecture_and_Token_Efficiency.md),
including source-to-live lineage and old/proposed cases on the configured models. Deterministic
tests, model evaluations and real user QA prove different things.

## Submit work

Open an issue with the expected result, actual result and reproducible steps. For a pull request,
explain the problem, resulting behavior, relevant validation and remaining gaps. Identify any
component and parent-pin changes needed to deliver it. Maintainers review correctness, user
experience, simplicity and alignment before merging.

Follow the component's style and tooling. Explain non-obvious decisions in comments; keep routine
code readable without narration. Use the [troubleshooting guide](docs/06_TROUBLESHOOTING.md) for
setup and runtime failures.

## License

Contributions to this repository use its [LICENSE](LICENSE). Component repositories retain their
upstream-compatible licenses; see [LICENSE-MATRIX.md](LICENSE-MATRIX.md).
