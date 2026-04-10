#!/usr/bin/env python3
"""Gemma 4 Local Benchmark Runner — Apple M5 system with 32GB unified memory.

Runs performance and intelligence evals on Gemma 4 E2B, E4B, and 26B MoE
via the Ollama API. Outputs structured JSON results.

Usage:
    python3 qa/gemma4-local-benchmarks/run_eval.py
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

OLLAMA_URL = "http://localhost:11434"
MODELS = ["gemma4:e2b", "gemma4:latest", "gemma4:26b"]
MODEL_LABELS = {"gemma4:e2b": "E2B", "gemma4:latest": "E4B", "gemma4:26b": "26B-MoE"}
PERF_RUNS = 3
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ollama_generate(model, prompt, system=None, max_tokens=1024, timeout=120):
    """Call Ollama /api/generate (non-streaming) and return full response dict."""
    import urllib.request
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": max_tokens},
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e), "response": ""}


def ollama_chat(model, messages, system=None, max_tokens=1024, tools=None, timeout=120):
    """Call Ollama /api/chat (non-streaming)."""
    import urllib.request
    body = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"num_predict": max_tokens},
    }
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def measure_ttft_streaming(model, prompt, timeout=60):
    """Measure TTFT using streaming endpoint. Returns milliseconds."""
    import urllib.request
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": {"num_predict": 1},
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read(1)  # first byte
            ttft = (time.perf_counter() - start) * 1000
        return ttft
    except Exception as e:
        return -1


def get_memory_stats():
    """Return dict with memory pressure info."""
    try:
        result = subprocess.run(
            ["vm_stat"], capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().split("\n")
        stats = {}
        for line in lines[1:]:
            parts = line.split(":")
            if len(parts) == 2:
                key = parts[0].strip()
                val = parts[1].strip().rstrip(".")
                try:
                    stats[key] = int(val)
                except ValueError:
                    pass
        page_size = 16384  # M5 uses 16K pages
        free_pages = stats.get("Pages free", 0)
        active_pages = stats.get("Pages active", 0)
        inactive_pages = stats.get("Pages inactive", 0)
        wired_pages = stats.get("Pages wired down", 0)
        compressed = stats.get("Pages stored in compressor", 0)
        swapouts = stats.get("Swapouts", 0)
        return {
            "free_gb": round(free_pages * page_size / 1e9, 2),
            "active_gb": round(active_pages * page_size / 1e9, 2),
            "wired_gb": round(wired_pages * page_size / 1e9, 2),
            "compressed_gb": round(compressed * page_size / 1e9, 2),
            "swapouts": swapouts,
        }
    except Exception:
        return {}


def get_ollama_ps():
    """Get currently loaded model memory from ollama ps."""
    try:
        result = subprocess.run(
            ["ollama", "ps"], capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()
    except Exception:
        return ""


def preload_model(model):
    """Force-load a model by generating a single token."""
    ollama_generate(model, "hi", max_tokens=1, timeout=60)
    time.sleep(2)


def unload_model(model):
    """Unload model by setting keep_alive to 0."""
    import urllib.request
    body = json.dumps({
        "model": model,
        "prompt": "",
        "keep_alive": 0,
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
    except Exception:
        pass
    time.sleep(3)


# ---------------------------------------------------------------------------
# Performance tests
# ---------------------------------------------------------------------------

def run_perf_ttft(model):
    """Measure TTFT at 3 prompt lengths, cold + warm, 3 runs each."""
    prompts = {
        "short_50tok": "Explain what a neural network is in one sentence.",
        "medium_500tok": "Write a detailed explanation of how transformers work in machine learning, covering attention mechanisms, positional encoding, and the encoder-decoder architecture. Include specific technical details about multi-head attention, layer normalization, and feed-forward networks. " * 3,
        "long_2000tok": "Explain the complete history of artificial intelligence from its inception to modern day, covering key milestones, breakthroughs, setbacks, and future directions. Include details about symbolic AI, expert systems, the AI winters, the rise of machine learning, deep learning revolution, large language models, and the current state of AI research. Discuss the contributions of key figures like Alan Turing, John McCarthy, Geoffrey Hinton, Yann LeCun, and others. " * 5,
    }
    results = {}
    for label, prompt in prompts.items():
        runs_cold = []
        runs_warm = []
        for i in range(PERF_RUNS):
            # Cold: unload then measure
            unload_model(model)
            cold = measure_ttft_streaming(model, prompt)
            runs_cold.append(cold)
            # Warm: model already loaded
            warm = measure_ttft_streaming(model, prompt)
            runs_warm.append(warm)
        results[label] = {
            "cold_ms": {"mean": round(sum(runs_cold) / len(runs_cold), 1),
                        "values": [round(v, 1) for v in runs_cold]},
            "warm_ms": {"mean": round(sum(runs_warm) / len(runs_warm), 1),
                        "values": [round(v, 1) for v in runs_warm]},
        }
    return results


def run_perf_tps(model):
    """Measure tokens/sec at different context lengths."""
    contexts = {
        "100tok": "Hello, ",
        "1k_tok": "Explain the theory of relativity. " * 30,
        "4k_tok": "Explain the theory of relativity in great detail. " * 120,
    }
    results = {}
    preload_model(model)
    for label, prompt in contexts.items():
        runs = []
        for _ in range(PERF_RUNS):
            resp = ollama_generate(model, prompt, max_tokens=200, timeout=180)
            if "error" in resp:
                runs.append(0)
                continue
            eval_count = resp.get("eval_count", 0)
            eval_duration = resp.get("eval_duration", 1)
            tps = eval_count / (eval_duration / 1e9) if eval_duration > 0 else 0
            runs.append(round(tps, 2))
        results[label] = {
            "tps": {"mean": round(sum(runs) / len(runs), 2),
                    "values": runs},
        }
    return results


def run_perf_memory(model):
    """Measure memory footprint."""
    unload_model(model)
    time.sleep(2)
    mem_before = get_memory_stats()
    preload_model(model)
    mem_loaded = get_memory_stats()
    ollama_ps = get_ollama_ps()
    # Generate with 4K context to measure peak
    ollama_generate(model, "Explain everything about AI. " * 120, max_tokens=200, timeout=180)
    mem_peak = get_memory_stats()
    return {
        "before_load": mem_before,
        "after_load": mem_loaded,
        "after_4k_gen": mem_peak,
        "ollama_ps": ollama_ps,
    }


# ---------------------------------------------------------------------------
# Intelligence tests
# ---------------------------------------------------------------------------

CODING_PROBLEMS = [
    {
        "id": "code_1_fizzbuzz",
        "prompt": "Write a Python function `custom_fizzbuzz(n, divisors)` that takes an integer n and a dict mapping divisors to words. For numbers 1 to n, if divisible by a key, append that word. Print the combined word or the number. Example: custom_fizzbuzz(15, {3: 'Fizz', 5: 'Buzz'}) prints standard FizzBuzz. Return None. Only output the function, no explanation.",
        "check": "def",
        "type": "generation",
    },
    {
        "id": "code_2_trie",
        "prompt": "Implement a Trie class in Python with methods: insert(word), search(word) -> bool, starts_with(prefix) -> bool. Only output the class, no explanation.",
        "check": "class Trie",
        "type": "generation",
    },
    {
        "id": "code_3_flatten_json",
        "prompt": "Write a Python function `flatten_json(obj, prefix='')` that takes a nested dict and returns a flat dict with dot-notation keys. Example: {'a': {'b': 1, 'c': {'d': 2}}} -> {'a.b': 1, 'a.c.d': 2}. Handle lists by using index as key (e.g., 'a.0'). Only output the function.",
        "check": "def flatten_json",
        "type": "generation",
    },
    {
        "id": "code_4_rotated_search",
        "prompt": "Write a Python function `search_rotated(nums, target)` that searches for target in a rotated sorted array and returns its index, or -1 if not found. Must be O(log n). Only output the function.",
        "check": "def search_rotated",
        "type": "generation",
    },
    {
        "id": "code_5_lru_cache",
        "prompt": "Implement an LRU cache in Python as a class `LRUCache` with `__init__(self, capacity)`, `get(self, key) -> int` (returns -1 if not found), and `put(self, key, value)`. Both operations must be O(1). Use OrderedDict or implement with a doubly-linked list + dict. Only output the class.",
        "check": "class LRUCache",
        "type": "generation",
    },
]

BUG_DETECTION = [
    {
        "id": "bug_1_offbyone",
        "prompt": """Find the bug in this binary search and fix it:

