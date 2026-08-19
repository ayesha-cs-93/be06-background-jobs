"""
Stage 5: run all eval cases through the endpoint and print the score.
Usage: python evals/run_eval.py
Assumes the API is running locally on port 8000.
"""
import json
import requests

with open("evals/cases.json") as f:
    cases = json.load(f)

correct = 0
failed_cases = []

for i, case in enumerate(cases):
    resp = requests.post("http://localhost:8000/enrich", json=case["input"])
    if resp.status_code != 200:
        failed_cases.append((i, case["input"]["title"], f"HTTP {resp.status_code}"))
        continue

    result = resp.json()
    if result["category"] == case["expected_category"]:
        correct += 1
    else:
        failed_cases.append((i, case["input"]["title"], f"got {result['category']}, expected {case['expected_category']}"))

print(f"\nScore: {correct}/{len(cases)}")
if failed_cases:
    print("\nFailed cases:")
    for idx, title, reason in failed_cases:
        print(f"  [{idx}] {title}: {reason}")
