# === VIVENTIUM START ===
# Feature: Local whisper.cpp STT accuracy + speed benchmark harness.
# Purpose:
#   Safety net for tuning the local whisper STT (Core ML / retry-fallback cap / audio_ctx).
#   Per Key Principles 0 (outcome = Quality + Performance): a tuning change is only acceptable
#   if it is FASTER *and* does NOT regress accuracy. This harness measures BOTH on the REAL
#   decode path by importing the provider's own `_get_model` + `_transcribe_kwargs`, so we test
#   exactly what production runs (same model, same kwargs, including any new tuning env).
#
#   Deterministic, public-safe audio is synthesized with macOS `say` + `afconvert` (16 kHz mono),
#   covering the dimensions the owner called out: short / medium / long(>12s) / with-pause /
#   without-pause / fast-speech. Ground-truth text is known, so we compute word error rate (WER).
#
#   Usage:
#     .venv/bin/python tests/stt_local_accuracy_bench.py                 # current (baseline) config
#     STT_BENCH_LABEL=tuned VIVENTIUM_STT_TEMPERATURE_FALLBACK=off \
#       .venv/bin/python tests/stt_local_accuracy_bench.py               # a tuned config
#     .venv/bin/python tests/stt_local_accuracy_bench.py --json out.json # machine-readable
#
#   A/B: run once to write baseline.json, change env/config, run again, then `--compare a.json b.json`.
# Added: 2026-05-30
# === VIVENTIUM END ===

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

import numpy as np

# Import the REAL provider decode path (not a reimplementation) so the harness is faithful.
_HERE = Path(__file__).resolve().parent
_GATEWAY = _HERE.parent
if str(_GATEWAY) not in sys.path:
    sys.path.insert(0, str(_GATEWAY))

from pywhispercpp_provider import (  # noqa: E402
    _default_model_name,
    _get_model,
    _transcribe_kwargs,
)

# --- Test corpus: (id, ground_truth, say_text, rate, dimension) -----------------------------
# say_text may include `[[slnc N]]` inline pauses (N ms); ground_truth excludes the markers.
# Words only (no digits/symbols) so WER is not unfairly penalized by formatting choices.
SAY_VOICE = os.getenv("STT_BENCH_VOICE", "Daniel")  # clear en_GB voice present on macOS
CORPUS = [
    ("short_nopause", "hello there how are you doing today",
     "hello there how are you doing today", 180, "short/no-pause"),
    ("short2_nopause", "what is the weather like outside right now",
     "what is the weather like outside right now", 180, "short/no-pause"),
    ("medium_nopause",
     "please remind me to call the dentist office tomorrow afternoon before it closes",
     "please remind me to call the dentist office tomorrow afternoon before it closes",
     180, "medium/no-pause"),
    ("medium_withpause",
     "so what do you think about the plan should we move forward or wait a little longer",
     "so what do you think [[slnc 600]] about the plan [[slnc 600]] should we move forward or wait a little longer",
     180, "medium/with-pause"),
    ("fast_speech",
     "please remind me to call the dentist office tomorrow afternoon before it closes",
     "please remind me to call the dentist office tomorrow afternoon before it closes",
     290, "fast-speech"),
    ("long_nopause",
     "i had a really long day at work and i want to talk through everything that happened "
     "first the morning meeting ran over by almost an hour then the client changed their mind "
     "about the design and finally the build broke right before we were supposed to ship it",
     "i had a really long day at work and i want to talk through everything that happened "
     "first the morning meeting ran over by almost an hour then the client changed their mind "
     "about the design and finally the build broke right before we were supposed to ship it",
     180, "long(>12s)/no-pause"),
    ("long_withpause",
     "i had a really long day at work and i want to talk through everything that happened "
     "first the morning meeting ran over by almost an hour then the client changed their mind "
     "about the design and finally the build broke right before we were supposed to ship it",
     "i had a really long day at work and i want to talk through everything that happened "
     "[[slnc 700]] first the morning meeting ran over by almost an hour [[slnc 700]] "
     "then the client changed their mind about the design [[slnc 700]] and finally the build "
     "broke right before we were supposed to ship it",
     180, "long(>12s)/with-pause"),
]

_PUNCT = str.maketrans("", "", ".,!?;:\"'()-")


