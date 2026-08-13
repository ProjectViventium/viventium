# GlassHive Agent Provider Capability Sync — 2026-08-12

## Outcome

PASS for the local full-access policy. Safe prompts-only sync previously rejected three
already-running Agents because canonical configuration authorized full GlassHive access but
tracked and generated provider-capability metadata omitted the matching `default_access` and
`allow_full_access` fields.

## Fix And Evidence

- The compiler now projects both values from canonical GlassHive provider settings into LibreChat
  provider capabilities.
- The tracked local LibreChat source declares the same public default policy, keeping direct sync
  validation aligned with compiled runtime validation.
- The focused compiler contract and hosted LibreChat suite cover the compiled and tracked policy.
- The same three-Agent prompts-only dry run that failed closed before the fix now succeeds without
  selecting protected model, provider, tool, voice, or GlassHive option fields.
- Supported transactional activation completed with the exact merged LibreChat pin. Both canonical
  and isolated generated runtime configs contain `default_access: full` and
  `allow_full_access: true`, and a post-activation Telegram Main turn initialized and completed.
- The reviewed non-dry-run update selected only Main, Reality Check, and Red Team in prompts-only
  mode. A fresh compare found no remaining instruction drift and no adjacent LibreChat-config
  drift.
- Remaining live/source differences are intentionally preserved user/runtime choices: GlassHive
  workspace/fallback options, two model flags, two voice flags, and background fallback ordering.

This pass does not authorize a broad Agent sync or replace final clean-main activation after the
parent pull request merges.

No private prompts, account identifiers, paths, credentials, or runtime records are included here.
