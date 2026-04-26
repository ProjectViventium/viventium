# Telegram Media Prerequisites QA Plan

## Scope

Verify that Telegram voice-note and video-note prerequisites are installed and validated through the
public Viventium install and runtime paths.

## Requirements Under Test

- Telegram voice-note transcription must not depend on undeclared machine-local tools.
- When Telegram is enabled, Viventium preflight/install must detect and install the required media
  dependency batch automatically.
- Telegram startup must refuse to report healthy when the required media dependency is missing or
  installed but not runnable.
- Telegram runtime must stop before chat submission and return one clean media-decoder error if
  ffmpeg becomes broken after startup.
- Documentation must explain the owning cause, fix, and recovery path without relying on private
  machine state.

## Environments

- Public repo checkout at the repository root
- Release-style automated tests under `tests/release/`
- Telegram bridge tests under `viventium_v0_4/telegram-viventium/tests/`

## Test Cases

1. Preflight with native install, local voice, and Telegram enabled lists `ffmpeg` as a required Mac prerequisite.
2. Preflight without Telegram enabled does not pull in the Telegram-only `ffmpeg` requirement.
3. Telegram launcher contract checks `ffmpeg` before starting the bot and fails clearly if it cannot be made available.
4. Telegram launcher contract repairs a present-but-broken Homebrew `ffmpeg` when automatic ffmpeg repair is enabled.
5. Telegram voice/video transcription surfaces a structured decoder error when runtime probing fails.
6. Existing Telegram lazy-STT contracts still pass after the prerequisite changes.
7. Telegram requirements and troubleshooting docs describe the prerequisite and failure mode.

## Expected Results

- `bin/viventium install` and `bin/viventium upgrade` pick up `ffmpeg` through preflight whenever
  Telegram is enabled.
- `viventium_v0_4/viventium-librechat-start.sh` does not silently start a partially broken Telegram
  bridge when `ffmpeg` is unavailable or installed but not runnable.
- Failed decoder probes do not create LibreChat user turns.
- The repo contains a public-safe QA report with the executed commands and outcomes.
