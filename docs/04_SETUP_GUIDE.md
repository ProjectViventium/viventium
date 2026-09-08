# Setup Guide

This guide reflects the current source-checkout setup candidate. It does not claim that the pending
signed/notarized immutable Easy Install artifact is publicly released.

## Current Release Target

- macOS only for the current release candidate
- Apple Silicon is the primary clean-room acceptance target

## Primary Flow

From a Viventium source checkout, run the installer:

```bash
./install.sh
```

Choose **Easy Install** for the recommended first run. It uses the native local core, keeps remote
access local-only, and defers Docker, Voice, Recall, channels, and automation until after a working
provider-backed answer. The internal runtime/profile values are implementation details, not choices
a new user needs to understand.

Choose **Custom Settings Install** only when you deliberately want to select runtimes, providers,
integrations, or optional capabilities during installation. Skipped settings remain available later
through `bin/viventium configure`.

The current source-checkout path still requires Git and may install developer/runtime prerequisites.
The finished Easy Install contract removes those prerequisites through a verified immutable payload;
that release gate remains open.

Headless configuration flow:

```bash
./install.sh --headless --config-input /absolute/path/to/preset.yaml
```

This writes the canonical config to:

```text
~/Library/Application Support/Viventium/config.yaml
```

Reference config files in the repo:

- `config.schema.yaml` — authoritative option schema
- `config.minimal.example.yaml` — smallest supported example
- `config.full.example.yaml` — full option surface with inline explanations
- `librechat.yaml.example` — advanced generated/runtime reference only

Generated machine-local runtime files:

- `~/Library/Application Support/Viventium/runtime/runtime.env`
- `~/Library/Application Support/Viventium/runtime/runtime.local.env`
- `~/Library/Application Support/Viventium/state/runtime/<profile>/librechat.generated.yaml`

Before component bootstrap and doctor, the installer runs one aggregated preflight screen:

- detect every missing prerequisite at once
- show one batch install plan
- install the missing native or Docker prerequisites in one pass after one confirmation prompt

After the core starts, browser setup opens automatically:

1. create the first local administrator;
2. continue to Connected Accounts;
3. add one OpenAI or Anthropic API key through the encrypted user-key path;
4. verify the provider and send the first message.

If automatic handoff is dismissed, reopen it from `Settings -> Connected Accounts`. A saved
credential is not called `Ready` until its live test succeeds. Optional Gmail/Drive, Outlook/MS365,
Groq, Grok/xAI, channels, Voice, and Recall setup must not block the first useful answer.

If setup or startup does not complete, validate and retry with:

```bash
bin/viventium doctor
bin/viventium start
```

Remote-access note:

- if you choose public browser access and your router already gives `80/tcp` or `443/tcp` to another
  LAN device, Viventium now keeps the local install running and records the exact blocker in
  `bin/viventium status` instead of aborting the whole startup
- fix the reported router/DNS/public-edge blocker later and rerun `bin/viventium start`

Telegram first-run note:

- if Telegram Bridge is enabled, Viventium now keeps retrying the bridge automatically until the
  LibreChat API is actually ready on a clean first build
- during that window, `bin/viventium status` shows the bridge as `Starting` instead of a false
  stopped state

macOS helper note:

- on clean supported installs, Viventium now uses the shipped matching menu-bar helper binary first
  when it matches the tracked helper sources
- local Swift helper builds remain a development override, not the default end-user dependency path
- the helper's Advanced menu exposes user-safe maintenance actions:
  - `Check for Updates...`
  - `Prompt Workbench > Open`
  - `Prompt Workbench > Start`
  - `Prompt Workbench > Stop`
  - `Create Backup Snapshot`
  - `Heal Viventium...`
  - `Report a Bug...`
  - `Request a Feature...`
- `Prompt Workbench > Stop` stops only the workbench web app and leaves the main Viventium runtime
  in its current state
- `Create Backup Snapshot` runs the same supported snapshot flow as `bin/viventium snapshot` and
  reveals the latest snapshot folder when it completes

Refresh an existing local install after new published changes:

```bash
bin/viventium upgrade
```

Optional restart as part of the same upgrade:

```bash
bin/viventium upgrade --restart
```

Upgrade now captures pre/post continuity audits. If the post-upgrade audit reports an `error`,
automatic restart is blocked until the operator reviews the drift.

If upgrade/start reports that local Meilisearch is reachable but recent failed tasks make the
derived search index unusable, treat it as a derived-index repair, not a Mongo/chat-history repair.
Use `bin/viventium status` for the exact service message, then rebuild or recreate the local
Meilisearch-derived index from Mongo-backed conversations before restarting local search work. This
can be an expected one-time repair after a Meilisearch image/version upgrade; do not delete or edit
Mongo conversation data for it.

Important:

- fixes inside pinned component repos do not reach a clean machine automatically
- if LibreChat or the modern playground changes, publish rebuilt component snapshots before expecting
  `upgrade` on another Mac to pick up the fix

Stop:

```bash
bin/viventium stop
```

Snapshot local state:

```bash
bin/viventium snapshot
```

Capture the current continuity metadata without taking a full payload snapshot:

```bash
bin/viventium continuity-audit
```

Validate a snapshot without changing a target:

```bash
bin/viventium restore \
  --snapshot-dir <path> \
  --target-config-home <empty-app-support-path> \
  --validate-only
```

Restore a current-format complete bundle into a fresh independent source install:

```bash
mkdir -m 700 <empty-owner-only-mongo-data-path>

bin/viventium restore \
  --snapshot-dir <path> \
  --target-config-home <empty-app-support-path> \
  --target-repo-root <fresh-viventium-checkout> \
  --target-mongo-uri mongodb://127.0.0.1:<port>/<new-empty-database> \
  --target-mongo-data-path <empty-owner-only-mongo-data-path>

<fresh-viventium-checkout>/bin/viventium \
  --app-support-dir <empty-app-support-path> start
```

Restore notes:

- complete snapshots include sanitized config, allowlisted logical chat/memory/agent/account data,
  local uploads, schedules, hashes/counts, and a separate metadata-only continuity audit
- provider/channel/browser secrets and passwords are not migrated; reconnect accounts and use the
  supported password recovery path after restore
- Recall/RAG indexes are derived and are not trusted from the bundle; restore automatically writes
  the rebuild-required marker, which must be cleared intentionally only after rebuild
- restore never overwrites an existing App Support target, uploads directory, or nonempty Mongo DB
- the owner-only Mongo data path makes the independent restore restartable on its selected loopback
  port; omitting it retains the inspection/compatibility contract but not the restart-safe `v2` ledger
- bundles are owner-only but not self-encrypted; keep them on an encrypted host/external volume
- target start regenerates runtime files from canonical config plus the strict restore-selection ledger;
  helper binding must still be regenerated for the fresh target
- use the target checkout's local `password-reset-link <restored-user-email>` command to recover a
  restored browser user; provider and channel accounts must be reconnected separately

## What the New Surface Does

- uses `config.yaml` as the human-facing source of truth
- stores secrets in macOS Keychain
- compiles runtime env/yaml files into App Support
- exports runtime env into the existing v0.4 launcher through override hooks
- keeps the current v0.4 launcher as the compatibility engine underneath

## Current Compatibility Notes

- `viventium_v0_4/viventium-librechat-start.sh` still powers the actual startup flow
- root `.env` / `.env.local` remain compatibility inputs for advanced local development only
- `viventium_v0_3_py` is legacy and not part of the target public release surface
- if native install enables `MS365`, Docker Desktop is still required today because the local MS365 MCP remains Docker-backed
- OpenAI/Anthropic local installs should automatically surface Connected Accounts actions from the generated runtime config
- Google Workspace and Microsoft 365 tasks still require each local user to connect those services
  in `Settings -> Connected Accounts`; those OAuth links are user-scoped and are not implied by the
  installer alone
- if the configured provider auth mode is API key, the default local OpenAI inventory should stay on safe broadly accessible models rather than premium subscription-only ones

## Release Prep

For source development and release checks, prepare the contributor environment below first.
Then run the release suite from the repository root with that environment's Python:

```bash
.venv/bin/python -m pytest tests/release/ -q
```

## Contributor Setup

The source-checkout test path uses Python 3.12 and Node 24, matching the
[macOS validation workflow](../.github/workflows/config-compile.yml). Git is required to fetch the
[pinned component repositories](../components.lock.json). Full release tests also need FFmpeg and
ffprobe; component tests can require their own native tools and local services. The source
installer's [preflight](../scripts/viventium/preflight.py) reports prerequisites selected by the
runtime config. These developer requirements do not define the finished Easy Install payload.

From the repository root, use a standard local Python environment:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r scripts/viventium/requirements-tests.txt
```

[requirements-tests.txt](../scripts/viventium/requirements-tests.txt) is shared with CI and includes
the separate [runtime Python requirements](../scripts/viventium/requirements.txt). The installer
does not install pytest into every system Python. A `No module named pytest` error means the test
environment is missing or the wrong interpreter was used; it is not a failed product test.

For a fresh checkout, fetch the components selected by your public config before building or
running their tests. This example uses the full checked-in example, as the release workflow does:

```bash
.venv/bin/python scripts/viventium/bootstrap_components.py \
  --repo-root "$PWD" --config config.full.example.yaml --jobs 1
.venv/bin/python scripts/viventium/bootstrap_components.py \
  --repo-root "$PWD" --config config.full.example.yaml --validate-only --strict-pinned
.venv/bin/python -m pytest tests/release/test_config_compiler.py -q
```

`--validate-only --strict-pinned` performs no clone or checkout and reports missing, dirty or
non-pinned selected components. Use the bootstrap mutation only in the fresh checkout; preserve
existing component work. Bootstrap precedes compiler tests because compilation reads the selected
component's source-of-truth configuration and prompts. Each nested repository owns its instructions,
dependencies and tests.
For LibreChat, continue with its [AGENTS.md](../viventium_v0_4/LibreChat/AGENTS.md); the
[validation workflow](../.github/workflows/config-compile.yml) shows the package/client build order.
Voice and other optional selections can require additional components and tools.

Before starting a runtime, follow the existing
[Contributor Quickstart](requirements_and_learnings/50_Stable_Dev_Runtime.md#contributor-quickstart).
It first inspects the installed runtime owner, then creates, inspects and starts named `dev-env`
state. Creation needs an existing canonical config; on a new machine, complete the source install
above first. A dev environment has separate local state and ports, with the shared-service limits
listed in that owner. Selecting `dev-runtime activate-current` changes the installed runtime;
it is not part of setting up tests. Source edits and passing tests do not prove that an installed
process contains those edits.

To choose a change and its evidence, start from the
[capability and acceptance map](README.md#capabilities-and-acceptance), read the owning
requirement and runtime document, then follow its code, tests and QA case. The
[runtime implementation index](../viventium_v0_4/docs/IMPLEMENTATION_INDEX.md) and
[release-test ownership map](../qa/release-test-owners.yaml) provide the next links. Follow the
[QA contract](../qa/README.md) for the real affected surface; record missing prerequisites and
unrun user paths separately from passing automated checks.
