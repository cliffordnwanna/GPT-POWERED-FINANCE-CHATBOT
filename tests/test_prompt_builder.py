"""
tests/test_prompt_builder.py — Unit tests for Prompt Construction.

Tests cover:
  - System prompt content and governance constraints
  - Message list structure (order, roles)
  - Analysis context injection
  - Conversation history inclusion
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prompt_builder import build_system_prompt, build_chat_messages


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

class TestBuildSystemPrompt:

    def test_returns_string(self):
        assert isinstance(build_system_prompt(), str)

    def test_not_empty(self):
        assert len(build_system_prompt()) > 0

    def test_contains_governance_constraints(self):
        assert "governance" in build_system_prompt().lower()

    def test_contains_privacy_constraint(self):
        assert "privacy" in build_system_prompt().lower() or "personal" in build_system_prompt().lower()

    def test_contains_no_legal_advice(self):
        prompt = build_system_prompt().lower()
        assert "legal" in prompt

    def test_contains_no_investment_advice(self):
        prompt = build_system_prompt().lower()
        assert "investment" in prompt

    def test_not_a_financial_advisor_stated(self):
        prompt = build_system_prompt().lower()
        assert "not a financial advisor" in prompt


# ---------------------------------------------------------------------------
# Message assembly — no analysis context
# ---------------------------------------------------------------------------

class TestBuildChatMessagesBasic:

    def test_first_message_is_system(self):
        messages = build_chat_messages("Hello", history=[])
        assert messages[0]["role"] == "system"

    def test_last_message_is_user(self):
        messages = build_chat_messages("Hello", history=[])
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "Hello"

    def test_message_count_no_history(self):
        # System prompt + user message = 2 messages
        messages = build_chat_messages("Hello", history=[])
        assert len(messages) == 2

    def test_history_inserted_before_user_message(self):
        history = [
            {"role": "user",      "content": "first question"},
            {"role": "assistant", "content": "first answer"},
        ]
        messages = build_chat_messages("second question", history=history)
        # Order: system, user(first), assistant(first), user(second)
        assert messages[1]["content"] == "first question"
        assert messages[2]["content"] == "first answer"
        assert messages[-1]["content"] == "second question"

    def test_message_count_with_history(self):
        history = [
            {"role": "user",      "content": "q1"},
            {"role": "assistant", "content": "a1"},
        ]
        messages = build_chat_messages("q2", history=history)
        # System + 2 history + current = 4
        assert len(messages) == 4


# ---------------------------------------------------------------------------
# Message assembly — with analysis context
# ---------------------------------------------------------------------------

class TestBuildChatMessagesWithContext:

    def test_analysis_context_injected_as_second_system_message(self):
        ctx = "--- Financial Analysis Summary ---\nTotal spend: $1,000"
        messages = build_chat_messages("Explain my spending", history=[], analysis_context=ctx)
        # messages[0] = base system prompt, messages[1] = analysis context
        assert messages[1]["role"] == "system"
        assert "Financial Analysis Summary" in messages[1]["content"]

    def test_user_message_still_last_with_context(self):
        ctx = "some context"
        messages = build_chat_messages("My question", history=[], analysis_context=ctx)
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "My question"

    def test_message_count_with_context_no_history(self):
        # System base + analysis context system + user = 3
        messages = build_chat_messages("q", history=[], analysis_context="ctx")
        assert len(messages) == 3

    def test_context_instructs_model_not_to_contradict(self):
        ctx = "analysis data"
        messages = build_chat_messages("q", history=[], analysis_context=ctx)
        context_msg = messages[1]["content"]
        assert "contradict" in context_msg.lower()

    def test_no_context_when_none_passed(self):
        messages = build_chat_messages("q", history=[], analysis_context=None)
        # Only one system message when no context
        system_messages = [m for m in messages if m["role"] == "system"]
        assert len(system_messages) == 1
