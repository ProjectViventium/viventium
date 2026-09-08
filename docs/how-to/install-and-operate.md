# Install and operate Viventium

## Install

The release target is Apple Silicon macOS. The source-checkout installer still needs developer
prerequisites; a signed immutable Easy Install release is a separate acceptance gate. See the
[current setup guide](../04_SETUP_GUIDE.md).

```sh
./install.sh
```

The installer writes the human-owned configuration to
`~/Library/Application Support/Viventium/config.yaml`, stores secrets in macOS Keychain, and
generates runtime files under Application Support. Generated files are outputs; do not edit them as
the source of a product fix.

For a non-interactive install:

```sh
./install.sh --headless --config-input /absolute/path/to/preset.yaml
```

## Operate

To let workers use your Mac, open **Viventium → Computer Access**. Allow Viventium to control apps
and see the screen. Enable Full Disk Access when your work needs protected files, and approve
macOS's app-specific Automation prompts as needed. If macOS asks to reopen Viventium, finish
active work first. Chat remains available while computer access is off.

```sh
bin/viventium doctor
bin/viventium start
bin/viventium status
bin/viventium stop
```

Optional capabilities must fail independently and truthfully. A Voice, search, RAG, Telegram, or
worker dependency may be degraded without blocking the first useful Main chat.

## Local development

Follow [Contributor setup](../04_SETUP_GUIDE.md#contributor-setup) for the supported toolchain,
shared test dependencies, pinned bootstrap, and an isolated `dev-env`. It links the existing
[development runtime owner](../requirements_and_learnings/50_Stable_Dev_Runtime.md#contributor-quickstart).
Source changes do not change the installed runtime until explicit activation.

## Diagnose

Start with `bin/viventium status` and `bin/viventium doctor`. Distinguish stopped, starting,
degraded, unavailable, missing authorization, missing configuration, and unsupported setup. Do not
repair a product defect by hand-editing generated runtime files or database leftovers.

The detailed pre-cutover setup, environment, and troubleshooting files remain readable during the
lossless migration: [`04_SETUP_GUIDE.md`](../04_SETUP_GUIDE.md),
[`05_ENVIRONMENT.md`](../05_ENVIRONMENT.md), and
[`06_TROUBLESHOOTING.md`](../06_TROUBLESHOOTING.md).
