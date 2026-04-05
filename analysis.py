"""
analysis.py — Financial Analysis Engine.

This module is the data science layer of the Finance Intelligence System.
It is entirely independent of the LLM. The functions here are deterministic
and reproducible — the same input always produces the same output.

The LLM receives the structured output of this module as context. It does not
receive raw user data. This separation is a deliberate architectural decision:
computation is separated from explanation.

Pipeline:
    load_transactions()
        -> validate_schema()
        -> aggregate_spending()
        -> detect_budget_deviation()
        -> compute_rolling_averages()
        -> detect_anomalies()
        -> segment_user()

All public functions accept a pandas DataFrame with columns:
    date (str or datetime), category (str), amount (float), description (str)
"""

import os
from typing import Dict, List

import pandas as pd

REQUIRED_COLUMNS = {"date", "amount", "category"}
SAMPLE_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "sample_transactions.csv")

# ---------------------------------------------------------------------------
# Category alias map — normalises common variations to a canonical name.
# Categories not in this map are kept as-is (lowercased + stripped).
# ---------------------------------------------------------------------------
_CATEGORY_ALIASES: Dict[str, str] = {
    # food / eating
    "food": "food", "groceries": "food", "grocery": "food", "supermarket": "food",
    "eating out": "food", "dining": "food", "dining out": "food", "restaurant": "food",
    "restaurants": "food", "takeaway": "food", "takeout": "food", "meals": "food",
    "cafe": "food", "coffee": "food", "lunch": "food", "breakfast": "food", "dinner": "food",
    # transport
    "transport": "transport", "transportation": "transport", "travel": "transport",
    "commute": "transport", "car": "transport", "fuel": "transport", "petrol": "transport",
    "gas station": "transport", "taxi": "transport", "uber": "transport", "lyft": "transport",
    "bus": "transport", "train": "transport", "rail": "transport", "tube": "transport",
    "metro": "transport", "parking": "transport", "flight": "transport", "flights": "transport",
    # utilities
    "utilities": "utilities", "utility": "utilities", "bills": "utilities", "bill": "utilities",
    "electric": "utilities", "electricity": "utilities", "gas": "utilities", "water": "utilities",
    "internet": "utilities", "broadband": "utilities", "phone": "utilities", "mobile": "utilities",
    "council tax": "utilities", "rent": "utilities",
    # entertainment
    "entertainment": "entertainment", "fun": "entertainment", "leisure": "entertainment",
    "hobbies": "entertainment", "hobby": "entertainment", "subscription": "entertainment",
    "subscriptions": "entertainment", "streaming": "entertainment", "movies": "entertainment",
    "cinema": "entertainment", "theatre": "entertainment", "theater": "entertainment",
    "games": "entertainment", "gaming": "entertainment", "sport": "entertainment",
    "sports": "entertainment", "gym": "health",
    # health
    "health": "health", "medical": "health", "healthcare": "health", "pharmacy": "health",
    "chemist": "health", "doctor": "health", "dentist": "health", "optical": "health",
    "fitness": "health", "wellbeing": "health", "wellness": "health", "vitamins": "health",
    # savings / investment
    "savings": "savings", "saving": "savings", "save": "savings",
    "investment": "savings", "investments": "savings", "pension": "savings",
    "isa": "savings", "stocks": "savings", "shares": "savings",
    # shopping
    "shopping": "shopping", "clothes": "shopping", "clothing": "shopping",
    "fashion": "shopping", "shoes": "shopping", "accessories": "shopping",
    "amazon": "shopping", "online shopping": "shopping",
    # education
    "education": "education", "school": "education", "tuition": "education",
    "courses": "education", "course": "education", "books": "education",
    "training": "education", "learning": "education",
    # personal care
    "personal care": "personal care", "beauty": "personal care", "haircut": "personal care",
    "hair": "personal care", "salon": "personal care", "spa": "personal care",
}


