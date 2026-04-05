"""
generate_data.py — Generates a realistic 90-day simulated transaction dataset.

The dataset models a single user's spending across six categories over three months.
Controlled anomalies are injected on specific dates to give the anomaly detector
something real to find. This script is reproducible: the same random seed always
produces the same file.

Run once to produce sample_transactions.csv:
    python data/generate_data.py
"""

import csv
import os
import random
from datetime import date, timedelta

RANDOM_SEED = 42
DAYS = 90
START_DATE = date(2026, 1, 1)
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "sample_transactions.csv")

# ---------------------------------------------------------------------------
# Category configuration
# Each entry: (category_name, daily_mean_spend, daily_std_dev)
# These values model a plausible monthly budget for a single person.
# ---------------------------------------------------------------------------
CATEGORIES = [
    ("food",        45.0,  12.0),
    ("transport",   15.0,   5.0),
    ("utilities",   10.0,   3.0),
    ("entertainment", 8.0,  4.0),
    ("health",       6.0,   3.0),
    ("savings",     30.0,   5.0),
]

# Anomaly injections: (day_offset_from_start, category, anomaly_amount)
# These represent realistic one-off events (e.g. car repair, dining out).
ANOMALIES = [
    (14, "food", 180.0),         # Large dinner or grocery stock-up
    (31, "transport", 220.0),    # Car repair or flight
    (57, "entertainment", 150.0), # Concert or event tickets
    (72, "health", 200.0),       # Dental or specialist visit
]


def generate() -> None:
    random.seed(RANDOM_SEED)
    rows = []

    for day_offset in range(DAYS):
        current_date = START_DATE + timedelta(days=day_offset)

        # Each day has 1–3 transactions across randomly selected categories
        categories_today = random.sample(CATEGORIES, k=random.randint(1, 3))

        for category, mean, std in categories_today:
            amount = round(max(1.0, random.gauss(mean, std)), 2)
            rows.append({
                "date": current_date.isoformat(),
                "category": category,
                "amount": amount,
                "description": f"{category.capitalize()} expense",
            })

    # Inject controlled anomalies
    for day_offset, category, amount in ANOMALIES:
        anomaly_date = START_DATE + timedelta(days=day_offset)
        rows.append({
            "date": anomaly_date.isoformat(),
            "category": category,
            "amount": amount,
            "description": f"{category.capitalize()} anomaly (controlled)",
        })

    # Sort by date for a clean, chronological file
    rows.sort(key=lambda r: r["date"])

    fieldnames = ["date", "category", "amount", "description"]
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} transactions -> {OUTPUT_FILE}")


if __name__ == "__main__":
    generate()
