# Finance Intelligence System — Complete Build Plan

**Project:** GPT-Powered Finance Intelligence System  
**Purpose:** ACS Skills Assessment Portfolio + GitHub Public Project + Live Deployment  
**Target audience for reading this document:** You — before interviews, before assessment submission, and before each build phase.

---

## Final Positioning Statement

When asked what you built, say this exactly:

> "I built a production-grade financial intelligence system that combines a statistical analysis pipeline with LLM reasoning, underpinned by a responsible AI governance layer to ensure safe, explainable, and auditable outputs."

Never say "I built a finance chatbot."

---

## Architecture Overview

```
User Request
     |
     v
Streamlit Web Application (Docker Container)
     |
     v
Input Validation + Prompt Injection Guard   <-- Governance Layer
     |
     v
Financial Analysis Engine
  - Spending aggregation and category breakdown
  - Budget deviation detection
  - Rolling average trend analysis
  - Z-score anomaly detection
  - Rule-based user segmentation
     |
     v
Explainability Layer
  - Structured insight object (evidence + finding)
     |
     v
Prompt Builder
  - Injects structured analysis context into prompt
     |
     v
OpenAI API (provider-agnostic; Azure OpenAI supported)
     |
     v
Output Filtering + Disclaimer Injection     <-- Governance Layer
     |
     v
Response + Metrics Logging + Audit Log
     |
     v
User (Streamlit UI with System Status Panel)
```

---

## Confirmed Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| API Provider | OpenAI API (provider-agnostic) | Faster deployment; designed to switch to Azure OpenAI with one config change |
| Frontend | Streamlit | Production-grade data app framework, no separate frontend needed |
| Deployment | Docker + VPS | Stronger for interviews; demonstrates containerisation and infrastructure knowledge |
| Dataset | Realistic simulated dataset | Improves data science credibility; demonstrates data engineering awareness |
| Memory strategy | Sliding window (last N turns + system prompt) | Prevents context overflow; token-aware |
| Secret management | Environment variables via .env (never committed) | 12-Factor App compliance; production standard |

---

## File Structure (Final)

```
GPT-POWERED-FINANCE-CHATBOT/
|
|-- app.py                          # Streamlit application (two tabs)
|-- chatbot.py                      # GPT client with sliding window memory
|-- analysis.py                     # Financial analysis engine (DS layer)
|-- explainer.py                    # Explainability layer (structured insight output)
|-- prompt_builder.py               # Prompt construction from analysis context
|-- validators.py                   # Input/output validation and injection guard
|-- governance.py                   # Responsible AI: disclaimers, audit log, filtering
|-- metrics.py                      # Response latency, token usage, cost estimation
|-- logger.py                       # Structured JSON logging
|-- config.py                       # Environment variable loading
|
|-- data/
|   |-- generate_data.py            # Script to produce realistic simulated dataset
|   |-- sample_transactions.csv     # Pre-generated dataset (committed to repo)
|
|-- tests/
|   |-- test_analysis.py
|   |-- test_validators.py
|   |-- test_prompt_builder.py
|   |-- test_explainer.py
|   |-- test_chatbot.py
|
|-- .github/
|   |-- workflows/
|       |-- ci.yml                  # GitHub Actions: lint + test on every push
|
|-- finance_chatbot.ipynb           # Cleaned reference notebook (no duplicates)
|-- Dockerfile                      # Non-root user, multi-stage build
|-- docker-compose.yml              # Runtime env injection, port binding
|-- .env.example                    # Safe to commit; documents required vars
|-- .gitignore                      # Excludes .env, __pycache__, logs
|-- requirements.txt                # Pinned dependencies
|-- README.md                       # Professional README (no emojis)
|-- ARCHITECTURE.md                 # System design document
|-- BUILD_PLAN.md                   # This file
```

---

## Phase Breakdown

---

### Phase 1 — Project Foundation

**Goal:** Establish the professional project scaffold before writing any logic.

**Files created:**
- `requirements.txt` — all dependencies with pinned versions
- `.env.example` — documents required environment variables
- `.gitignore` — excludes secrets, cache, logs, virtual environments
- `config.py` — single source of truth for all configuration values

**Notebook fix:**
- Remove duplicate `chat_history` and `ask_gpt()` definitions
- Fix API version from `2023-05-15` to current
- Restructure steps so definitions appear before usage

**What to say in interview:**

> "I separated all configuration from application code using environment variables loaded via python-dotenv, following the 12-Factor App methodology. This allows the same codebase to be deployed to any environment — local, staging, or production — by changing only environment variables."

**Test:** `python config.py` — should print loaded config values without error.

---

### Phase 2 — Financial Analysis Engine (Data Science Layer)

**Goal:** Build the analytical pipeline that processes financial data before any LLM involvement.

**File:** `analysis.py`

**Functions built:**
1. `validate_schema(df)` — enforces required columns (`date`, `amount`, `category`) before analysis runs; raises `ValueError` on missing fields
2. `load_transactions(filepath)` — loads CSV, calls `validate_schema` immediately
3. `aggregate_spending(df)` — total spend, spend by category, percentage split
4. `get_top_transactions(df, n=5)` — returns the top N rows by amount; no statistical inference
5. `compute_rolling_averages(df, window=7)` — rolling spend trend over time
6. `segment_user(df)` — data-driven segmentation based on the user's own spend distribution:
   - `concentrated`: top category exceeds 50% of total spend
   - `diversified`: no single category exceeds 25% of total spend
   - `moderate`: all other cases
   - `moderate`: all other cases

**File:** `data/generate_data.py` — generates 90 days of realistic transactions across 6 categories with controlled anomalies built in.

**What to say in interview:**

> "The system applies a statistical analysis pipeline before any LLM involvement. I implemented schema validation for data integrity, z-score-based anomaly detection, rolling average trend analysis, and rule-based user segmentation. Segmentation rules are explicit and auditable — this is an intentional design choice that prioritises transparency over black-box clustering. The LLM receives structured analytical output, not raw user input."

**Test:** `python analysis.py` — should print a summary of sample data analysis.

---

### Phase 3 — Explainability Layer

**Goal:** Produce a structured insight object that makes the system's reasoning transparent and auditable.

**File:** `explainer.py`

**Output structure:**
```python
{
    "finding": "Overspending detected in food category",
    "evidence": {
        "food_spend_pct": 45.2,
        "recommended_pct": 30.0,
        "deviation": "+15.2%"
    },
    "risk_level": "medium",
    "trend": "increasing over last 14 days",
    "segment": "overspender"
}
```

**Why this matters:** The GPT prompt receives this structured object. The LLM explains it in natural language. The UI can also render the raw evidence alongside the explanation — so users see both the data and the interpretation.

**What to say in interview:**

> "I designed an explainability layer that separates analytical computation from natural language explanation. The system produces a structured insight object with raw evidence, which the LLM then narrates. This improves transparency and trust, and means the system's conclusions can be audited independently of the LLM response."

---

### Phase 4 — Core Backend Modules

**Goal:** Build the GPT client, prompt builder, and logger.

**File:** `chatbot.py`
- Sliding window memory (configurable `MAX_HISTORY_TURNS`)
- Retry logic with exponential backoff for rate limits and transient errors
- Handles `content_filter` finish reason gracefully
- Fallback mode: if the OpenAI API is unavailable, returns a structured analytical summary without LLM narration — the system degrades gracefully
- Provider-agnostic: supports both `openai` and `openai[azure]` via config flag

**File:** `prompt_builder.py`
- `build_system_prompt()` — constructs the base system prompt with safety constraints
- `build_analysis_prompt(insight_object)` — injects structured explainer output into prompt
- `build_chat_prompt(user_message, context)` — assembles final message list

**File:** `logger.py`
- Structured JSON logging (timestamp, session ID, event type, token count, latency)
- Writes to `logs/app.log`
- Separate audit log for every LLM input/output pair

**What to say in interview:**

> "I implemented token-aware memory management using a sliding window that retains the system prompt plus the last N conversation turns. This prevents context overflow errors without losing conversational coherence. The backoff retry handles transient API failures gracefully."

---

### Phase 5 — Governance and Responsible AI Layer

**Goal:** Build the safety and compliance layer. This is the differentiator in your portfolio.

**File:** `validators.py`
- `validate_input(text)` — enforces max length (500 chars), strips leading/trailing whitespace
- `detect_prompt_injection(text)` — pattern matching against known injection phrases (`ignore previous instructions`, `disregard`, `jailbreak`, etc.)
- `validate_output(text)` — flags outputs containing financial instrument names, legal advice phrases

**File:** `governance.py`
- `inject_disclaimer(response)` — appends standard disclaimer to every response
- `log_audit_event(input, output, session_id)` — writes to immutable audit log
- `handle_content_filter(response)` — returns safe fallback if OpenAI content filter triggered

**What to say in interview:**

> "I implemented a responsible AI governance layer with three components: input validation with prompt injection detection, output filtering with disclaimer injection, and immutable audit logging of all LLM interactions. This is consistent with responsible AI principles and would satisfy a compliance review in a regulated industry."

---

### Phase 6 — Streamlit Application

**Goal:** Build the production web interface.

**File:** `app.py`

**Tab 1 — Spending Analyser:**
- Upload a CSV or use the sample dataset
- Displays: total spend, category breakdown bar chart, budget deviation table, anomaly flags, rolling trend line chart, user segment badge
- "Analyse with AI" button — passes explainer output to GPT, returns natural language summary

**Tab 2 — Finance Assistant:**
- Chat interface with multi-turn conversation
- Session state manages conversation history
- Context from Tab 1 analysis is retained and injected automatically if available
- Input length counter visible to user
- Rate limit: max 20 requests per session

**Sidebar — System Status Panel:**
- API status indicator
- Average response time (this session)
- Total tokens used (this session)
- Estimated cost (this session, based on model pricing)

**What to say in interview:**

> "I used Streamlit for the frontend because it allows rapid development of data-driven applications with built-in session state management, without requiring a separate frontend codebase. The application is stateless by design — all state is held in the session, making horizontal scaling straightforward."

---

### Phase 7 — Metrics and Observability

**Goal:** Make the system measurable. Metrics are what separate engineering from scripting.

**File:** `metrics.py`
- `record_request(latency_ms, prompt_tokens, completion_tokens, model, success)` — appends to in-session metrics store
- `get_session_summary()` — returns avg latency, total tokens, estimated USD cost, `requests_count`, `error_count`
- `estimate_cost(prompt_tokens, completion_tokens, model)` — uses published pricing per 1K tokens
- Tracking both `requests_count` and `error_count` enables system reliability monitoring

**What to say in interview:**

> "I built an observability layer that tracks response latency, token consumption, and estimated API cost at the session level. In a production system this would feed into a centralised metrics store such as Prometheus. For this deployment it is surfaced in the UI sidebar so the cost per interaction is visible."

---

### Phase 8 — Testing Suite

**Goal:** Demonstrate engineering rigour. Even 5 passing tests on CI is a strong signal.

**Files and what they test:**

| File | Tests |
|---|---|
| `tests/test_analysis.py` | Aggregation correctness, anomaly detection accuracy, segmentation rules, rolling average shape |
| `tests/test_validators.py` | Input length rejection, injection detection (positive and negative cases) |
| `tests/test_prompt_builder.py` | Prompt contains expected sections, analysis context injected correctly |
| `tests/test_explainer.py` | Insight object structure, evidence fields present and typed correctly |
| `tests/test_chatbot.py` | Mocked API call returns expected format, sliding window truncates correctly |

**File:** `.github/workflows/ci.yml`
- Triggers on every push to `main`
- Steps: checkout, install dependencies, run flake8 lint, run pytest
- Badge displayed in README

**What to say in interview:**

> "I wrote a test suite covering the analysis engine, validation layer, prompt builder, and explainability module. Tests use unittest.mock to stub the OpenAI API, ensuring the test suite runs completely offline in CI without exposing credentials. The GitHub Actions pipeline runs on every commit."

---

### Phase 9 — Deployment

**Goal:** Ship a live, accessible application on your VPS.

**File:** `Dockerfile`
- Base image: `python:3.11-slim`
- Non-root user for security
- Dependencies installed in a separate layer for cache efficiency
- `EXPOSE 8501`

**File:** `docker-compose.yml`
- Mounts `.env` at runtime (never baked into image)
- Maps port 8501
- Health check configured

**VPS deployment steps (exact commands provided in Phase 9):**
1. SSH to VPS
2. Clone repo
3. Create `.env` from `.env.example`
4. `docker compose up -d --build`
5. Configure nginx reverse proxy (optional, for custom domain)

**What to say in interview:**

> "The application is containerised using Docker with a non-root user for security hardening and a layered build for cache efficiency. Secrets are injected at runtime via environment variables — they are never baked into the image. The system is stateless, so it can be restarted or scaled without data loss."

---

### Phase 10 — Documentation

**Goal:** README and ARCHITECTURE.md that demonstrate professional communication.

**README.md sections:**
- Project summary (one paragraph, no emojis)
- Architecture diagram (ASCII/text)
- Quickstart (local, Docker)
- Environment variables reference
- Running tests
- Deployment guide
- Design decisions
- CI badge

**ARCHITECTURE.md sections:**
- System components and responsibilities
- Data flow (numbered steps)
- Governance model
- Technology choices with justification
- Known limitations and future work

---

## Security Checklist (Non-Negotiable)

- [ ] API key loaded from environment variable only
- [ ] `.env` in `.gitignore`
- [ ] Input length validated (max 500 characters)
- [ ] Prompt injection detection active
- [ ] `max_tokens` hard-capped in config
- [ ] Rate limit per session (max 20 requests)
- [ ] No credentials in Dockerfile or docker-compose.yml
- [ ] Non-root Docker user
- [ ] Audit log written for every LLM interaction

---

## Dependencies (requirements.txt)

```
openai==1.30.1
streamlit==1.35.0
python-dotenv==1.0.1
pandas==2.2.2
numpy==1.26.4
scipy==1.13.0
plotly==5.22.0
tenacity==8.3.0
pytest==8.2.0
flake8==7.0.0
```

---

## Interview Preparation — Key Questions and Answers

**Q: Why did you choose OpenAI API over Azure OpenAI?**  
A: "I designed the system to be provider-agnostic — switching between OpenAI and Azure OpenAI requires only a configuration change, not a code change. For this deployment I used the OpenAI API for speed and flexibility, but the architecture is ready for Azure OpenAI in an enterprise context."

**Q: What makes this data science rather than just prompt engineering?**  
A: "The system applies a full statistical analysis pipeline before any LLM involvement — aggregation, budget deviation, rolling average trend detection, z-score anomaly detection, and rule-based segmentation. The LLM receives structured analytical output, not raw input. The analysis can operate independently of the LLM."

**Q: How did you handle safety and responsible AI?**  
A: "I built a dedicated governance layer with input validation, prompt injection detection, output filtering, disclaimer injection, and immutable audit logging. Every LLM interaction is logged with the input, output, session ID, and timestamp."

**Q: How does it handle context limits?**  
A: "I implemented sliding window memory management. The system always retains the system prompt plus the last N conversation turns. Older turns are dropped when the window is full. N is configurable via environment variable."

**Q: How would you scale this?**  
A: "The application is stateless — all session state is in Streamlit session state, not the server. Horizontal scaling requires only a load balancer in front of multiple container replicas. The audit and metrics logs would be externalised to a centralised store in a scaled deployment."

**Q: How does the system behave if the AI is unavailable?**  
A: "The system degrades gracefully. The analytical pipeline is deterministic and reproducible, so spending insights, anomaly flags, and segmentation are always available. The LLM layer is non-deterministic and used only for natural language explanation — if it is unavailable, the system returns the structured analytical summary directly."

> Key sentence to memorise: "The analytical pipeline is deterministic and reproducible. The LLM layer is non-deterministic and used only for explanation." This demonstrates a deep understanding of AI system architecture.

---

## Build Order Summary

| Phase | Key Output | Estimated Time |
|---|---|---|
| 1 | Scaffold, config, cleaned notebook | 30 min |
| 2 | Analysis engine + dataset generator | 60 min |
| 3 | Explainability layer | 30 min |
| 4 | Chatbot, prompt builder, logger | 45 min |
| 5 | Governance and validation | 30 min |
| 6 | Streamlit app | 90 min |
| 7 | Metrics | 20 min |
| 8 | Tests + CI | 45 min |
| 9 | Docker + VPS deployment | 30 min |
| 10 | README + ARCHITECTURE.md | 45 min |

**Total estimated build time: approximately 7 hours of focused work across sessions.**

---

## Start Command

When you are ready to begin, say: **"start Phase 1"**

Each phase will be built completely, explained fully, and confirmed working before moving to the next.
