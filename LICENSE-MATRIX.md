# License Matrix

Viventium is released as a set of separate repository surfaces. Do not present
the project as if one top-level license governs every component.

| Surface | License | Why |
|---|---|---|
| `viventium` main repo | FSL 1.1 with Apache-2.0 future license | This repo contains Viventium-owned orchestration, product docs, installer, config compiler, and public release tooling. |
| `GlassHive` | FSL 1.1 with Apache-2.0 future license | This first-party component repo contains Viventium-owned sandbox/runtime code and has no external upstream fork boundary. |
| `viventium-librechat` | MIT | LibreChat is MIT-licensed. The public component repo must preserve MIT compatibility and notices. |
| `viventium-openclaw` | MIT | OpenClaw is MIT-licensed. |
| `skyvern-source` | AGPL-3.0 | Skyvern is AGPL and must remain isolated in its own repo. |
| `google_workspace_mcp` | MIT | Preserve upstream license. |
| `ms-365-mcp-server` | MIT | Preserve upstream license. |
| `mcp-youtube-transcript` | MIT | Preserve upstream license and notice in the component repo. |
| `agents-playground` | Apache-2.0 | Preserve upstream license and NOTICE. |
| `livekit` | Apache-2.0 | Preserve upstream license and NOTICE. |
| `cartesia-voice-agent` | Apache-2.0 | Preserve upstream license. |
| `agent-starter-react` | MIT | Preserve upstream license. |
| private preservation repo | Private | Stores personal state, backups, prompts, secrets, and private documentation. |
| `<enterprise-deployment-repo>` | Private | Deployment automation and service-only infrastructure repo. |

## Rules

1. The root `LICENSE` in `viventium` applies only to Viventium-owned files in
   that repo.
2. Every public component repo keeps its own upstream-compatible license file.
3. Placeholder public component repos must clearly say they are placeholders and
   must carry the required upstream legal files before upstream-derived source lands there.
4. `components.lock.json` is the public contract for which component repo and
   commit the product expects.
5. `skyvern-source` must stay separately published and separately licensed.
6. FSL repos are source-available today; public docs must not describe them as
   OSI open source before the future Apache-2.0 conversion date applies.
7. Private repos are not part of the public licensing surface.
