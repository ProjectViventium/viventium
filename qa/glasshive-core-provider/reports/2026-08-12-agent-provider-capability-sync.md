# GlassHive Agent Provider Capability Sync — 2026-08-12

## Outcome

PARTIAL pending post-fix activation and surgical prompt reconciliation. Safe prompts-only sync
previously rejected three already-running Agents because canonical configuration authorized full
GlassHive access but tracked and generated provider-capability metadata omitted the matching
`default_access` and `allow_full_access` fields.

## Fix And Evidence

- The compiler now projects both values from canonical GlassHive provider settings into LibreChat
  provider capabilities.
- The tracked local LibreChat source declares the same public default policy, keeping direct sync
  validation aligned with compiled runtime validation.
- Focused compiler/source parity tests pass for the full-access policy.
- The same three-Agent prompts-only dry run that failed closed before the fix now succeeds without
  selecting protected model, provider, tool, voice, or GlassHive option fields.

Final acceptance requires a supported activation, a reviewed non-dry-run prompt update limited to
Main, Reality Check, and Red Team, and a fresh live/source compare.

No private prompts, account identifiers, paths, credentials, or runtime records are included here.
