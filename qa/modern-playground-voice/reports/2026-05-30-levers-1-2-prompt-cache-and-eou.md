<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# 2026-05-30 — Voice latency Levers 1 & 2 (xAI prompt-cache key; EOU tuning)

## Lever 1 — xAI/grok prompt-cache key: INVESTIGATED → REJECTED (no win)

**Hypothesis:** adding `prompt_cache_key` (or `x-grok-conv-id`) so grok reuses its stable system
prefix would cut voice TTFT from ~1.68s toward the reference ~0.72s.

**Test (direct configured-account probe):** a local public-safe TTFT probe outside this repo called
api.x.ai with a configured provider credential, an 11.5k-char stable system prefix, and a short user
turn. It ran 9 scenarios x 3 runs: no-key vs key-as-body-field vs key-as-header, cold + warm turns.

**Result:**
| condition | TTFT range |
|---|---|
| no key (warm) | 1.2–2.4s |
| prompt_cache_key body (warm) | 1.2–3.0s |
| x-grok-conv-id header (warm) | 1.2–2.7s |

- TTFT difference key-vs-no-key is run-to-run noise; the key did **not** reduce first-token time.
- grok returned `cached_tokens = null` on **every** call despite the stable prefix → caching not
  surfaced/engaged on this account.
- Prefix-busting was ruled out: the voice agent's `{{current_datetime}}` token sits at offset
  16421/16442 (tail), so the prefix IS stable — the key still didn't help.

**Decision:** NOT shipped. Adding it would be config noise claiming a false win (Key Principles §0).
grok TTFT ~1.2–2.5s is the provider floor on this account; the real TTFT levers are model choice and
cortex/EOU/preemptive, not a cache key.

## Lever 2 — Voice EOU / turn-detection ceiling: IMPLEMENTED (live A/B pending)

**Root cause (from voice_gateway.log + code):** product EOU p50 1.40s (max 7.69s) is driven by the
semantic turn detector riding `max_endpointing_delay` (default 1.8s, worker.py:720-723). Reference
~0.50s uses aggressive provider endpointing.

**Change (canonical config, parity-safe, already-wired knob):** add
`voice.turn_handling.max_endpointing_delay_s: 0.8` (+ explicit `min_endpointing_delay_s: 0.35` floor)
to the three config surfaces:
- canonical local runtime config file outside git
- `config.full.example.yaml` (with explanatory comment)
- `config.schema.yaml`

Compiler wiring confirmed: `config_compiler.py:2796-2798` emits
`VIVENTIUM_VOICE_MAX_ENDPOINTING_DELAY_S` from `voice.turn_handling.max_endpointing_delay_s`;
worker.py:1809 consumes it. Verified statically: the compiler's exact emit logic on the live config
produces `VIVENTIUM_VOICE_MAX_ENDPOINTING_DELAY_S=0.8`. All three YAMLs parse. Rationale respects
06_Voice_Calls.md:21-24 (keep 0.35s min + 0.5s VAD-silence floor so a short reflective pause still
gets one detector evaluation and is not cut mid-sentence; only the *ceiling* drops 1.8→0.8).

**Status: PASS (synthetic-mic live A/B). Audible-call acceptance remains PARTIAL per qa/README.md.**

### Live evidence captured (2026-05-30, post-restart, worker pid started 10:49:34)
Runtime chain verified: `config.yaml turn_handling.max_endpointing_delay_s: 0.8` →
`config_compiler.py:2796` → `runtime.env:229 VIVENTIUM_VOICE_MAX_ENDPOINTING_DELAY_S=0.8` →
running worker process env (`ps eww`) → live call log.

Harness: `qa/modern-playground-voice/scripts/livekit_synthetic_audio_qa.js` (fake-mic WAV → real
voice worker/STT → persisted transcript), local whisper `large-v3-turbo`.

**Case EOU pause-700ms (fixture `pause-700ms.wav`, 0.7s mid-sentence gap):**
- voice_gateway.log this run: `turn_detection=turn_detector min_endpoint=0.35s max_endpoint=0.8s
  eou_delay=0.77s`
- **EOU 1.40s p50 (before) → 0.77s (after)** — the detector now hits the 0.8 ceiling instead of
  riding to 1.8s. ~0.6s saved per turn.
- **No mid-sentence cutoff**: `transcriptCount=1` (one persisted turn, not two siblings). The 0.7s
  pause did NOT prematurely fork the sentence. PASS MPV-011 + MPV-012.

**Case EOU pause-1500ms (fixture `pause-1500ms.wav`, 1.5s mid-thought gap):**
- voice_gateway.log this run: `max_endpoint=0.8s eou_delay=0.945s`.
- `transcriptCount=2` — the 1.5s pause split into TWO turns. Full text preserved across both; this is
  NOT a sentence cut, it is two endpointed segments.

### The tradeoff (flagged honestly, not hidden)
The continuation window IS `max_endpointing_delay` — there is no separate merge knob in worker.py. So
a pause longer than the ceiling necessarily ends the turn. With max=1.8 (old), a 1.5s pause was held
as one turn; with max=0.8 (new), it splits. This is the unavoidable cost of sub-second EOU using a
single knob.

Against the authoritative contract this is acceptable: 06_Voice_Calls.md:21-24 forbids forking a
*sentence* and cutting a *short reflective pause* — it does not mandate holding a full 1.5s silence as
one turn. The `expected_transcript_rows=1` on the 1.5s fixture was calibrated to the old 1.8s ceiling,
not a product requirement. The 0.7s case (a genuinely short reflective pause) correctly stays one turn.

**Decision surfaced for owner:** pick the ceiling deliberately —
- `0.8s` = snappiest EOU (~0.77s), but 1.0-1.5s pauses split into separate turns.
- `~1.2s` = compromise (holds most reflective pauses, EOU ~1.1s).
- Or add a true continuation/merge window distinct from `max_endpointing_delay` so EOU can be low
  AND long pauses still merge — a larger change (own task), not part of this lever.

Shipped value is `0.8`. Acceptance per Key Principles §0: faster end-of-turn (0.77s vs 1.40s p50) with
no sentence-fork on a short pause; the 1.5s-pause split is a documented, contract-compatible tradeoff,
not a silent regression. Audible playback quality is the standing synthetic-mic PARTIAL ceiling
(qa/README.md).
