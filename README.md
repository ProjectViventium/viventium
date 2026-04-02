# Viventium

**Your second brain for real work.**

Viventium thinks with you, remembers what matters, and helps move work forward across voice, chat, and your tools. It is built to feel fast on the surface, go deeper in the background, and give you more control over how it runs.

[Website](https://www.viventium.ai) · [Docs](https://www.viventium.ai/docs) · [Changelog](https://www.viventium.ai/changelog) · [Roadmap](https://www.viventium.ai/roadmap) · [Community](https://www.viventium.ai/community)

## Why Viventium

- **Voice + chat, one continuity layer**: think out loud, type when needed, and keep the same context across both.
- **Background agents you can steer**: get a fast first reply, then let deeper work continue without blocking the conversation.
- **Memory that compounds**: keep active context, preferences, drafts, and follow-through instead of starting from zero every day.
- **Safe execution**: move from conversation into real work with tools, code, scheduling, and controlled automation.
- **Run it your way**: local-first, bring-your-own-keys, connected accounts, or managed paths as the product evolves.

## What You Get

A local Viventium install can give you:

- the main `Viventium` agent plus built-in background agents
- voice calls and the modern playground
- memory, recall, morning briefings, and scheduling
- connected accounts for OpenAI / Anthropic where supported
- optional BYOK provider setup across OpenAI, Anthropic, Groq, xAI, Google, OpenRouter, and more
- local web search and code-interpreter-compatible tooling when enabled in config

## Quick Start

**Current verified install path:** macOS, repo-local install.

```bash
git clone https://github.com/ProjectViventium/viventium.git
cd viventium
./install.sh
```

On macOS, install also adds `Viventium Helper` to the status bar so you can open, start, and stop the local stack without going back to Terminal.

Then start or check the stack:

```bash
bin/viventium doctor
bin/viventium start
```

Upgrade an existing install:

```bash
bin/viventium upgrade --restart
```

Stop the stack:

```bash
bin/viventium stop
```

## Configuration

Start here if you want to understand or customize the install surface:

- [`config.schema.yaml`](./config.schema.yaml): authoritative option schema
- [`config.minimal.example.yaml`](./config.minimal.example.yaml): smallest supported example
- [`config.full.example.yaml`](./config.full.example.yaml): full supported config with inline explanations
- [`librechat.yaml.example`](./librechat.yaml.example): advanced generated/runtime reference
- [`.env.example`](./.env.example): advanced compatibility reference

The canonical machine-local config lives at:

- `~/Library/Application Support/Viventium/config.yaml`

Generated runtime files live under:

- `~/Library/Application Support/Viventium/runtime/runtime.env`
- `~/Library/Application Support/Viventium/runtime/runtime.local.env`
- `~/Library/Application Support/Viventium/state/runtime/isolated/librechat.generated.yaml`

## Default Product Surface

Viventium ships from tracked source-of-truth files so new installs get a real product setup, not a bare upstream shell.

Important source files:

- [`viventium_v0_4/LibreChat/viventium/source_of_truth/local.librechat.yaml`](./viventium_v0_4/LibreChat/viventium/source_of_truth/local.librechat.yaml): shipped local LibreChat defaults
- [`viventium_v0_4/LibreChat/viventium/source_of_truth/local.viventium-agents.yaml`](./viventium_v0_4/LibreChat/viventium/source_of_truth/local.viventium-agents.yaml): shipped built-in agents

That source-of-truth is expected to carry the real Viventium defaults for:

- pinned `Viventium` main agent
- built-in background agents
- memory and recall behavior
- speech, scheduling, and operational defaults
- curated provider and model surfaces
- connected-account and BYOK setup paths

## Current Support

The current public-ready install target is:

- macOS
- local install first
- Apple Silicon is the primary clean-room target

Intel Macs can still run Viventium, but some local voice/STT choices may need different configuration than Apple Silicon.

## Commands

```bash
bin/viventium doctor
bin/viventium launch
bin/viventium start
bin/viventium stop
bin/viventium upgrade --restart
bin/viventium install-helper
bin/viventium uninstall-helper
bin/viventium snapshot
bin/viventium restore
```

## Roadmap

The current verified open install path is the repo-local flow above.

Planned future install surfaces:

- `npx viventium`
- `brew install viventium`

Those are not the current verified public install path yet.

## Community

Viventium is being shaped in public through the build log, roadmap, and community.

- [Join Discord](https://discord.gg/mk3dsvc6)
- [Read the changelog](https://www.viventium.ai/changelog)
- [Follow the roadmap](https://www.viventium.ai/roadmap)
- [Explore the docs](https://www.viventium.ai/docs)

## License

The main repo uses the Functional Source License 1.1 with an Apache-2.0 future license. See [`LICENSE`](./LICENSE), [`LICENSE-MATRIX.md`](./LICENSE-MATRIX.md), and [`THIRD_PARTY_LICENSES.md`](./THIRD_PARTY_LICENSES.md).
