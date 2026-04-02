# QA

This folder is the public-safe home for end-to-end QA plans, execution notes, and reports.

## Rules

- Keep one living QA source of truth per feature or flow.
- For non-trivial feature, bug, runtime, installer, or release work:
  1. write or update the QA plan first
  2. define the end-to-end test cases
  3. run an independent QA pass
  4. save the findings and evidence here
- Prefer feature folders such as `qa/<feature>/`.
- Keep QA artifacts public-safe:
  - no secrets
  - no private prompts
  - no customer data
  - no personal chats or attachments
  - no machine-local runtime exports
- Use synthetic non-personal test data.
- When browser behavior matters, use real-browser QA such as Playwright CLI or equivalent.

## Suggested Shape

- `qa/<feature>/README.md`
  - scope
  - requirements under test
  - environments
  - test cases
  - expected results
- `qa/<feature>/report.md`
  - date
  - build or commit under test
  - steps executed
  - findings
  - regressions
  - follow-ups
