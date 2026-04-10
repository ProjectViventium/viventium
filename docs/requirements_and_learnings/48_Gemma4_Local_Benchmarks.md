# 48 — Gemma 4 Local Benchmarks

> Feature doc for local Gemma 4 model evaluation on Apple Silicon.
> QA evidence: `qa/gemma4-local-benchmarks/`

## Motivation

Evaluate Google's Gemma 4 model family for local inference on an Apple M5 system with
32GB unified memory.
Determine which variants are viable for local agent, tool-use, and general intelligence
workloads, and how they compare to frontier cloud models (Claude Opus 4.6, GPT 5.4).

## Model Family Overview

Released April 2, 2026 by Google DeepMind. Apache 2.0 license. Training data cutoff: January 2025.

### Variants

| Variant | Total Params | Active Params | Architecture | Context | Modalities | Ollama Q4 Size |
|---------|-------------|---------------|-------------|---------|------------|---------------|
| E2B | 5.1B | 2.3B | Dense + PLE | 128K | Text, Image, Audio | 7.2 GB |
| E4B | 8B | 4.5B | Dense + PLE | 128K | Text, Image, Audio | 9.6 GB |
| 26B A4B | 25.2B | 3.8B | MoE (128 experts, 8+1 active) | 256K | Text, Image | 18 GB |
| 31B | 30.7B | 30.7B | Dense | 256K | Text, Image | 20 GB |

### Architecture Notes

- **PLE (Per-Layer Embeddings):** E2B and E4B inject a secondary embedding signal into every
  decoder layer, giving a 2.3B-active model the representational depth of its full 5.1B count.
- **MoE (26B A4B):** 128 small experts per MoE layer, router selects 2 of 128 plus 1 shared
  expert per token. Only ~3.8B parameters fire per forward pass. Achieves ~97% of the dense
  31B quality at a fraction of compute.
- **Audio:** Only E2B and E4B support native audio input. 26B and 31B are text+image only.
- **Function calling:** All variants ship with 6 dedicated special tokens for structured function
  calling — not prompt-engineered, baked into the tokenizer.

### Quantization and Memory Requirements

| Variant | Q4_K_M | Q8_0 | BF16 | Fits 32GB? |
|---------|--------|------|------|-----------|
| E2B | 7.2 GB | 8.1 GB | 10 GB | All quants fit |
| E4B | 9.6 GB | 12 GB | 16 GB | All quants fit |
| 26B A4B | 18 GB | 28 GB | — | Q4 fits, Q8 does not |
| 31B | 20 GB | 34 GB | 63 GB | Q4 fits (tight), Q8 does not |

## Published Benchmarks

### Official Scores (Google DeepMind Model Card)

| Benchmark | E2B | E4B | 26B MoE | 31B Dense | Gemma 3 27B |
|-----------|-----|-----|---------|-----------|-------------|
| MMLU Pro | 60.0% | 69.4% | 82.6% | 85.2% | 67.6% |
| MMMLU (Multilingual) | 67.4% | 76.6% | 86.3% | 88.4% | — |
| AIME 2026 (math) | 37.5% | 42.5% | 88.3% | 89.2% | 20.8% |
| LiveCodeBench v6 | 44.0% | 52.0% | 77.1% | 80.0% | 29.1% |
| Codeforces ELO | 633 | 940 | 1718 | 2150 | — |
| GPQA Diamond (grad science) | 43.4% | 58.6% | 82.3% | 84.3% | 42.4% |
| Tau2-bench (tool use) | 29.4% | 57.5% | 85.5% | 86.4% | 6.6% |
| BigBench Extra Hard | 21.9% | 33.1% | 64.8% | 74.4% | 19.3% |
| MMMU Pro (multimodal) | 44.2% | 52.6% | 73.8% | 76.9% | 49.7% |
| MATH-Vision | 52.4% | 59.5% | 82.4% | 85.6% | — |
| MRCR v2 8-needle 128K | 19.1% | 25.4% | 44.1% | 66.4% | — |
| Arena AI ELO | — | — | 1441 (#6) | 1452 (#3) | 1365 |

### Generation-Over-Generation Leaps (31B vs. Gemma 3 27B)

- AIME 2026: 20.8% → 89.2% (4.3x)
- Tau2-bench: 6.6% → 86.4% (13x)
- BigBench Extra Hard: 19.3% → 74.4% (3.9x)
- LiveCodeBench v6: 29.1% → 80.0% (2.7x)
- GPQA Diamond: 42.4% → 84.3% (2x)

## Frontier Baseline Comparison

| Capability | Gemma 4 31B | Claude Opus 4.6 | GPT 5.4 |
|------------|------------|-----------------|---------|
| Arena rank | #3 global | Top tier | Top tier |
| Code (SWE/LCB) | 80.0% LCB | ~80.8% SWE-bench | Competitive |
| Math (AIME) | 89.2% | Strong | Strong |
| Science (GPQA) | 84.3% | 94%+ class | 94%+ class |
| Tool use (Tau2) | 86.4% | Native excellence | Strong |
| Context window | 256K | 1M+ | 1M+ |
| Runs locally | Yes | No | No |
| Cost per token | $0 | API pricing | API pricing |

Gemma 4 31B reaches ~85-90% of frontier quality. For local/offline/private use, it is the
strongest open model available as of April 2026.

## Apple Silicon Performance

### Inference Engine Comparison

| Engine | Gemma 4 Support | Speed vs Ollama | Status |
|--------|----------------|-----------------|--------|
| Ollama (llama.cpp backend) | Day-0 | Baseline | Stable |
| MLX (Apple native) | Day-0 via mlx-vlm/mlx-lm | 1.5-2x faster | Best perf today |
| Ollama MLX backend | In progress (#15436) | Will match MLX | Not yet stable |

### Measured Speeds — Apple M5 32GB (Ollama, Q4_K_M)

| Variant | TPS (100 tok ctx) | TPS (1K ctx) | TPS (4K ctx) | TTFT warm (short) |
|---------|-------------------|-------------|-------------|-------------------|
| E2B | **69.20** | 55.95 | 41.79 | 170 ms |
| E4B | 40.72 | 25.99 | 22.92 | 192 ms |
| 26B MoE | 24.76 | 20.50 | 24.18 | 646 ms |
| 31B Dense | not tested (memory risk on 32GB) | — | — | — |

The 26B MoE is the sweet spot: only 3.8B active params per token means bandwidth-efficient
inference, while scoring within 3% of the 31B on most benchmarks.

## LibreChat Local Endpoint Contract

Verified locally on 2026-04-10 against the live Viventium native stack.

- `mlx_lm==0.31.2` does expose OpenAI-style `/v1/*` routes, but starting it with the Hugging Face
  repo id (`mlx-community/gemma-4-26b-a4b-it-4bit`) caused startup to hang while resolving remote
  metadata, even though the model was already cached locally.
- The stable operator path is to start the server from the cached snapshot path with
  `HF_HUB_OFFLINE=1`, which avoids the blocking Hugging Face lookup entirely.
- Native Viventium installs must target `http://localhost:8484/v1` for the MLX custom endpoint.
  Docker installs should target `http://host.docker.internal:8484/v1`.

### Stable Local Startup

Use the wrapper that resolves the cached snapshot automatically:

```bash
scripts/viventium/start_mlx_server.sh
```

The wrapper:

- finds a Python runtime with `mlx_lm` installed
- resolves the cached snapshot for `mlx-community/gemma-4-26b-a4b-it-4bit`
- forces `HF_HUB_OFFLINE=1`
- starts the MLX server on `http://localhost:8484/v1`

### MLX Reference Benchmarks (M5 Max 128GB, 4-bit)

From Incept5/gemma4-benchmark:

| Model | 4K Decode | 256K Decode | Memory |
|-------|-----------|-------------|--------|
| E2B | 205 tok/s | 78 tok/s | 4.7 GB |
| E4B | 127 tok/s | 27 tok/s | 6.4 GB |
| 26B MoE | 113 tok/s | 30 tok/s | 17.1 GB |
| 31B Dense | 27 tok/s | 7 tok/s | 22.7 GB |

## Intelligence Assessment by Domain (Measured Locally)

| Category | E2B | E4B | 26B MoE | Scoring Method |
|----------|-----|-----|---------|---------------|
| Coding generation (5) | 0.80 | **1.00** | **1.00** | Exact output check |
| Bug detection (3) | 0.33 | **1.00** | **1.00** | Fix keyword match |
| Math/Logic (5) | 0.00 | 0.40 | 0.40 | Exact answer match (strict) |
| Factual accuracy (6) | **0.83** | 0.67 | 0.67 | Exact answer match |
| Hallucination resist (3) | 0.67 | 0.67 | **1.00** | Refusal signal detection |
| Instruction following (5) | **1.00** | 0.80 | 0.80 | Format compliance check |
| Tool use (4) | 0.75 | 0.75 | **1.00** | Tool name + no-hallucinate |
| **Composite (weighted)** | **0.61** | **0.74** | **0.82** | See QA report for weights |
| Tool Calling | Weak | Moderate | Very Strong | Very Strong | Tau2 86.4%, native tokens |
| Science/Bio | Fair | Good | Strong | Very Strong | GPQA 84.3% |
| Business/Finance | Fair | Moderate | Good | Strong | Inferred from MMLU Pro |
| Psychology | Fair | Moderate | Good | Good | No specific benchmarks |
| Creative Writing | Moderate | Moderate | Good | Good | Arena ELO component |
| Instruction Following | Good | Good | Strong | Strong | Agent-first design |
| Planning | Weak | Moderate | Strong | Strong | BBH 74.4% |
| Multilingual | Good | Good | Very Strong | Very Strong | 140+ langs, 88.4% MMMLU |
| Multimodal (Vision) | Good | Good | Strong | Very Strong | MMMU Pro 76.9% |

## Local Eval Plan

See `qa/gemma4-local-benchmarks/README.md` for the full test plan and acceptance criteria.

### What We Measure

1. **Performance:** TTFT, tokens/sec (short and long context), memory footprint
2. **Intelligence:** Multi-domain question battery (coding, math, business, science, etc.)
3. **Tool use:** Structured function calling with native tokens
4. **Instruction following:** Direction compliance, format adherence
5. **Correctness:** Factual accuracy, hallucination rate
6. **Creativity:** Open-ended generation quality
7. **Context utilization:** Needle-in-haystack at various depths

### Baseline Comparisons

- Claude Opus 4.6 (via API)
- GPT 5.4 (via API)
- Cross-variant (E2B vs E4B vs 26B vs 31B)
- Cross-engine (Ollama vs MLX)

## References

- Google DeepMind Gemma 4 model card
- Ollama gemma4 tags page
- Incept5/gemma4-benchmark (Apple Silicon MLX benchmarks)
- Hugging Face Gemma 4 blog post
- Google Developers blog (Gemma 4 agentic skills)
- Ollama issue #15436 (MLX backend for Gemma 4)
- mlx-vlm Gemma 4 support documentation
