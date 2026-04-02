# Setup Guide

This guide reflects the supported public-facing setup surface.

## Supported Target

- macOS only for the public install path
- Apple Silicon is the primary clean-room acceptance target

## Primary Flow

Run the installer:

```bash
./install.sh
```

Recommended mode today for the most reliable first run:

- `native`
- `isolated` profile
- modern playground default

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

Before component bootstrap and doctor, the installer should now run one aggregated preflight screen:

- detect every missing prerequisite at once
- show one batch install plan
- install the missing native or Docker prerequisites in one pass after one confirmation prompt

Then validate and start:

```bash
bin/viventium doctor
bin/viventium start
```

Refresh an existing local install after new published changes:

```bash
bin/viventium upgrade
```

Optional restart as part of the same upgrade:

```bash
bin/viventium upgrade --restart
```

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

Inspect or apply restore actions:

```bash
bin/viventium restore --snapshot-dir <path>
```

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
- if the configured provider auth mode is API key, the default local OpenAI inventory should stay on safe broadly accessible models rather than premium subscription-only ones

## Release Prep

Before any file move or publishing:

```bash
python3 scripts/release/build_release_manifests.py
```
