# Agent Streaming Usage Metadata

## Overview
The Agents runtime can request per-chunk usage metadata from providers. Some providers (notably
Perplexity) stream usage fields in multiple chunks, which triggers LangChain merge warnings.

## Core Requirements
- Avoid per-chunk usage streaming for providers that emit duplicate usage fields.
- Preserve usage totals via the final response payload.
- Keep provider-specific logic centralized in the Agents runtime configuration.

## Specifications
- Location: `viventium_v0_4/LibreChat/packages/api/src/agents/run.ts`
- Behavior:
  - `streamUsage` defaults to `true` for standard providers.
  - For providers in `customProviders`, force `streamUsage = false` and `usage = true`.
  - Perplexity must be included in `customProviders` to prevent `completion_tokens` merge warnings.
  - Voice-mode requests (`viventiumSurface=voice` or `viventiumInputMode` starts with `voice`) disable `streamUsage` to avoid repeated merge warnings in voice streams.
  - `VIVENTIUM_DISABLE_STREAM_USAGE=1` disables `streamUsage` globally and forces `usage = true`.
  - The `viventium-librechat-start.sh` launcher exports `VIVENTIUM_DISABLE_STREAM_USAGE=1` by default (override to re-enable).

## Integration Points
- `viventium_v0_4/LibreChat/packages/api/src/agents/run.ts`
- `viventium_v0_4/LibreChat/librechat.yaml` (custom endpoint definitions)

## Edge Cases
- Custom endpoints that reuse OpenAI-like models may also stream usage; add them to
  `customProviders` as needed.
- Streaming usage should remain enabled for providers that do not emit conflicting usage metadata.

## Learnings
- LangChain’s `_mergeDicts` warns on duplicate `completion_tokens` fields when types differ.
- Disabling per-chunk usage for Perplexity removes log noise without losing final usage totals.
