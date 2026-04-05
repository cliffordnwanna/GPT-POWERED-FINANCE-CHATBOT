"""
logger.py — Structured JSON Logging.

Two log streams are maintained:

1. Application log (logs/app.log)
   General events: startup, errors, API calls, session events.
   Format: one JSON object per line (JSON Lines / NDJSON).

2. Audit log (logs/audit.log)
   Immutable record of every LLM interaction: session ID, timestamp,
   input sent to the LLM, output received. This log is append-only
   by design — nothing is ever overwritten or deleted.

In a production system these logs would be shipped to a centralised
log aggregator (e.g. CloudWatch, Datadog, ELK). For this deployment
they are written to the local filesystem and can be tailed for debugging.

Usage:
    from logger import get_logger, audit
    log = get_logger(__name__)
    log.info("session started", extra={"session_id": sid})
    audit(session_id=sid, user_input="...", assistant_output="...")
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Directory setup — platform-resilient
# Hugging Face Spaces, Azure Container Apps, and other cloud platforms may
# mount the app directory as read-only or restrict writes. We try the app
# directory first, then /tmp/logs, then fall back to stderr-only logging.
# ---------------------------------------------------------------------------

def _resolve_log_dir() -> str:
    """
    Return a writable directory for log files.

    Priority:
      1. logs/ inside the app directory (ideal — persists for the session)
      2. /tmp/logs (always writable on Linux-based cloud platforms)
    """
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs"),
        os.path.join("/tmp", "logs"),
    ]
    for path in candidates:
        try:
            os.makedirs(path, exist_ok=True)
            # Test that we can actually write
            test_file = os.path.join(path, ".write_test")
            with open(test_file, "w") as f:
                f.write("")
            os.remove(test_file)
            return path
        except OSError:
            continue
    return ""   # Empty string signals stderr-only mode


LOG_DIR = _resolve_log_dir()
APP_LOG_PATH = os.path.join(LOG_DIR, "app.log") if LOG_DIR else ""
AUDIT_LOG_PATH = os.path.join(LOG_DIR, "audit.log") if LOG_DIR else ""


# ---------------------------------------------------------------------------
# JSON log formatter
# ---------------------------------------------------------------------------

class JsonFormatter(logging.Formatter):
    """
    Formats each log record as a single JSON object on one line.
    Structured logs are machine-readable and can be queried without parsing.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Merge any extra fields passed via the extra= kwarg
        for key, value in record.__dict__.items():
            if key not in {
                "args", "asctime", "created", "exc_info", "exc_text",
                "filename", "funcName", "id", "levelname", "levelno",
                "lineno", "message", "module", "msecs", "msg", "name",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName",
            }:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload)


# ---------------------------------------------------------------------------
# Logger factory
# ---------------------------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger that writes JSON to both the app log file and stdout.

    Calling this multiple times with the same name returns the same logger
    (Python's logging module guarantees this).
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Already configured

    from config import LOG_LEVEL
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)

    formatter = JsonFormatter()

    # File handler — persists logs (skipped when filesystem is read-only)
    if APP_LOG_PATH:
        try:
            file_handler = logging.FileHandler(APP_LOG_PATH, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except OSError:
            pass   # Fall through to stderr-only

    # Stream handler — visible in terminal / Docker logs
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


# ---------------------------------------------------------------------------
# Audit log (append-only)
# ---------------------------------------------------------------------------

def audit(
    session_id: str,
    user_input: str,
    assistant_output: str,
    tokens_used: int = 0,
    latency_ms: float = 0.0,
) -> None:
    """
    Write an immutable audit record for a single LLM interaction.

    The audit log records every input sent to the LLM and every output
    received. This supports compliance, debugging, and post-hoc review.
    It is separate from the application log so it can be given stricter
    access controls in a production environment.

    Args:
        session_id:        Caller-supplied session identifier.
        user_input:        The exact text sent to the LLM (after validation).
        assistant_output:  The exact text returned by the LLM (before filtering).
        tokens_used:       Total tokens consumed (prompt + completion).
        latency_ms:        Round-trip latency in milliseconds.
    """
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "tokens_used": tokens_used,
        "latency_ms": round(latency_ms, 2),
        "user_input": user_input,
        "assistant_output": assistant_output,
    }
    if AUDIT_LOG_PATH:
        try:
            with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except OSError:
            # Filesystem not writable — fall back to stderr so the record is
            # captured by the platform's container log collector.
            print(json.dumps(record), file=sys.stderr)
    else:
        print(json.dumps(record), file=sys.stderr)
