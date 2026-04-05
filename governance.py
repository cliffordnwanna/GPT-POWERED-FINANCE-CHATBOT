"""
governance.py — Responsible AI Governance Layer.

This module is the final gate before a response reaches the user. It:

1. Injects a mandatory disclaimer onto responses that touch investment,
   tax, or legal topics (as flagged by validators.validate_output).

2. Handles the OpenAI content filter result — if the model was blocked
   by the content safety system, a structured safe fallback is returned.

3. Provides a rate limit check per session to prevent API abuse.

The governance layer is deliberately separate from the chatbot and
validators. It encapsulates compliance logic in one place so it can
be audited, updated, and tested independently.

Public interface:
    apply_governance(response_text, finish_reason, session_id)
        -> governed_text: str
    check_rate_limit(session_request_count) -> (allowed: bool, reason: str)
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import Tuple

import config
from validators import validate_output

# ---------------------------------------------------------------------------
# Standard disclaimer text
# ---------------------------------------------------------------------------

_DISCLAIMER = (
    "\n\n---\n"
    "Disclaimer: This response is for educational purposes only. "
    "It does not constitute financial, investment, legal, or tax advice. "
    "Please consult a qualified financial professional before making any financial decisions."
)

# ---------------------------------------------------------------------------
# Content filter fallback
# ---------------------------------------------------------------------------

_CONTENT_FILTER_RESPONSE = (
    "This response was blocked by the content safety system. "
    "Please rephrase your question and try again. "
    "If you have concerns about financial matters, please consult a qualified professional."
)

# ---------------------------------------------------------------------------
# Governance functions
# ---------------------------------------------------------------------------


def apply_governance(
    response_text: str,
    finish_reason: str,
    session_id: str = "unknown",
) -> str:
    """
    Apply governance rules to an LLM response before it reaches the user.

    Steps:
        1. If finish_reason is 'content_filter', return the safe fallback.
        2. Scan the response for output flags using validate_output().
        3. If flags are present, append the standard disclaimer.

    Args:
        response_text:  Raw LLM output text.
        finish_reason:  The finish_reason field from the API response
                        (e.g. 'stop', 'length', 'content_filter').
        session_id:     Used for logging only.

    Returns:
        Governed response text, with disclaimer appended if required.
    """
    from logger import get_logger
    log = get_logger(__name__)

    if finish_reason == "content_filter":
        log.warning(
            "Content filter triggered — returning safe fallback",
            extra={"session_id": session_id},
        )
        return _CONTENT_FILTER_RESPONSE

    needs_disclaimer, flags = validate_output(response_text)

    if needs_disclaimer:
        log.info(
            "Disclaimer injected",
            extra={"session_id": session_id, "flags": flags},
        )
        return response_text + _DISCLAIMER

    return response_text


def check_rate_limit(session_request_count: int) -> Tuple[bool, str]:
    """
    Enforce the per-session request rate limit.

    Args:
        session_request_count: Number of requests made in the current session.

    Returns:
        Tuple of (allowed: bool, reason: str).
        If allowed is True, reason is empty.
        If allowed is False, reason explains the limit.

    The limit is defined by MAX_REQUESTS_PER_SESSION in config. This is a
    simple counter-based limit. In a multi-user production deployment this
    would be backed by a distributed store (e.g. Redis) keyed by user ID.
    For this single-user deployment, Streamlit session state is sufficient.
    """
    if session_request_count >= config.MAX_REQUESTS_PER_SESSION:
        return False, (
            f"You have reached the session limit of "
            f"{config.MAX_REQUESTS_PER_SESSION} requests. "
            "Please start a new session or contact support."
        )
    return True, ""


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    os.environ.setdefault("OPENAI_API_KEY", "test-key")
    os.environ.setdefault("MAX_INPUT_LENGTH", "500")
    os.environ.setdefault("MAX_REQUESTS_PER_SESSION", "20")

    print("=== Governance Layer Tests ===\n")

    # Test 1: Content filter
    result = apply_governance("some blocked text", "content_filter", "test-001")
    assert "blocked by the content safety system" in result
    print("[PASS] Content filter returns safe fallback")

    # Test 2: Clean response — no disclaimer
    clean = "One approach is to review your monthly subscriptions and cancel unused ones."
    result = apply_governance(clean, "stop", "test-001")
    assert "Disclaimer" not in result
    print("[PASS] Clean response passes through without disclaimer")

    # Test 3: Response with investment language — disclaimer added
    investment = "You should buy index funds for long-term growth in your portfolio."
    result = apply_governance(investment, "stop", "test-001")
    assert "Disclaimer" in result
    print("[PASS] Investment language triggers disclaimer injection")

    # Test 4: Rate limit — within limit
    allowed, reason = check_rate_limit(session_request_count=5)
    assert allowed is True
    print("[PASS] Request within limit is allowed")

    # Test 5: Rate limit — at limit
    allowed, reason = check_rate_limit(session_request_count=20)
    assert allowed is False
    assert "session limit" in reason
    print("[PASS] Request at limit is blocked")

    print("\nAll governance tests passed.")
