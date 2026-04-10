# Gemma 4 Local Benchmarks — Test Plan

> Quantitative evaluation of the Gemma 4 model family on an Apple M5 system with 32GB unified
> memory.
> Feature doc: `docs/requirements_and_learnings/48_Gemma4_Local_Benchmarks.md`

## Hardware Under Test

- Apple M5, 32GB unified memory
- macOS (Darwin 25.4.0)
- Engines: Ollama (llama.cpp backend), MLX (mlx-lm / mlx-vlm)

## Models Under Test

| ID | Ollama Tag | Quant | Size |
|----|-----------|-------|------|
| G4-E2B | `gemma4:e2b` | Q4_K_M | 7.2 GB |
| G4-E4B | `gemma4:latest` | Q4_K_M | 9.6 GB |
| G4-26B | `gemma4:26b` | Q4_K_M | 18 GB |
| G4-31B | `gemma4:31b` | Q4_K_M | 20 GB |

## Baselines

- Claude Opus 4.6 (via API — same prompts, measure response quality only, not latency)
- GPT 5.4 (via API — same prompts, measure response quality only, not latency)

---

## Category 1: Performance Metrics

All measured locally on the Apple M5 32GB system. Each measurement repeated 3x, report mean
and stdev.

### 1.1 Time to First Token (TTFT)

- **Method:** `curl` to Ollama `/api/generate` with `stream: true`, measure time from request
  send to first chunk received. For MLX, use `mlx_lm.generate` with timing wrapper.
- **Prompt lengths:** 50 tokens (short), 500 tokens (medium), 2000 tokens (long)
- **Unit:** milliseconds
- **Runs:** 3 per model per prompt length, cold start (first run after model load) + warm (subsequent)

### 1.2 Tokens Per Second (Generation Speed)

- **Method:** Generate 200 tokens from a fixed prompt. Measure wall-clock time for the full
  generation. TPS = output_tokens / generation_time.
- **Context lengths:** 100 tokens, 1K tokens, 4K tokens, 16K tokens
- **Unit:** tokens/second
- **Runs:** 3 per model per context length

### 1.3 Memory Footprint

- **Method:** Before model load, record `memory_pressure` and available memory.
  After model load + idle, record again. After generation at 4K context, record again.
- **Metrics:**
  - Idle model memory (GB)
  - Peak memory during 4K context generation (GB)
  - Swap usage (MB) — critical indicator for 32GB constraint
- **Unit:** GB (memory), MB (swap)

### 1.4 Context Window Stress Test

- **Method:** Feed progressively longer inputs (1K, 4K, 16K, 32K, 64K tokens) and
  measure TPS at each level. Note the point where swap begins or generation becomes
  unusable (<1 tok/s).
- **Unit:** tokens/second at each context depth, plus max usable context (tokens)

---

## Category 2: Intelligence — Coding

### 2.1 Code Generation (5 problems)

Each problem scored: 0 (fails), 0.5 (partial/needs fix), 1.0 (correct first try).

| # | Problem | Language | Difficulty |
|---|---------|----------|-----------|
| 1 | FizzBuzz with custom divisors | Python | Easy |
| 2 | Implement a trie with insert/search/prefix | Python | Medium |
| 3 | Parse nested JSON and flatten to dot-notation keys | Python | Medium |
| 4 | Binary search on rotated sorted array | Python | Medium |
| 5 | Implement an LRU cache with O(1) get/put | Python | Hard |

**Score:** sum / 5 = accuracy (0.0 to 1.0)

### 2.2 Bug Detection (3 problems)

Present code with a subtle bug. Model must identify the bug and fix it.
Scored: 0 (misses bug), 0.5 (identifies but wrong fix), 1.0 (correct diagnosis + fix).

| # | Bug Type | Language |
|---|----------|---------|
| 1 | Off-by-one in binary search | Python |
| 2 | Race condition in async code | Python |
| 3 | SQL injection vulnerability | Python |

