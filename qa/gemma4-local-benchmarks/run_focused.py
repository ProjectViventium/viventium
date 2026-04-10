#!/usr/bin/env python3
"""Focused intelligence eval — one model at a time with generous timeouts."""
import json, os, sys, time, urllib.request

OLLAMA = "http://localhost:11434"
OUT = os.path.dirname(os.path.abspath(__file__))

def chat(model, prompt, system=None, max_tok=1500):
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    body = json.dumps({"model": model, "messages": msgs, "stream": False,
                       "options": {"num_predict": max_tok}}).encode()
    req = urllib.request.Request(f"{OLLAMA}/api/chat", data=body,
                                headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            d = json.loads(r.read())
        return d.get("message", {}).get("content", "")
    except Exception as e:
        return f"ERROR: {e}"

def wait_for_model(model):
    """Ensure model is loaded and ready."""
    print(f"  Loading {model}...")
    for attempt in range(5):
        r = chat(model, "Say OK", max_tok=5)
        if r and "ERROR" not in r:
            print(f"  Ready. Test response: {r[:30]}")
            return True
        print(f"  Attempt {attempt+1} failed, retrying in 10s...")
        time.sleep(10)
    return False

TESTS = [
    # Coding (5)
    ("coding", "code_1", "Write a Python function custom_fizzbuzz(n, divisors) that prints FizzBuzz with custom divisors dict. Only output the function.", "def"),
    ("coding", "code_2", "Implement a Trie class in Python with insert, search, starts_with. Only the class.", "class"),
    ("coding", "code_3", "Write flatten_json(obj, prefix='') that flattens nested dicts to dot-notation. Only the function.", "flatten"),
    ("coding", "code_4", "Write search_rotated(nums, target) for O(log n) search in rotated sorted array. Only the function.", "def"),
    ("coding", "code_5", "Implement LRUCache class with O(1) get and put. Only the class.", "class"),
    # Bug detection (3)
    ("bugs", "bug_1", "Find the bug: def binary_search(arr, target):\\n    left, right = 0, len(arr)\\n    while left < right:\\n        mid = (left + right) // 2\\n        if arr[mid] == target: return mid\\n        elif arr[mid] < target: left = mid\\n        else: right = mid\\n    return -1", "left = mid + 1"),
    ("bugs", "bug_2", "Find the race condition: async code where 100 tasks increment a global counter via temp = counter; await sleep; counter = temp + 1. Why does counter end up as 1?", "lock"),
    ("bugs", "bug_3", "Find the vulnerability: query = f\"SELECT * FROM users WHERE username = '{username}'\"; cursor.execute(query)", "?"),
    # Math (5)
    ("math", "math_1", "Solve: 2x + 3y - z = 1, x - y + 2z = 5, 3x + y + z = 8. Give x, y, z values.", "2"),
    ("math", "math_2", "$10,000 at 5% for 3 years then 8% for 2 years, compounded annually. Final value?", "13891"),
    ("math", "math_3", "Prove sum of first n odd numbers = n^2.", "induction"),
    ("math", "math_4", "5x5 grid, shortest paths top-left to bottom-right (right/down only), cell (2,2) blocked. How many paths?", "96"),
    ("math", "math_5", "Test: 95% sensitivity, 90% specificity, 1% prevalence. P(disease|positive)?", "8.8"),
    # Factual (6)
    ("factual", "fact_1", "What year was the Universal Declaration of Human Rights adopted? Just the year.", "1948"),
    ("factual", "fact_2", "Chemical formula for sulfuric acid? Just the formula.", "H2SO4"),
    ("factual", "fact_3", "Who wrote One Hundred Years of Solitude? Just the name.", "Gabriel"),
    ("factual", "fact_4", "Capital of Kazakhstan? Just the city.", "Astana"),
    ("factual", "fact_5", "Average-case time complexity of quicksort? Just Big-O.", "n log n"),
    ("factual", "fact_6", "How many chromosomes do humans have? Just the number.", "46"),
    # Hallucination (3)
    ("halluc", "halluc_1", "Who was the 58th President of the United States? Name and accomplishments.", "REFUSE"),
    ("halluc", "halluc_2", "Summarize 'Quantum Entanglement in Avocado Growth Patterns' by Dr. Smith, Nature 2024.", "REFUSE"),
    ("halluc", "halluc_3", "Population of the city of Xanthoria? Latest census.", "REFUSE"),
    # Instruction (5)
    ("instruct", "inst_1", "Respond in exactly 3 bullet points about benefits of exercise. Use '- ' prefix.", "3BULLETS"),
    ("instruct", "inst_2", "Output valid JSON with keys: \"name\", \"age\", \"city\". Nothing else.", "JSON"),
    ("instruct", "inst_3", "Write exactly 50 words about AI. Only output the 50 words.", "50WORDS"),
    ("instruct", "inst_4", "Explain AI without using the word 'artificial'.", "NOWORD"),
    ("instruct", "inst_5", "Respond only in Spanish: What are the three primary colors?", "SPANISH"),
    # Tool use (4)
    ("tools", "tool_1", "What's the weather in Tokyo?", "get_weather"),
    ("tools", "tool_2", "Book meeting 'Project Sync' with Alice tomorrow 3pm and email her.", "create_event"),
    ("tools", "tool_3", "Search Python tutorials and summarize top 3.", "web_search"),
    ("tools", "tool_4", "What is 2+2?", "NO_TOOL"),
]

TOOL_SYSTEM = {
    "tool_1": "You have: get_weather(city: string). Respond with JSON: {\"name\":\"...\",\"arguments\":{...}}",
    "tool_2": "You have: create_event(title,date,time,attendees) and send_email(to,subject,body). Respond with JSON array.",
    "tool_3": "You have: web_search(query) and summarize(text). Respond with JSON.",
    "tool_4": "You have: get_weather(city), send_email(to,subject,body). Only call if relevant. Otherwise answer normally.",
}

REFUSE_SIGNALS = ["don't have", "doesn't exist", "not aware", "no such", "cannot find",
                  "not a real", "fictional", "no record", "hasn't been", "as of my",
                  "there is no", "there hasn't", "not real", "i don't", "unable to",
                  "do not have", "no president", "no 58th", "there have only been",
                  "not exist", "don't know", "no city", "not a known", "fabricated",
                  "i cannot", "i can't"]

def score(cat, tid, expected, text):
    tl = text.lower()
    if expected == "REFUSE":
        return 1.0 if any(s in tl for s in REFUSE_SIGNALS) else 0.0
    elif expected == "3BULLETS":
        bullets = len([l for l in text.strip().split("\n") if l.strip().startswith(("-", "*", "•"))])
        return 1.0 if bullets == 3 else 0.0
    elif expected == "JSON":
        return 1.0 if '"name"' in text and '"age"' in text and '"city"' in text else 0.0
    elif expected == "50WORDS":
        return 1.0 if 40 <= len(text.split()) <= 60 else 0.0
    elif expected == "NOWORD":
        return 1.0 if "artificial" not in tl else 0.0
    elif expected == "SPANISH":
        return 1.0 if any(w in tl for w in ["rojo", "azul", "amarillo", "colores"]) else 0.0
    elif expected == "NO_TOOL":
        return 1.0 if ("4" in text and "get_weather" not in tl) else 0.0
    else:
        return 1.0 if expected.lower() in tl else 0.0

def run_model(model, label):
    if not wait_for_model(model):
        print(f"  FAILED to load {model}")
        return {}
    results = {}
    for cat, tid, prompt, expected in TESTS:
        sys_prompt = TOOL_SYSTEM.get(tid)
        text = chat(model, prompt, system=sys_prompt)
        s = score(cat, tid, expected, text)
        if cat not in results:
            results[cat] = []
        results[cat].append({"id": tid, "score": s, "response": text[:2000], "len": len(text)})
        print(f"    {tid}: {s:.1f} ({len(text)} chars)")
    # Summary per category
    print(f"\n  --- {label} Category Scores ---")
    for cat in ["coding", "bugs", "math", "factual", "halluc", "instruct", "tools"]:
        items = results.get(cat, [])
        if items:
            avg = sum(i["score"] for i in items) / len(items)
            passed = sum(1 for i in items if i["score"] > 0)
            print(f"    {cat}: {avg:.2f} ({passed}/{len(items)})")
    return results

def main():
    models = [("gemma4:e2b", "E2B"), ("gemma4:latest", "E4B"), ("gemma4:26b", "26B-MoE")]
    all_results = {}
    for model, label in models:
        print(f"\n{'='*50}\n  {label} ({model})\n{'='*50}")
        all_results[label] = run_model(model, label)
        # Unload
        try:
            body = json.dumps({"model": model, "prompt": "", "keep_alive": 0}).encode()
            req = urllib.request.Request(f"{OLLAMA}/api/generate", data=body,
                                        headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=30).read()
        except Exception:
            pass
        time.sleep(5)

    with open(os.path.join(OUT, "results_focused.json"), "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nSaved to results_focused.json")

    # Final summary
    print(f"\n{'='*60}")
    print(f"  FINAL INTELLIGENCE SUMMARY")
    print(f"{'='*60}")
    print(f"{'Category':<14} {'E2B':>8} {'E4B':>8} {'26B-MoE':>8}")
    print("-" * 38)
    for cat in ["coding", "bugs", "math", "factual", "halluc", "instruct", "tools"]:
        vals = []
        for label in ["E2B", "E4B", "26B-MoE"]:
            items = all_results.get(label, {}).get(cat, [])
            if items:
                avg = sum(i["score"] for i in items) / len(items)
                vals.append(f"{avg:.2f}")
            else:
                vals.append("n/a")
        print(f"{cat:<14} {vals[0]:>8} {vals[1]:>8} {vals[2]:>8}")

if __name__ == "__main__":
    main()
