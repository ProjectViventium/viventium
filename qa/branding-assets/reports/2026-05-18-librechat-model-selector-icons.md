# Branding Assets QA Run - 2026-05-18

## Summary

- Result: PASS for `BRAND-004`; PARTIAL for broader `BRAND-001`/`BRAND-003` surfaces not directly touched by the escaped bug.
- Build/source under test: working tree LibreChat fork and branding docs/QA updates.
- Runtime/artifact under test: local LibreChat web runtime at localhost frontend/API ports.
- Environment: local development runtime with synthetic QA login data.
- Tester: Codex.
- Related change: model selector and agent fallback icon paths now render the Viventium logo asset instead of LibreChat's generic feather, with explicit light/dark theme handling.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `BRAND-004` | PASS | Playwright DOM: 20 model options; first 12 visible Viventium rows use `/assets/logo.svg`; `featherCount: 0`; dark rows `color-scheme: dark`; light rows `color-scheme: light`. Screenshots: `output/playwright/viventium-model-selector-logo-dark.png`, `output/playwright/viventium-model-selector-logo-light.png`. | Direct escaped-bug regression. |
| `BRAND-001` | PARTIAL | LibreChat web UI verified; playground not run because this change only touches LibreChat model/agent icon rendering. | Follow-up full branding sweep still needed for release-wide `BRAND-001`. |
| `BRAND-003` | PARTIAL | Focused Jest covers missing-avatar fallback rendering `/assets/logo.svg`; no separate Agent Builder missing-avatar browser path was run. | Direct model selector path is covered by `BRAND-004`. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `BRAND-UC-004` | Open the model selector in light and dark mode and verify all visible Viventium model icons are the V logo, not the LibreChat feather. | Playwright browser against LibreChat chat UI. | PASS | Selected model button and visible Viventium model rows show the Viventium "V" logo in both themes. | Runtime `/api/config` exposes first spec `iconURL: /assets/logo.svg`; source docs updated in `16_Branding_and_Assets.md`; focused Jest and lint pass; post-reload console showed 0 errors and 1 framework warning. | None for this bug. |
| `BRAND-UC-001` | Verify web assets render from portable paths. | LibreChat web UI only. | PARTIAL | Model selector and selected model button render portable `/assets/logo.svg`. | Source/config agree for LibreChat model specs. | Playground and full favicon/PWA pass not run. |
| `BRAND-UC-003` | Verify branded fallback persists after refresh/parity step. | LibreChat model selector after light/dark reload. | PARTIAL | Model selector remained correct after theme reloads. | Focused fallback tests pass for agent cards and utility fallback. | Separate missing-avatar Agent Builder browser path not run. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: LibreChat model selector model-spec icon rendering.
- Requirement: Viventium surfaces must not show upstream LibreChat feather branding; Viventium logo must be theme-aware.
- Use case: `BRAND-UC-004`.
- QA case: `BRAND-004`.
- Expected result: selected model button and visible Viventium model rows use `/assets/logo.svg`, no `.lucide-feather`, and explicit app light/dark themes set matching image `color-scheme`.
- Actual evidence: Playwright browser PASS in both explicit dark and light modes; focused Jest PASS; touched-file ESLint PASS.
- Remaining gap or fix: none for the reported model selector bug.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Branding requirement doc plus `BRAND-004` / `BRAND-UC-004`. |
| Code owning path | Which code path owns the behavior? | `SpecIcon.tsx` classifies model-spec icon URLs; `URLIcon.tsx` renders image URLs; `ViventiumLogoIcon.tsx` and `viventiumLogoTheme.ts` handle fallback logo/theme bridging; `Icons.tsx`, `agents.tsx`, `MinimalIcon.tsx`, and `MessageEndpointIcon.tsx` own agent fallback surfaces. |
| Docs and nested docs/repos | Which docs or nested repo docs define the expected behavior? | `docs/requirements_and_learnings/16_Branding_and_Assets.md`; LibreChat runtime docs were inspected before code changes. |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | Focused Jest for `SpecIcon`, `ViventiumLogoIcon`, agent utilities, and AgentCard; touched-file ESLint; config compiler tests; Playwright browser QA. |
| Local/external prerequisite state | Which required local service, provider, Docker-backed sidecar, OAuth grant, API key, model, or hosted dependency was proven healthy or degraded? | Local frontend/API responded; `/api/config` returned Viventium title and `/assets/logo.svg` for model specs. |
| Logs | Which sanitized logs confirm or contradict the result? | After authenticated reloads, Playwright console summary showed 0 errors and 1 framework warning. |
| DB/state/persistence | Which sanitized state, DB count/hash, persisted message, config, or artifact confirms it? | Synthetic QA login data was used only to reach the real UI; no private user data or identifiers retained here. Light/dark preference persisted through reload via app theme storage. |
| Generated/shipped artifact | Which generated config, compiled bundle, prebuilt helper, or installed artifact was inspected when applicable? | Runtime config and source-of-truth config both point model-spec icons to `/assets/logo.svg`; config compiler tests passed. |
| Real user path | Which browser/computer, Telegram, voice, installer, CLI, MCP/tool, scheduler, or GlassHive path was used like a user? | Browser login, chat page, model selector open, light/dark theme reload, visual inspection, DOM inspection. |
| Visual/UX comparison | Does the visible UI/UX or delivered result match the expected behavior and supporting evidence? | Yes. Screenshots show Viventium "V" icons in dark and light selector states. |
| Not run / blocked | Which required surface was not run, and why is the result partial or blocked? | Playground, helper packaging, and separate Agent Builder missing-avatar browser path were not run because the reported bug is scoped to LibreChat model selector icons. Full client `typecheck` remains blocked by unrelated existing errors; no touched-file matches were reported. |

