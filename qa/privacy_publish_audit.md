# Privacy / Publish Audit

## Purpose

Public-safe packaging audit for the review branches prepared on April 12, 2026.

## Scope Reviewed

- parent repo review work outside `main`
- nested `viventium_v0_4/LibreChat` review work outside `main`
- nested `viventium_v0_4/MCPs/google_workspace_mcp` review work outside `main`

## Checks Run

- diff-to-`main` scans for absolute local paths, personal emails, token-like strings, and owner-name leakage
- tracked-tree scans for obvious local-path and secret markers
- nested-repo inventory to ensure parent and component histories are reviewed separately
- git identity check for public-safe author name and email on the parent and `LibreChat` repos
- local-runtime artifact check for nested `LibreChat` state

## Findings

- No diff-to-`main` findings for obvious personal paths, personal emails, or token-like secrets in the parent repo, `LibreChat`, or `google_workspace_mcp`
- One personal test fixture was present in the Telegram test suite and was replaced with a synthetic username
- One secret-looking local default token was present in the Cursor bridge helper and was replaced with a clearly synthetic local token
- One local runtime artifact directory, `.rag-pgdata/`, was present in the nested `LibreChat` working tree and is now ignored
- One owner-specific LAN IP string was present in public release tests and is now replaced with the public-safe placeholder `192.0.2.44`
- One stale doc reference to a missing `scripts/release/build_release_manifests.py` command was removed so public release instructions match the current tree

## Sanitization Fixes Applied

- `scripts/cursor_bridge/claude_openai_compat_bridge.py`
  - default auth token changed from a secret-shaped placeholder to `local-bridge-token`
- `viventium_v0_4/telegram-viventium/tests/test_bot_stream_preview.py`
  - synthetic test username changed to `sampleuser`
- `viventium_v0_4/LibreChat/.gitignore`
  - added `.rag-pgdata/`

## Remaining Human Review Focus

- review the parent repo memory/recall/install work against the public install story
- review the nested `LibreChat` recall and activation changes against the current agent/source-of-truth config
- review the separate MLX archive branch as archival/benchmark work, not as part of the default install path
- review the Telegram local Bot API branch as a distinct feature slice before merge

## Notes

- This audit is publish-safety evidence for PR review, not a claim that every unrelated release test in the full repository already passes.
- Review branches and PRs should still be assessed against the relevant scoped test results for each feature slice.