**Score:** sum / 3 = accuracy (0.0 to 1.0)

---

## Category 3: Intelligence — Math / Logic

### 3.1 Mathematical Reasoning (5 problems)

| # | Problem | Domain | Difficulty |
|---|---------|--------|-----------|
| 1 | Solve a system of 3 equations | Algebra | Medium |
| 2 | Calculate compound interest with varying rates | Finance math | Medium |
| 3 | Prove a simple number theory claim (e.g., sum of first n odds = n^2) | Proof | Medium |
| 4 | Combinatorics: paths in a grid with obstacles | Combinatorics | Hard |
| 5 | Probability: Bayesian update with 3 events | Probability | Hard |

**Scoring:** 0 (wrong answer), 0.5 (correct approach, arithmetic error), 1.0 (correct answer with valid reasoning).

**Score:** sum / 5 = accuracy (0.0 to 1.0)

---

## Category 4: Intelligence — Business & Finance

### 4.1 Business Reasoning (4 problems)

| # | Problem | Domain |
|---|---------|--------|
| 1 | Read a simplified P&L statement and identify the 3 biggest cost drivers | Financial analysis |
| 2 | Given unit economics (CAC, LTV, churn), determine if a SaaS business is viable | Unit economics |
| 3 | Draft a pricing strategy for a B2B product given market positioning data | Strategy |
| 4 | Identify risks in a proposed acquisition based on a term sheet summary | M&A analysis |

**Scoring:** Each answer graded on a rubric by Claude Opus 4.6 as judge (0.0 to 1.0 scale):
- 0.0-0.3: Fundamentally wrong or missing key elements
- 0.4-0.6: Partially correct, misses important factors
- 0.7-0.8: Mostly correct, minor gaps
- 0.9-1.0: Comprehensive and accurate

**Score:** mean of 4 grades (0.0 to 1.0)

---

## Category 5: Intelligence — Science & Biology

### 5.1 Scientific Reasoning (4 problems)

| # | Problem | Domain |
|---|---------|--------|
| 1 | Explain the mechanism of CRISPR-Cas9 gene editing | Molecular biology |
| 2 | Given experimental data (table), identify the independent/dependent variables and suggest a control | Experimental design |
| 3 | Explain why antibiotic resistance evolves faster in hospitals | Evolutionary biology |
| 4 | Describe the carbon cycle and identify 2 human interventions that disrupt it | Earth science |

**Scoring:** Claude Opus 4.6 as judge, same 0.0-1.0 rubric as business section.

**Score:** mean of 4 grades (0.0 to 1.0)

---

## Category 6: Intelligence — Psychology & Social Science

### 6.1 Psychology Reasoning (3 problems)

| # | Problem | Domain |
|---|---------|--------|
| 1 | Describe 3 cognitive biases that affect investment decisions, with examples | Behavioral econ |
| 2 | A manager's team has low morale after layoffs. Propose an evidence-based intervention plan citing specific psychological frameworks | Org psych |
| 3 | Given a scenario with conflicting witness accounts, explain why memories diverge and which account is likely more reliable | Cognitive psych |

**Scoring:** Claude Opus 4.6 as judge, same 0.0-1.0 rubric.

**Score:** mean of 3 grades (0.0 to 1.0)

---

## Category 7: Tool Use / Function Calling

### 7.1 Structured Tool Call (4 scenarios)

System prompt defines available tools. Model must respond with correctly formatted tool calls.

| # | Scenario | Tools Available | Expected |
|---|----------|----------------|---------|
| 1 | "What's the weather in Tokyo?" | `get_weather(city: str)` | Single correct call |
| 2 | "Book a meeting with Alice tomorrow at 3pm and email her the invite" | `create_event(...)`, `send_email(...)` | Two sequential calls |
| 3 | "Search for Python tutorials and summarize the top 3 results" | `web_search(query: str)`, `summarize(text: str)` | Chained calls |
| 4 | "What's 2+2?" (no relevant tool) | `get_weather(...)`, `send_email(...)` | Should NOT call any tool |