## User-Grade Evidence

- Surface exercised: LibreChat chat UI model selector.
- Real user path: authenticated synthetic QA user opened `/c/new`, opened model selector, repeated after explicit dark and light theme reloads.
- Visible outcome: Viventium "V" logo appears for the selected model and visible Viventium model rows; no LibreChat feather icon appears.
- Expanded/detail state: model selector listbox contained 20 options; first 12 visible Viventium rows used `/assets/logo.svg`.
- Persistence/reload result: explicit `dark` reload produced `color-scheme: dark`; explicit `light` reload produced `color-scheme: light`.
- Local/external prerequisite state: local runtime API config available and Viventium-branded.
- Evidence retrieval classification, if applicable: successful.
- Fallback path, if applicable: not needed.
- Backend/log/DB confirmation: runtime config confirmed Viventium model specs use `/assets/logo.svg`; no post-reload browser console errors.
- Final model/runtime wording check: final result is scoped to model selector and affected fallback icon surfaces; broader branding release readiness is not claimed.
- Substitution check: automated tests and config inspection support, but do not replace, the real browser selector evidence.

## Automated Evidence

```bash
npm run test:ci -- SpecIcon.test.tsx ViventiumLogoIcon.test.tsx agents.spec.tsx AgentCard.spec.tsx
npx eslint client/src/components/Endpoints/ViventiumLogoIcon.tsx client/src/components/Endpoints/viventiumLogoTheme.ts client/src/components/Endpoints/URLIcon.tsx client/src/components/Endpoints/__tests__/ViventiumLogoIcon.test.tsx client/src/components/Chat/Menus/Endpoints/components/SpecIcon.tsx client/src/hooks/Endpoint/Icons.tsx client/src/utils/agents.tsx client/src/components/Endpoints/MinimalIcon.tsx client/src/components/Endpoints/MessageEndpointIcon.tsx client/src/utils/__tests__/agents.spec.tsx client/src/components/Agents/tests/AgentCard.spec.tsx client/src/components/Chat/Menus/Endpoints/components/__tests__/SpecIcon.test.tsx
uv run --with pytest --with pyyaml python -m pytest tests/release/test_config_compiler.py -q
npm run typecheck
```

- Focused Jest: PASS, 4 suites / 38 tests.
- Touched-file ESLint: PASS.
- Config compiler: PASS, 92 tests.
- Client typecheck: FAIL due existing unrelated errors; scan of the captured output found no touched-file matches for this change.

## Findings

- Defects: fixed `SpecIcon` relative asset path misclassification and LibreChat feather fallback exposure.
- Regressions: none found in focused tests or real browser selector QA.
- Flakes: none observed.
- Environment issues: full client typecheck remains blocked by unrelated existing TypeScript errors outside this change.
- Residual risks: full branding sweep across playground/helper assets was not part of this scoped bug fix.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
