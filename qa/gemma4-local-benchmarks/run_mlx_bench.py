#!/usr/bin/env python3
"""MLX speed benchmark for Gemma 4 on Apple Silicon.

Compares MLX inference speed to Ollama for the same models.
Only measures TPS and TTFT — intelligence tests reuse Ollama results.

Usage:
    python3 qa/gemma4-local-benchmarks/run_mlx_bench.py
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

# MLX models on Hugging Face (4-bit quantized)
MLX_MODELS = {
    "E2B": "mlx-community/gemma-4-e2b-it-4bit",
    "E4B": "mlx-community/gemma-4-e4b-it-4bit",
    "26B-MoE": "mlx-community/gemma-4-27b-it-4bit",
}

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
RUNS = 3

def check_mlx():
    try:
        import mlx_lm
        print(f"mlx_lm version: {mlx_lm.__version__}")
        return True
    except ImportError:
        print("ERROR: mlx_lm not installed. Run: pip3 install mlx-lm")
        return False


def benchmark_model(model_id, label):
    """Benchmark a single MLX model. Returns dict with TPS and TTFT."""
    from mlx_lm import load, generate

    print(f"\n  Loading {label} ({model_id})...")
    start_load = time.perf_counter()
    try:
        model, tokenizer = load(model_id)
    except Exception as e:
        print(f"  ERROR loading {label}: {e}")
        return {"error": str(e)}
    load_time = time.perf_counter() - start_load
    print(f"  Loaded in {load_time:.1f}s")

    prompts = {
        "short": "Explain what a neural network is in one sentence.",
        "medium": "Write a detailed explanation of how transformers work in machine learning. " * 3,
    }

    results = {"load_time_s": round(load_time, 2)}

    for prompt_label, prompt in prompts.items():
        tps_runs = []
        ttft_runs = []

        for run in range(RUNS):
            # Measure generation
            start = time.perf_counter()
            output = generate(
                model, tokenizer,
                prompt=prompt,
                max_tokens=200,
                verbose=False,
            )
            elapsed = time.perf_counter() - start

            # Count output tokens
            out_tokens = len(tokenizer.encode(output))
            tps = out_tokens / elapsed if elapsed > 0 else 0
            tps_runs.append(round(tps, 2))

            # TTFT approximation: time to first token via generating just 1 token
            start_ttft = time.perf_counter()
            _ = generate(model, tokenizer, prompt=prompt, max_tokens=1, verbose=False)
            ttft_ms = (time.perf_counter() - start_ttft) * 1000
            ttft_runs.append(round(ttft_ms, 1))

        results[prompt_label] = {
            "tps": {
                "mean": round(sum(tps_runs) / len(tps_runs), 2),
                "values": tps_runs,
            },
            "ttft_ms": {
                "mean": round(sum(ttft_runs) / len(ttft_runs), 1),
                "values": ttft_runs,
            },
        }
        print(f"    {prompt_label}: {results[prompt_label]['tps']['mean']} tok/s, "
              f"TTFT {results[prompt_label]['ttft_ms']['mean']} ms")

    # Cleanup
    del model, tokenizer
    return results


def main():
    print("=" * 60)
    print("  GEMMA 4 MLX SPEED BENCHMARK")
    print(f"  {datetime.now(timezone.utc).isoformat()}")
    print("  Hardware: Apple M5 system with 32GB unified memory")
    print("=" * 60)

    if not check_mlx():
        sys.exit(1)

    all_results = {
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hardware": "Apple M5 system with 32GB unified memory",
            "engine": "MLX (mlx-lm)",
            "runs_per_test": RUNS,
        },
        "models": {},
    }

    for label, model_id in MLX_MODELS.items():
        print(f"\n{'='*60}")
        print(f"  {label}: {model_id}")
        print(f"{'='*60}")
        all_results["models"][label] = benchmark_model(model_id, label)

    # Save results
    out_path = os.path.join(OUTPUT_DIR, "results_mlx.json")
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n\nResults saved to {out_path}")

    # Summary
    print("\n\n--- MLX SPEED SUMMARY ---")
    print(f"{'Model':<12} {'Short TPS':>12} {'Medium TPS':>12} {'Short TTFT':>12}")
    print("-" * 48)
    for label in ["E2B", "E4B", "26B-MoE"]:
        m = all_results["models"].get(label, {})
        if "error" in m:
            print(f"{label:<12} {'ERROR':>12} {'':>12} {'':>12}")
            continue
        s_tps = m.get("short", {}).get("tps", {}).get("mean", "n/a")
        m_tps = m.get("medium", {}).get("tps", {}).get("mean", "n/a")
        s_ttft = m.get("short", {}).get("ttft_ms", {}).get("mean", "n/a")
        print(f"{label:<12} {s_tps:>12} {m_tps:>12} {str(s_ttft)+' ms':>12}")


if __name__ == "__main__":
    main()
