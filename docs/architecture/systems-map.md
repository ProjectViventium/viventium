# Systems map

## Entrypoints

| Purpose | Entrypoint |
| --- | --- |
| Install | `./install.sh` |
| Public CLI | `bin/viventium` |
| Full v0.4 launcher | `viventium_v0_4/viventium-librechat-start.sh` |
| Local installed-runtime status | `bin/viventium dev-runtime status` |
| Side-by-side development | `bin/viventium dev-env create dev` |

## Active components

| Component | Responsibility |
| --- | --- |
| LibreChat | Main, web UI, agents, memory, prompt composition, source ordering, delivery state |
| GlassHive | Durable missions, admission, isolated workspaces, provider execution, callbacks, artifacts |
| Voice gateway | LiveKit media, speech-to-text, text-to-speech, endpointing, interruption |
| Modern playground | Call, Wing, Listen-Only, captions, browser audio and task controls |
| Telegram bridge | Telegram input, previews, files, voice notes, and final delivery |
| Prompt Workbench | Prompt lineage, compile/live drift, evaluation, and controlled rollout |
| RAG services | Owner-scoped conversation and transcript retrieval with health/freshness gates |

## Authority boundaries

- Core owns Main, source order, trusted origin, user authorization, and presentation state.
- GlassHive owns mission identity, execution lifecycle, recovery, controls, and artifacts.
- Provider-native child agents remain internal to one mission root.
- Voice owns media presentation; Core owns durable tasks and effects.
- Saved memory, conversation recall, transcript evidence, and Feelings are separate state surfaces.
- Generated files under Application Support are runtime outputs, not authoring sources.

Managed components may be separate Git repositories. A nested source change is not shipped until
its component commit, parent pin in `components.lock.json`, generated or prebuilt artifact, and
installed runtime agree.

The former mixed-stack map remains readable at [`docs/03_SYSTEMS_MAP.md`](../03_SYSTEMS_MAP.md)
during migration with its retained component detail.
