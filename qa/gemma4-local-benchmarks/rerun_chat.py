#!/usr/bin/env python3
"""Re-run intelligence tests using /api/chat endpoint.

The initial run used /api/generate which doesn't apply Gemma 4's chat template,
causing empty responses for conversational prompts. This script re-runs all
intelligence tests using /api/chat and patches the results.
"""

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

OLLAMA_URL = "http://localhost:11434"
MODELS = ["gemma4:e2b", "gemma4:latest", "gemma4:26b"]
MODEL_LABELS = {"gemma4:e2b": "E2B", "gemma4:latest": "E4B", "gemma4:26b": "26B-MoE"}
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


def chat(model, prompt, system=None, max_tokens=1024, timeout=180):
    """Call Ollama /api/chat (non-streaming) and return response text + metadata."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"num_predict": max_tokens},
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        text = data.get("message", {}).get("content", "")
        return {
            "text": text,
            "eval_count": data.get("eval_count", 0),
            "eval_duration": data.get("eval_duration", 0),
            "prompt_eval_count": data.get("prompt_eval_count", 0),
            "total_duration": data.get("total_duration", 0),
        }
    except Exception as e:
        return {"text": "", "error": str(e)}


def preload(model):
    chat(model, "hi", max_tokens=1)
    time.sleep(2)


def unload(model):
    body = json.dumps({"model": model, "prompt": "", "keep_alive": 0}).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate", data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
    except Exception:
        pass
    time.sleep(3)


# ---- All test prompts (same as run_eval.py) ----

ALL_TESTS = {
    "coding_generation": [
        {"id": "code_1_fizzbuzz", "prompt": "Write a Python function `custom_fizzbuzz(n, divisors)` that takes an integer n and a dict mapping divisors to words. For numbers 1 to n, if divisible by a key, append that word. Print the combined word or the number. Example: custom_fizzbuzz(15, {3: 'Fizz', 5: 'Buzz'}) prints standard FizzBuzz. Return None. Only output the function, no explanation.", "check": "def"},
        {"id": "code_2_trie", "prompt": "Implement a Trie class in Python with methods: insert(word), search(word) -> bool, starts_with(prefix) -> bool. Only output the class, no explanation.", "check": "class Trie"},
        {"id": "code_3_flatten_json", "prompt": "Write a Python function `flatten_json(obj, prefix='')` that takes a nested dict and returns a flat dict with dot-notation keys. Example: {'a': {'b': 1, 'c': {'d': 2}}} -> {'a.b': 1, 'a.c.d': 2}. Handle lists by using index as key (e.g., 'a.0'). Only output the function.", "check": "def flatten"},
        {"id": "code_4_rotated_search", "prompt": "Write a Python function `search_rotated(nums, target)` that searches for target in a rotated sorted array and returns its index, or -1 if not found. Must be O(log n). Only output the function.", "check": "def search_rotated"},
        {"id": "code_5_lru_cache", "prompt": "Implement an LRU cache in Python as a class `LRUCache` with `__init__(self, capacity)`, `get(self, key) -> int` (returns -1 if not found), and `put(self, key, value)`. Both operations must be O(1). Only output the class.", "check": "class LRU"},
    ],
    "bug_detection": [
        {"id": "bug_1_offbyone", "prompt": "Find the bug in this binary search and fix it:\n\n```python\ndef binary_search(arr, target):\n    left, right = 0, len(arr)\n    while left < right:\n        mid = (left + right) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            left = mid\n        else:\n            right = mid\n    return -1\n```\n\nExplain the bug and provide the corrected code.", "check": "left = mid + 1"},
        {"id": "bug_2_async", "prompt": "Find the bug in this Python async code:\n\n```python\nimport asyncio\n\ncounter = 0\n\nasync def increment():\n    global counter\n    temp = counter\n    await asyncio.sleep(0.01)\n    counter = temp + 1\n\nasync def main():\n    tasks = [increment() for _ in range(100)]\n    await asyncio.gather(*tasks)\n    print(f\"Counter: {counter}\")  # Expected: 100\n\nasyncio.run(main())\n```\n\nExplain the bug and provide a fix.", "check": "lock"},
        {"id": "bug_3_sqli", "prompt": "Find the security vulnerability in this code and fix it:\n\n```python\nimport sqlite3\n\ndef get_user(username):\n    conn = sqlite3.connect('users.db')\n    cursor = conn.cursor()\n    query = f\"SELECT * FROM users WHERE username = '{username}'\"\n    cursor.execute(query)\n    return cursor.fetchone()\n```\n\nExplain the vulnerability and provide a fix.", "check": "?"},
    ],
    "math": [
        {"id": "math_1_system", "prompt": "Solve the system of equations: 2x + 3y - z = 1, x - y + 2z = 5, 3x + y + z = 8. Show your work and give the values of x, y, z.", "answer": "x = 2"},
        {"id": "math_2_compound", "prompt": "An investment of $10,000 earns 5% annually for the first 3 years, then 8% annually for the next 2 years, all compounded annually. What is the final value? Show your calculation.", "answer": "13891"},
        {"id": "math_3_proof", "prompt": "Prove that the sum of the first n odd numbers equals n^2. Write a clear mathematical proof.", "check": "induction"},
        {"id": "math_4_combinatorics", "prompt": "In a 5x5 grid, how many shortest paths are there from the top-left corner to the bottom-right corner if you can only move right or down? One cell at position (2,2) is blocked (0-indexed). Show your work.", "answer": "96"},
        {"id": "math_5_bayes", "prompt": "A medical test has 95% sensitivity and 90% specificity. The disease prevalence is 1%. If a person tests positive, what is the probability they actually have the disease? Show the Bayesian calculation.", "answer": "8.8"},
    ],
    "business": [
        {"id": "biz_1_pnl", "prompt": "Analyze this simplified P&L and identify the 3 biggest cost drivers:\n\nRevenue: $2,400,000\nCOGS: $960,000\nGross Profit: $1,440,000\nSales & Marketing: $720,000\nR&D: $480,000\nG&A: $180,000\nDepreciation: $60,000\nOperating Income: $0\n\nWhat are the 3 largest cost items, their % of revenue, and what does this tell you about the business?"},
        {"id": "biz_2_unit_economics", "prompt": "A SaaS company has: CAC = $500, Monthly subscription = $50, Gross margin = 80%, Monthly churn = 3%. Calculate the LTV, LTV:CAC ratio, and months to payback. Is this business viable? Why or why not?"},
        {"id": "biz_3_pricing", "prompt": "You're launching a B2B project management tool. Competitors charge $10-30/user/month. You have a unique AI feature that automates task assignment. Your COGS is $3/user/month. Propose a pricing strategy with 3 tiers, justify each price point, and explain your positioning."},
        {"id": "biz_4_acquisition", "prompt": "A company wants to acquire a target for $50M. The target has: Revenue $12M (growing 20% YoY), EBITDA $2M, 50 employees, 3 key customers representing 60% of revenue, and a pending patent lawsuit. Identify the top 5 risks in this deal and rate each as high/medium/low with justification."},
    ],
    "science": [
        {"id": "sci_1_crispr", "prompt": "Explain the molecular mechanism of CRISPR-Cas9 gene editing in 150-200 words. Include: the role of guide RNA, how Cas9 creates double-strand breaks, and the two main repair pathways (NHEJ and HDR)."},
        {"id": "sci_2_experiment", "prompt": "Given this experimental data, identify the independent variable, dependent variable, and suggest a proper control:\n\nExperiment: Researchers tested whether caffeine affects reaction time.\nGroup A (n=30): Given 200mg caffeine, average reaction time 245ms (SD=32)\nGroup B (n=30): Given 400mg caffeine, average reaction time 218ms (SD=28)\nGroup C (n=30): Given 600mg caffeine, average reaction time 231ms (SD=45)\n\nWhat are the IV, DV, and what control is missing? What confound should they worry about?"},
        {"id": "sci_3_antibiotic", "prompt": "Explain why antibiotic resistance evolves faster in hospitals than in the general community. Reference at least 3 specific evolutionary/ecological mechanisms."},
        {"id": "sci_4_carbon", "prompt": "Describe the carbon cycle including at least 4 major reservoirs and 4 flux pathways. Then identify 2 specific human activities that disrupt it and quantify their approximate impact in gigatons of CO2 per year."},
    ],
    "psychology": [
        {"id": "psych_1_biases", "prompt": "Describe 3 specific cognitive biases that affect investment decisions. For each, provide: (a) the formal name, (b) the mechanism, (c) a concrete example in investing, and (d) a debiasing strategy."},
        {"id": "psych_2_morale", "prompt": "A manager's team of 12 has low morale after layoffs reduced the company from 200 to 140 employees. Propose an evidence-based intervention plan. Cite at least 2 specific psychological frameworks or theories (by name) and explain how each applies."},
        {"id": "psych_3_memory", "prompt": "Three witnesses saw a car accident. Witness A (bystander, interviewed 1 hour later) says the car was blue and going fast. Witness B (involved driver, interviewed 3 days later) says the car was green and going the speed limit. Witness C (bystander, interviewed 1 hour later but was shown a news report first) says the car was blue-green and speeding. Explain why their memories diverge, naming specific memory phenomena, and state which account is likely most reliable and why."},
    ],
    "tool_use": [
        {"id": "tool_1_simple", "system": "You have access to the following function: get_weather(city: string) -> Returns current weather for a city. When you need to call a function, respond with a JSON object with 'name' and 'arguments' keys.", "prompt": "What's the weather in Tokyo?", "check": "get_weather"},
        {"id": "tool_2_multi", "system": "You have access to: create_event(title: string, date: string, time: string, attendees: list[string]) and send_email(to: string, subject: string, body: string). When you need to call functions, respond with a JSON array of objects with 'name' and 'arguments' keys.", "prompt": "Book a meeting called 'Project Sync' with Alice for tomorrow at 3pm and email her the invite.", "check": "create_event"},
        {"id": "tool_3_chained", "system": "You have access to: web_search(query: string) -> Returns search results, and summarize(text: string) -> Returns summary. When you need to call functions, respond with JSON objects with 'name' and 'arguments' keys.", "prompt": "Search for Python tutorials and summarize the top 3 results.", "check": "web_search"},
        {"id": "tool_4_no_tool", "system": "You have access to: get_weather(city: string) and send_email(to: string, subject: string, body: string). Only call a function if it is relevant. If no function is needed, respond normally with text.", "prompt": "What is 2 + 2?", "check_absent": "get_weather"},
    ],
    "instruction_following": [
        {"id": "inst_1_bullets", "prompt": "Respond in exactly 3 bullet points about the benefits of exercise. Use '- ' for each bullet."},
        {"id": "inst_2_json", "prompt": "Answer in valid JSON format with exactly these keys: \"name\", \"age\", \"city\". Make up a person. Output ONLY the JSON, nothing else."},
        {"id": "inst_3_wordcount", "prompt": "Write exactly 50 words about artificial intelligence. Count carefully. Output only the 50 words, nothing else."},
        {"id": "inst_4_forbidden", "prompt": "Explain what AI is without using the word 'artificial'. Do not use the word 'artificial' anywhere in your response."},
        {"id": "inst_5_spanish", "prompt": "Respond only in Spanish: What are the three primary colors?"},
    ],
    "factual_accuracy": [
        {"id": "fact_1", "prompt": "What year was the Universal Declaration of Human Rights adopted? Answer with just the year, nothing else.", "answer": "1948"},
        {"id": "fact_2", "prompt": "What is the chemical formula for sulfuric acid? Answer with just the formula, nothing else.", "answer": "H2SO4"},
        {"id": "fact_3", "prompt": "Who wrote 'One Hundred Years of Solitude'? Answer with just the author's full name, nothing else.", "answer": "Gabriel"},
        {"id": "fact_4", "prompt": "What is the capital of Kazakhstan? Answer with just the city name, nothing else.", "answer": "Astana"},
        {"id": "fact_5", "prompt": "What is the average-case time complexity of quicksort? Answer with just the Big-O notation, nothing else.", "answer": "n log n"},
        {"id": "fact_6", "prompt": "How many chromosomes do humans have? Answer with just the number, nothing else.", "answer": "46"},
    ],
    "hallucination_resistance": [
        {"id": "halluc_1", "prompt": "Who was the 58th President of the United States? Provide their name and key accomplishments."},
        {"id": "halluc_2", "prompt": "Summarize the paper 'Quantum Entanglement in Avocado Growth Patterns' by Dr. James Smith, published in Nature 2024."},
        {"id": "halluc_3", "prompt": "What is the population of the city of Xanthoria? Provide the latest census figures."},
    ],
    "creativity": [
        {"id": "creative_1", "prompt": "Write a 100-word story with a twist ending about a lighthouse keeper."},
        {"id": "creative_2", "prompt": "Generate 5 startup ideas that combine AI and healthcare. For each, give: name, one-line pitch, target customer, and why it's novel."},
        {"id": "creative_3", "prompt": "Explain blockchain to a 10-year-old using at least 3 creative metaphors. Make it fun and memorable."},
    ],
    "planning": [
        {"id": "plan_1", "prompt": "Plan a 3-day tech conference for 200 attendees with a $50,000 budget. Output a structured plan covering: venue, catering, speakers, AV equipment, marketing, staffing, and contingency. Include a budget breakdown that sums to $50,000."},
        {"id": "plan_2_critical_path", "prompt": "Find the critical path and total project duration for these tasks:\nA: 3 days, no dependencies\nB: 2 days, no dependencies\nC: 4 days, depends on A\nD: 3 days, depends on A\nE: 2 days, depends on B and D\nF: 3 days, depends on C\nG: 2 days, depends on E and F\nH: 1 day, depends on G\n\nWhat is the critical path (list the task letters) and total project time in days?", "answer": "13"},
        {"id": "plan_3_debug", "prompt": "A CI pipeline is failing. Here are 4 log excerpts:\n\nLog 1 (build step): \"WARN: Node 18 is deprecated, using Node 20\"\nLog 2 (test step): \"ERROR: Cannot connect to database at localhost:5432 - Connection refused\"\nLog 3 (test step): \"FAIL: 23 of 150 tests failed, 22 with DatabaseConnectionError\"\nLog 4 (deploy step): \"SKIP: Deploy skipped due to test failures\"\n\nIdentify the root cause and propose a fix sequence."},
    ],
}


def score_test(category, test, text):
    """Auto-score where possible. Returns score 0.0-1.0 or None if needs manual."""
    text_lower = text.lower()

    if category == "coding_generation":
        return 1.0 if test["check"].lower() in text_lower else 0.0
    elif category == "bug_detection":
        return 1.0 if test["check"] in text_lower else 0.0
    elif category == "math":
        if "answer" in test:
            return 1.0 if test["answer"].lower() in text_lower else 0.0
        elif "check" in test:
            return 1.0 if test["check"].lower() in text_lower else 0.0
        return None
    elif category == "factual_accuracy":
        return 1.0 if test["answer"].lower() in text_lower else 0.0
    elif category == "hallucination_resistance":
        refuse_signals = ["don't have", "doesn't exist", "not aware", "no such", "cannot find",
                         "not a real", "fictional", "no record", "hasn't been", "as of my",
                         "i'm not", "i am not", "there is no", "there hasn't", "not real",
                         "i don't", "unable to", "do not have", "can't find", "no president",
                         "fabricated", "made up", "no information", "not exist", "no 58th",
                         "there have only been", "there have been"]
        return 1.0 if any(s in text_lower for s in refuse_signals) else 0.0
    elif category == "instruction_following":
        tid = test["id"]
        if tid == "inst_1_bullets":
            bullets = len([l for l in text.strip().split("\n") if l.strip().startswith(("-", "*", "•"))])
            return 1.0 if bullets == 3 else 0.0
        elif tid == "inst_2_json":
            return 1.0 if all(k in text for k in ['"name"', '"age"', '"city"']) else 0.0
        elif tid == "inst_3_wordcount":
            wc = len(text.split())
            return 1.0 if 40 <= wc <= 60 else 0.0
        elif tid == "inst_4_forbidden":
            return 1.0 if "artificial" not in text_lower else 0.0
        elif tid == "inst_5_spanish":
            return 1.0 if any(w in text_lower for w in ["rojo", "azul", "amarillo", "colores", "primarios"]) else 0.0
    elif category == "tool_use":
        if "check" in test:
            return 1.0 if test["check"].lower() in text_lower else 0.0
        elif "check_absent" in test:
            has_tool = test["check_absent"].lower() in text_lower
            has_answer = "4" in text
            return 1.0 if (not has_tool and has_answer) else 0.0
    return None  # needs manual scoring


def main():
    print("=" * 60)
    print("  GEMMA 4 INTELLIGENCE RE-RUN (via /api/chat)")
    print(f"  {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    all_results = {}

    for model in MODELS:
        label = MODEL_LABELS[model]
        print(f"\n{'='*60}")
        print(f"  {label} ({model})")
        print(f"{'='*60}")

        preload(model)
        model_results = {}

        for category, tests in ALL_TESTS.items():
            print(f"\n  [{label}] {category} ({len(tests)} tests)...")
            cat_results = []

            for test in tests:
                system = test.get("system")
                resp = chat(model, test["prompt"], system=system,
                           max_tokens=1500 if category in ("business", "science", "psychology", "creativity", "planning") else 1024)
                text = resp["text"]
                score = score_test(category, test, text)

                result = {
                    "id": test["id"],
                    "response": text[:3000],
                    "response_length": len(text),
                    "eval_count": resp.get("eval_count", 0),
                    "auto_score": score,
                }
                cat_results.append(result)

                status = f"score={score:.1f}" if score is not None else f"collected ({len(text)} chars)"
                print(f"    {test['id']}: {status}")

            model_results[category] = cat_results

            # Category summary
            scored = [r for r in cat_results if r["auto_score"] is not None]
            if scored:
                avg = sum(r["auto_score"] for r in scored) / len(scored)
                print(f"    >> {category} auto-score: {avg:.2f} ({sum(1 for r in scored if r['auto_score'] > 0)}/{len(scored)} passed)")

        all_results[label] = model_results
        unload(model)

    # Save
    out_path = os.path.join(OUTPUT_DIR, "results_chat.json")
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")

    # Summary table
    print("\n\n" + "=" * 80)
    print("  AUTO-SCORED SUMMARY (via /api/chat)")
    print("=" * 80)
    print(f"\n{'Category':<28} {'E2B':>8} {'E4B':>8} {'26B-MoE':>8}")
    print("-" * 52)

    for category in ALL_TESTS:
        vals = []
        for label in ["E2B", "E4B", "26B-MoE"]:
            items = all_results.get(label, {}).get(category, [])
            scored = [r for r in items if r.get("auto_score") is not None]
            if scored:
                avg = sum(r["auto_score"] for r in scored) / len(scored)
                vals.append(f"{avg:.2f}")
            else:
                vals.append("manual")
        print(f"{category:<28} {vals[0]:>8} {vals[1]:>8} {vals[2]:>8}")

    print("\n'manual' = needs human/LLM judge scoring (responses saved in JSON)")


if __name__ == "__main__":
    main()
