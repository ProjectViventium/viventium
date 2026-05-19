# Voice Component Upstream Refresh Migration

Date: 2026-05-18

## Objective

Migrate the Viventium voice component fork modifications onto the latest original upstream branches while preserving upstream improvements wherever compatible. The raw line-by-line diff artifact is the source-of-truth todo inventory:

- `tmp/voice-component-fork-inventory/2026-05-18-raw-line-by-line-diffs.md`
- `docs/requirements_and_learnings/52_Voice_Component_Fork_Modification_Inventory.md`

## Publication Decision

This migration report records the evaluation work, not the default release decision. The default
public voice playground is the modern `agent-starter-react` LiveKit UI. The classic
`agents-playground` branch is not part of the default install/bootstrap path and should remain
inactive unless a deployment explicitly sets `runtime.playground_variant: classic`.

## Branch Strategy

- Create a latest-upstream baseline branch named `_original` in each voice component repo.
- Create an apply branch from `_original` for the Viventium migration work.
- Use ignored worktrees under `tmp/voice-upstream-refresh/` so existing nested repo checkouts and local dirty files are not disturbed.

## Initial Safety Findings

- `viventium_v0_4/agent-starter-react` had a pre-existing local modification in `app/api/connection-details/route.ts`; this migration does not switch or overwrite that working tree.
- `viventium_v0_4/agents-playground`, `viventium_v0_4/livekit`, and `viventium_v0_4/cartesia-voice-agent` were not edited in-place for this migration; dedicated worktrees are used.

## Component Ledger

| Component | Upstream branch | `_original` branch | Apply branch | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| `agent-starter-react` | `upstream/main` `cee4acfd969c` | `_original` `cee4acfd969c` | `codex/viventium-upstream-refresh` at `e6ccd49ca44a` | committed | Active modern voice UI. |
| `agents-playground` | `upstream/main` `b6e09509fe36` | `_original` `b6e09509fe36` | `codex/viventium-upstream-refresh` at `82bec6259708` | committed | Classic fallback/reference playground. |
| `livekit` | `upstream/master` `f303f499efab` | `_original` `f303f499efab` | `codex/viventium-upstream-refresh` at `e0e1355e07ab` | committed | Public placeholder with upstream LICENSE/NOTICE/README retained. |
| `cartesia-voice-agent` | `upstream/main` `c6873f2f7efb` | `_original` `c6873f2f7efb` | `codex/viventium-upstream-refresh` at `f8183c2e8c9e` | committed | Public placeholder with upstream LICENSE/NOTICE/README retained. |

## Running Decisions

- Used ignored worktrees under `tmp/voice-upstream-refresh/` because the shared `agent-starter-react` checkout had a pre-existing dirty file.
- Added/fetched `upstream` remotes for all four nested repos before creating `_original`.
- `livekit` latest upstream advanced from the inventory-observed `37eb7a327647` to `f303f499efab`; the other three upstream heads matched the inventory-observed commits.
- `agent-starter-react`: preserved upstream Next/LiveKit dependency security bumps for packages Viventium actually imports, but pruned upstream-only Agents UI dependencies because the Viventium fork deletes their consumers.
- `agent-starter-react`: kept upstream `taskfile.yaml` cleanup, removed obsolete `shadcn:install`, and deleted `app/api/token/route.ts` in favor of Viventium `app/api/connection-details/route.ts` plus call-session APIs.
- `agent-starter-react`: documented the intentional discard of upstream audio visualizer configuration knobs; Viventium owns a voice-first call UI with route controls instead of upstream visualizer customization.
- `agents-playground`: kept the classic Viventium fallback hook/token architecture instead of upstream's newer Agent SDK / TokenSource / debug-panel pivot.
- `agents-playground`: absorbed upstream security movement through package ranges and regenerated `pnpm-lock.yaml`; removed stale `package-lock.json` to avoid npm/pnpm disagreement.
- `agents-playground`: deleted direct `@bufbuild/protobuf` because there are no source importers after retaining the Viventium classic hook tree.
- `agents-playground`: dedented the replayed Viventium `.gitignore` block because the old indented patterns did not actually ignore `tmp/`, `backups/`, `videos/`, or `har/`.
- `agents-playground`: intentionally did not backport upstream PRs for Agent SDK session/debug architecture; PR #199 fresh-token-per-connect remains a candidate follow-up rather than part of this compatibility port.
- `agents-playground`: browser QA found that latest `@livekit/protocol` serialized `RoomAgentDispatch.deployment` into token-embedded `roomConfig.agents`, which local LiveKit server `1.10.1` rejects. The migration now keeps participant JWTs room-join-only, removes direct `@livekit/protocol`, and relies on Viventium explicit dispatch with warning logs.
- `livekit`: retained the placeholder strategy after latest upstream advanced to `f303f499efab`; upstream's RTX/version-compare changes do not affect Viventium because the active runtime uses the installed LiveKit server path.
- `cartesia-voice-agent`: retained the placeholder strategy; active Cartesia behavior remains in Viventium voice gateway/shared voice configuration.
- Placeholder repos: after Claude review, re-added upstream legal attribution files and one-page placeholder READMEs so the public repos are explicit rather than silent empty forks.

