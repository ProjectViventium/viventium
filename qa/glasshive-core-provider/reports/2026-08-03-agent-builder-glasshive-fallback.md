# Agent Builder GlassHive Fallback QA — 2026-08-03

## Outcome

`GCP-019`, `TR-011`, and `TELEGRAM-UC-010` are **PARTIAL**. The corrected source and focused
regressions prove the existing Agent Builder fallback can select GlassHive/Claude Opus 5, preserve
its model effort, create a distinct fallback provider attempt, and reject fallback after authoring.
Real Claude Opus 5 authentication/availability was also proven with synthetic content.

Installed Telegram and Agent Builder acceptance are not claimed. The installed runtime still carries
the old capability that excludes GlassHive from fallback targets and is owned by a different
protected checkout. Promoting the current dirty multi-repository checkout would also activate
unrelated work, so it was not used as a shortcut. The Main Agent therefore remains safely on its
prior direct Anthropic fallback until runtime config/build activation can happen first.

## Root cause

Three independent conditions produced the escaped failure:

1. Compiled capability metadata set `automatic_fallback_target: false`, so Agent Builder hid
   GlassHive and server validation rejected it.
2. The built-in and live Main Agent generic `fallback_llm_*` fields pointed to direct Anthropic
   `claude-opus-4-8`, not GlassHive `claude-code:opus` (Claude / Opus 5).
3. GlassHive lifecycle `started` status entered chat reasoning. LibreChat correctly refuses a second
   author once reasoning begins, so the lifecycle-only delta incorrectly locked the fallback.

Merely changing the saved model is insufficient. A same-provider retry that reuses
`main:<responseMessageId>` reopens GlassHive's failed idempotent Codex request. The fallback must keep
the same outer LibreChat/Telegram turn while using a distinct provider attempt key,
`main-fallback:<responseMessageId>`.

The public rate-limit text was already a recoverable fallback class. Structured
`provider_quota_exhausted` classification is useful hardening but is not credited as the primary fix.

## Corrected contract

- The ordinary Agent Builder fields `fallback_llm_provider`, `fallback_llm_model`, and
  `fallback_llm_model_parameters` own this recovery.
- The built-in Main Agent and background-Agent bootstrap source select GlassHive / Claude Opus 5
  with `high` effort for the generic Agent fallback.
- Queue/wait/start/provider-switch lifecycle events stay out of reasoning.
- The primary and fallback use distinct provider-attempt keys inside one visible turn.
- Lazy fallback initialization receives the selected provider capability, broker bundle, and
  cancellation endpoint.
- Cancellation during lazy initialization prevents the fallback; cancellation after the switch
  targets only the active fallback attempt.
- Visible text or genuine reasoning/plan/tool/file evidence permanently locks fallback for the turn.
- `glasshive_options.fallback_*` remains a separate configurable advanced option and is disabled on
  the built-in and live Main Agent.
- When GlassHive is disabled at install time, every built-in Agent fallback is normalized to a
  distinct supported direct-provider route rather than silently dropping recovery.
- The retired direct Opus model is absent from active source, compiler, runtime, UI, and test
  surfaces; dated historical QA reports remain unchanged as evidence of what those old runs used.

## Evidence actually run

### Source and focused regressions

- Red-first tests reproduced missing attempt identity/capability switching, stripped Claude effort,
  and the absent runtime fallback marker.
- 203 focused LibreChat backend/runtime-model tests passed.
- 149 compiler tests passed, including the GlassHive fallback capability, built-in Agent selection,
  non-GlassHive install normalization, and a new dev-env regression for configs that rely on default
  app-facing ports.
- All 39 stable-dev workflow tests passed with the supported Python 3.12 interpreter explicitly
  selected. Five runtime-intent/public-evidence safety tests also passed.
- 36 API package validation/initialization tests and 61 data-provider configuration tests passed.
- 258 post-build backend/callback/sync tests passed.
- The Agent Builder fallback-picker test passed all 7 cases in an isolated Jest runner and proves a
  capability-declared GlassHive provider appears in the generic fallback picker.
- The full GlassHive runtime test suite completed with no failures. The HTTP-level regression keeps
  one outer conversation/message while issuing `main:<message>` for Codex and
  `main-fallback:<message>` for Claude, with no provider-internal fallback header or persisted option.
- Production API/data packages and the frontend were rebuilt successfully; post-build verification
  passed.
- The earlier controlled provider test confirmed the authenticated CLI resolves
  `claude-code:opus` to native `claude-opus-5`. That test exercised the optional provider-internal
  path and proves Claude availability only; it does **not** count as Agent Builder fallback acceptance.

### Live state safety

