"""
explainer.py — Explainability Layer.

This module converts raw analysis output into a structured insight object.
The insight object has two purposes:

1. It is passed to the LLM as context. The LLM narrates the findings in natural
   language — it does not perform the analysis itself.

2. It is rendered directly in the UI alongside the LLM response. Users see
   both the raw evidence and the natural language explanation, so they can
   verify the system's reasoning independently of the LLM.

This separation is a core design principle:
    - The analysis pipeline is deterministic and reproducible.
    - The LLM is non-deterministic and used only for explanation.

The system can produce insight objects and display them even if the LLM is
unavailable — the analytical conclusions always stand on their own.
"""

from typing import Dict, List, Any


# ---------------------------------------------------------------------------
# Trend summarisation
# ---------------------------------------------------------------------------

def _summarise_trend(rolling_averages: List[Dict]) -> str:
    """
    Summarise the spending trend from rolling average data.

    Compares the average of the last half of the period against the first half.
    Returns a human-readable trend description.
    """
    if len(rolling_averages) < 4:
        return "insufficient data to determine trend"

    half = len(rolling_averages) // 2
    early = [r["rolling_avg"] for r in rolling_averages[:half]]
    recent = [r["rolling_avg"] for r in rolling_averages[half:]]

    early_mean = sum(early) / len(early)
    recent_mean = sum(recent) / len(recent)

    if early_mean == 0:
        return "insufficient data to determine trend"

    change_pct = ((recent_mean - early_mean) / early_mean) * 100

    if change_pct > 10:
        return f"increasing — average daily spend is up {change_pct:.1f}% in the second half of the period"
    elif change_pct < -10:
        return f"decreasing — average daily spend is down {abs(change_pct):.1f}% in the second half of the period"
    return "stable — no significant change across the period"


# ---------------------------------------------------------------------------
# Primary finding
# ---------------------------------------------------------------------------

def _derive_primary_finding(aggregation: Dict, segmentation: Dict) -> str:
    """Derive the primary finding from the user's own data. No external benchmarks."""
    by_pct = aggregation.get("by_category_pct", {})
    if not by_pct:
        return "No spending data available."

    top_cat = max(by_pct, key=by_pct.get)
    top_pct = by_pct[top_cat]
    return f"{top_cat.capitalize()} is the largest spending category at {top_pct:.1f}% of total spend."


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def build_insight(analysis_results: Dict) -> Dict[str, Any]:
    """
    Convert raw analysis output into a structured insight object.

    Returns:
        finding         : Primary finding as a plain sentence.
        trend           : Human-readable trend description.
        segment         : User segment label.
        segment_reason  : Why this segment was assigned.
        top_category    : Category with the highest spend.
        total_spend     : Total spend across the period.
        date_range      : Period covered by the analysis.
        by_category_pct : {category: pct} breakdown.
        by_category     : {category: amount} breakdown.
        top_transactions: Top 5 largest individual transactions.
    """
    aggregation = analysis_results["aggregation"]
    segmentation = analysis_results["segmentation"]
    rolling_averages = analysis_results["rolling_averages"]
    top_transactions = analysis_results.get("top_transactions", [])

    by_category = aggregation["by_category"]
    top_category = max(by_category, key=by_category.get) if by_category else "unknown"

    return {
        "finding": _derive_primary_finding(aggregation, segmentation),
        "trend": _summarise_trend(rolling_averages),
        "segment": segmentation["segment"],
        "segment_reason": segmentation["reason"],
        "top_category": top_category,
        "total_spend": aggregation["total_spend"],
        "date_range": aggregation["date_range"],
        "by_category_pct": aggregation["by_category_pct"],
        "by_category": aggregation["by_category"],
        "top_transactions": top_transactions,
    }


def format_for_prompt(insight: Dict[str, Any]) -> str:
    """
    Format an insight object as a structured text block for injection into the LLM.
    Goal: total spend → category contributions → behaviour pattern → tailored insight.
    """
    top_cats = sorted(insight.get("by_category_pct", {}).items(), key=lambda x: -x[1])
    top_cat_lines = "\n".join(
        f"  {cat.capitalize()}: {pct:.1f}%  ({insight.get('by_category', {}).get(cat, 0):,.2f})"
        for cat, pct in top_cats
    )

    top_tx_lines = ""
    for t in insight.get("top_transactions", []):
        top_tx_lines += f"\n  - {t.get('date','')} | {t.get('category','')} | {t.get('amount',0):,.2f}"
        if t.get("description"):
            top_tx_lines += f" | {t.get('description','')}"

    return f"""--- Financial Analysis Summary ---
Period        : {insight['date_range']['start']} to {insight['date_range']['end']}
Total spend   : {insight['total_spend']:,.2f}
Top category  : {insight['top_category'].capitalize()}
User segment  : {insight['segment'].upper()} — {insight['segment_reason']}

Spending by category (% of total):
{top_cat_lines}

Spending trend:
  {insight['trend']}

Largest individual transactions:{top_tx_lines}
--- End of Analysis Summary ---"""


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from analysis import run_full_analysis, SAMPLE_DATA_PATH

    print("Building insight object from sample data...\n")
    results = run_full_analysis(SAMPLE_DATA_PATH)
    insight = build_insight(results)

    print("Structured insight object:")
    print(json.dumps(insight, indent=2, default=str))
    print()
    print("Formatted prompt context:")
    print(format_for_prompt(insight))
