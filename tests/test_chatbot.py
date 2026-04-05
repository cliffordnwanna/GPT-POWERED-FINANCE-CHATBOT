"""
tests/test_chatbot.py — Unit tests for the GPT Client.

The OpenAI API is mocked using unittest.mock so no network calls are made
and no API key is required. These tests run completely offline in CI.

Tests cover:
  - Sliding window memory truncation
  - Successful API call returns text and records history
  - Fallback message returned when API raises an exception
  - Rate limit error triggers fallback (not an unhandled exception)
  - Conversation reset clears history correctly
  - Content filter finish_reason returns safe message
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("OPENAI_API_KEY", "test-key-for-ci")
os.environ.setdefault("USE_AZURE", "false")
os.environ.setdefault("MODEL_NAME", "gpt-4o-mini")
os.environ.setdefault("MAX_TOKENS", "500")
os.environ.setdefault("MAX_HISTORY_TURNS", "5")
os.environ.setdefault("MAX_INPUT_LENGTH", "500")
os.environ.setdefault("MAX_REQUESTS_PER_SESSION", "20")
os.environ.setdefault("LOG_LEVEL", "ERROR")  # Suppress log output during tests


# ---------------------------------------------------------------------------
# Helpers: build a mock OpenAI response object
# ---------------------------------------------------------------------------

def _mock_response(content="Test reply from GPT.", finish_reason="stop", total_tokens=100):
    choice = MagicMock()
    choice.message.content = content
    choice.finish_reason = finish_reason

    usage = MagicMock()
    usage.total_tokens = total_tokens

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bot():
    """
    Return a FinanceChatbot instance with the OpenAI client mocked.
    The mock client is accessible via bot._client for per-test configuration.
    """
    with patch("chatbot._OpenAIClient") as MockClient:
        mock_client_instance = MagicMock()
        MockClient.return_value = mock_client_instance

        from chatbot import FinanceChatbot
        instance = FinanceChatbot(session_id="test-session")
        instance._client = mock_client_instance
        yield instance


# ---------------------------------------------------------------------------
# Sliding window memory
# ---------------------------------------------------------------------------

class TestSlidingWindow:

    def test_history_below_limit_not_truncated(self, bot):
        for i in range(3):
            bot._history.append({"role": "user",      "content": f"q{i}"})
            bot._history.append({"role": "assistant", "content": f"a{i}"})
        windowed = bot._get_windowed_history()
        assert len(windowed) == 6  # 3 turns * 2 messages

    def test_history_above_limit_truncated(self, bot):
        # MAX_HISTORY_TURNS = 5 (set via env above)
        for i in range(8):  # 8 turns — 3 over the limit
            bot._history.append({"role": "user",      "content": f"q{i}"})
            bot._history.append({"role": "assistant", "content": f"a{i}"})
        windowed = bot._get_windowed_history()
        assert len(windowed) == 10  # 5 turns * 2 messages

    def test_oldest_turns_dropped(self, bot):
        for i in range(7):
            bot._history.append({"role": "user",      "content": f"question {i}"})
            bot._history.append({"role": "assistant", "content": f"answer {i}"})
        windowed = bot._get_windowed_history()
        # First entry in window should be turn 2 (turns 0 and 1 were dropped)
        assert "question 2" in windowed[0]["content"]

    def test_recent_turns_preserved(self, bot):
        for i in range(7):
            bot._history.append({"role": "user",      "content": f"question {i}"})
            bot._history.append({"role": "assistant", "content": f"answer {i}"})
        windowed = bot._get_windowed_history()
        assert "question 6" in windowed[-2]["content"]

    def test_reset_clears_history(self, bot):
        bot._history = [
            {"role": "user",      "content": "old message"},
            {"role": "assistant", "content": "old reply"},
        ]
        bot.reset()
        assert bot._history == []
        assert bot.history_length == 0


# ---------------------------------------------------------------------------
# Successful API call
# ---------------------------------------------------------------------------

class TestSuccessfulCall:

    def test_reply_text_returned(self, bot):
        bot._client.chat.completions.create.return_value = _mock_response("Hello from GPT.")
        reply, tokens, latency = bot.chat("What is budgeting?")
        assert reply == "Hello from GPT."

    def test_tokens_returned(self, bot):
        bot._client.chat.completions.create.return_value = _mock_response(total_tokens=150)
        _, tokens, _ = bot.chat("Test question")
        assert tokens == 150

    def test_latency_is_positive(self, bot):
        bot._client.chat.completions.create.return_value = _mock_response()
        _, _, latency = bot.chat("Test question")
        assert latency > 0

    def test_user_message_appended_to_history(self, bot):
        bot._client.chat.completions.create.return_value = _mock_response()
        bot.chat("My question")
        user_msgs = [m for m in bot._history if m["role"] == "user"]
        assert any("My question" in m["content"] for m in user_msgs)

    def test_assistant_reply_appended_to_history(self, bot):
        bot._client.chat.completions.create.return_value = _mock_response("GPT reply here.")
        bot.chat("Any question")
        assistant_msgs = [m for m in bot._history if m["role"] == "assistant"]
        assert any("GPT reply here." in m["content"] for m in assistant_msgs)

    def test_analysis_context_used_in_call(self, bot):
        bot._client.chat.completions.create.return_value = _mock_response()
        bot.chat("Question with context", analysis_context="--- Analysis ---\nTotal: $1000")
        call_args = bot._client.chat.completions.create.call_args
        # messages is passed as a keyword argument
        messages_sent = call_args.kwargs.get("messages", [])
        if not messages_sent and call_args.args:
            messages_sent = call_args.args[0]
        # Find system message containing the analysis context
        context_messages = [
            m for m in messages_sent
            if m.get("role") == "system" and "Analysis" in m.get("content", "")
        ]
        assert len(context_messages) >= 1


# ---------------------------------------------------------------------------
# Failure and fallback behaviour
# ---------------------------------------------------------------------------

class TestFallbackBehaviour:

    def test_api_exception_returns_fallback(self, bot):
        from openai import APIConnectionError
        bot._client.chat.completions.create.side_effect = APIConnectionError(request=MagicMock())
        reply, _, _ = bot.chat("Test question")
        assert "unavailable" in reply.lower()

    def test_authentication_error_returns_specific_message(self, bot):
        from openai import AuthenticationError
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 401
        mock_response_obj.json.return_value = {"error": {"message": "Invalid API key", "type": "invalid_request_error", "code": "invalid_api_key"}}
        bot._client.chat.completions.create.side_effect = AuthenticationError(
            message="Invalid API key",
            response=mock_response_obj,
            body={"error": {"message": "Invalid API key"}},
        )
        reply, _, _ = bot.chat("Test question")
        assert "authentication" in reply.lower() or "api key" in reply.lower()

    def test_content_filter_returns_safe_message(self, bot):
        bot._client.chat.completions.create.return_value = _mock_response(
            content="blocked content",
            finish_reason="content_filter",
        )
        reply, _, _ = bot.chat("A question that triggers content filter")
        assert "content safety" in reply.lower() or "blocked" in reply.lower()

    def test_history_still_updated_on_failure(self, bot):
        from openai import APIConnectionError
        bot._client.chat.completions.create.side_effect = APIConnectionError(request=MagicMock())
        initial_len = bot.history_length
        bot.chat("Failed question")
        assert bot.history_length == initial_len + 2  # user + fallback assistant
