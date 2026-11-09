# Telegram local call and network recovery — 2026-10-28

## Summary

QA: **blast-radius**. Overall result: **PARTIAL**. The repair candidate is loaded and the local
media path passes. Public phone calling still needs registrar verification and device acceptance.
This follows [the earlier phone/local-entry report](2026-10-27-phone-and-local-call-entry.md).

## Scope Run

| Requested result | Delivered change | Current evidence | Remaining gate |
| --- | --- | --- | --- |
| Local call from Telegram | `/call` includes **Call on the Viventium computer**; `/call local` works without a public origin. One existing session and one-use launch serve both choices. | Real Telegram rendered both choices and the explicit local-only choice. Real Chrome connected, displayed a reply and ended normally. | Computer Use could not activate Telegram's custom message button. The browser test used the same normal linked-account call-link API; it does not prove the literal button tap. |
| Voice input and output | Reuse the existing selected speech route, call authority, conversation and gateway. No new media or authentication framework. | Readiness-gated LiveKit SDK test: injected speech → final transcript → correct final answer → received active PCM → accepted End. DB confirms the original conversation, consumed launch and ended sessions. | Hardware microphone, audible quality, browser reload of linked history and phone audio remain separate acceptance checks. |
| Bot remains responsive | Fetch the call link outside the async handler's event loop; retain public-only fallback when Telegram rejects an optional button. | Before/after bot tests, including thread execution and rejected-button handling. Exception logs do not expose launch URLs. | No endurance claim. |
| Recover existing public mappings | Keep the normal successful renewal interval; retry a failed renewal after 60 seconds. Preserve the existing ownership and public-address guards. | Existing owned mappings were restored through the supported refresh command. Two causal worker tests and the 59-check focused ownership/renewal selection pass. | Long-outage and full renewal-cycle endurance are not proved by a manual refresh. |
| Reach the public call from a phone | Preserve the public HTTPS route and correct only reviewed stale DNS records. | The DNS review identified stale records. Proposed corrections preserve their names, types and TTL. | **BLOCKED:** provider setup prerequisites were not completed in this dated run. No DNS change or cellular/same-Wi-Fi acceptance is claimed. |
| Run the candidate without configuration drift | Use normal supported startup and the prepared immutable bot component. | Loaded bot bytes match source; canonical configuration and component lock hashes are unchanged; Core and Playground return 200. After a host restart, the installed helper restored the same runtime. | Development candidate, not a publication or full Voice acceptance claim. |

## Traceability

Requirement trace: [Voice](../../../docs/requirements_and_learnings/capabilities/voice.md),
[Telegram bridge](../../../docs/requirements_and_learnings/03_Telegram_Bridge.md) and
[remote access](../../../docs/requirements_and_learnings/47_Remote_Access_and_Tunneling.md)
→ `local-call-entry` and `telegram-call-public-edge` in [the case bank](../cases.yaml)
→ reachable authorized call, unchanged context, honest rejection and recovery → evidence above.

## Automated Evidence

Focused Core link tests: **13 passed**. Existing launch-authority consumers: **2 passed**.
Telegram configuration selection: **63 passed**; final affected controls: **8 passed**.
These selections overlap other retained receipts and are not summed into a unique total.
Source syntax and launcher parsing pass. Invalid targets, non-loopback and credentialed local URLs,
agent denial, missing public configuration and rejected optional buttons have causal coverage.
Unit launch-replay checks pass; a real used-link replay is **NOT RUN** on this candidate.

## Findings

An earlier SDK attempt sent audio before the agent was listening and ended before a delayed native
speech-model load recovered. A process sample showed a wait inside macOS display services; its
underlying cause is unproved. This attempt is retained as **FAIL-INCONCLUSIVE**. The corrected QA
harness waits for the existing agent state before injection; its fresh post-restart run passes.
No speech-model downgrade or speculative gateway patch was made.

Opus 5.5 reviewed the source, requirements, causal tests, runtime and process evidence. It found no
critical security or flow issue in the repair batch and challenged the premature SDK readiness
assumption. Private receipts retain exact hashes, IDs, source preimages and screenshots. No raw
prompts, accounts, credentials, machine paths or private logs are included here.

Provider benchmarks, cognitive parity, sub-two-second latency, glitch-free audio, full-project suites
and public release are **NOT RUN / NOT CLAIMED** by this repair batch.

## Full-View Evidence Checklist

The retained evidence above identifies the selected source, tests, artifact and state checks, visible user path and remaining gaps. This format update does not renew that historical acceptance for the publication candidate.

## User-Grade Evidence

- Surface exercised: Telegram controls, real Chrome call entry and readiness-gated RTC speech injection.
- Real user path: Telegram rendered the local choices and Chrome connected through the normal linked call API; the custom Telegram button itself was not activated.
- Visible outcome: Chrome displayed a reply and ended normally; the local SDK path returned the expected answer and active PCM.
- Expanded/detail state: Consumed launch, ended sessions, button rejection and mapping ownership were checked; physical audio and literal button-tap acceptance remain separate.
- Persistence/reload result: The installed helper restored the same runtime after a host restart; linked-history browser reload and real used-link replay were not run.
- Backend/log/DB confirmation: Call/session state, loaded bot source, preserved configuration and scoped renewal checks support the selected local path.
- Final model/runtime wording check: Injected speech and received PCM do not establish hardware quality or public phone reachability.
- Substitution check: Automated checks, source review and model review support only their stated scopes; they do not replace the required visible, persistence or physical-audio evidence.

## Public-Safety Review

Raw prompts, personal media, accounts, credentials, operational identifiers, source hashes, screenshots and logs remain private. Only sanitized behavior, bounded evidence and remaining gaps are published.
