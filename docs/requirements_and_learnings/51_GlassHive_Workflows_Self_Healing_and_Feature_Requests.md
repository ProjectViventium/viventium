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
- A configured conversation-provider fallback is still the same logical Viventium agent. Lazy or
  initialization-time materialization must attach a fresh endpoint-owned, signed capability bundle
  through the same helper as the primary route. Do not copy arbitrary primary headers or drop
  `agents_md`, `claude_md`, `codex_md`, broker capabilities, visible history, or the one final
  Feeling tail.
- Conversation mode must not rewrite instruction files inside the user's selected workspace. Any
  signed capability-routing guidance that the worker needs must also reach the provider's real
  developer-authority message. A service-backed host resource may have a filename-like label without
  being mounted locally; when its authorized host tool covers the evidence, the worker calls that
  tool before filesystem discovery. This is a structured capability rule, never a prompt/entity
  classifier.

An August 4, 2026 fallback incident established this boundary. Request/run/worker joins proved the
declared Claude fallback really executed; a mutable provider-session row had made a historical join
look misleading. The actual defect was narrower: primary Codex workers carried the signed capability
bundle, while every lazily materialized fallback worker lacked it because attachment ran only for
the primary config. The shared endpoint-first attachment path now runs for both. Regression coverage
forces the fallback, validates its signed keys and declared endpoint, preserves one Feeling tail and
history continuity, and restores the configured primary on the next eligible turn. The primary
throw is also logged exactly once with only its safe class, status, code, chain depth, and message
hash; raw messages, stacks, credentials, and secret material are forbidden.

An August 6, 2026 Telegram incident established the cross-process ownership boundary. A secondary
service instance sharing the live store and runtime root reconciled a host run that belonged to the
primary service. Its process-local map could not see the still-running CLI, so it falsely published
`run.orphaned` and interrupted the provider request; the owning processor later returned success and
unconditionally overwrote that interruption. The provider translated the transient interruption as
user cancellation, so the configured Agent fallback was never eligible and Telegram showed a
generic connection error. Host runtimes now resolve a live PID from the durable active-session
record only when it matches the run, its owner-service PID is live, and its matching `running`
heartbeat is fresh. A short fresh-heartbeat finalization lease covers the child-exit/writeback window;
a stale or ownerless lease cannot pin the run, and reconciliation terminates an ownerless surviving
child. Genuine ownership loss becomes structured retryable provider loss, processor success and
failure writes use a compare-and-set from `running`, and LibreChat preserves exact structured provider
codes such as `provider_temporarily_unavailable` instead of collapsing them into a generic completion
error. Explicit user Stop is still cancelled and cannot fall back. Regression and installed-runtime
QA cover foreign-process reconcile, dead owner/live child, stale/reused PIDs, late completion/error,
Stop/no-fallback, and native Telegram recovery through Claude Opus 5 at high effort.

An August 8, 2026 continuity rerun established the conversation-mode instruction-delivery boundary.
LibreChat correctly projected a signed `file_search` broker grant, but its routing brief lived only
in bootstrap instruction-file fields. GlassHive intentionally did not write those files into the
user's normal conversation workspace, so a host worker saw recall filenames and tried local shell
discovery before the broker. The capability bundle now carries a distinct conversation-provider
instruction field; LibreChat places it in developer authority before the final dynamic state tail.
Native Telegram and the isolated provider eval both prove one broker search and zero native command
substitutions after the repair.

An August 10, 2026 long foreground-consult run established the graph-lifetime boundary. The graph
was initialized once, but a final Main re-entry occurred after GlassHive's 300-second bootstrap
signature window and was rejected before a provider request could exist. Workspace-bound graph
routes now re-mint the complete request-scoped broker grant and signed bootstrap bundle immediately
before every actual model invocation, including primary, consultant, Main re-entry, and graph-model
fallback attempts. Re-minting reuses the participant's initialized tool/MCP definitions without
reloading them, while re-resolving current authorized host resources before mint. It does not
serialize the signing closure, extend either TTL, or renew an expired bearer token. If current
authority cannot be projected, stale signed headers and stale capability claims are removed before
invocation. Stop is rechecked after asynchronous preparation and before the provider is called.

## Host Authentication And Cognitive Parity

GlassHive `/host` and LibreChat connected accounts are intentionally different authentication
planes:

- `/host` authenticates a local Codex/Claude worker for the current machine/operator session.
- the signed broker grant authorizes only the declared user, endpoint, capabilities, and lifetime
  for one conversation-provider execution;
- LibreChat OpenAI/Anthropic OAuth authenticates the signed-in user's model account;
- saved memory, recall corpus, and Google/Microsoft tools keep their own identity and ACL boundaries.

The host must never copy, infer, or substitute credentials between these planes. The parity contract
is instead structural: primary and fallback workers receive the same factual goal, visible history,
authorized memory/recall context, declared broker tools, dynamic state, and completion boundary. A
grant-mint failure, expired grant, unavailable recall provider, missing per-user OAuth, or terminal
provider rejection is an explicit capability failure—not an empty result and not permission for
native filesystem discovery.

Broker grants are short-lived bearer credentials and are never accepted after their signed `exp`.
The normal initial grant is ten minutes. Scheduled work receives a delay-aware initial lifetime
(one hour by default, capped at 24 hours) so a known near-future dispatch can remain usable without
pretending an expired bearer token has been renewed. User, endpoint, capability, resource, and tool
scope come only from the signed payload. A live Viventium graph may issue a new short-lived grant
from its still-authorized request context immediately before another provider invocation; this is a
new host-side issuance, not bearer renewal. Work outside that owning request context still needs a
future authenticated re-mint protocol; until then it must fail closed and report that limitation.

Conversation-provider grants additionally require signed `conversation_id` and `message_id`
scope, and every production mint path disables dynamic policy-server expansion. The worker receives
only the exact declared broker servers/capabilities for that turn. Grant lifetimes are absolutely
clamped to 24 hours even if a caller requests more. Bearer possession remains the realistic
authorization ceiling until an authenticated renewal/exchange protocol exists; this is not a proof
of end-user presence.

Capability preparation is degradable per capability, not per whole turn. If conversation recall
file priming fails, the bundle marks `file_search` unavailable with its structured reason and keeps
the remaining authorized provider/tools usable. The worker must not replace that missing brokered
capability with host filesystem search, and the host must not report an empty search as if the
provider had returned no matches.

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