**Scoring per scenario:**
- Correct tool name: 0.25
- Correct arguments: 0.25
- Correct call structure (JSON format): 0.25
- Correct sequencing / no hallucinated calls: 0.25

**Score:** sum across 4 scenarios / 4 = accuracy (0.0 to 1.0)

---

## Category 8: Instruction Following / Direction Compliance

### 8.1 Format Compliance (5 tests)

| # | Instruction | Check |
|---|-------------|-------|
| 1 | "Respond in exactly 3 bullet points" | Count bullets == 3 |
| 2 | "Answer in JSON with keys: name, age, city" | Valid JSON, exact keys present |
| 3 | "Write exactly 50 words about AI" | Word count within 45-55 |
| 4 | "Do NOT mention the word 'artificial'" | Word absent from response |
| 5 | "Respond only in Spanish" | Language detection == Spanish |

**Scoring:** Binary per test: 1.0 (passes check) or 0.0 (fails).

**Score:** sum / 5 = compliance rate (0.0 to 1.0)

---

## Category 9: Factual Accuracy / Hallucination Rate

### 9.1 Factual Questions (6 questions with verifiable answers)

| # | Question | Correct Answer | Domain |
|---|----------|---------------|--------|
| 1 | What year was the Universal Declaration of Human Rights adopted? | 1948 | History |
| 2 | What is the chemical formula for sulfuric acid? | H2SO4 | Chemistry |
| 3 | Who wrote "One Hundred Years of Solitude"? | Gabriel Garcia Marquez | Literature |
| 4 | What is the capital of Kazakhstan? | Astana | Geography |
| 5 | What is the time complexity of quicksort's average case? | O(n log n) | CS |
| 6 | How many chromosomes do humans have? | 46 | Biology |

**Scoring:** Binary: 1.0 (correct) or 0.0 (incorrect/hallucinated).

**Score:** sum / 6 = accuracy (0.0 to 1.0)

### 9.2 Hallucination Resistance (3 trick questions)

| # | Question | Expected Behavior |
|---|----------|------------------|
| 1 | "Who was the 58th President of the United States?" | Should say there hasn't been one (or state knowledge cutoff) |
| 2 | "Summarize the paper 'Quantum Entanglement in Avocado Growth Patterns' by Dr. Smith" | Should say it can't find / doesn't know this paper |
| 3 | "What is the population of the city of Xanthoria?" | Should say this isn't a real city |

**Scoring:** 1.0 (correctly refuses/flags uncertainty), 0.5 (hedges but provides fabricated info), 0.0 (confidently hallucinates).

**Score:** sum / 3 = resistance rate (0.0 to 1.0)

---

## Category 10: Creativity

### 10.1 Creative Generation (3 tasks)

| # | Task | Evaluation Criteria |
|---|------|-------------------|
| 1 | Write a 100-word story with a twist ending about a lighthouse keeper | Coherence, surprise factor, prose quality |
| 2 | Generate 5 startup ideas combining AI and healthcare | Novelty, feasibility, specificity |
| 3 | Write a metaphor-rich explanation of blockchain for a 10-year-old | Clarity, creativity of metaphors, age-appropriateness |

**Scoring:** Claude Opus 4.6 as judge rates each 0.0-1.0 on the stated criteria.

**Score:** mean of 3 grades (0.0 to 1.0)

---

## Category 11: Planning / Multi-Step Reasoning

### 11.1 Planning Tasks (3 scenarios)

| # | Scenario | Evaluation |
|---|----------|-----------|
| 1 | Plan a 3-day conference for 200 attendees with a $50K budget. Output a structured plan. | Completeness (all logistics covered), feasibility (budget realistic), structure |
| 2 | Given a dependency graph of 8 tasks with durations, find the critical path and total project time | Correctness of critical path, correct total time |
| 3 | Debug a failing CI pipeline: given 4 log excerpts, identify root cause and propose fix order | Correct root cause, logical fix sequence |

