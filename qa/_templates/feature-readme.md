# <Feature> QA

## Scope

- Owning requirements doc:
- Runtime/code owners:
- User-visible surfaces:
- Out of scope:

## Quality Bar

- Primary user outcome:
- Speed/latency expectation:
- Persistence/reload expectation:
- Failure behavior:
- Public/private boundary:

## Environments

- Local:
- CI:
- Connected-account or external-service assumptions:
- Synthetic fixtures:

## Required Suites

| Suite | Command or Manual Path | Required When | Last Run |
| --- | --- | --- | --- |
| Unit/API | `<command>` | Every code change touching this feature | `<date/result/report>` |
| User-grade surface QA | `<browser/telegram/voice/scheduler path>` | Every user-visible behavior change | `<date/result/report>` |
| Full feature regression | `<command/manual suite>` | Before release-readiness or production signoff | `<date/result/report>` |

## Coverage Matrix

Use this section or a separate `coverage.md` when the feature has many agents, tools, surfaces, or
requirements to trace.

| Requirement / Surface | Cases | Last Full Run |
| --- | --- | --- |
| `<requirement>` | `<FEATURE>-001` | `<date/result/report>` |

## Natural User Use Case Coverage

Link to `cases.md#natural-user-use-case-checklist`. Keep this feature-specific: list the user actions
people naturally try, then prove each one with the real surface and supporting logs/DB/code/docs
evidence.

| Use Case Class | Feature-specific examples | Required evidence |
| --- | --- | --- |
| Happy path | `<primary user action>` | Real surface plus supporting code/log/DB/docs state |
| Degraded or missing setup | `<missing auth/config/service/local prerequisite/provider>` | Honest user copy plus health/log/config evidence, prerequisite state such as Docker/provider health when relevant, and fallback result or blocked reason |
| Persistence or parity | `<reload/restart/cross-surface behavior>` | Stored state, linked surface, and generated/shipped artifact check when applicable |

## Current Status

- Last full QA:
- Current result:
- Known gaps:
- Next required hardening:
