---
title: Finance Intelligence System
emoji: ðŸ“Š
colorFrom: blue
colorTo: green
sdk: streamlit
sdk_version: 1.35.0
app_file: app.py
pinned: true
---

# Finance Intelligence System

A production-grade personal finance assistant that combines a **deterministic statistical analysis pipeline** with **GPT-powered natural language guidance**, underpinned by a **responsible-AI governance layer**.

Upload a bank transaction CSV and get instant category breakdowns, spending trends, and actionable AI-generated advice. All grounded in your actual numbers, never invented.

Built as a full-stack data science and AI engineering demonstration by [Clifford Nwanna](https://github.com/cliffordnwanna).

---

## Live Demo

ðŸŸ¢ **[Try it live on Hugging Face Spaces](https://huggingface.co/spaces/cliffordnwanna/finance-intelligence)**

To run locally:
```bash
git clone https://github.com/cliffordnwanna/GPT-POWERED-FINANCE-CHATBOT.git
cd GPT-POWERED-FINANCE-CHATBOT
pip install -r requirements.txt
# Add your OpenAI API key to .env (see Configuration below)
streamlit run app.py
```

---

## Screenshots

### 1. Home Screen
![Home screen with intro banner and upload prompt](images/01-home.png)

### 2. Analysis Dashboard
![Spending summary metrics after uploading transactions](images/02-dashboard.png)

### 3. Top Categories
![Top 3 categories table with spend totals and percentages](images/03-transactions.png)

### 4. AI Insights
![AI Insights panel showing spending analysis](images/04-AI_Insights.png)

### 5. Finance Assistant in Action
![Finance Assistant tab showing AI response with structured analysis](images/05-chat.png)

---

## What It Does

| Layer | What happens |
|-------|-------------|
| **Data ingestion** | Validates CSV schema, normalises columns, enforces types |
| **Statistical analysis** | Aggregation by category, user segmentation, rolling averages, top-spend ranking |
| **Explainability** | Converts raw numbers into a structured insight object passed to the UI and the LLM |
| **Governance** | Prompt injection detection, output scanning, rate limiting, disclaimer injection |
| **LLM narration** | GPT narrates the analytical findings â€” it does not compute them |
| **Observability** | JSON-structured dual logging (app + audit), session metrics, token tracking |

---

## Architecture

```
CSV Upload
    â”‚
    â–¼
analysis.py  â”€â”€ deterministic statistical pipeline (no LLM)
    â”‚
    â–¼
explainer.py â”€â”€ structured insight object
    â”‚
    â”œâ”€â”€â–º Rendered directly in the UI (charts, tables, metric cards)
    â”‚
    â””â”€â”€â–º Injected as context â”€â”€â–º prompt_builder.py â”€â”€â–º chatbot.py â”€â”€â–º GPT API
                                                              â”‚
                                                      governance.py
                                                      (output scan + disclaimer)
                                                              â”‚
                                                              â–¼
                                                         Streamlit UI
```

**The statistical pipeline and the LLM are strictly separated.** The app produces correct output even when the LLM is unavailable.

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Web framework | Streamlit 1.35 |
| LLM provider | OpenAI GPT-4o-mini |
| Data analysis | pandas 2.2 |
| Visualisation | Plotly 5.22 |
| API resilience | tenacity (exponential backoff + retry) |
| Configuration | python-dotenv (12-Factor App pattern) |
| Logging | Python logging â€” JSON-structured dual output |
| Deployment | Hugging Face Spaces (Streamlit SDK) |

---

## Configuration

Create a `.env` file in the project root:

```
OPENAI_API_KEY=your_key_here
```

No other secrets are required to run locally.

---

## Using Your Own Data

The app accepts any CSV with these columns:

| Column | Required | Example | Notes |
|--------|----------|---------|-------|
| `date` | âœ… | `2026-03-15` | YYYY-MM-DD, DD/MM/YYYY, or MM/DD/YYYY |
| `category` | âœ… | `food` | Case-insensitive â€” any label works |
| `amount` | âœ… | `45.50` | Positive values only â€” no currency symbols |
| `description` | Optional | `Grocery store` | Included if present |

**File size limit:** 5 MB Â· **Row limit:** 100,000 transactions

> **Tip for accurate results:** Use one consistent label per category throughout your file. For example, use `savings` for every savings entry rather than mixing `savings`, `savings account`, and `monthly savings`. The app shows you every distinct category it detected so you can spot inconsistencies before analysing.

A ready-to-fill CSV template is available via the download button inside the app.

---

## Data Validation

Every uploaded file passes through a 13-point validation pipeline before any analysis runs:

| Check | What it catches |
|-------|----------------|
| File size | Files over 5 MB |
| File type | Non-CSV files (`.xlsx`, `.pdf`, etc.) |
| Encoding | UTF-8, UTF-8-BOM, Latin-1 (Excel exports) â€” auto-detected |
| Parse failure | Corrupted or malformed files |
| Missing columns | Wrong file or missing headers |
| Empty columns | Header present but no data |
| Amount type | Text, currency symbols, percentages |
| Negative amounts | Bank exports with debits as negatives |
| Date format | Unrecognisable date strings |
| Future dates | Dates ahead of today (advisory warning) |
| Empty categories | Blank category cells |
| Duplicate rows | Accidental copy-paste duplication (advisory warning) |
| Wrong file type | Non-financial column names misidentified as CSVs |

**Errors are blocking** â€” the upload is rejected with a plain-English explanation and an actionable fix.  
**Warnings are advisory** â€” the upload proceeds but the user is informed.

---

## Project Structure

```
.
â”œâ”€â”€ app.py                    # Streamlit web app â€” entry point
â”œâ”€â”€ analysis.py               # Statistical pipeline (LLM-independent)
â”œâ”€â”€ explainer.py              # Structured insight builder
â”œâ”€â”€ chatbot.py                # GPT client (sliding window, retry, fallback)
â”œâ”€â”€ prompt_builder.py         # LLM message assembly and validation
â”œâ”€â”€ validators.py             # CSV input validation + injection detection
â”œâ”€â”€ governance.py             # Rate limiting + output disclaimer injection
â”œâ”€â”€ metrics.py                # Session observability (latency, tokens)
â”œâ”€â”€ logger.py                 # Dual JSON logging (app.log + audit.log)
â”œâ”€â”€ config.py                 # 12-Factor configuration loader
â”œâ”€â”€ data/
â”‚   â”œâ”€â”€ sample_transactions.csv        # Ready-to-use demo dataset
â”‚   â””â”€â”€ test_category_normalisation.csv
â”œâ”€â”€ images/                   # App screenshots
â”œâ”€â”€ .streamlit/config.toml    # Streamlit server settings
â””â”€â”€ requirements.txt          # Production dependencies
```

---

## Key Design Decisions

**Why separate the statistical pipeline from the LLM?**
Deterministic analysis is independently testable and auditable. The LLM is used only to narrate the findings in plain English. This satisfies explainability requirements, enables graceful degradation if the API is unavailable, and prevents the model from hallucinating financial figures.

**Why no fuzzy category matching?**
Earlier versions used `difflib` fuzzy matching to merge similar labels (e.g. `savings` and `savings account`). This was removed because it silently changed the user's data without consent. The system now applies exact case-insensitive matching only, and surfaces all detected categories to the user so they can fix inconsistencies themselves.

**Why a sliding-window conversation history?**
The most recent 10 turns are sent to the LLM, keeping responses contextually relevant while bounding token cost. Older turns are dropped from the prompt â€” not from the audit log.

**Why show top 3 categories instead of individual transactions?**
Aggregated category totals answer the question users actually have: *"Where is my money going?"* Individual transactions repeat the same category multiple times and shift focus from patterns to events.

---

## Responsible AI Controls

- Input validation and length limits before every LLM call
- 13-pattern prompt injection detection â€” blocked at the input layer
- System prompt versioning (`v1.1.0`) with explicit injection-defence instructions
- Output scanning for investment, tax, and legal language
- Automatic disclaimer injection when flags trigger
- Session-level rate limiting
- Append-only audit log of every LLM interaction (session ID, tokens, latency)
- Graceful degradation when the LLM is unavailable â€” analysis still renders
- System prompt prohibits requesting or storing PII

---

## License

MIT License â€” free to use, modify, and distribute with attribution.
