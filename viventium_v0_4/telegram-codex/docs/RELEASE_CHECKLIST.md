# Release Checklist

Use this before flipping the repository public under MIT.

## Code and config

- [ ] No real bot tokens or populated `.env` files are tracked
- [ ] No populated `config/settings.yaml` or `config/projects.yaml` are tracked
- [ ] No machine-specific runtime state is tracked
- [ ] Tests pass with `uv run pytest -q`

## Docs

- [ ] README is accurate
- [ ] Security limitations are stated plainly
- [ ] Setup docs match the actual commands
- [ ] CONTRIBUTING, SECURITY, LICENSE, and Code of Conduct are present

## Repository settings

- [ ] Private vulnerability reporting is enabled
- [ ] Issue templates are enabled
- [ ] Branch protection is configured if needed

## Product sanity

- [ ] Pairing works
- [ ] `/projects`, `/use`, `/status`, `/reset` work
- [ ] Text prompt flow works
- [ ] Voice note transcription works
- [ ] No tests touched personal Telegram contacts or personal chats

