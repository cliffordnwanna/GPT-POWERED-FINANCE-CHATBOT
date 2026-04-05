"""
debug_llm.py — Quick LLM diagnostic. Run this directly in the terminal.
Usage: python debug_llm.py
"""
import os
import sys
import time

# Load .env
from dotenv import load_dotenv
load_dotenv(override=True)

api_key = os.getenv("OPENAI_API_KEY", "")
model = os.getenv("MODEL_NAME", "gpt-4o-mini")

print(f"[1] API key loaded : {'YES (' + api_key[:12] + '...)' if api_key else 'NO — MISSING'}")
print(f"[2] Model          : {model}")

if not api_key:
    print("[ERROR] OPENAI_API_KEY is empty. Check your .env file.")
    sys.exit(1)

try:
    from openai import OpenAI
except ImportError:
    print("[ERROR] openai package not installed. Run: pip install openai")
    sys.exit(1)

client = OpenAI(api_key=api_key)

print("[3] Sending test message to OpenAI...")
start = time.perf_counter()

try:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Say hello in one word."}],
        max_tokens=10,
        timeout=20.0,
    )
    elapsed = (time.perf_counter() - start) * 1000
    reply = response.choices[0].message.content
    tokens = response.usage.total_tokens
    print(f"[4] SUCCESS — reply: '{reply}'")
    print(f"    Tokens used : {tokens}")
    print(f"    Latency     : {elapsed:.0f} ms")

except Exception as e:
    elapsed = (time.perf_counter() - start) * 1000
    print(f"[4] FAILED after {elapsed:.0f} ms")
    print(f"    Error type  : {type(e).__name__}")
    print(f"    Error detail: {e}")
