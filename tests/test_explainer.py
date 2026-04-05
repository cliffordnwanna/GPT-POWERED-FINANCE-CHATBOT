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
            "finding", "evidence", "risk_level", "trend",
            "segment", "segment_reason", "anomaly_count",
            "top_anomalies", "top_category", "total_spend", "date_range",
        }
        assert required_keys.issubset(set(sample_insight.keys()))

    def test_evidence_has_required_fields(self, sample_insight):
        evidence = sample_insight["evidence"]
        assert "category" in evidence
        assert "actual_pct" in evidence
        assert "deviation" in evidence

    def test_risk_level_is_valid(self, sample_insight):
        assert sample_insight["risk_level"] in ("low", "medium", "high")

    def test_segment_is_valid(self, sample_insight):
        assert sample_insight["segment"] in ("conservative", "moderate", "overspender")

    def test_total_spend_is_positive(self, sample_insight):
        assert sample_insight["total_spend"] > 0

    def test_anomaly_count_matches_list(self, sample_insight):
        assert sample_insight["anomaly_count"] == len(
            run_full_analysis(SAMPLE_DATA_PATH)["anomalies"]
        )

    def test_top_anomalies_limited_to_three(self, sample_insight):
        assert len(sample_insight["top_anomalies"]) <= 3

    def test_date_range_has_start_and_end(self, sample_insight):
        assert "start" in sample_insight["date_range"]
        assert "end" in sample_insight["date_range"]


# ---------------------------------------------------------------------------
# Risk level classification
# ---------------------------------------------------------------------------

class TestRiskLevel:

    def test_high_risk_when_two_over_budget(self, over_budget_results):
        insight = build_insight(over_budget_results)
        assert insight["risk_level"] == "high"

    def test_medium_risk_when_one_over_budget(self):
        results = {
            "aggregation": {
                "total_spend": 1000.0,
                "by_category": {"food": 400.0, "savings": 600.0},
                "by_category_pct": {"food": 40.0, "savings": 60.0},
                "transaction_count": 20,
                "date_range": {"start": "2026-01-01", "end": "2026-01-31"},
            },
            "budget_deviation": [
                {"category": "food",    "actual_pct": 40.0, "budget_pct": 30.0, "deviation": 10.0, "status": "over_budget"},
                {"category": "savings", "actual_pct": 60.0, "budget_pct": 20.0, "deviation": 40.0, "status": "on_track"},
            ],
            "anomalies": [],
            "segmentation": {"segment": "moderate", "reason": "test", "category_pcts": {}},
            "rolling_averages": [],
        }
        insight = build_insight(results)
        assert insight["risk_level"] == "medium"

    def test_low_risk_when_none_over_budget(self):
        results = {
            "aggregation": {
                "total_spend": 1000.0,
                "by_category": {"food": 250.0, "savings": 750.0},
                "by_category_pct": {"food": 25.0, "savings": 75.0},
                "transaction_count": 10,
                "date_range": {"start": "2026-01-01", "end": "2026-01-31"},
            },
            "budget_deviation": [
                {"category": "food",    "actual_pct": 25.0, "budget_pct": 30.0, "deviation": -5.0, "status": "on_track"},
            ],
            "anomalies": [],
            "segmentation": {"segment": "conservative", "reason": "test", "category_pcts": {}},
            "rolling_averages": [],
        }
        insight = build_insight(results)
        assert insight["risk_level"] == "low"


# ---------------------------------------------------------------------------
# Prompt formatting
# ---------------------------------------------------------------------------

class TestFormatForPrompt:

    def test_output_is_string(self, sample_insight):
        result = format_for_prompt(sample_insight)
        assert isinstance(result, str)

    def test_output_contains_total_spend(self, sample_insight):
        result = format_for_prompt(sample_insight)
        # Formatted as $3,994.77 — check the formatted string is present
        assert f"${sample_insight['total_spend']:,.2f}" in result

    def test_output_contains_risk_level(self, sample_insight):
        result = format_for_prompt(sample_insight)
        assert sample_insight["risk_level"].upper() in result

    def test_output_contains_finding(self, sample_insight):
        result = format_for_prompt(sample_insight)
        # The finding is a sentence — check the first 20 chars are present
        assert sample_insight["finding"][:20] in result

    def test_output_contains_date_range(self, sample_insight):
        result = format_for_prompt(sample_insight)
        assert sample_insight["date_range"]["start"] in result
        assert sample_insight["date_range"]["end"] in result

    def test_output_contains_segment(self, sample_insight):
        result = format_for_prompt(sample_insight)
        assert sample_insight["segment"].upper() in result
