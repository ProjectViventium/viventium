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
- encrypted browser-entered API keys for OpenAI and Anthropic
- optional BYOK provider setup across Groq, xAI, Google, OpenRouter, and more
- an explicitly experimental subscription-account compatibility bridge for established setups
- local web search and code-interpreter-compatible tooling when enabled in config

## Quick Start

### Easy Install (Recommended)

Easy Install is the guided, native-first product path for a new Mac. It is designed to install the
useful local core without Docker, open browser setup automatically, and let you securely add an
OpenAI or Anthropic API key before your first answer. Optional providers, channels, voice, recall,
and automation come later.

The command below exercises the current source-checkout candidate. It still requires Git and may
install developer/runtime prerequisites; it is not the finished no-developer-tools Easy Install
artifact.

**Current source-checkout entrypoint:** copy and run this line on macOS:

```bash
git clone https://github.com/ProjectViventium/viventium.git && cd viventium && ./install.sh
```

Choose **Easy Install** when prompted. The signed/notarized immutable release and pristine-Mac gate
remain open, so do not treat this source-checkout path as the finished public installer.

### Custom Settings Install

Choose **Custom Settings Install** in the same installer when you deliberately want to select the
runtime mode, providers, integrations, or optional capabilities during installation. Settings you
skip can still be added later with `bin/viventium configure`.

On macOS, install also adds `Viventium Helper` to the status bar so you can open, start, stop,
snapshot the local stack, and open the local Prompt Workbench without going back to Terminal.

First-run notes:

- remote access stays optional; if public-edge setup hits a router-port conflict, the local install
  now keeps running and `bin/viventium status` reports the exact blocker
- public-browser installs can keep sign-up open just long enough to create the first account, then
  automatically close browser registration for safer exposure
- the macOS helper now uses the shipped matching helper binary first on clean installs instead of
  depending on opportunistic local Swift builds
- the helper's `Advanced > Prompt Workbench` submenu can Open, Start, or Stop only the Prompt
  Workbench web app; it does not stop the main Viventium runtime
- after you create your local account, setup should open Connected Accounts automatically; add at
  least one foundation-model API key (`OpenAI` or `Anthropic`). If you dismiss setup, reopen it from
  `Settings -> Connected Accounts`. Gmail/Drive and Outlook/MS365 accounts are separate optional
  connections.

If startup does not complete, or you need to check it later:

```bash
bin/viventium doctor
bin/viventium start
```

Upgrade an existing install:

```bash
bin/viventium upgrade --restart
```

If upgrade detects continuity drift that could make restored recall or saved state misleading, it
now writes pre/post continuity audits and can block the automatic restart until the operator
reviews the issue.

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

Viventium does not use a repository `.env.example` as a secret-authoring surface. The installer
compiles machine-local runtime environment files from canonical config and Keychain references.

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

The current release target, which is not yet a public-release claim, is:

- macOS
- local install first
- Apple Silicon is the primary clean-room target

Source contracts and the helper cover Intel, but the exact current payload has not completed its
Intel install, first-use, and restart acceptance run. Intel support must remain unclaimed until that
gate passes.

## Commands

```bash
bin/viventium doctor
bin/viventium launch
bin/viventium start
bin/viventium stop
bin/viventium upgrade --restart
bin/viventium install-helper
bin/viventium uninstall-helper
bin/viventium continuity-audit
bin/viventium snapshot
bin/viventium restore
```

## Roadmap

The current source-checkout evaluation path is the repo-local flow above. The finished public path
still requires the signed/notarized immutable payload and exact clean-machine acceptance.

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
