# Voice STT (local whisper.cpp) QA

## Scope
Local on-device speech-to-text for the voice surface: `pywhispercpp` (whisper.cpp) running
`large-v3-turbo`, warm-loaded in the voice gateway worker. Covers transcription **accuracy (WER)**
and **decode latency** together — per Key Principles §0, a latency change that regresses accuracy is
a regression, not a win.

## Owning code / docs
- Provider: `viventium_v0_4/voice-gateway/pywhispercpp_provider.py`
- Harness: `viventium_v0_4/voice-gateway/tests/stt_local_accuracy_bench.py`
- Feature docs: `docs/requirements_and_learnings/52_Voice_Component_Fork_Modification_Inventory.md`,
  `viventium_v0_4/docs/VOICE_CALLS.md`
- Related QA: `qa/modern-playground-voice/` (full call latency)

## Quality bar
- **Accuracy:** no WER regression > 0.02 on any case vs the committed baseline.
- **Performance:** warm decode well under real-time (RTF < 0.5) on all cases; bound worst-case
  (degraded-audio) tail.
- **Local-first:** STT stays local (whisper.cpp). Cloud STT (AssemblyAI/OpenAI) remains a separate
  selectable option, not the default — do not "fix" local latency by switching the default to cloud.

## Harness
Deterministic, public-safe: macOS `say` + `afconvert` synthesize 16 kHz mono clips from known
ground-truth text across short / medium / long(>12s) / with-pause / no-pause / fast-speech, plus
seeded **degraded variants** (white-noise low-SNR, heavy attenuation) that actually trigger
whisper's temperature-fallback loop. WER computed dependency-free (token Levenshtein). Imports the
real provider decode path (`_get_model`, `_transcribe_kwargs`) so it tests exactly what production
runs, including any tuning env. A/B via `--compare a.json b.json` with a hard WER-regression gate.

```bash
cd viventium_v0_4/voice-gateway
.venv/bin/python tests/stt_local_accuracy_bench.py --json <temp>/baseline.json
VIVENTIUM_STT_TEMPERATURE_INC=0 STT_BENCH_LABEL=capped \
  .venv/bin/python tests/stt_local_accuracy_bench.py --json <temp>/capped.json
.venv/bin/python tests/stt_local_accuracy_bench.py --compare <temp>/baseline.json <temp>/capped.json
```

## Latest status (2026-05-30)
- Baseline accuracy: **WER 0.000 on all clean clips**, RTF 0.04–0.22 (15.6s audio → 0.66s decode).
  Local STT is accurate and faster than real-time — **not** a current voice bottleneck.
- Retry-fallback cap (`VIVENTIUM_STT_TEMPERATURE_INC=0`): **REJECTED by QA.** Full 21-case degraded
  A/B showed it regresses accuracy on 3 noisy/quiet clips (e.g. `long_withpause/quiet` WER
  0.000→0.204) AND was not faster (mean p50 493→540ms). The fallback retries do real work on hard
  audio. The env knob ships but **defaults to library behavior (no cap)**; do not set it to 0 globally.
- Core ML / ANE encoder: **PARKED** — `coremlc` needs full Xcode (~17GB; only 12GB free here) and
  the ANE encoder path is broken on Apple Silicon + macOS 26 (whisper.cpp #3702, silent Metal
  fallback). No real win on this machine today. Runbook retained for a future Xcode/OS where it works.
- **Conclusion: local STT has no safe speed win available; leave it as-is.** The real voice latency
  wins are the LLM/EOU/preemptive-TTS/cortex levers, not STT.

See `cases.md` for durable cases and `reports/` for dated evidence.
