# Nightly Default Personalization Continuity — 2026-07-24

<!-- qa-evidence-exempt: This source-level synthetic continuity regression has no user-visible surface; installed upgrade acceptance remains explicitly pending below. -->

## Outcome

The versioned nightly-default migration is now additive at each config leaf. Existing explicit
enabled/disabled and valid empty values remain authoritative when the version marker is first added,
including settings for nightly routines, Prompt Workbench and its seed, memory hardening, GlassHive,
and the host worker. Unknown config extensions also remain present.

The automatic local worker profile is added only when its field is absent. A present empty profile is
preserved as an owner choice. After the marker is current, a no-change run does not rewrite the file.

## Escaped Failure And Repair

The regression fixture initially failed in three places: the pure reconciler, its executable
file-writing path, and the shell wrapper used by normal start. Each showed existing `false` values
being replaced by shipped `true` defaults.

The repair replaced unconditional first-version assignments with missing-leaf additions and changed
worker-profile discovery to test field presence rather than truthiness.

## Automated Evidence

- Pure unit coverage includes explicit `false`, empty strings, nested owner extensions, and unknown
  top-level/runtime/integration values.
- The executable reconciler fixture proves first migration preserves those values, adds only missing
  defaults, retains the owner file mode, and performs a byte- and modification-time-exact second-run
  no-op.
- The extracted public CLI wrapper used by `start` executes against a synthetic canonical config and
  preserves the same personalization.
- Existing later-disable and authenticated-worker discovery coverage remains part of the focused
  suite.

The final focused default-nightly and public CLI upgrade/start contract suite passed all 91 tests.

No live App Support state, provider account, database, conversation, prompt, schedule, or runtime was
read or modified.

## Remaining Acceptance

Automated source and CLI-wrapper evidence is complete for this regression. A disposable installed
existing-user start and supported upgrade should still verify visible runtime health and generated
config alignment before the universal upgrade path is called fully finished.