## Verification Log

- Branch setup: PASS. `_original` branches and `codex/viventium-upstream-refresh` worktrees created for all four component repos without switching the shared nested checkouts.
- `agent-starter-react`: `pnpm install` PASS after dependency pruning.
- `agent-starter-react`: `pnpm exec tsc --noEmit` PASS.
- `agent-starter-react`: `pnpm run lint` PASS; upstream `next lint` deprecation notice only.
- `agent-starter-react`: `pnpm run build` PASS on Next `15.5.18`; warning only that `metadataBase` defaults to `http://localhost:3000` for social images.
- `agent-starter-react`: Playwright CLI render PASS at `http://127.0.0.1:3101`; page title `Viventium Voice Assistant`, route controls visible, no console errors beyond React DevTools info.
- `agents-playground`: `pnpm install` PASS under pnpm `10.33.0`.
- `agents-playground`: `pnpm exec tsc --noEmit` PASS.
- `agents-playground`: `pnpm run lint` PASS with two inherited `react-hooks/exhaustive-deps` warnings in `src/components/playground/Playground.tsx`.
- `agents-playground`: `pnpm run build` PASS on Next `15.5.18` with the same inherited hook warnings.
- `agents-playground`: Playwright CLI render PASS at `http://127.0.0.1:3102`; page title `LiveKit Agents Playground`, connect form visible, no console errors beyond React DevTools/HMR info.
- `livekit`: placeholder shape PASS; root contains `.gitignore`, `LICENSE`, `NOTICE`, and `README.md` only, with public-safety grep clean.
- `cartesia-voice-agent`: placeholder shape PASS; root contains `.gitignore`, `LICENSE`, `NOTICE`, and `README.md` only, with public-safety grep clean.
- Staged diff hygiene before component commits: PASS. `git diff --cached --check` was clean in all four worktrees.
- Staged public-safety scans before component commits: PASS. No local user paths, personal identifiers, or common secret token patterns were found in staged text content.
- Component branch commits: PASS. All four `codex/viventium-upstream-refresh` worktrees are clean after commit.
- Migration report public-safety scan: PASS. No local user paths, personal identifiers, or common secret token patterns were found in this report or the voice fork inventory doc.
- Parent boundary contamination guard: PASS. `uvx pytest tests/release/test_project_boundary_contamination.py -q` completed with `1 passed`.
- Parent boundary contamination guard rerun after browser QA/report updates: PASS. `uvx pytest tests/release/test_project_boundary_contamination.py -q` completed with `1 passed`.
- Viventium wrapper sanity: PASS. `agent-starter-react` has 57 `VIVENTIUM START` and 57 `VIVENTIUM END` markers; `agents-playground` has 21 of each. Placeholder repos intentionally have no code wrappers because they retain only attribution and placeholder metadata.
- Local runtime setup for browser QA: PASS. `livekit-server --dev --bind 127.0.0.1` ran on `ws://localhost:7880`; migrated `agent-starter-react` ran at `http://localhost:3101`; migrated `agents-playground` ran at `http://localhost:3102`.
- Browser-use QA, modern pre-call UI: PASS. In-app browser verified page title, visible Viventium launch screen, route controls, Listening provider menu, and Speaking provider menu.
- Browser-use QA, modern direct-dispatch path: PARTIAL/BLOCKED. With `AGENT_NAME=viventium`, Start Chat reached `/api/connection-details`, but LiveKit returned `503 no response from servers` for agent dispatch because no local agent worker was registered.
- Browser-use QA, modern call-session path without direct dispatch: PASS/PARTIAL. Playwright with fake microphone verified local LiveKit room connect, session controls, Voice menu, Wing Mode dialog, End Call return path, and screenshot artifacts under `output/playwright/`. The call-session state API returned expected `500` errors because `VIVENTIUM_LIBRECHAT_ORIGIN` was not configured in this isolated run.
- Browser-use QA, fallback pre-call UI: PASS. In-app browser verified the fallback playground rendered, displayed room/agent/user panels, retained `viventium` as default agent name, and exposed Settings menu toggles.
- Browser-use QA, fallback local connect: FAIL then PASS after fix. Initial fake-mic Playwright connect failed because the token embedded `roomConfig.agents` with a newer `RoomAgentDispatch.deployment` field that local LiveKit server `1.10.1` rejected. The refreshed fix removes token-embedded `RoomConfiguration.agents`, keeps explicit dispatch best-effort with warning logs, removes direct `@livekit/protocol`, and verified `Connected`, `Disconnect`, `Fake Default Audio Input`, no connection-error toast, and no browser console errors.
- Fallback token-shape regression check: PASS. `/api/token` returned `200`; decoded local dev JWT had `hasRoomConfig: false`, retained the requested room grant, and used issuer `devkey`.

