# Voice STT (local whisper.cpp) — QA cases

Run via `viventium_v0_4/voice-gateway/tests/stt_local_accuracy_bench.py`. All audio is synthetic and
public-safe (macOS `say`). Expected outcomes are the quality bar in `README.md`.

| ID | Case | Input | Expected | Forbidden |
|----|------|-------|----------|-----------|
| STT-L-01 | Short, no pause | ~2s clean speech | WER 0.000, decode < 0.5s | any word error on clean audio |
| STT-L-02 | Medium, no pause | ~4.5s clean | WER 0.000, RTF < 0.5 | truncated/dropped words |
| STT-L-03 | Medium, with pauses | ~5.8s w/ 600ms gaps | WER 0.000; pauses don't split/cut words | premature end / lost trailing words |
| STT-L-04 | Fast speech | ~3s @ 290 wpm | WER 0.000 | degraded accuracy at speed |
| STT-L-05 | Long > 12s, no pause | ~13s (full audio_ctx path) | WER 0.000; not truncated | sentence truncation at audio_ctx switch |
| STT-L-06 | Long > 12s, with pauses | ~15.6s w/ 700ms gaps | WER 0.000 | mid-utterance cutoff |
| STT-L-07 | Degraded (noise/quiet) | low-SNR + attenuated variants | best-effort WER; **decode tail bounded** | fallback loop causing multi-second spike with no accuracy gain |
| STT-L-08 | Retry-cap A/B | baseline vs `VIVENTIUM_STT_TEMPERATURE_INC=0` | gate: ship only if faster AND no WER regression > 0.02 | **2026-05-30: FAILED gate (WER regressed on 3 clips, not faster) → cap NOT shipped as default** |
| STT-L-09 | Local-first default | provider config | default STT stays local whisper | default silently switched to cloud STT |

## Natural User Use Case Checklist

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `STT-L-UC-001` | Speak a short, clean voice prompt and compare local STT text with the expected transcript. | `06_Voice_Calls.md` / `STT-L-01`, `STT-L-02` | Modern playground or voice gateway STT harness with synthetic audio | Transcript text, WER result, decode timing, provider config, and voice gateway logs | The transcript is accurate, low-latency, and still uses local whisper.cpp unless the user selected a hosted provider. | PASS 2026-05-30 via synthetic harness; user-grade playground call remains owned by `qa/modern-playground-voice/` |
| `STT-L-UC-002` | Speak a long or paused utterance and verify the tail is not clipped. | `06_Voice_Calls.md` / `STT-L-05`, `STT-L-06` | Modern playground or voice gateway STT harness with synthetic long audio | Ground-truth text, WER result, audio duration, decode timing, and local provider kwargs | The final words appear in the transcript and the long-audio path stays faster than real time. | PASS 2026-05-30 via synthetic harness |
| `STT-L-UC-003` | Try degraded/noisy input and compare the retry-cap A/B result before changing defaults. | `14_Voice_Latency_and_Memory_RCA.md` / `STT-L-07`, `STT-L-08`, `STT-L-09` | Voice gateway STT benchmark, provider config inspection, modern playground follow-up when defaults change | A/B WER and timing JSON, config default, public-safe report, and voice QA owner linkage | A latency optimization is rejected if accuracy regresses; the default does not silently switch from local STT to cloud STT. | FAILED gate 2026-05-30 for retry cap; default unchanged |

## Automation
- `tests/stt_local_accuracy_bench.py` (speed + WER, A/B compare with WER-regression gate).
- Degraded suite (`STT_BENCH_DEGRADED=1`, default on) exercises the temperature-fallback path so
  STT-L-07/08 are meaningful.

## Last run
- 2026-05-30 — `reports/2026-05-30-retry-fallback-cap.md` (STT-L-01…07,09 PASS; **STT-L-08 FAILED gate
  → retry-cap rejected, not shipped as default**). Local STT left as-is; no safe speed win.
