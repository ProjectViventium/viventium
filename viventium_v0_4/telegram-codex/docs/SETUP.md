# Setup

## Quick local setup

```bash
cd viventium_v0_4/telegram-codex
cp .env.example .env
cp config/settings.example.yaml config/settings.yaml
cp config/projects.example.yaml config/projects.yaml
uv sync
uv run pytest -q
uv run telegram-codex
```

## Setup through Viventium

1. Enable `integrations.telegram_codex` in `~/Library/Application Support/Viventium/config.yaml` or opt in during the Viventium wizard
2. Run `bin/viventium compile-config`
3. Start the service through the Viventium launcher or export the generated paths and run `uv run telegram-codex`

Generated files:

- `~/Library/Application Support/Viventium/runtime/service-env/telegram-codex.env`
- `~/Library/Application Support/Viventium/runtime/telegram-codex/settings.yaml`
- `~/Library/Application Support/Viventium/runtime/telegram-codex/projects.yaml`

Durable pairing state:

- approved Telegram accounts persist under the machine-local app-state tree, scoped to the bot identity
- short-lived pending pair tokens remain in the runtime profile state
- if you upgrade from an older runtime-local `paired_users.json`, the service migrates it automatically on first boot

## Required local secrets

`.env`

```env
TELEGRAM_CODEX_BOT_TOKEN=your_bot_token
TELEGRAM_CODEX_BOT_USERNAME=your_bot_username
```

## Required local project aliases

`config/projects.yaml`

```yaml
default_project: viventium_core
projects:
  viventium_core:
    path: /absolute/path/to/viventium_core
  another_repo:
    path: /absolute/path/to/another/repo
```

## Recommended first run

1. Start the sidecar
2. Message the bot with `/start`
3. Open the localhost pairing link on the same machine
4. Send `/projects`
5. Send `/use <alias>`
6. Send a small text prompt before testing voice notes or file attachments

## Notes

- `settings.yaml` controls runtime paths, pairing host/port, and Codex sandbox mode
- by default, `settings.yaml` does not need a hardcoded `paired_users_path`; the service chooses a stable OS-appropriate path automatically
- `projects.yaml` is the allowlist of workspaces the bot may access
- Telegram attachments are staged under `.telegram_codex/attachments` inside the active project
- Tracked files stay example-only; real local config remains untracked by default
