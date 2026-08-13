# GlassHive Agent Provider Capability Sync — 2026-08-12

## Outcome

PARTIAL pending activation of the compiled policy. Safe prompts-only sync previously rejected three
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
- An earlier supported transactional activation established the safe isolated candidate and
  rollback path; the candidate still needs one restart after compiling the new policy.
- The reviewed non-dry-run update selected only Main, Reality Check, and Red Team in prompts-only
  mode. A fresh compare found no remaining instruction drift and no adjacent LibreChat-config
  drift.
- Remaining live/source differences are intentionally preserved user/runtime choices: GlassHive
  workspace/fallback options, two model flags, two voice flags, and background fallback ordering.

Final acceptance requires the post-compiler transactional activation. This pass does not authorize
a broad Agent sync or replace final clean-main activation after the nested and parent pull requests
merge.

No private prompts, account identifiers, paths, credentials, or runtime records are included here.