def _normalise_category(raw: str) -> str:
    """Normalise a category string to its canonical form.

    Only applies exact matches after lowercasing and stripping whitespace.
    If the value is not in the alias table, it is kept exactly as-is
    (lowercased + stripped) so the user's own labels are preserved.
    """
    cleaned = raw.lower().strip()
    return _CATEGORY_ALIASES.get(cleaned, cleaned)


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def validate_schema(df: pd.DataFrame) -> None:
    """
    Validate that the DataFrame contains the required columns.

    Raises:
        ValueError: if any required column is missing.

    This runs before any analysis to ensure data integrity. It is the data
    engineering equivalent of a contract — the pipeline fails fast with a
    clear error rather than producing silent incorrect results.
    """
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required column(s): {', '.join(sorted(missing))}. "
            f"Expected: {', '.join(sorted(REQUIRED_COLUMNS))}."
        )


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_transactions(filepath: str) -> pd.DataFrame:
    """
    Load a transaction CSV file and return a validated, typed DataFrame.

    Args:
        filepath: Absolute or relative path to the CSV file.

    Returns:
        DataFrame with columns: date (datetime64), category (str),
        amount (float64), description (str).

    Raises:
        FileNotFoundError: if the file does not exist.
        ValueError: if required columns are missing.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Transaction file not found: {filepath}")

    df = pd.read_csv(filepath)
    validate_schema(df)

    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = df["amount"].astype(float)
    df["category"] = df["category"].astype(str).apply(_normalise_category)

    return df


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate_spending(df: pd.DataFrame) -> Dict:
    """
    Compute total spending and a per-category breakdown.

    Returns a dict with:
        total_spend (float): sum of all transaction amounts.
        by_category (dict): {category: total_amount}.
        by_category_pct (dict): {category: percentage_of_total}.
        transaction_count (int): number of transactions.
        date_range (dict): {start: str, end: str}.
    """
    total = round(df["amount"].sum(), 2)
    by_category = (
        df.groupby("category")["amount"]
        .sum()
        .round(2)
        .to_dict()
    )
    by_category_pct = {
        cat: round((amt / total) * 100, 2) if total > 0 else 0.0
        for cat, amt in by_category.items()
    }

    return {
        "total_spend": total,
        "by_category": by_category,
        "by_category_pct": by_category_pct,
        "transaction_count": len(df),
        "date_range": {
            "start": df["date"].min().strftime("%Y-%m-%d"),
            "end": df["date"].max().strftime("%Y-%m-%d"),
        },
    }





# ---------------------------------------------------------------------------
# Rolling averages
# ---------------------------------------------------------------------------

def compute_rolling_averages(df: pd.DataFrame, window: int = 7) -> pd.DataFrame:
    """
    Compute a rolling average of daily total spending.

    Groups transactions by day, fills missing days with zero, and computes
    a rolling mean over the specified window. This reveals spending trends
    that are not visible in raw totals.

    Args:
        df: Transaction DataFrame.
        window: Rolling window size in days (default: 7).

    Returns:
        DataFrame with columns: date, daily_total, rolling_avg.
    """
    daily = (
        df.groupby(df["date"].dt.date)["amount"]
        .sum()
        .reset_index()
    )
    daily.columns = ["date", "daily_total"]
    daily["date"] = pd.to_datetime(daily["date"])

    # Fill in missing days so the rolling window is consistent
    full_range = pd.date_range(
        start=daily["date"].min(),
        end=daily["date"].max(),
        freq="D",
    )
    daily = daily.set_index("date").reindex(full_range, fill_value=0.0).reset_index()
    daily.columns = ["date", "daily_total"]

    daily["rolling_avg"] = (
        daily["daily_total"]
        .rolling(window=window, min_periods=1)
        .mean()
        .round(2)
    )

    return daily


# ---------------------------------------------------------------------------
# Notable transactions
# ---------------------------------------------------------------------------

def get_top_transactions(df: pd.DataFrame, n: int = 5) -> List[Dict]:
    """
    Return the n largest individual transactions by amount.

    No statistical threshold — just the top spends ranked by size.
    These are always meaningful to a user regardless of category or frequency.
    """
    top = (
        df.nlargest(n, "amount")[["date", "category", "amount", "description"]]
        .copy()
    )
    top["date"] = top["date"].dt.strftime("%Y-%m-%d")
    return top.to_dict(orient="records")


# ---------------------------------------------------------------------------
# User segmentation
# ---------------------------------------------------------------------------

def segment_user(df: pd.DataFrame) -> Dict:
    """
    Classify the user into a spending segment using their own data only.

    Rules (data-driven, no hardcoded category assumptions):
        concentrated : top category > 50% of total spend
        diversified  : no single category exceeds 25% of total spend
        moderate     : all other cases
    """
    aggregation = aggregate_spending(df)
    pcts = aggregation["by_category_pct"]

    if not pcts:
        return {"segment": "moderate", "reason": "Insufficient data.", "category_pcts": pcts}

    top_cat = max(pcts, key=pcts.get)
    top_pct = pcts[top_cat]

    if top_pct > 50.0:
        segment = "concentrated"
        reason = (
            f"{top_cat.capitalize()} accounts for {top_pct:.1f}% of total spend — "
            "spending is heavily concentrated in one area."
        )
    elif top_pct <= 25.0:
        segment = "diversified"
        reason = (
            f"No single category exceeds 25% of total spend. "
            f"The highest is {top_cat.capitalize()} at {top_pct:.1f}%."
        )
    else:
        segment = "moderate"
        reason = (
            f"{top_cat.capitalize()} is the top category at {top_pct:.1f}% of total spend."
        )

    return {
        "segment": segment,
        "reason": reason,
        "category_pcts": pcts,
    }


# ---------------------------------------------------------------------------
# Complete pipeline runner
# ---------------------------------------------------------------------------

def run_full_analysis(filepath: str) -> Dict:
    """
    Run the complete analysis pipeline on a transaction file.

    Returns:
        Dict containing all analysis results keyed by stage name.
    """
    df = load_transactions(filepath)

    return {
        "aggregation": aggregate_spending(df),
        "top_transactions": get_top_transactions(df),
        "segmentation": segment_user(df),
        "rolling_averages": compute_rolling_averages(df).to_dict(orient="records"),
    }


# ---------------------------------------------------------------------------
# Self-test (run directly to verify the module works)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running analysis on sample dataset...\n")
    results = run_full_analysis(SAMPLE_DATA_PATH)

    agg = results["aggregation"]
    print(f"Date range    : {agg['date_range']['start']} to {agg['date_range']['end']}")
    print(f"Transactions  : {agg['transaction_count']}")
    print(f"Total spend   : ${agg['total_spend']:,.2f}")
    print()

    print("Category breakdown:")
    for cat, pct in sorted(agg["by_category_pct"].items(), key=lambda x: -x[1]):
        amount = agg["by_category"][cat]
        print(f"  {cat:<15} ${amount:>8,.2f}  ({pct:.1f}%)")
    print()

    print("Top transactions:")
    for t in results["top_transactions"]:
        print(f"  {t['date']} | {t['category']:<15} | ${t['amount']:>8.2f} | {t.get('description', '')}")
    print()

    seg = results["segmentation"]
    print(f"User segment  : {seg['segment'].upper()}")
    print(f"Reason        : {seg['reason']}")
