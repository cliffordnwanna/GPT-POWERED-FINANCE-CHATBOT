import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analysis import run_full_analysis, SAMPLE_DATA_PATH
from explainer import build_insight, format_for_prompt
results = run_full_analysis(SAMPLE_DATA_PATH)
insight = build_insight(results)
ctx = format_for_prompt(insight)
print(ctx)
print()
for word in ["budget", "over_budget", "recommended", "$"]:
    if word in ctx.lower():
        print(f"WARN: found banned term: {word}")
    else:
        print(f"OK: no '{word}' in context")
