"""
tests/test_analysis.py — Unit tests for the Financial Analysis Engine.

Tests cover:
  - Schema validation (valid and invalid DataFrames)
  - Spending aggregation correctness
  - Budget deviation status classification
  - Rolling average output shape and values
  - Anomaly detection (known anomalies must be flagged, normal values must not)
  - User segmentation rules (all three segments)
  - Full pipeline smoke test on the sample dataset

All tests are deterministic and offline — no API calls or file I/O beyond
loading the pre-generated sample dataset.
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis import (
    validate_schema,
    aggregate_spending,
    detect_budget_deviation,
    compute_rolling_averages,
    detect_anomalies,
    segment_user,
    run_full_analysis,
    SAMPLE_DATA_PATH,
    DEFAULT_BUDGETS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_df(rows):
    """Build a minimal transaction DataFrame from a list of dicts."""
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = df["amount"].astype(float)
    df["category"] = df["category"].str.lower()
    return df


@pytest.fixture
def simple_df():
    return _make_df([
        {"date": "2026-01-01", "category": "food",      "amount": 50.0},
        {"date": "2026-01-02", "category": "food",      "amount": 60.0},
        {"date": "2026-01-03", "category": "transport", "amount": 20.0},
        {"date": "2026-01-04", "category": "savings",   "amount": 40.0},
        {"date": "2026-01-05", "category": "food",      "amount": 55.0},
    ])


@pytest.fixture
def sample_df():
    return pd.read_csv(SAMPLE_DATA_PATH, parse_dates=["date"])


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class TestValidateSchema:

    def test_valid_schema_passes(self, simple_df):
        """No exception raised for a conformant DataFrame."""
        validate_schema(simple_df)  # Should not raise

    def test_missing_date_column_raises(self):
        df = pd.DataFrame({"amount": [10.0], "category": ["food"]})
        with pytest.raises(ValueError, match="date"):
            validate_schema(df)

    def test_missing_amount_column_raises(self):
        df = pd.DataFrame({"date": ["2026-01-01"], "category": ["food"]})
        with pytest.raises(ValueError, match="amount"):
            validate_schema(df)

    def test_missing_category_column_raises(self):
        df = pd.DataFrame({"date": ["2026-01-01"], "amount": [10.0]})
        with pytest.raises(ValueError, match="category"):
            validate_schema(df)

    def test_multiple_missing_columns_listed(self):
        df = pd.DataFrame({"date": ["2026-01-01"]})
        with pytest.raises(ValueError):
            validate_schema(df)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

class TestAggregateSpending:

    def test_total_spend_is_sum_of_amounts(self, simple_df):
        result = aggregate_spending(simple_df)
        assert result["total_spend"] == pytest.approx(225.0)

    def test_category_totals_are_correct(self, simple_df):
        result = aggregate_spending(simple_df)
        assert result["by_category"]["food"] == pytest.approx(165.0)
        assert result["by_category"]["transport"] == pytest.approx(20.0)
        assert result["by_category"]["savings"] == pytest.approx(40.0)

    def test_category_percentages_sum_to_100(self, simple_df):
        result = aggregate_spending(simple_df)
        total_pct = sum(result["by_category_pct"].values())
        assert total_pct == pytest.approx(100.0, abs=0.1)

    def test_transaction_count_is_correct(self, simple_df):
        result = aggregate_spending(simple_df)
        assert result["transaction_count"] == 5

    def test_date_range_is_correct(self, simple_df):
        result = aggregate_spending(simple_df)
        assert result["date_range"]["start"] == "2026-01-01"
        assert result["date_range"]["end"] == "2026-01-05"


# ---------------------------------------------------------------------------
# Budget deviation
# ---------------------------------------------------------------------------

class TestDetectBudgetDeviation:

    def test_over_budget_status_applied(self):
        # Food at 100% — must be over budget (budget is 30%)
        df = _make_df([{"date": "2026-01-01", "category": "food", "amount": 100.0}])
        result = detect_budget_deviation(df)
        food_entry = next(r for r in result if r["category"] == "food")
        assert food_entry["status"] == "over_budget"

    def test_under_budget_status_applied(self):
        # Only savings present — utilities will be zero, below its 10% budget
        df = _make_df([{"date": "2026-01-01", "category": "savings", "amount": 100.0}])
        result = detect_budget_deviation(df)
        utilities_entry = next(r for r in result if r["category"] == "utilities")
        assert utilities_entry["status"] == "under_budget"

    def test_on_track_within_2pct_tolerance(self):
        # Build a DataFrame where food is exactly 30% — should be on_track
        total = 100.0
        df = _make_df([
            {"date": "2026-01-01", "category": "food",      "amount": 30.0},
            {"date": "2026-01-01", "category": "savings",   "amount": 20.0},
            {"date": "2026-01-01", "category": "transport", "amount": 15.0},
            {"date": "2026-01-01", "category": "utilities", "amount": 10.0},
            {"date": "2026-01-01", "category": "entertainment", "amount": 10.0},
            {"date": "2026-01-01", "category": "health",    "amount": 15.0},
        ])
        result = detect_budget_deviation(df)
        food_entry = next(r for r in result if r["category"] == "food")
        assert food_entry["status"] == "on_track"

    def test_results_sorted_by_deviation_descending(self, simple_df):
        result = detect_budget_deviation(simple_df)
        deviations = [r["deviation"] for r in result]
        assert deviations == sorted(deviations, reverse=True)

    def test_custom_budgets_used(self, simple_df):
        custom = {"food": 80.0}  # Very high budget — food should be under
        result = detect_budget_deviation(simple_df, budgets=custom)
        food_entry = next(r for r in result if r["category"] == "food")
        assert food_entry["status"] == "under_budget"


# ---------------------------------------------------------------------------
# Rolling averages
# ---------------------------------------------------------------------------

class TestComputeRollingAverages:

    def test_output_has_required_columns(self, simple_df):
        result = compute_rolling_averages(simple_df)
        assert "date" in result.columns
        assert "daily_total" in result.columns
        assert "rolling_avg" in result.columns

    def test_date_range_is_complete(self, simple_df):
        # simple_df spans 5 days — result should have 5 rows
        result = compute_rolling_averages(simple_df)
        assert len(result) == 5

    def test_rolling_avg_not_null(self, simple_df):
        result = compute_rolling_averages(simple_df)
        assert result["rolling_avg"].isna().sum() == 0

    def test_rolling_avg_with_window_1_equals_daily(self, simple_df):
        result = compute_rolling_averages(simple_df, window=1)
        # With window=1, rolling avg equals the daily total
        for _, row in result.iterrows():
            assert row["rolling_avg"] == pytest.approx(row["daily_total"])

    def test_custom_window_accepted(self, simple_df):
        result = compute_rolling_averages(simple_df, window=3)
        assert len(result) == 5


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

class TestDetectAnomalies:

    def test_known_anomaly_is_flagged(self):
        # One very large transaction among many normal ones — must be flagged
        rows = [{"date": f"2026-01-{i+1:02d}", "category": "food", "amount": 40.0}
                for i in range(20)]
        rows.append({"date": "2026-01-21", "category": "food", "amount": 500.0})
        df = _make_df(rows)
        anomalies = detect_anomalies(df)
        assert len(anomalies) >= 1
        assert anomalies.iloc[0]["amount"] == 500.0

    def test_anomalies_sorted_by_z_score_descending(self):
        rows = [{"date": f"2026-01-{i+1:02d}", "category": "food", "amount": 40.0}
                for i in range(20)]
        rows.append({"date": "2026-01-21", "category": "food", "amount": 500.0})
        rows.append({"date": "2026-01-22", "category": "food", "amount": 300.0})
        df = _make_df(rows)
        anomalies = detect_anomalies(df)
        z_scores = anomalies["z_score"].tolist()
        assert z_scores == sorted(z_scores, reverse=True)

    def test_no_anomalies_returns_empty_dataframe(self):
        # All identical amounts — std is 0, so no z-scores computed
        rows = [{"date": f"2026-01-{i+1:02d}", "category": "food", "amount": 50.0}
                for i in range(10)]
        df = _make_df(rows)
        anomalies = detect_anomalies(df)
        assert len(anomalies) == 0

    def test_anomaly_result_has_z_score_column(self):
        rows = [{"date": f"2026-01-{i+1:02d}", "category": "food", "amount": 40.0}
                for i in range(20)]
        rows.append({"date": "2026-01-21", "category": "food", "amount": 500.0})
        df = _make_df(rows)
        anomalies = detect_anomalies(df)
        assert "z_score" in anomalies.columns

    def test_z_score_above_threshold_for_flagged(self):
        rows = [{"date": f"2026-01-{i+1:02d}", "category": "food", "amount": 40.0}
                for i in range(20)]
        rows.append({"date": "2026-01-21", "category": "food", "amount": 500.0})
        df = _make_df(rows)
        anomalies = detect_anomalies(df)
        assert all(anomalies["z_score"] >= 2.0)


# ---------------------------------------------------------------------------
# User segmentation
# ---------------------------------------------------------------------------

class TestSegmentUser:

    def test_overspender_when_food_exceeds_40pct(self):
        df = _make_df([
            {"date": "2026-01-01", "category": "food",      "amount": 500.0},
            {"date": "2026-01-01", "category": "transport", "amount": 100.0},
            {"date": "2026-01-01", "category": "savings",   "amount": 100.0},
        ])
        result = segment_user(df)
        # food is 500/700 = 71.4% — above 40% threshold
        assert result["segment"] == "overspender"

    def test_conservative_when_savings_exceeds_30pct(self):
        df = _make_df([
            {"date": "2026-01-01", "category": "food",    "amount": 50.0},
            {"date": "2026-01-01", "category": "savings", "amount": 200.0},
        ])
        result = segment_user(df)
        # savings is 200/250 = 80% — above 30%
        assert result["segment"] == "conservative"

    def test_moderate_when_no_threshold_exceeded(self):
        df = _make_df([
            {"date": "2026-01-01", "category": "food",      "amount": 100.0},
            {"date": "2026-01-01", "category": "transport", "amount": 80.0},
            {"date": "2026-01-01", "category": "savings",   "amount": 50.0},
            {"date": "2026-01-01", "category": "utilities", "amount": 80.0},
        ])
        result = segment_user(df)
        # food is 100/310 = 32% (< 40%), savings is 50/310 = 16% (< 30%)
        assert result["segment"] == "moderate"

    def test_segment_result_contains_reason(self):
        df = _make_df([{"date": "2026-01-01", "category": "food", "amount": 100.0}])
        result = segment_user(df)
        assert "reason" in result
        assert len(result["reason"]) > 0

    def test_overspender_takes_priority_over_conservative(self):
        # Food > 40% AND savings > 30% — overspender rule fires first
        df = _make_df([
            {"date": "2026-01-01", "category": "food",    "amount": 500.0},
            {"date": "2026-01-01", "category": "savings", "amount": 400.0},
        ])
        result = segment_user(df)
        assert result["segment"] == "overspender"


# ---------------------------------------------------------------------------
# Full pipeline smoke test
# ---------------------------------------------------------------------------

class TestRunFullAnalysis:

    def test_smoke_test_on_sample_data(self):
        """Run the complete pipeline on the pre-generated sample dataset."""
        results = run_full_analysis(SAMPLE_DATA_PATH)
        assert "aggregation" in results
        assert "budget_deviation" in results
        assert "anomalies" in results
        assert "segmentation" in results
        assert "rolling_averages" in results

    def test_sample_data_total_spend_is_positive(self):
        results = run_full_analysis(SAMPLE_DATA_PATH)
        assert results["aggregation"]["total_spend"] > 0

    def test_sample_data_anomalies_detected(self):
        """The sample dataset has controlled anomalies — at least one must be found."""
        results = run_full_analysis(SAMPLE_DATA_PATH)
        assert len(results["anomalies"]) >= 1

    def test_missing_file_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            run_full_analysis("/nonexistent/path/transactions.csv")