Required live/source comparison exposed unrelated voice/cortex drift. A narrow reviewed restoration
removed only the mistakenly enabled provider-internal fallback fields from the live Main Agent.
A live pull verified:

- primary remains GlassHive / Codex
- `glasshive_options` contains only workspace/access
- generic fallback remains direct Anthropic pending runtime-first activation
- unrelated voice and user-managed fields were untouched

### Independent review

Claude Opus 5 xHigh independently confirmed the author-lock, capability, and same-provider
idempotency RCA. It rejected live Agent-first sync because the installed capability still excludes
GlassHive, and identified cancellation rebinding, lazy-init cancellation, per-model effort hygiene,
non-GlassHive install fallback, stale build artifacts, and superseded QA wording as required gaps.
Those findings were remediated and covered by the passing regressions/builds above. The review does
not replace installed browser or Telegram evidence.

### User-path attempt

- The supported side-by-side dev path correctly compiled GlassHive with
  `automatic_fallback_target: true`, but the initial config relied on profile-default web ports. A
  red-first compiler regression now proves the dev defaults become API `4180`, web `4190`,
  playground `4300`, and voice health `9301`.
- The dev startup then failed closed because its Mongo state did not match the installed singleton
  already using the configured port. A narrower manual launch was aborted when Meilisearch
  persistence/credential ownership also did not match. No browser result from that attempt is
  credited.
- The temporary dev state was stopped and removed. The installed runtime was restored through its
  supported stop/background-launch path. Mongo, Meilisearch, LibreChat API, frontend proxy,
  Telegram bridge, and Telegram Codex were directly rechecked as healthy/running afterward.
- The installed `/api/endpoints` still reports GlassHive
  `automatic_fallback_target: false`, so runtime-first activation and the narrow Agent sync were not
  attempted.

## High-effort bootstrap and retired-model follow-up

The follow-up migration changed the bootstrap contract from max to **high** effort and widened it
from Main to all twelve source-owned conscious/background Agents. The provider-internal
`glasshive_options.fallback_*` fields remain absent; only the ordinary Agent Builder
`fallback_llm_*` fields select GlassHive / Claude / Opus 5.

Evidence run after that migration:

- Source/compiler invariant checks parsed both shipped YAML templates and proved all twelve Agent
  fallback bags equal `glasshive-harness / claude-code:opus / high`, the capability allows
  `automatic_fallback_target`, its Opus 5 recommended effort is high, and the Main Agent has no
  provider-internal fallback.
- GlassHive-disabled normalization proved every built-in falls back to the supported direct
  `anthropic / claude-opus-5` route instead of retaining an unavailable harness or the retired
  direct Opus route.
- The exact Telegram message "The model provider rate-limited this request. Please try again
  shortly." is regression-covered and produces a GlassHive Opus 5 fallback Agent with high effort;
  the final fallback-helper suite passed 23/23.
- Relevant API tests passed 223/223 before the added exact-message regression; API-package tests
  passed 29/29, data-provider tests 74/74, client Agent Builder/Feelings tests 35/35, and both touched
  GlassHive runtime suites passed.
- The broad root regression command passed 290 tests and exposed three failures. The two in-scope
  capability/source and direct-Anthropic-role failures were fixed and passed individually. One
  unrelated pre-existing productivity-prompt assertion remains outside this change.
- API/data/client packages and the production client rebuilt successfully. A post-build scan found
  no retired-model reference in rebuilt artifacts. An active-surface regression scan likewise
  found none in source, compiler, templates, docs, QA contracts, or tests; dated historical QA
  reports retain their old model names as factual evidence.
- A read-only Playwright run reached the installed login page without credentials. The installed
  `/api/endpoints` still reports `automatic_fallback_target: false` and Opus recommended effort
  `max`, confirming that the new checkout/build has not been activated in the protected installed
  runtime. No Agent or runtime state was written.

## Remaining acceptance

1. Activate compiled runtime config/build first and verify `/api/config` exposes GlassHive as an
   automatic fallback target.
2. Only then narrowly sync the Main Agent's three generic `fallback_llm_*` fields; verify the
   provider-internal fallback remains absent.
3. Run Agent Builder browser QA: GlassHive appears in Fallback AI Provider, Claude / Opus 5 saves,
   refresh persists, and the primary remains Codex.
4. Run a controlled exact pre-authoring quota failure through the real Telegram path and prove two
   distinct provider attempts, one Claude answer, no primary error bubble, active-attempt Stop, and
   no retry after authored activity.

Until those installed user paths pass, the feature remains **PARTIAL**, not done or release-ready.
<!-- qa-evidence-exempt: Historical or specialized supporting artifact retained without retroactively inventing missing evidence; current release acceptance requires a fresh full-view report. -->
