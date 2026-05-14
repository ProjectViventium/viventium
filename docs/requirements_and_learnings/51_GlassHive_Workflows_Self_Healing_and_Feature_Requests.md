# 51. GlassHive Workflows: Self Healing, Bug Reports, and Feature Requests

## Purpose

Viventium needs reusable local work workflows for self-healing, bug reports, and feature requests.
GlassHive is the preferred worker substrate because it already owns projects, workers, runs,
host-native Codex/Claude execution, workspaces, logs, lifecycle, and live visibility. Viventium owns
the product workflow adapter, safety gates, helper UX, docs, redaction, QA, and PR policy.

## Boundary

- GlassHive remains generic and standalone.
- Viventium passes work through a `bootstrap_bundle`; GlassHive must not read Viventium Mongo,
  LibreChat internals, App Support config formats, or workflow-specific product state directly.
- Workflow commands poll GlassHive run/project state from `bin/viventium`.
- CLI/helper workflows do not reuse chat-anchored GlassHive callback receivers.
- If GlassHive host workers are disabled or unhealthy, workflows fail loud by default. Any degraded
  non-GlassHive mode must be explicit and documented as degraded; it must not become a second hidden
  worker runtime.

## Shared Workflow Adapter

The Viventium workflow adapter lives under `scripts/viventium/workflows/`, with
`scripts/viventium/workflows.py` kept as a compatibility entrypoint. It is invoked through:

```bash
bin/viventium workflows status --json
bin/viventium workflows start heal
bin/viventium workflows start feature-request --request "..."
bin/viventium workflows start bug-report --what-happened "..." --steps-to-reproduce "..."
bin/viventium workflows approve
bin/viventium workflows cancel
bin/viventium workflows open-artifacts
```

Convenience aliases:

```bash
bin/viventium heal start
bin/viventium feature-request start --request "..."
bin/viventium feature-request approve
bin/viventium report-bug start --what-happened "..."
bin/viventium report-bug approve
```

Raw run artifacts live under App Support:

```text
~/Library/Application Support/Viventium/state/workflows/runs/<run-id>/
```

They are private local operator artifacts until a redaction/promotion step creates public-safe QA or
PR material.

## Self Healing Workflow

Default mode is diagnose-only.

Flow:

1. write `01-rca-prompt.md`
2. produce RCA Markdown
3. orchestrator reviews/stress-tests RCA
4. produce proposed-fix Markdown
5. orchestrator reviews proposed fix
6. explicit apply mode creates and writes only to an isolated `heal/<slug>-<run-id>` worktree
7. tests and QA must prove the product is healthy

Helper surface:

- Advanced > Heal Viventium
- provider selector, with Auto/Codex/Claude options and Codex preferred in Auto
- xHigh reasoning default, normalized to `xhigh` in workflow state
- status label: `Healing (N mins passed)`
- Cancel Active Workflow
- local artifacts opener

## Feature Request Workflow

Feature requests must complete intake before implementation.

Required intake:

- success criteria
- non-obvious cases
- missing requirements
- non-goals
- impacted surfaces
- QA acceptance

The approved feature description is materialized as `feature-request.md`. Implementation starts only
after user approval through `bin/viventium feature-request approve` or the helper's
**Approve Build or Fix...** action. Approval creates an isolated `feature/<slug>-<run-id>` worktree
and points the worker at the approved spec.

Canceling a workflow must clean up Viventium-created isolated worktrees and throwaway branches when
they are still clean and have no commits beyond the recorded base commit. Dirty or advanced worktrees
are left in place for manual review instead of being destructively removed.

PR policy:

- `feature_requests.pr.create_after_user_approval` defaults to true and currently governs local
  feature and bug-fix PR preparation prompts.
- The compiler exports the workflow-neutral
  `VIVENTIUM_WORK_REQUEST_CREATE_PR_AFTER_USER_APPROVAL` runtime flag for shared workflow code, plus
  the legacy feature-request-specific flag for compatibility.
- PR creation still requires approved spec, isolated worktree, passing QA summary, public-safe scan,
  and no unrelated dirty work.
- If the setting is false, Viventium asks whether to create the PR.
- Local implementation and PR preparation are separate from pushing or opening a cloud PR. Publishing
  remains an explicit later action.

## Bug Report Workflow

Bug reports use the same shared workflow adapter and approval/isolated-worktree mechanics as feature
requests, but the intake is bug-specific and starts from the user's report instead of letting Heal
infer the problem from logs alone.

Required intake:

- what happened
- steps to reproduce
- expected behavior
- actual behavior
- other useful details
- missing reproduction details
- non-obvious cases
- impacted surfaces
- evidence/logs/state to inspect
- QA acceptance and regression coverage

The approved report is materialized as `bug-report.md`. Implementation starts only after user
approval through `bin/viventium report-bug approve`, `bin/viventium workflows approve`, or the
helper's **Approve Build or Fix...** action. Approval creates an isolated
`bugfix/<slug>-<run-id>` worktree and points the worker at the approved report.

Bug report implementation must combine the feature-request approval gate with the self-heal RCA
discipline:

1. reproduce or validate the bug from the approved report
2. inspect relevant logs, code, state, nested repos, and docs
3. write RCA and proposed-fix artifacts
4. run orchestrator review gates where available
5. implement only after the gates pass
6. run the documented QA acceptance and regression coverage

If the report does not contain enough detail to reproduce or validate the bug, the worker asks for
the missing detail instead of guessing or coding from ambiguous input.

## No Hardcoded Runtime NLU

Workflow starts are operator-explicit through CLI/helper commands or future structured tools. Runtime
code must not dispatch heal, bug-report, or feature-request flows by matching prompt text such as
"fix this" or "add a feature." Future chat activation must use source-of-truth activation prompts and
structured tool arguments.

## QA Requirements

Acceptance requires proving:

- GlassHive enabled path dispatches a host worker with sanitized bootstrap input
- GlassHive disabled path fails loud or enters explicitly degraded mode
- raw artifacts stay out of git and QA
- helper shows workflow in-progress status
- self-heal default does not mutate code
- apply mode uses isolated worktree
- bug-report intake captures user reproduction details before any fix work
- bug-report approval uses an isolated `bugfix/<slug>` worktree
- feature-request intake blocks implementation until success criteria are approved
- PR creation cannot publish private artifacts or unrelated local edits