**Scoring:**
- Problem 2: Binary correctness (1.0 or 0.0 for critical path, 1.0 or 0.0 for total time) → average
- Problems 1 & 3: Claude Opus 4.6 as judge, 0.0-1.0

**Score:** mean of 3 grades (0.0 to 1.0)

---

## Scoring Aggregation

### Per-Model Scorecard

| Category | Weight | Score Range |
|----------|--------|------------|
| Performance: TTFT (ms) | — | Raw measurement |
| Performance: TPS (tok/s) | — | Raw measurement |
| Performance: Memory (GB) | — | Raw measurement |
| Performance: Max usable context (tokens) | — | Raw measurement |
| Coding accuracy | 15% | 0.0-1.0 |
| Math/Logic accuracy | 10% | 0.0-1.0 |
| Business/Finance | 10% | 0.0-1.0 |
| Science/Biology | 10% | 0.0-1.0 |
| Psychology/Social | 5% | 0.0-1.0 |
| Tool use accuracy | 15% | 0.0-1.0 |
| Instruction following | 10% | 0.0-1.0 |
| Factual accuracy | 10% | 0.0-1.0 |
| Hallucination resistance | 5% | 0.0-1.0 |
| Creativity | 5% | 0.0-1.0 |
| Planning | 5% | 0.0-1.0 |

**Composite Intelligence Score** = weighted sum of all 0.0-1.0 categories (excludes raw
performance metrics which are reported separately).

### Cross-Engine Comparison (Ollama vs MLX)

For each model variant, compare:
- TPS (Ollama) vs TPS (MLX)
- TTFT (Ollama) vs TTFT (MLX)
- Memory footprint (Ollama) vs Memory footprint (MLX)

---

## Execution Method

### Ollama Performance Tests

```bash
# TTFT measurement
time curl -s http://localhost:11434/api/generate \
  -d '{"model":"gemma4:e2b","prompt":"Hello","stream":true}' \
  | head -c 1

# TPS measurement
curl -s http://localhost:11434/api/generate \
  -d '{"model":"gemma4:e2b","prompt":"...","stream":false}' \
  | jq '.eval_count, .eval_duration'
# TPS = eval_count / (eval_duration / 1e9)
```

### Ollama Intelligence Tests

```bash
# Each question sent via API, response captured
curl -s http://localhost:11434/api/chat \
  -d '{
    "model": "gemma4:e2b",
    "messages": [{"role":"user","content":"..."}],
    "stream": false
  }' | jq -r '.message.content'
```

### MLX Performance Tests

```bash
# Via mlx-lm Python API
python3 -c "
from mlx_lm import load, generate
import time
model, tokenizer = load('mlx-community/gemma-4-E2B-it-4bit')
start = time.time()
result = generate(model, tokenizer, prompt='Hello', max_tokens=200)
elapsed = time.time() - start
print(f'TPS: {200/elapsed:.1f}')
"
```

### Automated Test Runner

A Python script (`qa/gemma4-local-benchmarks/run_eval.py`) will:
1. Load each model
2. Run all test categories
3. Measure all performance metrics
4. Collect all responses
5. Score deterministic categories automatically
6. Use Claude Opus 4.6 API as judge for subjective categories
7. Output results to `qa/gemma4-local-benchmarks/report.md`

---

## Acceptance Criteria

- All 4 models evaluated on all categories
- Performance metrics include mean + stdev from 3 runs
- All intelligence scores are 0.0-1.0 with clear per-question breakdowns
- Composite score computed with stated weights
- MLX vs Ollama speed comparison for all 4 variants
- Results documented in `report.md` with tables, not prose
- No qualitative labels without backing numbers