## Claude Review Log

- `agent-starter-react`: Claude structured review completed. Incorporated the high-severity dependency pruning finding, removed the misleading `app/(app)/page.tsx` wrapper, narrowed the `lib/utils.ts` wrapper to the actual `cn()` helper, and added `.playwright-cli/` to `.gitignore`.
- `agent-starter-react`: Remaining Claude-noted gaps before release/landing: real LiveKit voice user-path QA for mic publish, transcript dedupe, citation stripping, Wing Mode, Listen-Only persistence, recovery, wake-lock, and fallback display; parent component checkout/pin still not updated from the ignored migration worktree.
- `agents-playground`: Claude structured review completed. Incorporated lockfile/index cleanup, removed stale `package-lock.json`, staged regenerated `pnpm-lock.yaml`, added Viventium wrappers, dedented `.gitignore`, and documented deliberate upstream discards.
- `agents-playground`: Remaining Claude-noted gaps before release/landing: real fallback LiveKit connect/mic/transcript path, token endpoint unit coverage, and optional fresh-token-per-connect backport decision.
- `agents-playground` follow-up compatibility review: Claude agreed that removing token-embedded `roomConfig.agents` is the right compatibility fix for LiveKit server `1.10.1`, because `@livekit/protocol` `1.45.x` adds `RoomAgentDispatch.deployment`. Incorporated the requested comment specificity, dispatch warning logs, and inventory update. Remaining high-severity landing gap is agent-worker proof: this local run verified room/mic connection, but not that a registered `viventium` worker actually joins and produces transcript/audio.
- `livekit` / `cartesia-voice-agent`: Claude structured review completed. Incorporated the legal/boundary finding by re-adding LICENSE/NOTICE and placeholder README files while keeping the placeholder deletion strategy.
- Placeholder remaining gap before release/landing: push the component origins, then update the parent `components.lock.json`; do not push `_original` branches unless intentionally publishing full upstream source history is desired.

## Release / Landing Gaps

- Parent component pins were not updated in this pass. The active release path is the modern
  `agent-starter-react` playground; the classic `agents-playground` migration remains excluded from
  default publishing so it does not consume install or runtime resources by default.
- Full LiveKit voice-call UX QA remains partial because this pass ran local LiveKit room/microphone browser QA but did not run a registered Viventium agent worker, transcript round trip, recovery, or wake-lock persistence against the full LibreChat call-session runtime.
- The shared nested repo checkouts under `viventium_v0_4/` were not switched or overwritten; the migrated code lives on the dedicated component branches listed above.
