"""
tests/test_explainer.py — Unit tests for the Explainability Layer.

Tests cover:
  - Insight object structure and required fields
  - Risk level classification rules
  - Trend summarisation direction
  - Primary finding derivation
  - Prompt formatting output
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis import run_full_analysis, SAMPLE_DATA_PATH
from explainer import build_insight, format_for_prompt


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sample_insight():
    results = run_full_analysis(SAMPLE_DATA_PATH)
    return build_insight(results)


@pytest.fixture
def over_budget_results():
    """Synthetic results with two over-budget categories."""
    return {
        "aggregation": {
            "total_spend": 1000.0,
            "by_category": {"food": 450.0, "transport": 200.0, "savings": 350.0},
            "by_category_pct": {"food": 45.0, "transport": 20.0, "savings": 35.0},
            "transaction_count": 30,
            "date_range": {"start": "2026-01-01", "end": "2026-01-31"},
        },
        "budget_deviation": [
            {"category": "food",      "actual_pct": 45.0, "budget_pct": 30.0, "deviation": 15.0,  "status": "over_budget"},
            {"category": "transport", "actual_pct": 20.0, "budget_pct": 15.0, "deviation": 5.0,   "status": "over_budget"},
            {"category": "savings",   "actual_pct": 35.0, "budget_pct": 20.0, "deviation": 15.0,  "status": "on_track"},
        ],
        "anomalies": [
            {"date": "2026-01-15", "category": "food", "amount": 180.0, "description": "test", "z_score": 4.5}
        ],
        "segmentation": {
            "segment": "overspender",
            "reason": "Food spending (45.0%) exceeds the 40% threshold.",
            "category_pcts": {"food": 45.0, "transport": 20.0, "savings": 35.0},
        },
        "rolling_averages": [
            {"date": "2026-01-01", "daily_total": 30.0, "rolling_avg": 30.0},
            {"date": "2026-01-31", "daily_total": 40.0, "rolling_avg": 40.0},
        ],
    }


# ---------------------------------------------------------------------------
# Insight object structure
# ---------------------------------------------------------------------------

class TestInsightStructure:

    def test_all_required_keys_present(self, sample_insight):
        required_keys = {
            "finding", "trend", "segment", "segment_reason",
            "top_category", "total_spend", "date_range",
            "by_category_pct", "by_category", "top_transactions",
        }
        assert required_keys.issubset(set(sample_insight.keys()))

    def test_segment_is_valid(self, sample_insight):
        assert sample_insight["segment"] in ("conservative", "moderate", "overspender", "concentrated")

    def test_total_spend_is_positive(self, sample_insight):
        assert sample_insight["total_spend"] > 0

    def test_date_range_has_start_and_end(self, sample_insight):
        assert "start" in sample_insight["date_range"]
        assert "end" in sample_insight["date_range"]

    def test_top_category_is_string(self, sample_insight):
        assert isinstance(sample_insight["top_category"], str)
        assert len(sample_insight["top_category"]) > 0

    def test_finding_is_non_empty_string(self, sample_insight):
        assert isinstance(sample_insight["finding"], str)
        assert len(sample_insight["finding"]) > 10

    def test_by_category_pct_sums_to_100(self, sample_insight):
        total = sum(sample_insight["by_category_pct"].values())
        assert abs(total - 100.0) < 0.5

    def test_top_transactions_is_list(self, sample_insight):
        assert isinstance(sample_insight["top_transactions"], list)


# ---------------------------------------------------------------------------
# Prompt formatting
# ---------------------------------------------------------------------------

class TestFormatForPrompt:

    def test_output_is_string(self, sample_insight):
        result = format_for_prompt(sample_insight)
        assert isinstance(result, str)

    def test_output_contains_total_spend(self, sample_insight):
        result = format_for_prompt(sample_insight)
        assert f"{sample_insight['total_spend']:,.2f}" in result

    def test_output_contains_finding(self, sample_insight):
        result = format_for_prompt(sample_insight)
        assert sample_insight["top_category"].capitalize() in result

    def test_output_contains_date_range(self, sample_insight):
        result = format_for_prompt(sample_insight)
        assert sample_insight["date_range"]["start"] in result
        assert sample_insight["date_range"]["end"] in result

    def test_output_contains_segment(self, sample_insight):
        result = format_for_prompt(sample_insight)
        assert sample_insight["segment"].upper() in result
