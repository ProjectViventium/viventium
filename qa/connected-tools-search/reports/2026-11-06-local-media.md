# Local media tools — 2026-11-06

## Summary

QA: blast-radius. Retained development evidence from an isolated macOS arm64 candidate.
This report does not certify the new publication tree or an installed release.
Case: [local-media-worker-delivery](../cases.yaml). Source: the
[local media package](../../../viventium_v0_4/MCPs/local-media/README.md).

## Scope Run

| Scenario | Observed result |
| --- | --- |
| Quick local still draft | Codex selected Z-Image Turbo. The 384 × 384 PNG was returned by xPerfect and loaded in the browser. |
| Polished local product still | Codex selected Qwen-Image 2.1. The 384 × 384 PNG was returned and loaded. |
| Recolor a reference while keeping composition | Codex used Qwen-Image 2.1 with the workspace reference. The returned PNG kept the teapot, framing, and window light. |
| Local text-to-video with audio | Claude selected MiniMax H3. Both the one-second delivered clip and the 5.875-second clip had audio tracks and played to the end in the browser. The longer clip put the steam behind the lid rather than clearly at the spout. |
| Animate a supplied image | Claude passed the reference to MiniMax H3. The 2.33-second MP4 kept the teapot and opening composition and included an audio track. |
| Stop and recover | The native Stop control ended a second take, removed its staging files and released the renderer. A follow-up turn returned the first clip with identical bytes. |
| Native discovery and permissions | The real Direct MCP client found both tools, and a call with an outside reference was denied. Grok's ACP projection used the same server declaration. |
| Installed package and failure paths | The wheel built and installed in a separate environment. Four tests passed for discovery, result delivery, disabled and missing models, workspace scope, busy render and cancellation. |

Run receipts connect the native calls, selected models, artifact hashes, API downloads and browser
playback. Synthetic media and full traces are kept in private QA evidence. Local model files were
provisioned for the test. The normal configuration is opt-in.

Live Codex and Claude worker runs passed. Direct provider turns lacked credentials in the isolated
instance. Grok's native provider sign-in was expired. Their configuration checks do not establish
live provider-turn parity. The local module targets authorized Mac host workers; managed Library and
restricted Docker workers do not receive this connection. No installed product rollout was tested.

## Automated Evidence

### Publication consumer recheck — 2026-11-08

The exact candidate wheel built and installed in a separate private QA environment. Five installed-
package tests passed, including actual MCP stdio discovery, synthetic result bytes, workspace and
worker-temporary-output boundaries, busy-render refusal and process cancellation. The native
renderer was a synthetic test executable; this is not a new model-quality, hardware or provider
parity run. Earlier real-model observations above retain their date and scope. Raw source traces,
credentials, model files and generated media remain private.

## Traceability

The [local-media cases](../cases.yaml) and [local media package](../../../viventium_v0_4/MCPs/local-media/README.md) own worker delivery, local scope, cancellation and opt-in configuration.

## Full-View Evidence Checklist

The retained evidence above identifies the selected source, tests, artifact and state checks, visible user path and remaining gaps. This format update does not renew that historical acceptance for the publication candidate.

## User-Grade Evidence

- Surface exercised: Browser playback and downloads, native Worker/MCP calls and an isolated installed wheel.
- Real user path: Codex and Claude generated and returned the synthetic media described above; other provider-turn parity was not established.
- Visible outcome: Returned images loaded and the delivered clips played to the end; the longer clip retained its stated visual defect.
- Expanded/detail state: Stop, renderer release, denied outside references and installed-package failure paths were checked within the recorded scope.
- Persistence/reload result: A follow-up returned the first clip with identical bytes; installed product restart and rollout were not tested.
- Backend/log/DB confirmation: Private receipts connect native calls, artifact bytes, downloads and playback; the publication recheck used a synthetic renderer.
- Final model/runtime wording check: Earlier real-model evidence and the later synthetic installed-package recheck remain separate.
- Substitution check: Automated checks, source review and model review support only their stated scopes; they do not replace the required visible, persistence or physical-audio evidence.

## Findings

Opt-in local media passed the recorded Worker paths. Direct and Grok live-turn parity and an installed rollout remain unproved.

## Public-Safety Review

Raw prompts, personal media, accounts, credentials, operational identifiers, source hashes, screenshots and logs remain private. Only sanitized behavior, bounded evidence and remaining gaps are published.
