<!-- qa-evidence-exempt: legacy sanitized RCA/QA note retained for historical context; current acceptance must use cases plus a fresh v2 report. -->

# 2026-06-07 Public Nested Repo Push QA

## Scope

Release-readiness evidence for pushing local Viventium development through the public nested repos
and updating the parent component lock.

## Nested PRs

| Repo | PR | Resulting `origin/main` ref |
| --- | --- | --- |
| `ProjectViventium/viventium-librechat` | https://github.com/ProjectViventium/viventium-librechat/pull/35 | `b9f8660725571fb7875f64d9010b44120775a0be` |
| `ProjectViventium/GlassHive` | https://github.com/ProjectViventium/GlassHive/pull/23 | `c8e08cf8921ff184af23fde7eb884cabc7a2b9fc` |
| `ProjectViventium/agent-starter-react` | https://github.com/ProjectViventium/agent-starter-react/pull/6 | `83044a509b2ccd798deee916291776912b5c1b9e` |

## Public-Safety Review

- Scanned parent, LibreChat, GlassHive, and agent-starter-react public-candidate diffs for named
  client/project markers, local usernames/hostnames, local absolute paths, private IP ranges, and
  secret/token shapes.
- Re-ran scans on the actual nested PR branch diffs before merge.
- Re-ran addition-side PR patch scans before merge.
- Residual hits were reviewed and limited to intentional redaction regexes or synthetic placeholder
  email examples.
- ClaudeViv review-only pass found one local username fixture and stale component pins; both were
  fixed before merge/pin update.

## Verification Run

| Surface | Evidence |
| --- | --- |
| Parent release tests | `779 passed, 1 skipped` for `tests/release/` |
| Parent focused gate | `68 passed` for QA contract, helper, stable-runtime, governance, and activation source-of-truth tests |
| Parent installer/config slice | `162 passed` for bootstrap selection, public manifest, config compiler, and upgrade tests |
| Telegram component | `298 passed` |
| Shared component | `11 passed` |
| Voice gateway | `341 passed`, plus subtests passed |
| LibreChat local suites | `test:api`, `test:packages:api`, `test:packages:data-provider`, `test:packages:data-schemas`, `test:client`, and scheduling-cortex tests passed |
| LibreChat GitHub checks | package builds, ESLint, API tests, package tests, Ubuntu/Windows/Vite, Redis integration, i18n-unused, and unused-package checks passed |
| GlassHive runtime | `335 passed, 3 skipped` |
| GlassHive UI | `77 passed` |
| Voice playground | `pnpm build`, `pnpm format:check`, and GitHub `test` check passed |
| Browser QA | Prompt Workbench, GlassHive stub runtime/UI, and voice playground local dev server were exercised through a real browser |
| Fresh public install | PASS: raw public `install.sh` from the parent PR branch cloned the parent repo into `<temp>`, bootstrapped LibreChat, agent-starter-react, and GlassHive at the merged pinned refs, compiled runtime files with `START_GLASSHIVE=true`, and passed doctor with `--no-start` |
| Public upgrade check | PASS: temp PR-branch install reported no blockers, no dirty checkout, no component lock drift, no helper rebuild, and no update drift |
| Public upgrade | PASS: temp PR-branch install pulled the PR branch, kept LibreChat, agent-starter-react, and GlassHive at clean pinned refs, recompiled runtime files, and passed doctor without restarting the live local stack |

## Install/Upgrade Notes

- During the first isolated install probe, a fully temporary `HOME` correctly failed preflight because
  no Codex or Claude CLI login existed in that throwaway home. The final install acceptance used a
  temporary Viventium install root and App Support state while allowing the host CLI auth probe to see
  the already-signed-in local CLI account.
- The temp full-upgrade acceptance used non-default QA ports before the upgrade run so it would not
  stop, restart, or collide with the live local Viventium stack.
- The upgrade command exited successfully. Its continuity audit reported a warning only because the
  temp no-start install did not have a running Mongo service for continuity introspection; the audit
  reported no errors.
- A fresh-install gap was found and fixed during this QA pass: GlassHive was enabled in config, but
  the bootstrap selector did not fetch the `GlassHive` component before compile/start. The selector
  now includes `GlassHive` whenever `integrations.glasshive.enabled=true`, and the regression test
  verifies that default modern voice installs fetch LibreChat, agent-starter-react, and GlassHive.

## Result

`components.lock.json` now pins the merged nested `main` refs listed above, so fresh install and
upgrade flows fetch the public merged code instead of stale component commits.

The parent installer branch acceptance proved the public entrypoint and upgrade path before merge.
After merge, the same branch commit becomes the public `main` entrypoint.
