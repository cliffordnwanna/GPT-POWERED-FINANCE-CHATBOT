"""
metrics.py — Session Observability and Cost Estimation.

Tracks per-session metrics for the Finance Intelligence System:
  - Response latency (milliseconds)
  - Token usage (prompt + completion, per request)
  - Estimated API cost (USD, based on published per-token pricing)
  - Request count and error count

These metrics serve two purposes:
  1. Displayed live in the Streamlit sidebar — so the cost per interaction
     is visible during the demo.
  2. Demonstrate production awareness: a deployable system should expose
     its own health and cost metrics.

In a production deployment these values would be emitted to a centralised
metrics store (e.g. Prometheus, Datadog). For this deployment they are
held in session state and surfaced in the UI.

Public interface:
    SessionMetrics          — dataclass holding all metric state
    record_request(...)     — append one request's stats
    get_summary(metrics)    — return formatted summary dict
    estimate_cost(...)      — calculate USD cost for a request
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dataclasses import dataclass, field
from typing import Dict, List

# ---------------------------------------------------------------------------
# Token pricing (USD per 1,000 tokens — approximate, as of early 2026)
# Update these if OpenAI changes pricing.
# ---------------------------------------------------------------------------

_PRICING: Dict[str, Dict[str, float]] = {
    "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.00060},
    "gpt-4o":      {"prompt": 0.00250, "completion": 0.01000},
    "gpt-4-turbo": {"prompt": 0.01000, "completion": 0.03000},
    "gpt-3.5-turbo": {"prompt": 0.00050, "completion": 0.00150},
}

_DEFAULT_PRICING = {"prompt": 0.00050, "completion": 0.00150}


# ---------------------------------------------------------------------------
# Session metrics container
# ---------------------------------------------------------------------------

@dataclass
class SessionMetrics:
    """
    Holds all metrics for a single Streamlit session.

    One instance is stored in st.session_state so it persists across
    Streamlit re-runs within the same browser session.
    """
    request_count: int = 0
    error_count: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cost_usd: float = 0.0
    latencies_ms: List[float] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Record a completed request
# ---------------------------------------------------------------------------

def record_request(
    metrics: SessionMetrics,
    latency_ms: float,
    prompt_tokens: int,
    completion_tokens: int,
    model: str,
    success: bool = True,
) -> None:
    """
    Append one request's stats to the session metrics object.

    Args:
        metrics:           The SessionMetrics instance to update (mutated in place).
        latency_ms:        Round-trip latency for this request in milliseconds.
        prompt_tokens:     Number of prompt tokens consumed.
        completion_tokens: Number of completion tokens consumed.
        model:             Model identifier string (used for cost lookup).
        success:           False if the request raised an exception or returned
                           a fallback response.
    """
    metrics.request_count += 1
    if not success:
        metrics.error_count += 1

    metrics.total_prompt_tokens += prompt_tokens
    metrics.total_completion_tokens += completion_tokens
    metrics.latencies_ms.append(latency_ms)

    cost = estimate_cost(prompt_tokens, completion_tokens, model)
    metrics.total_cost_usd += cost


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------

def estimate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model: str,
) -> float:
    """
    Estimate the USD cost of a single API call.

    Uses published pricing per 1,000 tokens. Falls back to a default rate
    if the model is not in the pricing table.

    Returns:
        Estimated cost in USD, rounded to 6 decimal places.
    """
    pricing = _PRICING.get(model.lower(), _DEFAULT_PRICING)
    prompt_cost = (prompt_tokens / 1000) * pricing["prompt"]
    completion_cost = (completion_tokens / 1000) * pricing["completion"]
    return round(prompt_cost + completion_cost, 6)


# ---------------------------------------------------------------------------
# Session summary
# ---------------------------------------------------------------------------

def get_summary(metrics: SessionMetrics) -> Dict:
    """
    Return a formatted summary dict for display in the Streamlit sidebar.

    Returns:
        Dict with keys: requests, errors, avg_latency_ms, total_tokens,
        prompt_tokens, completion_tokens, estimated_cost_usd.
    """
    avg_latency = (
        round(sum(metrics.latencies_ms) / len(metrics.latencies_ms), 1)
        if metrics.latencies_ms
        else 0.0
    )
    total_tokens = metrics.total_prompt_tokens + metrics.total_completion_tokens

    return {
        "requests": metrics.request_count,
        "errors": metrics.error_count,
        "avg_latency_ms": avg_latency,
        "total_tokens": total_tokens,
        "prompt_tokens": metrics.total_prompt_tokens,
        "completion_tokens": metrics.total_completion_tokens,
        "estimated_cost_usd": round(metrics.total_cost_usd, 6),
    }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

    print("=== Metrics Module Tests ===\n")

    m = SessionMetrics()

    # Simulate 3 successful requests
    record_request(m, latency_ms=320.0, prompt_tokens=150, completion_tokens=200, model="gpt-4o-mini", success=True)
    record_request(m, latency_ms=410.0, prompt_tokens=200, completion_tokens=250, model="gpt-4o-mini", success=True)
    record_request(m, latency_ms=290.0, prompt_tokens=180, completion_tokens=220, model="gpt-4o-mini", success=True)

    # Simulate 1 failed request
    record_request(m, latency_ms=5050.0, prompt_tokens=0, completion_tokens=0, model="gpt-4o-mini", success=False)

    summary = get_summary(m)
    print(f"Requests         : {summary['requests']}")
    print(f"Errors           : {summary['errors']}")
    print(f"Avg latency      : {summary['avg_latency_ms']} ms")
    print(f"Total tokens     : {summary['total_tokens']}")
    print(f"Prompt tokens    : {summary['prompt_tokens']}")
    print(f"Completion tokens: {summary['completion_tokens']}")
    print(f"Estimated cost   : ${summary['estimated_cost_usd']:.6f} USD")

    assert summary["requests"] == 4
    assert summary["errors"] == 1
    assert summary["avg_latency_ms"] == round((320 + 410 + 290 + 5050) / 4, 1)

    # Test cost estimation directly
    cost = estimate_cost(1000, 1000, "gpt-4o-mini")
    expected = round((1000 / 1000) * 0.00015 + (1000 / 1000) * 0.00060, 6)
    assert abs(cost - expected) < 1e-9, f"Cost mismatch: {cost} vs {expected}"
    print(f"\nCost for 1k+1k tokens (gpt-4o-mini): ${cost:.6f}")
    print("\nAll metrics tests passed.")
