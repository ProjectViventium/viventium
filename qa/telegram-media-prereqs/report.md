# Telegram Media Prerequisites QA Report

## Date

- 2026-04-02

## Build Under Test

- Repo branch: `main`
- Repo commit: `8d5b991`

## Automated Checks Executed

1. `python3 -m pytest tests/release/test_telegram_lazy_startup_contract.py tests/release/test_telegram_media_prereqs.py -q`
   - Result: `4 passed`
2. `python3 -m venv <temp>/viventium-testenv && <temp>/viventium-testenv/bin/pip install -q pytest PyYAML`
   - Result: temporary isolated test env created for subprocess-based preflight tests
3. `<temp>/viventium-testenv/bin/python -m pytest tests/release/test_preflight.py tests/release/test_telegram_lazy_startup_contract.py tests/release/test_telegram_media_prereqs.py -q`
   - Result: `20 passed`

## Independent QA Pass

### Installer / Preflight Contract

Command summary:

- Ran `scripts/viventium/preflight.py --config <synthetic telegram-on config> --json`
- Ran `scripts/viventium/preflight.py --config <synthetic telegram-off config> --json`

Observed results:

- Telegram enabled:
  - context reported `telegram_enabled=True`
  - `ffmpeg` appeared in the preflight items
  - `ffmpeg_status=missing` on the clean synthetic config, which is the expected installer signal
- Telegram disabled:
  - context reported `telegram_enabled=False`
  - `ffmpeg` was absent from the preflight items

### Telegram Launcher Self-Heal Contract

Command summary:

- Extracted `ensure_telegram_media_prereqs()` from `viventium_v0_4/viventium-librechat-start.sh`
- Ran it in a synthetic shell with:
  - no `ffmpeg` on `PATH`
  - a fake `brew` that installs a fake `ffmpeg`

Observed results:

- launcher output included:
  - `WARN:ffmpeg missing; attempting automatic install for Telegram media support`
  - `OK:ffmpeg is ready for Telegram media support`
- synthetic brew log recorded `install ffmpeg`
- final `command -v ffmpeg` succeeded in the harness

## Findings

- Root cause confirmed: Telegram voice-note transcription can reach the local `pywhispercpp` path, and
  `pywhispercpp` requires `ffmpeg` to decode non-WAV media such as Telegram voice notes.
- Fix verified: when Telegram is enabled, preflight now treats `ffmpeg` as a first-class prerequisite,
  and Telegram startup refuses to proceed as healthy unless `ffmpeg` is available or successfully
  auto-installed.

## Regressions

- None found in the targeted automated coverage or the independent QA pass above.

## Follow-Ups

- Full clean-machine `bin/viventium install` acceptance on a brand-new macOS environment is still
  recommended before public release, but the public-safe installer/runtime contract is now covered by
  automated tests plus the synthetic QA evidence above.

## 2026-04-26 Regression Addendum

### Incident Class

Telegram voice-note transcription reached local whisper successfully, but the host ffmpeg binary
aborted before decoding Telegram OGG audio into WAV. The failure was a present-but-not-runnable
Homebrew ffmpeg, not a missing binary and not LibreChat chat routing.

### Added Acceptance

- Preflight treats ffmpeg as healthy only after a real media probe succeeds.
- Installer formula handling rechecks runtime usability after Homebrew install and retries with a
  clean reinstall when a formula reports installed but remains unusable.
- Telegram launcher checks the same media probe and can repair a present-but-broken Homebrew ffmpeg
  when automatic ffmpeg repair is enabled.
- Telegram runtime returns a structured media-decoder error before chat submission if decoder health
  fails during voice/video transcription.
- Mongo evidence for the reproduced class showed zero LibreChat messages/conversations in the
  failed voice-note window, confirming the failed transcript was not forwarded as user input.
