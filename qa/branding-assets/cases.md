# Branding Assets QA Cases

## Case ID Convention

Use stable `BRAND-NNN` IDs for branding assets cases.

## Case Catalog

| Case ID | Requirement | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- |
| `BRAND-001` | Web assets render from portable paths | Web UI and playground | Playwright browser QA plus config compiler tests | PARTIAL 2026-05-18 (`reports/2026-05-18-librechat-model-selector-icons.md`; LibreChat model selector only) |
| `BRAND-002` | Helper/app assets match shipped artifacts | macOS helper, installer, generated manifests | test_macos_helper_install.py and release-readiness scan | NOT YET RUN (cataloged 2026-05-17; run when feature changes) |
| `BRAND-003` | Missing asset fallback stays branded | Agent/avatar UI, generated config | test_config_compiler.py | PARTIAL 2026-05-18 (`reports/2026-05-18-librechat-model-selector-icons.md`; focused automated fallback coverage only) |
| `BRAND-004` | Model selector uses the Viventium logo for configured local model-spec icons | LibreChat model selector | Playwright browser QA plus focused Jest | PASS 2026-05-18 (`reports/2026-05-18-librechat-model-selector-icons.md`) |

## `BRAND-001` - Web assets render from portable paths

- Requirement: Web assets render from portable paths.
- Risk covered: Viventium claims the behavior works without proving the real user-visible surface and supporting state.
- Preconditions: local runtime or focused harness is available with synthetic public-safe data.
- Steps:
  1. Open login, app shell, and playground; verify logo/favicon/brand assets load from repo/runtime public paths and survive refresh.
  2. Compare visible result with source/config, logs or persisted state summary, and the owning requirement doc.
  3. Save a public-safe dated report under `reports/` using the standard run-report template.
- Expected result: visible behavior, supporting evidence, and documentation agree.
- Forbidden result: mocks, backend logs, source inspection, or model output are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, state/log summary, and public-safety review.
- Automation: Playwright browser QA plus config compiler tests.
- Last run: PARTIAL 2026-05-18 (`reports/2026-05-18-librechat-model-selector-icons.md`;
  LibreChat model selector asset path verified, full playground/favicon/PWA sweep not run).

## `BRAND-002` - Helper/app assets match shipped artifacts

- Requirement: Helper/app assets match shipped artifacts.
- Risk covered: Viventium claims the behavior works without proving the real user-visible surface and supporting state.
- Preconditions: local runtime or focused harness is available with synthetic public-safe data.
- Steps:
  1. Inspect helper packaging and generated manifests; verify source asset, prebuilt artifact, and installer references agree.
  2. Compare visible result with source/config, logs or persisted state summary, and the owning requirement doc.
  3. Save a public-safe dated report under `reports/` using the standard run-report template.
- Expected result: visible behavior, supporting evidence, and documentation agree.
- Forbidden result: mocks, backend logs, source inspection, or model output are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, state/log summary, and public-safety review.
- Automation: test_macos_helper_install.py and release-readiness scan.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## `BRAND-003` - Missing asset fallback stays branded

- Requirement: Missing asset fallback stays branded.
- Risk covered: Viventium claims the behavior works without proving the real user-visible surface and supporting state.
- Preconditions: local runtime or focused harness is available with synthetic public-safe data.
- Steps:
  1. Simulate or inspect fallback paths for missing built-in/user agent avatars; verify Viventium fallback appears and no external/private image path is embedded.
  2. Compare visible result with source/config, logs or persisted state summary, and the owning requirement doc.
  3. Save a public-safe dated report under `reports/` using the standard run-report template.
- Expected result: visible behavior, supporting evidence, and documentation agree.
- Forbidden result: mocks, backend logs, source inspection, or model output are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, state/log summary, and public-safety review.
- Automation: test_config_compiler.py.
- Last run: PARTIAL 2026-05-18 (`reports/2026-05-18-librechat-model-selector-icons.md`;
  focused fallback tests pass, separate Agent Builder missing-avatar browser path not run).

## `BRAND-004` - Model selector uses the Viventium logo for configured local model-spec icons

- Requirement: Model selector rows and the selected model button must render configured local
  Viventium logo paths as image assets, not as endpoint icon keys.
- Risk covered: A configured `iconURL: /assets/logo.svg` can be misclassified as a built-in icon key
  and fall through to LibreChat's generic `agents` feather icon.
- Preconditions: local LibreChat runtime is available with synthetic public-safe QA login data and
  the Viventium model-spec bundle loaded.
- Steps:
  1. Open the LibreChat chat surface, select the model dropdown, and inspect the selected model
     button plus the visible model-spec rows.
  2. Repeat in explicit light and dark app themes.
  3. Verify visible Viventium "V" logo images use `/assets/logo.svg`, no `.lucide-feather` node is
     present, and the embedded SVG receives the app theme's `color-scheme`.
  4. Compare with source/config, automated tests, runtime config, console summary, and the owning
     branding requirement doc.
- Expected result: the selected model button and all visible Viventium model rows show the
  Viventium logo, remain theme-aware in light and dark modes, and expose no LibreChat feather icon.
- Forbidden result: a LibreChat feather icon, a broken image, a non-theme-aware Viventium logo, or
  private/local asset URLs in model-spec config.
- Evidence to capture: sanitized Playwright screenshot names, DOM count for visible rows, source
  file references, focused test results, and public-safety review.
- Automation: Playwright browser QA plus focused Jest component tests.
- Last run: PASS 2026-05-18 (`reports/2026-05-18-librechat-model-selector-icons.md`).

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Branding Assets. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `BRAND-UC-001` | On Web UI and playground, verify that web assets render from portable paths. | owning requirement for `BRAND-001` / `BRAND-001` | Web UI and playground | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to BRAND-001. | The visible result for BRAND-001 matches the documented requirement. | PARTIAL 2026-05-18 (`reports/2026-05-18-librechat-model-selector-icons.md`; LibreChat model selector only) |
| `BRAND-UC-002` | On macOS helper, installer, generated manifests, try helper/app assets match shipped artifacts with missing setup, missing auth/config, empty state, or a degraded dependency. | owning requirement for `BRAND-002` / `BRAND-002` | macOS helper, installer, generated manifests | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to BRAND-002. | The user sees an honest setup, retry, or degraded-state result for BRAND-002; no fake success is accepted. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `BRAND-UC-003` | After missing asset fallback stays branded, refresh, restart, retry, or switch linked surfaces and verify persistence/parity. | owning requirement for `BRAND-003` / `BRAND-003` | Agent/avatar UI, generated config | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to BRAND-003. | BRAND-003 remains correct after the persistence or parity step and final wording matches evidence. | PARTIAL 2026-05-18 (`reports/2026-05-18-librechat-model-selector-icons.md`; focused fallback tests only) |
| `BRAND-UC-004` | Open the model selector in light and dark mode and verify all visible Viventium model icons are the V logo, not the LibreChat feather. | owning requirement for `BRAND-004` / `BRAND-004` | LibreChat model selector | Source, owning requirement doc, runtime config, focused tests, Playwright DOM evidence, console summary, and screenshots. | Visible Viventium model rows and selected model button show `/assets/logo.svg`, carry the app theme `color-scheme`, and expose no `.lucide-feather` node. | PASS 2026-05-18 (`reports/2026-05-18-librechat-model-selector-icons.md`) |
