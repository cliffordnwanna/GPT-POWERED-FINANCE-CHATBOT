"""
config.py — Single source of truth for all application configuration.

Values are loaded from (in priority order):
  1. Streamlit secrets (st.secrets) — when deployed on Streamlit Community Cloud
  2. Environment variables / .env file — local development

This follows the 12-Factor App methodology: configuration is separated from
code so the same codebase runs in any environment without modification.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv(override=True)

# ---------------------------------------------------------------------------
# Streamlit secrets bridge
# Read from st.secrets when running on Streamlit Community Cloud.
# Falls back to os.getenv transparently so local dev is unchanged.
# ---------------------------------------------------------------------------

def _get(key: str, default: str = "") -> str:
    """Return value from st.secrets (Streamlit Cloud) or os.environ."""
    try:
        import streamlit as st
        return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        return os.getenv(key, default)

# ---------------------------------------------------------------------------
# OpenAI (standard API)
# ---------------------------------------------------------------------------
OPENAI_API_KEY: str = _get("OPENAI_API_KEY", "")
MODEL_NAME: str = _get("MODEL_NAME", "gpt-4o-mini")

# ---------------------------------------------------------------------------
# Azure OpenAI (optional provider — set USE_AZURE=true to activate)
# ---------------------------------------------------------------------------
USE_AZURE: bool = _get("USE_AZURE", "false").lower() == "true"
AZURE_OPENAI_API_KEY: str = _get("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_ENDPOINT: str = _get("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_DEPLOYMENT: str = _get("AZURE_OPENAI_DEPLOYMENT", "finance-assistant-model")
AZURE_OPENAI_API_VERSION: str = _get("AZURE_OPENAI_API_VERSION", "2024-02-01")

# ---------------------------------------------------------------------------
# Application settings
# ---------------------------------------------------------------------------
MAX_HISTORY_TURNS: int = int(_get("MAX_HISTORY_TURNS", "10"))
MAX_TOKENS: int = int(_get("MAX_TOKENS", "500"))
MAX_INPUT_LENGTH: int = int(_get("MAX_INPUT_LENGTH", "500"))
MAX_REQUESTS_PER_SESSION: int = int(_get("MAX_REQUESTS_PER_SESSION", "20"))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str = _get("LOG_LEVEL", "INFO")


def validate() -> None:
    """
    Validate that required configuration values are present.
    Called at application startup. Exits with a clear error message
    rather than failing later with a cryptic API error.

    On Streamlit Community Cloud: add secrets via the app dashboard.
    Locally: use .env file (see .env.example).
    """
    if USE_AZURE:
        required = {
            "AZURE_OPENAI_API_KEY": AZURE_OPENAI_API_KEY,
            "AZURE_OPENAI_ENDPOINT": AZURE_OPENAI_ENDPOINT,
        }
    else:
        required = {
            "OPENAI_API_KEY": OPENAI_API_KEY,
        }

    missing = [key for key, value in required.items() if not value]
    if missing:
        print(f"[config] ERROR: Missing required environment variables: {', '.join(missing)}")
        print("[config] Copy .env.example to .env and fill in your values.")
        sys.exit(1)


def print_summary() -> None:
    """Print a safe summary of loaded config (no secrets)."""
    provider = "Azure OpenAI" if USE_AZURE else "OpenAI"
    model = AZURE_OPENAI_DEPLOYMENT if USE_AZURE else MODEL_NAME
    print(f"[config] Provider      : {provider}")
    print(f"[config] Model         : {model}")
    print(f"[config] Max tokens    : {MAX_TOKENS}")
    print(f"[config] Max input len : {MAX_INPUT_LENGTH} chars")
    print(f"[config] History turns : {MAX_HISTORY_TURNS}")
    print(f"[config] Session limit : {MAX_REQUESTS_PER_SESSION} requests")
    print(f"[config] Log level     : {LOG_LEVEL}")


if __name__ == "__main__":
    validate()
    print_summary()
