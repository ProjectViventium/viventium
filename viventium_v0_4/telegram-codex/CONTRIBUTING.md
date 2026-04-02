# Contributing

Thanks for helping with `telegram-codex`.

## Before you open a PR

- Keep secrets and personal bot tokens out of the repo.
- Test only against bots or disposable chats.
- Keep localhost-only pairing as the default security story.
- Keep configuration machine-local. Tracked files should stay example-only.

## Local setup

```bash
uv sync
cp .env.example .env
cp config/settings.example.yaml config/settings.yaml
cp config/projects.example.yaml config/projects.yaml
uv run pytest -q
uv run telegram-codex
```

## Contribution shape

- Prefer small, reviewable pull requests.
- Add or update tests when behavior changes.
- Update docs when setup, commands, security behavior, or user-facing flows change.
- Call out any changes that widen local execution power or change the pairing model.

