"""
chatbot.py — GPT Client with Sliding Window Memory.

This module manages all LLM interactions. It is the boundary between the
application and the OpenAI API.

Key design decisions:

1. Sliding window memory
   Chat history grows with each turn. If the full history were always sent,
   it would eventually exceed the model's context window and raise a 400 error.
   The sliding window keeps the last MAX_HISTORY_TURNS user/assistant turns
   plus the system prompt(s). Older turns are dropped. The conversation remains
   coherent because recent context is preserved.

2. Retry with exponential backoff
   Transient failures (rate limits, network errors) are retried automatically
   using the tenacity library. The system waits 1s, then 2s, then 4s between
   attempts before giving up. This prevents a single blip from failing the request.

3. Graceful degradation (fallback mode)
   If the LLM is unreachable after all retries, the system does not crash. It
   returns a structured fallback message so the UI can inform the user and display
   the analytical summary. The analytical pipeline always operates independently.

4. Provider-agnostic
   The client initialises as Azure OpenAI or standard OpenAI based on the USE_AZURE
   config flag. No code change is required to switch providers — only config.

Usage:
    from chatbot import FinanceChatbot
    bot = FinanceChatbot()
    reply, tokens, latency = bot.chat("How can I reduce food spending?")
"""

import time
from typing import Dict, List, Optional, Tuple

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

import config
from logger import get_logger, audit
from prompt_builder import build_chat_messages

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Import the correct OpenAI client
# ---------------------------------------------------------------------------

try:
    if config.USE_AZURE:
        from openai import AzureOpenAI as _OpenAIClient
    else:
        from openai import OpenAI as _OpenAIClient
    from openai import (
        RateLimitError,
        AuthenticationError,
        APIConnectionError,
        APIStatusError,
    )
except ImportError as exc:
    raise ImportError(
        "openai package is not installed. Run: pip install openai"
    ) from exc

# ---------------------------------------------------------------------------
# Fallback response used when the LLM is unavailable
# ---------------------------------------------------------------------------

_FALLBACK_MESSAGE = (
    "The AI assistant is currently unavailable. "
    "Your spending analysis is shown above — please review the figures directly. "
    "Try again in a moment, or consult a qualified financial professional for guidance."
)


# ---------------------------------------------------------------------------
# Chatbot class
# ---------------------------------------------------------------------------

class FinanceChatbot:
    """
    Stateful GPT client for the Finance Intelligence System.

    Each instance maintains its own conversation history. For the Streamlit
    app, one instance is stored in st.session_state per browser session,
    so each user has independent history.
    """

    def __init__(self, session_id: Optional[str] = None) -> None:
        self.session_id = session_id or f"session_{int(time.time())}"
        self._history: List[Dict[str, str]] = []  # user/assistant turns only
        self._client = self._build_client()

        log.info(
            "FinanceChatbot initialised",
            extra={
                "session_id": self.session_id,
                "provider": "azure" if config.USE_AZURE else "openai",
                "model": self._model_id,
            },
        )

    # ------------------------------------------------------------------
    # Client initialisation
    # ------------------------------------------------------------------

    def _build_client(self):
        """Initialise the appropriate OpenAI client based on config."""
        if config.USE_AZURE:
            config.validate()
            self._model_id = config.AZURE_OPENAI_DEPLOYMENT
            return _OpenAIClient(
                api_key=config.AZURE_OPENAI_API_KEY,
                api_version=config.AZURE_OPENAI_API_VERSION,
                azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
            )
        else:
            config.validate()
            self._model_id = config.MODEL_NAME
            return _OpenAIClient(api_key=config.OPENAI_API_KEY)

    # ------------------------------------------------------------------
    # Sliding window memory management
    # ------------------------------------------------------------------

    def _get_windowed_history(self) -> List[Dict[str, str]]:
        """
        Return the most recent MAX_HISTORY_TURNS user/assistant pairs.

        Each "turn" is one user message + one assistant message = 2 entries.
        We slice from the end of the history list to keep recent context.
        """
        max_entries = config.MAX_HISTORY_TURNS * 2  # each turn = 2 messages
        return self._history[-max_entries:]

    def reset(self) -> None:
        """Clear conversation history. Used by the 'New Conversation' button."""
        self._history = []
        log.info("Conversation reset", extra={"session_id": self.session_id})

    # ------------------------------------------------------------------
    # API call with retry
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _call_api(self, messages: List[Dict[str, str]]) -> object:
        """
        Call the OpenAI chat completions API.

        Decorated with tenacity retry for RateLimitError and APIConnectionError.
        AuthenticationError is not retried — it will not resolve without a
        configuration fix.
        """
        return self._client.chat.completions.create(
            model=self._model_id,
            messages=messages,
            temperature=0.5,
            max_tokens=config.MAX_TOKENS,
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # Public chat interface
    # ------------------------------------------------------------------

    def chat(
        self,
        user_message: str,
        analysis_context: Optional[str] = None,
    ) -> Tuple[str, int, float]:
        """
        Send a user message and return the assistant reply.

        Args:
            user_message:      Validated user input text.
            analysis_context:  Optional formatted string from
                               explainer.format_for_prompt(). Injected as
                               system context when provided.

        Returns:
            Tuple of (reply_text, total_tokens_used, latency_ms).
            On failure, returns the fallback message with 0 tokens and the
            actual elapsed time.
        """
        messages = build_chat_messages(
            user_message=user_message,
            history=self._get_windowed_history(),
            analysis_context=analysis_context,
        )

        start_time = time.perf_counter()
        tokens_used = 0
        reply = _FALLBACK_MESSAGE

        try:
            response = self._call_api(messages)
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            finish_reason = response.choices[0].finish_reason

            if finish_reason == "content_filter":
                log.warning(
                    "Response blocked by content filter",
                    extra={"session_id": self.session_id},
                )
                reply = (
                    "This response was blocked by the content safety filter. "
                    "Please rephrase your question."
                )
            else:
                reply = response.choices[0].message.content or _FALLBACK_MESSAGE

            tokens_used = response.usage.total_tokens if response.usage else 0

            log.info(
                "API call successful",
                extra={
                    "session_id": self.session_id,
                    "tokens": tokens_used,
                    "latency_ms": round(elapsed_ms, 2),
                    "finish_reason": finish_reason,
                },
            )

        except AuthenticationError as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            log.error(
                "Authentication failed — check API key",
                extra={"session_id": self.session_id, "error": str(exc)},
            )
            reply = (
                "Authentication failed. Please check your API key configuration."
            )

        except (RateLimitError, APIConnectionError, APIStatusError) as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            log.error(
                "API call failed after retries",
                extra={"session_id": self.session_id, "error": str(exc)},
            )
            # reply remains the fallback message

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            log.error(
                "Unexpected error during API call",
                extra={"session_id": self.session_id, "error": str(exc)},
            )
            # reply remains the fallback message

        # Append to history regardless of success/failure so the UI stays consistent
        self._history.append({"role": "user", "content": user_message})
        self._history.append({"role": "assistant", "content": reply})

        # Write audit record
        audit(
            session_id=self.session_id,
            user_input=user_message,
            assistant_output=reply,
            tokens_used=tokens_used,
            latency_ms=elapsed_ms,
        )

        return reply, tokens_used, elapsed_ms

    # ------------------------------------------------------------------
    # Inspection helpers (used by the metrics sidebar)
    # ------------------------------------------------------------------

    @property
    def history_length(self) -> int:
        """Number of stored user/assistant messages (before windowing)."""
        return len(self._history)
