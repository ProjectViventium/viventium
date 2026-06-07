<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# 2026-05-30 — Local whisper STT: retry-fallback cap (REJECTED) + Core ML investigation

## Summary
Investigated tuning the local whisper.cpp STT (`large-v3-turbo`) to be faster without losing
accuracy. Built a reusable accuracy+speed harness with clean AND degraded audio. The retry-fallback
cap was **rejected by QA** (regressed accuracy, no speed gain). Core ML/ANE parked (not viable on
this machine/OS). Net: local STT is already accurate + faster-than-realtime; no safe speed win — leave as-is.

## Evidence chain
feature (local STT) → requirement (§0 faster AND not less accurate; local-first) → use cases
(STT-L-01…09) → harness (`tests/stt_local_accuracy_bench.py`) → results below → decision.

## What was run
Harness on the real provider decode path, `large-v3-turbo`, warm, M5 / macOS 26.4. 7 base clips ×
{clean, noise, quiet} = 21 cases, 2 timed runs each, A/B baseline vs `VIVENTIUM_STT_TEMPERATURE_INC=0`.

## Baseline accuracy + speed (clean clips)
WER **0.000 on every clean clip**. RTF 0.04–0.22; 15.6s audio decoded in ~0.66s. Conclusion: local
STT is accurate and comfortably faster than real-time — not the voice bottleneck.

## Retry-fallback cap A/B — FAILED the quality gate
Full 21-case degraded run (the earlier "−85…−159ms, zero WER change" claim was from a too-small
sample and is RETRACTED):

| case | WER base→cap | verdict |
|---|---|---|
| medium_withpause / noise | 0.000→0.529 | **WER REGRESS** |
| long_nopause / noise | 0.000→0.020 | **WER REGRESS** |
| long_withpause / quiet | 0.000→0.204 | **WER REGRESS** |
| (clean clips) | 0.000→0.000 | unchanged |
| mean | 0.061→0.078 | worse |
| mean p50 latency | 493ms→540ms | **slower, not faster** |

**Result:** disabling the temperature fallback lost words on hard/noisy audio AND did not reduce
latency. The fallback retries are doing real accuracy work. **FAILED STT-L-08 gate per Key
Principles §0 → not shipped as a default.**

## Decision
- `VIVENTIUM_STT_TEMPERATURE_INC` env knob shipped in `pywhispercpp_provider.py` (VIVENTIUM-wrapped)
  but **defaults to whisper.cpp library behavior (no cap)**. Verified: unset = library default,
  `0` = disabled retries, non-numeric = safely ignored. Do NOT set it to 0 globally.
- Local STT left as-is. No safe speed win available.

## Core ML / ANE — parked (proven, not assumed)
- `pywhispercpp==1.4.1` is the prebuilt PyPI wheel: links Metal + Accelerate, **0 CoreML symbols**
  (`otool`/`nm` verified); no `.mlmodelc` present.
- Two blockers: (1) model compile needs `coremlc` = full Xcode (~17GB; 12GB free); (2) ANE encoder
  path broken on Apple Silicon + macOS 26 (whisper.cpp #3702 → silent Metal fallback).
- Net: enabling Core ML here yields Metal-fallback parity, not a speedup. Runbook saved for a future
  Xcode-equipped machine / fixed OS.

## Why Core ML was missing originally
Core ML in whisper.cpp is opt-in at build time (special flag + converted model); the public wheel
ships without it. The install does the normal `pip install pywhispercpp` → Metal-only. Metal was
"fast enough" so it never stood out, and no QA compared encoder time against an ANE build. This
report + the harness close that observability gap (Key Principles §2.5).

## ANE across the wider local stack (audited)
TTS (Chatterbox MLX), local LLM (Ollama/llama.cpp), embeddings are **autoregressive or GPU-optimal**
— ANE is the wrong accelerator (poor at dynamic shapes / KV-cache); measured ANE LLM ~9 tok/s vs
MLX 93+. Silero VAD (~1MB) and the int8 turn-detector (CoreML EP can't run int8) show no win. The
whole local stack is already on the right accelerator (Metal/MLX). **No ANE migration worth pursuing today.**

## Lesson promoted
A larger A/B sample overturned a premature "safe + faster" conclusion from a small sample. Always run
the full degraded suite before accepting an STT tuning change. The harness now defaults degraded
clips ON so the fallback path is always exercised.
