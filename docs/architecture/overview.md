# Architecture overview

Viventium has one active product stack: `viventium_v0_4/`.

## Product flow

```text
User surface
  -> LibreChat Core and Main
  -> authorized memory, tools, scheduling, Voice, or Parallel Work
  -> durable state and delivery
  -> one truthful result on the originating surface
```

Main owns user-facing judgment and the final answer. Runtime code owns typed identity,
authorization, state, persistence, transport, and recovery. GlassHive owns durable worker missions;
it does not become another Main. The Voice gateway owns real-time media; it does not own durable
task truth.

## Owning seams

| Seam | Owner |
| --- | --- |
| Web application, Main, memory, prompt assembly | `viventium_v0_4/LibreChat/` |
| Install, config compile, health, lifecycle, restore | `scripts/viventium/` and `bin/viventium` |
| Durable worker missions and workspaces | `viventium_v0_4/GlassHive/` |
| Real-time speech and interruption | `viventium_v0_4/voice-gateway/` |
| Modern Call/Wing/Listen-Only client | `viventium_v0_4/agent-starter-react/` |
| Telegram transport | `viventium_v0_4/telegram-viventium/` |
| Prompt source, compile, sync, evaluation | Prompt registry plus Prompt Workbench |
| Acceptance contracts and evidence | `qa/` |

## Cross-system rules

- Trace `trigger -> config or prompt -> compiler or adapter -> runtime -> visible result -> durable
  state` before changing behavior.
- Capabilities and authorization come from typed metadata, not prompt text, labels, or provider
  names.
- A source fix is delivered only when component source, parent pin, generated or prebuilt output,
  installed runtime, visible behavior, and durable state agree where applicable.
- Optional services may degrade independently. They must not block the first useful Main answer.
- Every durable effect and result has an owner-scoped identity and safe retry boundary.
- Public artifacts contain no private prompts, user data, credentials, runtime dumps, or machine
  identity.

## Detail

- [Systems map](systems-map.md)
- [Interaction delivery](interaction-delivery.md)
- [Parallel Work runtime](parallel-work-runtime.md)
- [Prompt Workbench](prompt-workbench.md)
- [Existing cognition flow](../requirements_and_learnings/54_Emotional_Cortex_And_Feeling_State.md#request-lifecycle)
- [Component documentation](../../viventium_v0_4/docs/README.md)

The former mixed-stack overview remains readable at
[`docs/02_ARCHITECTURE_OVERVIEW.md`](../02_ARCHITECTURE_OVERVIEW.md) during the lossless migration;
its retained component detail remains available from this overview.
