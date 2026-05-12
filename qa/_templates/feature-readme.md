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

## Current Status

- Last full QA:
- Current result:
- Known gaps:
- Next required hardening:
