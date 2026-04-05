# Architecture — Finance Intelligence System

## Overview

The Finance Intelligence System is a two-layer architecture where a **deterministic statistical pipeline** and a **non-deterministic LLM** are kept strictly separate. The LLM receives pre-computed analytical facts as structured context — it does not have access to raw transaction data and does not perform calculations.

---

## System Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         BROWSER / USER                              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTPS (Nginx TLS termination)
┌──────────────────────────────▼──────────────────────────────────────┐
│                      STREAMLIT (app.py)                             │
│                                                                     │
│  ┌─────────────────────┐         ┌──────────────────────────────┐  │
│  │  Tab 1: Analyser    │         │  Tab 2: Finance Assistant    │  │
│  │                     │         │                              │  │
│  │  Upload / Sample ──►│─────────┤──► analysis_context         │  │
│  │  Statistical charts │         │  (shared session state)     │  │
│  │  Top 3 categories   │         │                              │  │
│  │  Rolling trend line │         │  Chat input ──► validators  │  │
│  │  AI Explanation btn │         │  ──► governance ──► chatbot │  │
│  └──────────┬──────────┘         └──────────────────────────────┘  │
└─────────────│────────────────────────────────────────────────────── ┘
              │
┌─────────────▼─────────────────────────────────────────────────────┐
│              STATISTICAL PIPELINE  (analysis.py)                  │
│                                                                    │
│   validate_schema()                                                │
│        │                                                           │
│   load_transactions()                                              │
│        │                                                           │
│   aggregate_spending()  ──► by_category, by_category_pct          │
│        │                                                           │
│   get_top_transactions(n=5)  ──► top N rows by amount             │
│        │                                                           │
│   compute_rolling_averages(window=7)  ──► daily + rolling trend   │
│        │                                                           │
│   segment_user()  ──► concentrated | moderate | diversified       │
│                       (data-driven, no hardcoded category rules)   │
└─────────────┬──────────────────────────────────────────────────── ┘
              │
┌─────────────▼──────────────────────────────────────────────────── ┐
│              EXPLAINABILITY LAYER  (explainer.py)                  │
│                                                                    │
│   build_insight(analysis_results)                                  │
│        ├── finding (human-readable primary sentence)              │
│        ├── trend (spending direction over the period)              │
│        ├── segment + segment_reason                                │
│        ├── top_category, top_transactions (top 5 by amount)       │
│        └── date_range, total_spend, by_category, by_category_pct  │
│                                                                    │
│   format_for_prompt(insight)                                       │
│        └── structured text block (injected as LLM system context) │
└─────────────┬──────────────────────────────────────────────────── ┘
              │
┌─────────────▼──────────────────────────────────────────────────── ┐
│              GOVERNANCE GATE  (validators.py + governance.py)      │
│                                                                    │
│  validate_input()                                                  │
│      ├── Empty / whitespace check                                  │
│      ├── Max length enforcement (500 chars default)                │
│      └── detect_prompt_injection() (13 patterns)                  │
│                                                                    │
│  apply_governance()                                                │
│      ├── Content filter finish_reason → safe fallback response    │
│      └── validate_output() → inject disclaimer if flagged         │
│                                                                    │
│  check_rate_limit()  ──► session cap (20 requests default)        │
└─────────────┬──────────────────────────────────────────────────── ┘
              │
┌─────────────▼──────────────────────────────────────────────────── ┐
│              GPT CLIENT  (chatbot.py)                              │
│                                                                    │
│  FinanceChatbot                                                    │
│      ├── _history: List[Dict]  (full in-memory history)           │
│      ├── _get_windowed_history()                                   │
│      │       MAX_HISTORY_TURNS × 2 messages (default 5 turns)     │
│      │       Oldest turns dropped first                            │
│      │                                                             │
│      ├── _call_api(messages)                                       │
│      │       @retry(RateLimitError | APIConnectionError)          │
│      │       wait_exponential(min=1s, max=8s), 3 attempts         │
│      │                                                             │
│      └── chat()                                                    │
│              ├── build_chat_messages() (prompt_builder.py)        │
│              ├── _call_api()                                       │
│              ├── content_filter check                              │
│              ├── AuthenticationError → specific message           │
│              └── All other failures → fallback message            │
│                                                                    │
│  Provider selection (USE_AZURE env var):                           │
│      false → openai.OpenAI(api_key=...)                            │
│      true  → openai.AzureOpenAI(api_key, endpoint, api_version)   │
└─────────────┬──────────────────────────────────────────────────── ┘
              │
┌─────────────▼──────────────────────────────────────────────────── ┐
│              OPENAI API  (external)                                │
│              GPT-4o-mini (default) or any OpenAI chat model       │
└──────────────────────────────────────────────────────────────────  ┘
```

---

## Data Flow — End to End

### Tab 1: Spending Analyser

```
1. User uploads CSV  ──► validate_schema()  ──► load_transactions()
2. run_full_analysis() ──► aggregate_spending, get_top_transactions,
                          compute_rolling_averages, segment_user
3. build_insight()  ──► structured insight dict
4. format_for_prompt()  ──► stored in st.session_state.analysis_context
5. UI renders: 4-metric row, bar chart, donut chart, trend line, top-3 categories table
6. "Analyse with AI" button:
   validate_input(fixed prompt)
   check_rate_limit()
   chatbot.chat(prompt, analysis_context=analysis_context)
   apply_governance(reply, finish_reason)
   Display governed_reply
```

### Tab 2: Finance Assistant

```
1. User types question
2. validate_input()  ──► length + injection check
3. check_rate_limit()
4. chatbot.chat(user_message, analysis_context)
   └── build_chat_messages():
       [system_prompt]
       [analysis_context system message]  ← if analysis has been run
       [windowed history]
       [current user message]
5. OpenAI API response
6. apply_governance()  ──► validate_output() → inject disclaimer if needed
7. Display in chat thread
8. audit() writes to logs/audit.log
```

---

## Prompt Architecture

```
messages = [
  {role: "system",  content: GOVERNANCE_SYSTEM_PROMPT},
  {role: "system",  content: ANALYSIS_CONTEXT},        ← injected when available
  {role: "user",    content: "first question"},
  {role: "assistant", content: "first answer"},
  ... (sliding window of recent turns)
  {role: "user",    content: CURRENT_MESSAGE},
]
```

The base system prompt encodes all governance constraints (no investment advice, no legal advice, no PII, always recommend consulting a professional). The analysis context block instructs the model: *"Do not contradict or ignore these figures."*

---

## Logging Architecture

Two independent JSON-Lines log streams:

| Stream | Path | Purpose | Retention |
|--------|------|---------|-----------|
| App log | `logs/app.log` | INFO/ERROR events, API call metadata | Rotate as needed |
| Audit log | `logs/audit.log` | Every LLM input/output pair, with tokens and latency | Append-only, preserve |

Both use `JsonFormatter` so they can be ingested by any log aggregation system (ELK, CloudWatch, etc.) without parsing.

---

## Security Controls

| Control | Implementation |
|---------|---------------|
| API key not in code | `python-dotenv`, `.env` excluded by `.gitignore` |
| Prompt injection | 13-pattern regex at input layer (`validators.py`) |
| Output scanning | Investment/tax/legal/guarantee phrases flagged |
| Non-root container | `USER appuser` in Dockerfile |
| TLS | Nginx terminates HTTPS; app only speaks HTTP internally |
| Security headers | `X-Frame-Options`, `X-Content-Type-Options`, `X-XSS-Protection` |
| CSRF | `enableXsrfProtection = true` in `.streamlit/config.toml` |
| Rate limiting | Session-level cap; production can add IP-level limits at Nginx |

---

## Segmentation Rules

Explicit, auditable, prioritised:

## Segmentation Rules

Data-driven, no hardcoded category assumptions:

```
if top_category_pct > 50%:
    segment = "concentrated"
elif top_category_pct <= 25%:
    segment = "diversified"
else:
    segment = "moderate"
```

Concentrated takes priority. Every classification includes a `reason` string with the exact percentages used. Rules are based purely on the user's own spend distribution — no external benchmarks.

---

## Category Normalisation

Applies exact case-insensitive matching only. `Savings`, `SAVINGS`, and `savings` all resolve to `savings`. Labels that do not appear in the alias table are kept exactly as the user wrote them — the system does not guess or infer. All detected categories are surfaced to the user in a collapsible panel so they can identify and fix inconsistencies before relying on the analysis.

---

## Configuration Reference

All settings in `.env` (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (required) | OpenAI API key |
| `MODEL_NAME` | `gpt-4o-mini` | Model identifier |
| `USE_AZURE` | `false` | Switch to Azure OpenAI |
| `MAX_HISTORY_TURNS` | `5` | Sliding window size |
| `MAX_TOKENS` | `500` | Max LLM response tokens |
| `MAX_INPUT_LENGTH` | `500` | Max user input characters |
| `MAX_REQUESTS_PER_SESSION` | `20` | Session rate cap |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
