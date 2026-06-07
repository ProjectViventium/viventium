<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# Plugged-In Memory Hardener Efficiency QA - 2026-05-27

## Scope

This report covers `MEMHARD-004`: plugged-in model-backed transcript maintenance must remain
efficient without stopping Viventium, Docker, or installed programs.

## Root Cause Confirmed

A pre-change operator loop repeatedly invoked transcript ingest with one file per run. Each
iteration paid the full wrapper -> Node -> Mongo -> model -> vector lifecycle startup cost. That
made the laptop hot even while plugged in because the battery/thermal gate was not involved and the
authoritative hardener did not have an apply cooldown or apply-mode batch floor.

## Fix Verified

- Node hardener now owns the dry-run/apply cooldown before Mongo/model work.
- Power override and efficiency override are separate; `--ignore-power-gate` cannot bypass the
  cooldown.
- Apply-mode transcript batches are floored to 5 files by default.
- Wrapper `--until-caught-up` defaults to one batch per invocation.
- Helper manual transcript ingest uses a one-batch interactive maintenance path that bypasses only
  the cooldown and still respects the power/thermal gate.
- `memory-harden status` avoids the global CLI lock and config compile path.
- Shipped macOS helper prebuilt and source hash were rebuilt after the helper source change.

## Evidence

- Static checks:
  - `node --check viventium_v0_4/LibreChat/scripts/viventium-memory-hardening.js` passed.
  - `python3 -m py_compile scripts/viventium/memory_harden.py scripts/viventium/config_compiler.py` passed.
  - `swiftc -parse-as-library -typecheck apps/macos/ViventiumHelper/Sources/ViventiumHelper/ViventiumHelperApp.swift` passed.
- Release tests:
  - `uvx --with pyyaml pytest tests/release/test_memory_hardening_contract.py -q`: 40 passed.
  - `uvx --with pyyaml pytest tests/release/test_config_compiler.py -q`: 106 passed.
  - `uvx --with pyyaml pytest tests/release/test_macos_helper_install.py -q`: 11 passed.
- Live operational checks:
  - Process scan found no active `memory_harden.py`, `viventium-memory-hardening.js`, or transcript
    repair loop consuming CPU.
  - Top CPU consumers were UI/browser/Codex/WindowServer/Docker VM classes, not the memory hardener.
  - Read-only `bin/viventium memory-harden status --json` completed while local runtime remained up.
  - Synthetic cooldown marker smoke returned `allowed: false`, `reason: maintenance_cooldown`, and
    the expected next allowed timestamp.

## Remaining Risk

The live status output had no efficiency marker yet because no post-fix apply run has completed on
the real local state. The synthetic cooldown smoke proves the Node gate; the real marker will appear
after the next model-backed apply reaches the new code path.

## Result

`MEMHARD-004` is `PASS` for source, generated config, helper artifact, release tests, Claude
review follow-up coverage, and live cooldown/status smoke. Full live transcript-vector acceptance
still depends on an operator-approved post-fix model-backed apply with available provider/vector
runtime.