```python
def binary_search(arr, target):
    left, right = 0, len(arr)
    while left < right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid
        else:
            right = mid
    return -1
```

Explain the bug and provide the corrected code.""",
        "expected_fix": "left = mid + 1",
    },
    {
        "id": "bug_2_async",
        "prompt": """Find the bug in this Python async code:

```python
import asyncio

counter = 0

async def increment():
    global counter
    temp = counter
    await asyncio.sleep(0.01)
    counter = temp + 1

async def main():
    tasks = [increment() for _ in range(100)]
    await asyncio.gather(*tasks)
    print(f"Counter: {counter}")  # Expected: 100

asyncio.run(main())
```

Explain the bug and provide a fix.""",
        "expected_fix": "lock",
    },
    {
        "id": "bug_3_sqli",
        "prompt": """Find the security vulnerability in this code and fix it:

```python
import sqlite3

def get_user(username):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    query = f"SELECT * FROM users WHERE username = '{username}'"
    cursor.execute(query)
    return cursor.fetchone()
```

Explain the vulnerability and provide a fix.""",
        "expected_fix": "parameterized",
    },
]

MATH_PROBLEMS = [
    {
        "id": "math_1_system",
        "prompt": "Solve the system of equations: 2x + 3y - z = 1, x - y + 2z = 5, 3x + y + z = 8. Show your work and give the values of x, y, z.",
        "answer": {"x": 2, "y": -1, "z": 3},
    },
    {
        "id": "math_2_compound",
        "prompt": "An investment of $10,000 earns 5% annually for the first 3 years, then 8% annually for the next 2 years, all compounded annually. What is the final value? Show your calculation.",
        "answer_approx": 13891.0,
        "tolerance": 50,
    },
    {
        "id": "math_3_proof",
        "prompt": "Prove that the sum of the first n odd numbers equals n^2. Write a clear mathematical proof.",
        "check": "induction",
    },
    {
        "id": "math_4_combinatorics",
        "prompt": "In a 5x5 grid, how many shortest paths are there from the top-left corner to the bottom-right corner if you can only move right or down? One cell at position (2,2) is blocked (0-indexed). Show your work.",
        "answer": 96,
    },
    {
        "id": "math_5_bayes",
        "prompt": "A medical test has 95% sensitivity and 90% specificity. The disease prevalence is 1%. If a person tests positive, what is the probability they actually have the disease? Show the Bayesian calculation.",
        "answer_approx": 0.088,
        "tolerance": 0.01,
    },
]

BUSINESS_PROBLEMS = [
    {
        "id": "biz_1_pnl",
        "prompt": """Analyze this simplified P&L and identify the 3 biggest cost drivers:

Revenue: $2,400,000
COGS: $960,000
Gross Profit: $1,440,000
Sales & Marketing: $720,000
R&D: $480,000
G&A: $180,000
Depreciation: $60,000
Operating Income: $0

What are the 3 largest cost items, their % of revenue, and what does this tell you about the business?""",
    },
    {
        "id": "biz_2_unit_economics",
        "prompt": "A SaaS company has: CAC = $500, Monthly subscription = $50, Gross margin = 80%, Monthly churn = 3%. Calculate the LTV, LTV:CAC ratio, and months to payback. Is this business viable? Why or why not?",
        "answer_ltv_approx": 1333,
    },
    {
        "id": "biz_3_pricing",
        "prompt": "You're launching a B2B project management tool. Competitors charge $10-30/user/month. You have a unique AI feature that automates task assignment. Your COGS is $3/user/month. Propose a pricing strategy with 3 tiers, justify each price point, and explain your positioning.",
    },
    {
        "id": "biz_4_acquisition",
        "prompt": "A company wants to acquire a target for $50M. The target has: Revenue $12M (growing 20% YoY), EBITDA $2M, 50 employees, 3 key customers representing 60% of revenue, and a pending patent lawsuit. Identify the top 5 risks in this deal and rate each as high/medium/low with justification.",
    },
]

SCIENCE_PROBLEMS = [
    {
        "id": "sci_1_crispr",
        "prompt": "Explain the molecular mechanism of CRISPR-Cas9 gene editing in 150-200 words. Include: the role of guide RNA, how Cas9 creates double-strand breaks, and the two main repair pathways (NHEJ and HDR).",
    },
    {
        "id": "sci_2_experiment",
        "prompt": """Given this experimental data, identify the independent variable, dependent variable, and suggest a proper control:

Experiment: Researchers tested whether caffeine affects reaction time.
Group A (n=30): Given 200mg caffeine, average reaction time 245ms (SD=32)
Group B (n=30): Given 400mg caffeine, average reaction time 218ms (SD=28)
Group C (n=30): Given 600mg caffeine, average reaction time 231ms (SD=45)

What are the IV, DV, and what control is missing? What confound should they worry about?""",
    },
    {
        "id": "sci_3_antibiotic",
        "prompt": "Explain why antibiotic resistance evolves faster in hospitals than in the general community. Reference at least 3 specific evolutionary/ecological mechanisms.",
    },
    {
        "id": "sci_4_carbon",
        "prompt": "Describe the carbon cycle including at least 4 major reservoirs and 4 flux pathways. Then identify 2 specific human activities that disrupt it and quantify their approximate impact in gigatons of CO2 per year.",
    },
]

PSYCHOLOGY_PROBLEMS = [
    {
        "id": "psych_1_biases",
        "prompt": "Describe 3 specific cognitive biases that affect investment decisions. For each, provide: (a) the formal name, (b) the mechanism, (c) a concrete example in investing, and (d) a debiasing strategy.",
    },
    {
        "id": "psych_2_morale",
        "prompt": "A manager's team of 12 has low morale after layoffs reduced the company from 200 to 140 employees. Propose an evidence-based intervention plan. Cite at least 2 specific psychological frameworks or theories (by name) and explain how each applies.",
    },
    {
        "id": "psych_3_memory",
        "prompt": "Three witnesses saw a car accident. Witness A (bystander, interviewed 1 hour later) says the car was blue and going fast. Witness B (involved driver, interviewed 3 days later) says the car was green and going the speed limit. Witness C (bystander, interviewed 1 hour later but was shown a news report first) says the car was blue-green and speeding. Explain why their memories diverge, naming specific memory phenomena, and state which account is likely most reliable and why.",
    },
]

TOOL_USE_SCENARIOS = [
    {
        "id": "tool_1_simple",
        "system": "You have access to the following function: get_weather(city: string) -> Returns current weather for a city. When you need to call a function, respond with a JSON object with 'name' and 'arguments' keys.",
        "prompt": "What's the weather in Tokyo?",
        "expected_tool": "get_weather",
        "expected_args": {"city": "Tokyo"},
    },
    {
        "id": "tool_2_multi",
        "system": "You have access to: create_event(title: string, date: string, time: string, attendees: list[string]) and send_email(to: string, subject: string, body: string). When you need to call functions, respond with a JSON array of objects with 'name' and 'arguments' keys.",
        "prompt": "Book a meeting called 'Project Sync' with Alice for tomorrow at 3pm and email her the invite.",
        "expected_tools": ["create_event", "send_email"],
    },
    {
        "id": "tool_3_chained",
        "system": "You have access to: web_search(query: string) -> Returns search results, and summarize(text: string) -> Returns summary. When you need to call functions, respond with JSON objects with 'name' and 'arguments' keys. You may need to chain calls.",
        "prompt": "Search for Python tutorials and summarize the top 3 results.",
        "expected_tool": "web_search",
    },
    {
        "id": "tool_4_no_tool",
        "system": "You have access to: get_weather(city: string) and send_email(to: string, subject: string, body: string). Only call a function if it is relevant. If no function is needed, respond normally.",
        "prompt": "What is 2 + 2?",
        "expected": "no_tool_call",
    },
]

INSTRUCTION_TESTS = [
    {
        "id": "inst_1_bullets",
        "prompt": "Respond in exactly 3 bullet points about the benefits of exercise.",
        "check": lambda r: r.count("•") == 3 or r.count("- ") == 3 or r.count("* ") == 3 or len([l for l in r.strip().split("\n") if l.strip().startswith(("-", "•", "*", "1", "2", "3"))]) == 3,
    },
    {
        "id": "inst_2_json",
        "prompt": 'Answer in JSON format with exactly these keys: "name", "age", "city". Make up a person.',
        "check": lambda r: all(k in r for k in ['"name"', '"age"', '"city"']),
    },
    {
        "id": "inst_3_wordcount",
        "prompt": "Write exactly 50 words about artificial intelligence. Count carefully.",
        "check": lambda r: 40 <= len(r.split()) <= 60,
    },
    {
        "id": "inst_4_forbidden",
        "prompt": "Explain AI without using the word 'artificial'. Do not use the word 'artificial' anywhere in your response.",
        "check": lambda r: "artificial" not in r.lower(),
    },
    {
        "id": "inst_5_spanish",
        "prompt": "Respond only in Spanish: What are the three primary colors?",
        "check": lambda r: any(w in r.lower() for w in ["rojo", "azul", "amarillo", "colores", "primarios"]),
    },
]

FACTUAL_QUESTIONS = [
    {"id": "fact_1", "prompt": "What year was the Universal Declaration of Human Rights adopted? Answer with just the year.", "answer": "1948"},
    {"id": "fact_2", "prompt": "What is the chemical formula for sulfuric acid? Answer with just the formula.", "answer": "H2SO4"},
    {"id": "fact_3", "prompt": "Who wrote 'One Hundred Years of Solitude'? Answer with just the name.", "answer": "Gabriel Garcia Marquez"},
    {"id": "fact_4", "prompt": "What is the capital of Kazakhstan? Answer with just the city name.", "answer": "Astana"},
    {"id": "fact_5", "prompt": "What is the average-case time complexity of quicksort? Answer with just the Big-O notation.", "answer": "O(n log n)"},
    {"id": "fact_6", "prompt": "How many chromosomes do humans have? Answer with just the number.", "answer": "46"},
]

HALLUCINATION_QUESTIONS = [
    {"id": "halluc_1", "prompt": "Who was the 58th President of the United States? Provide their name and key accomplishments.", "expected": "refuse"},
    {"id": "halluc_2", "prompt": "Summarize the paper 'Quantum Entanglement in Avocado Growth Patterns' by Dr. James Smith, published in Nature 2024.", "expected": "refuse"},
    {"id": "halluc_3", "prompt": "What is the population of the city of Xanthoria? Provide the latest census figures.", "expected": "refuse"},
]

CREATIVITY_TASKS = [
    {"id": "creative_1", "prompt": "Write a 100-word story with a twist ending about a lighthouse keeper. Exactly 100 words."},
    {"id": "creative_2", "prompt": "Generate 5 startup ideas that combine AI and healthcare. For each, give: name, one-line pitch, target customer, and why it's novel."},
    {"id": "creative_3", "prompt": "Explain blockchain to a 10-year-old using at least 3 creative metaphors. Make it fun and memorable."},
]

PLANNING_TASKS = [
    {"id": "plan_1", "prompt": "Plan a 3-day tech conference for 200 attendees with a $50,000 budget. Output a structured plan covering: venue, catering, speakers, AV equipment, marketing, staffing, and contingency. Include a budget breakdown that sums to $50,000."},
    {
        "id": "plan_2_critical_path",
        "prompt": """Find the critical path and total project duration for these tasks:
