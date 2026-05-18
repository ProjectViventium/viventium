# Viventium Workflow Adapter

This package owns Viventium-specific workflow setup for GlassHive-backed long-running work.
It builds sanitized bootstrap bundles, writes private local run artifacts, and exposes stable CLI
entrypoints for the status-bar helper and `bin/viventium`.

Supported product workflows:

- `heal`: diagnose Viventium from logs, state, docs, and code; apply mode is explicit.
- `feature-request`: collect success criteria before building a feature.
- `bug-report`: collect reproduction details before diagnosing and fixing a reported bug.

GlassHive stays generic. It receives project/worker/run payloads and host execution settings, but
does not read Viventium internals or own Viventium product policy.