def _normalize(text: str) -> list[str]:
    return text.lower().translate(_PUNCT).split()


def _wer(ref: str, hyp: str) -> float:
    """Word error rate via Levenshtein distance on token lists (dependency-free)."""
    r, h = _normalize(ref), _normalize(hyp)
    if not r:
        return 0.0 if not h else 1.0
    # DP edit distance
    prev = list(range(len(h) + 1))
    for i, rw in enumerate(r, 1):
        cur = [i] + [0] * len(h)
        for j, hw in enumerate(h, 1):
            cost = 0 if rw == hw else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[-1] / len(r)


def _synth_wav(say_text: str, rate: int, out_wav: Path) -> float:
    """Render `say` -> 16kHz mono 16-bit WAV. Returns audio duration (s)."""
    aiff = out_wav.with_suffix(".aiff")
    subprocess.run(["say", "-v", SAY_VOICE, "-r", str(rate), "-o", str(aiff), say_text],
                   check=True)
    subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1",
                    str(aiff), str(out_wav)], check=True)
    aiff.unlink(missing_ok=True)
    with wave.open(str(out_wav), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def _load_float32(wav_path: Path) -> np.ndarray:
    with wave.open(str(wav_path), "rb") as w:
        pcm = w.readframes(w.getnframes())
    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    return np.ascontiguousarray(audio)


# Deterministic noise so degraded clips are reproducible across runs (seeded per clip id).
def _degrade(audio: np.ndarray, kind: str, cid: str) -> np.ndarray:
    """Add reproducible degradation that exercises whisper's temperature-fallback loop.
    `noise` = additive white noise (low SNR); `quiet` = heavy attenuation (low signal)."""
    if kind == "clean":
        return audio
    rng = np.random.default_rng(abs(hash(cid)) % (2**32))
    if kind == "noise":
        noise = rng.standard_normal(audio.shape).astype(np.float32)
        rms = float(np.sqrt(np.mean(audio**2))) or 1e-4
        out = audio + noise * (rms * 0.9)  # ~ -1 dB SNR: hard but human-intelligible
    elif kind == "quiet":
        out = audio * 0.08 + rng.standard_normal(audio.shape).astype(np.float32) * 0.004
    else:
        return audio
    return np.ascontiguousarray(np.clip(out, -1.0, 1.0))


def _transcribe(model, audio: np.ndarray, model_name: str, duration_s: float) -> str:
    params = _transcribe_kwargs(os.getenv("VIVENTIUM_STT_LANGUAGE", "en"),
                                model_name=model_name, audio_duration_s=duration_s)
    segs = model.transcribe(audio, **params)
    return " ".join(s.text for s in segs) if segs else ""


def run(runs: int) -> dict:
    label = os.getenv("STT_BENCH_LABEL", "baseline")
    model_name = _default_model_name()
    model = _get_model(model_name)  # warm load + cached
    cache = Path(os.getenv("STT_BENCH_AUDIO_DIR", tempfile.gettempdir()) ) / "viv_stt_bench_audio"
    cache.mkdir(parents=True, exist_ok=True)

    # Warm the decoder once (first inference is always cold) before timing.
    _transcribe(model, np.zeros(16000, dtype=np.float32), model_name, 1.0)

    # Degraded variants exercise whisper's temperature-fallback loop (the retry-cap target).
    # Without these, clean greedy decode never retries and a temperature_inc change is untestable.
    degrade_kinds = ["clean"]
    if os.getenv("STT_BENCH_DEGRADED", "1").strip().lower() in {"1", "true", "yes", "on"}:
        degrade_kinds = ["clean", "noise", "quiet"]

    rows = []
    for cid, truth, say_text, rate, dim in CORPUS:
        wav = cache / f"{cid}.wav"
        if not wav.exists():
            _synth_wav(say_text, rate, wav)
        base_audio = _load_float32(wav)
        for kind in degrade_kinds:
            audio = _degrade(base_audio, kind, cid)
            dur = audio.size / 16000.0
            times, hyp = [], ""
            for _ in range(runs):
                t0 = time.perf_counter()
                hyp = _transcribe(model, audio, model_name, dur)
                times.append((time.perf_counter() - t0) * 1000.0)
            rows.append({
                "id": f"{cid}/{kind}", "dimension": f"{dim}/{kind}", "audio_s": round(dur, 2),
                "wer": round(_wer(truth, hyp), 4),
                "ms_p50": round(statistics.median(times), 1),
                "ms_min": round(min(times), 1), "ms_max": round(max(times), 1),
                "rtf": round((statistics.median(times) / 1000.0) / dur, 3) if dur else None,
                "truth": truth, "hyp": hyp.strip(),
            })

    result = {
        "label": label, "model": model_name,
        "audio_ctx_reduced_max_s": os.getenv("VIVENTIUM_STT_REDUCED_AUDIO_CTX_MAX_AUDIO_S", "12.0"),
        "temperature_fallback": os.getenv("VIVENTIUM_STT_TEMPERATURE_FALLBACK", "(default)"),
        "runs": runs, "rows": rows,
        "wer_mean": round(statistics.mean(r["wer"] for r in rows), 4),
        "ms_p50_mean": round(statistics.mean(r["ms_p50"] for r in rows), 1),
    }
    return result


def _print(res: dict) -> None:
    print(f"\n=== STT local bench: label={res['label']} model={res['model']} "
          f"fallback={res['temperature_fallback']} runs={res['runs']} ===")
    print(f"{'id':18} {'dimension':22} {'audio_s':>7} {'WER':>6} {'p50ms':>7} {'maxms':>7} {'rtf':>6}")
    for r in res["rows"]:
        print(f"{r['id']:18} {r['dimension']:22} {r['audio_s']:>7} {r['wer']:>6.3f} "
              f"{r['ms_p50']:>7.1f} {r['ms_max']:>7.1f} {str(r['rtf']):>6}")
    print(f"{'MEAN':18} {'':22} {'':>7} {res['wer_mean']:>6.3f} {res['ms_p50_mean']:>7.1f}")
    # surface any clip whose transcript drifted, for eyeball QA
    for r in res["rows"]:
        if r["wer"] > 0.0:
            print(f"  [drift] {r['id']} WER={r['wer']:.3f}\n     ref: {r['truth']}\n     hyp: {r['hyp']}")


def _compare(a_path: str, b_path: str) -> None:
    a = json.loads(Path(a_path).read_text())
    b = json.loads(Path(b_path).read_text())
    by_a = {r["id"]: r for r in a["rows"]}
    print(f"\n=== A/B: {a['label']} -> {b['label']} (model {a['model']}) ===")
    print(f"{'id':18} {'WER a→b':>14} {'p50ms a→b':>18} {'verdict':>10}")
    regressions = []
    for rb in b["rows"]:
        ra = by_a.get(rb["id"])
        if not ra:
            continue
        dwer = rb["wer"] - ra["wer"]
        dms = rb["ms_p50"] - ra["ms_p50"]
        # Quality gate (Key Principles 0): accuracy must not regress (tiny tolerance for noise).
        verdict = "OK"
        if dwer > 0.02:
            verdict = "WER REGRESS"
            regressions.append(rb["id"])
        elif dms < -50:
            verdict = "FASTER"
        print(f"{rb['id']:18} {ra['wer']:.3f}→{rb['wer']:.3f}{'':4} "
              f"{ra['ms_p50']:>7.1f}→{rb['ms_p50']:<7.1f} {verdict:>10}")
    print(f"\nMEAN WER {a['wer_mean']:.3f}→{b['wer_mean']:.3f}   "
          f"MEAN p50 {a['ms_p50_mean']:.1f}→{b['ms_p50_mean']:.1f}ms")
    if regressions:
        print(f"\n*** ACCURACY REGRESSION on: {', '.join(regressions)} — change is NOT acceptable per Key Principles 0 ***")
    else:
        print("\nNo accuracy regression. If faster, the change is acceptable.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Local whisper STT speed+accuracy bench")
    ap.add_argument("--runs", type=int, default=3, help="timed runs per clip (warm)")
    ap.add_argument("--json", help="write result JSON to this path")
    ap.add_argument("--compare", nargs=2, metavar=("A.json", "B.json"))
    args = ap.parse_args()

    if args.compare:
        _compare(*args.compare)
        return

    res = run(args.runs)
    _print(res)
    if args.json:
        Path(args.json).write_text(json.dumps(res, indent=2))
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