A: 3 days, no dependencies
B: 2 days, no dependencies
C: 4 days, depends on A
D: 3 days, depends on A
E: 2 days, depends on B and D
F: 3 days, depends on C
G: 2 days, depends on E and F
H: 1 day, depends on G

What is the critical path and total project time in days?""",
        "answer_path": ["A", "C", "F", "G", "H"],
        "answer_days": 13,
    },
    {"id": "plan_3_debug", "prompt": """A CI pipeline is failing. Here are 4 log excerpts:

Log 1 (build step): "WARN: Node 18 is deprecated, using Node 20"
Log 2 (test step): "ERROR: Cannot connect to database at localhost:5432 - Connection refused"
Log 3 (test step): "FAIL: 23 of 150 tests failed, 22 with DatabaseConnectionError"
Log 4 (deploy step): "SKIP: Deploy skipped due to test failures"

Identify the root cause and propose a fix sequence."""},
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_intelligence_tests(model):
    """Run all intelligence tests for one model. Returns dict of results."""
    label = MODEL_LABELS[model]
    results = {}

    print(f"\n{'='*60}")
    print(f"  INTELLIGENCE TESTS: {label} ({model})")
    print(f"{'='*60}")

    # Preload model
    preload_model(model)

    # --- Coding ---
    print(f"\n  [{label}] Coding generation (5 problems)...")
    coding_results = []
    for p in CODING_PROBLEMS:
        resp = ollama_generate(model, p["prompt"], max_tokens=1024, timeout=120)
        text = resp.get("response", "")
        coding_results.append({"id": p["id"], "response": text[:2000], "has_target": p["check"].lower() in text.lower()})
        print(f"    {p['id']}: {'PASS' if p['check'].lower() in text.lower() else 'FAIL'} (contains '{p['check']}')")

    print(f"\n  [{label}] Bug detection (3 problems)...")
    bug_results = []
    for p in BUG_DETECTION:
        resp = ollama_generate(model, p["prompt"], max_tokens=1024, timeout=120)
        text = resp.get("response", "")
        found = p["expected_fix"].lower() in text.lower()
        bug_results.append({"id": p["id"], "response": text[:2000], "found_fix": found})
        print(f"    {p['id']}: {'PASS' if found else 'FAIL'} (contains '{p['expected_fix']}')")

    results["coding"] = {"generation": coding_results, "bug_detection": bug_results}

    # --- Math ---
    print(f"\n  [{label}] Math/Logic (5 problems)...")
    math_results = []
    for p in MATH_PROBLEMS:
        resp = ollama_generate(model, p["prompt"], max_tokens=1024, timeout=120)
        text = resp.get("response", "")
        item = {"id": p["id"], "response": text[:2000]}
        if "answer" in p and isinstance(p["answer"], dict):
            for k, v in p["answer"].items():
                item[f"expected_{k}"] = v
                item[f"found_{k}"] = str(v) in text
        elif "answer" in p:
            item["expected"] = p["answer"]
            item["found"] = str(p["answer"]) in text
        elif "answer_approx" in p:
            item["expected_approx"] = p["answer_approx"]
        elif "check" in p:
            item["has_check"] = p["check"].lower() in text.lower()
        math_results.append(item)
        status = "collected"
        if "found" in item:
            status = "PASS" if item["found"] else "FAIL"
        print(f"    {p['id']}: {status}")

    results["math"] = math_results

    # --- Business ---
    print(f"\n  [{label}] Business/Finance (4 problems)...")
    biz_results = []
    for p in BUSINESS_PROBLEMS:
        resp = ollama_generate(model, p["prompt"], max_tokens=1500, timeout=120)
        text = resp.get("response", "")
        item = {"id": p["id"], "response": text[:3000]}
        biz_results.append(item)
        print(f"    {p['id']}: collected ({len(text)} chars)")

    results["business"] = biz_results

    # --- Science ---
    print(f"\n  [{label}] Science/Biology (4 problems)...")
    sci_results = []
    for p in SCIENCE_PROBLEMS:
        resp = ollama_generate(model, p["prompt"], max_tokens=1500, timeout=120)
        text = resp.get("response", "")
        sci_results.append({"id": p["id"], "response": text[:3000]})
        print(f"    {p['id']}: collected ({len(text)} chars)")

    results["science"] = sci_results

    # --- Psychology ---
    print(f"\n  [{label}] Psychology (3 problems)...")
    psych_results = []
    for p in PSYCHOLOGY_PROBLEMS:
        resp = ollama_generate(model, p["prompt"], max_tokens=1500, timeout=120)
        text = resp.get("response", "")
        psych_results.append({"id": p["id"], "response": text[:3000]})
        print(f"    {p['id']}: collected ({len(text)} chars)")

    results["psychology"] = psych_results

    # --- Tool Use ---
    print(f"\n  [{label}] Tool Use (4 scenarios)...")
    tool_results = []
    for s in TOOL_USE_SCENARIOS:
        resp = ollama_generate(model, s["prompt"], system=s["system"], max_tokens=512, timeout=60)
        text = resp.get("response", "")
        item = {"id": s["id"], "response": text[:1500]}
        if "expected_tool" in s:
            item["has_tool_name"] = s["expected_tool"].lower() in text.lower()
        if "expected" in s and s["expected"] == "no_tool_call":
            item["correctly_no_tool"] = "4" in text and not any(t in text.lower() for t in ["get_weather", "send_email"])
        tool_results.append(item)
        print(f"    {s['id']}: collected")

    results["tool_use"] = tool_results

    # --- Instruction Following ---
    print(f"\n  [{label}] Instruction Following (5 tests)...")
    inst_results = []
    for t in INSTRUCTION_TESTS:
        resp = ollama_generate(model, t["prompt"], max_tokens=512, timeout=60)
        text = resp.get("response", "")
        passed = t["check"](text)
        inst_results.append({"id": t["id"], "response": text[:1000], "passed": passed})
        print(f"    {t['id']}: {'PASS' if passed else 'FAIL'}")

    results["instruction_following"] = inst_results

    # --- Factual Accuracy ---
    print(f"\n  [{label}] Factual Accuracy (6 questions)...")
    fact_results = []
    for q in FACTUAL_QUESTIONS:
        resp = ollama_generate(model, q["prompt"], max_tokens=50, timeout=30)
        text = resp.get("response", "").strip()
        correct = q["answer"].lower() in text.lower()
        fact_results.append({"id": q["id"], "response": text[:200], "correct": correct, "expected": q["answer"]})
        print(f"    {q['id']}: {'PASS' if correct else 'FAIL'} (got: {text[:50]})")

    results["factual_accuracy"] = fact_results

    # --- Hallucination Resistance ---
    print(f"\n  [{label}] Hallucination Resistance (3 trick questions)...")
    halluc_results = []
    for q in HALLUCINATION_QUESTIONS:
        resp = ollama_generate(model, q["prompt"], max_tokens=512, timeout=60)
        text = resp.get("response", "")
        # Check if model refuses/hedges
        refuse_signals = ["don't have", "doesn't exist", "not aware", "no such", "cannot find",
                         "not a real", "fictional", "no record", "hasn't been", "as of my",
                         "i'm not", "i am not", "there is no", "there hasn't", "not real",
                         "i don't", "unable to", "do not have", "can't find", "no president",
                         "fabricated", "made up", "no information"]
        refused = any(sig in text.lower() for sig in refuse_signals)
        halluc_results.append({"id": q["id"], "response": text[:1500], "refused": refused})
        print(f"    {q['id']}: {'REFUSED (good)' if refused else 'HALLUCINATED (bad)'}")

    results["hallucination_resistance"] = halluc_results

    # --- Creativity ---
    print(f"\n  [{label}] Creativity (3 tasks)...")
    creative_results = []
    for t in CREATIVITY_TASKS:
        resp = ollama_generate(model, t["prompt"], max_tokens=1024, timeout=90)
        text = resp.get("response", "")
        creative_results.append({"id": t["id"], "response": text[:3000]})
        print(f"    {t['id']}: collected ({len(text)} chars)")

    results["creativity"] = creative_results

    # --- Planning ---
    print(f"\n  [{label}] Planning (3 scenarios)...")
    plan_results = []
    for t in PLANNING_TASKS:
        resp = ollama_generate(model, t["prompt"], max_tokens=2048, timeout=120)
        text = resp.get("response", "")
        item = {"id": t["id"], "response": text[:4000]}
        if "answer_days" in t:
            item["expected_days"] = t["answer_days"]
            item["found_days"] = str(t["answer_days"]) in text
            item["expected_path"] = t["answer_path"]
        plan_results.append(item)
        status = "collected"
        if "found_days" in item:
            status = f"days={'PASS' if item['found_days'] else 'FAIL'}"
        print(f"    {t['id']}: {status}")

    results["planning"] = plan_results

    return results


def run_performance_tests(model):
    """Run all performance tests for one model."""
    label = MODEL_LABELS[model]
    print(f"\n{'='*60}")
    print(f"  PERFORMANCE TESTS: {label} ({model})")
    print(f"{'='*60}")

    print(f"\n  [{label}] Memory footprint...")
    memory = run_perf_memory(model)

    print(f"\n  [{label}] Tokens/sec (3 context lengths, {PERF_RUNS} runs each)...")
    tps = run_perf_tps(model)

    print(f"\n  [{label}] TTFT (3 prompt lengths, cold+warm, {PERF_RUNS} runs each)...")
    ttft = run_perf_ttft(model)

    return {"memory": memory, "tps": tps, "ttft": ttft}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  GEMMA 4 LOCAL BENCHMARK SUITE")
    print(f"  {datetime.now(timezone.utc).isoformat()}")
    print(f"  Models: {', '.join(MODEL_LABELS.values())}")
    print("  Hardware: Apple M5 system with 32GB unified memory")
    print("=" * 60)

    all_results = {
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hardware": "Apple M5 system with 32GB unified memory",
            "engine": "Ollama",
            "models": MODELS,
            "perf_runs": PERF_RUNS,
        },
        "performance": {},
        "intelligence": {},
    }

    for model in MODELS:
        label = MODEL_LABELS[model]

        # Performance
        all_results["performance"][label] = run_performance_tests(model)

        # Intelligence
        all_results["intelligence"][label] = run_intelligence_tests(model)

        # Unload before next model
        unload_model(model)

    # Save raw results
    out_path = os.path.join(OUTPUT_DIR, "results_ollama.json")
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n\nResults saved to {out_path}")

    # Print summary
    print_summary(all_results)

    return all_results


def print_summary(results):
    """Print a human-readable summary table."""
    print("\n\n" + "=" * 80)
    print("  SUMMARY")
    print("=" * 80)

    # Performance
    print("\n--- PERFORMANCE ---")
    print(f"{'Metric':<30} {'E2B':>12} {'E4B':>12} {'26B-MoE':>12}")
    print("-" * 66)
    for label in ["E2B", "E4B", "26B-MoE"]:
        perf = results["performance"].get(label, {})
        tps_100 = perf.get("tps", {}).get("100tok", {}).get("tps", {}).get("mean", "n/a")
        tps_4k = perf.get("tps", {}).get("4k_tok", {}).get("tps", {}).get("mean", "n/a")
        ttft_warm = perf.get("ttft", {}).get("short_50tok", {}).get("warm_ms", {}).get("mean", "n/a")
    # Print as rows
    for metric_key, metric_name in [
        ("100tok", "TPS @ 100 tokens"),
        ("1k_tok", "TPS @ 1K tokens"),
        ("4k_tok", "TPS @ 4K tokens"),
    ]:
        vals = []
        for label in ["E2B", "E4B", "26B-MoE"]:
            v = results["performance"].get(label, {}).get("tps", {}).get(metric_key, {}).get("tps", {}).get("mean", "n/a")
            vals.append(f"{v}")
        print(f"{metric_name:<30} {vals[0]:>12} {vals[1]:>12} {vals[2]:>12}")

    for metric_key, metric_name in [
        ("short_50tok", "TTFT warm (short)"),
        ("medium_500tok", "TTFT warm (medium)"),
        ("long_2000tok", "TTFT warm (long)"),
    ]:
        vals = []
        for label in ["E2B", "E4B", "26B-MoE"]:
            v = results["performance"].get(label, {}).get("ttft", {}).get(metric_key, {}).get("warm_ms", {}).get("mean", "n/a")
            vals.append(f"{v} ms" if v != "n/a" else "n/a")
        print(f"{metric_name:<30} {vals[0]:>12} {vals[1]:>12} {vals[2]:>12}")

    # Intelligence auto-scored
    print("\n--- INTELLIGENCE (Auto-Scored) ---")
    print(f"{'Category':<30} {'E2B':>12} {'E4B':>12} {'26B-MoE':>12}")
    print("-" * 66)

    for label_key in ["E2B", "E4B", "26B-MoE"]:
        intel = results["intelligence"].get(label_key, {})

    # Coding generation
    vals = []
    for label in ["E2B", "E4B", "26B-MoE"]:
        gen = results["intelligence"].get(label, {}).get("coding", {}).get("generation", [])
        score = sum(1 for g in gen if g.get("has_target")) / max(len(gen), 1)
        vals.append(f"{score:.2f}")
    print(f"{'Coding generation (5)':<30} {vals[0]:>12} {vals[1]:>12} {vals[2]:>12}")

    # Bug detection
    vals = []
    for label in ["E2B", "E4B", "26B-MoE"]:
        bugs = results["intelligence"].get(label, {}).get("coding", {}).get("bug_detection", [])
        score = sum(1 for b in bugs if b.get("found_fix")) / max(len(bugs), 1)
        vals.append(f"{score:.2f}")
    print(f"{'Bug detection (3)':<30} {vals[0]:>12} {vals[1]:>12} {vals[2]:>12}")

    # Instruction following
    vals = []
    for label in ["E2B", "E4B", "26B-MoE"]:
        insts = results["intelligence"].get(label, {}).get("instruction_following", [])
        score = sum(1 for i in insts if i.get("passed")) / max(len(insts), 1)
        vals.append(f"{score:.2f}")
    print(f"{'Instruction following (5)':<30} {vals[0]:>12} {vals[1]:>12} {vals[2]:>12}")

    # Factual accuracy
    vals = []
    for label in ["E2B", "E4B", "26B-MoE"]:
        facts = results["intelligence"].get(label, {}).get("factual_accuracy", [])
        score = sum(1 for f in facts if f.get("correct")) / max(len(facts), 1)
        vals.append(f"{score:.2f}")
    print(f"{'Factual accuracy (6)':<30} {vals[0]:>12} {vals[1]:>12} {vals[2]:>12}")

    # Hallucination resistance
    vals = []
    for label in ["E2B", "E4B", "26B-MoE"]:
        halluc = results["intelligence"].get(label, {}).get("hallucination_resistance", [])
        score = sum(1 for h in halluc if h.get("refused")) / max(len(halluc), 1)
        vals.append(f"{score:.2f}")
    print(f"{'Hallucination resist (3)':<30} {vals[0]:>12} {vals[1]:>12} {vals[2]:>12}")

    print("\n--- INTELLIGENCE (Needs Manual Scoring) ---")
    print("Business (4), Science (4), Psychology (3), Creativity (3), Planning (3)")
    print("Tool Use (4) — responses collected, require manual review")
    print(f"\nFull responses saved in results_ollama.json")


if __name__ == "__main__":
    main()
