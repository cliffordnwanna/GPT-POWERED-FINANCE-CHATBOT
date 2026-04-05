"""
app.py — Finance Intelligence System: Streamlit Application.

This is the production web interface. It wires together every backend module
into a coherent user-facing application with two functional tabs:

  Tab 1 — Spending Analyser
    Upload a CSV of transactions (or use the included sample dataset).
    The system runs the full statistical analysis pipeline, renders charts,
    flags spending patterns, shows category breakdowns, and offers an AI explanation
    of the findings.

  Tab 2 — Finance Assistant
    Multi-turn conversational interface. If Tab 1 analysis has been run,
    the structured insight context is automatically injected into every
    prompt so the assistant can reference real figures from the user's data.

The sidebar displays a live System Status Panel showing API health, session
token usage, estimated cost, and request counts.

Run locally:
    streamlit run app.py

The application is stateless — all state is held in st.session_state.
Horizontal scaling requires only a load balancer with no shared server state.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import plotly.express as px
import streamlit as st

import config
from analysis import (
    SAMPLE_DATA_PATH,
    _normalise_category,
    aggregate_spending,
    compute_rolling_averages,
    get_top_transactions,
    load_transactions,
    segment_user,
)
from chatbot import FinanceChatbot
from explainer import build_insight, format_for_prompt
from governance import apply_governance, check_rate_limit
from metrics import SessionMetrics, get_summary, record_request
from validators import validate_input, validate_csv_upload

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Finance Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": (
            "**Finance Intelligence**  \n"
            "A personal finance intelligence system that turns your bank transactions "
            "into plain-language insights, spending breakdowns, and AI-powered advice.  \n\n"
            "Built with Python · Streamlit · OpenAI · pandas · scipy  \n\n"
            "Designed by Clifford Nwanna."
        )
    },
)

# ---------------------------------------------------------------------------
# App-wide intro banner
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%);
                border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; color: white;">

      <h2 style="margin:0 0 6px 0; font-size:1.45rem; font-weight:700;">Finance Intelligence System</h2>
      <p style="margin:0 0 6px 0; font-size:0.95rem; opacity:0.85;">
        Upload your transactions and get instant category breakdowns, spending trends, and AI-powered guidance.
      </p>
      <p style="margin:0 0 14px 0; font-size:0.92rem; opacity:0.75;">
        Whether you're trying to control spending, curious about your spending habits, or just want better financial clarity. This tool helps you make more confident, data-driven decisions.
      </p>

      <a href="https://github.com/cliffordnwanna/GPT-POWERED-FINANCE-CHATBOT"
         target="_blank"
         style="background:#e94560; color:white; padding:7px 16px; border-radius:6px;
                text-decoration:none; font-size:0.85rem; font-weight:600; display:inline-block; margin-right:16px;">
        📂 GitHub
      </a>
      <span style="font-size:0.8rem; opacity:0.55;">Built by Clifford Nwanna</span>
    </div>
    """,
    unsafe_allow_html=True,
)


def _init_session() -> None:
    """Initialise all session state keys on first load."""
    if "chatbot" not in st.session_state:
        st.session_state.chatbot = None  # Lazily initialised after key check
    if "metrics" not in st.session_state:
        st.session_state.metrics = SessionMetrics()
    if "analysis_context" not in st.session_state:
        st.session_state.analysis_context = None  # Set after Tab 1 analysis
    if "analysis_results" not in st.session_state:
        st.session_state.analysis_results = None
    if "insight" not in st.session_state:
        st.session_state.insight = None
    if "chat_display" not in st.session_state:
        st.session_state.chat_display = []  # List of (role, text) for rendering
    if "request_count" not in st.session_state:
        st.session_state.request_count = 0
    if "api_ok" not in st.session_state:
        st.session_state.api_ok = None  # None = unchecked, True/False after first call
    if "loaded_filename" not in st.session_state:
        st.session_state.loaded_filename = None
    if "suggested_question" not in st.session_state:
        st.session_state.suggested_question = None
    if "ai_insight_reply" not in st.session_state:
        st.session_state.ai_insight_reply = None
    if "follow_ups" not in st.session_state:
        st.session_state.follow_ups = []
    if "last_suggestion_idx" not in st.session_state:
        st.session_state.last_suggestion_idx = None
    if "loaded_categories" not in st.session_state:
        st.session_state.loaded_categories = []


_init_session()

# ---------------------------------------------------------------------------
# Custom CSS — production polish
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    [data-testid="stMetricValue"] {font-size: 1.25rem !important; font-weight: 600;}
    [data-testid="stMetricLabel"] {font-size: 0.78rem !important; color: #888;}
    div[data-testid="stExpander"] {border: 1px solid #e6e6e6; border-radius: 8px;}
    .stAlert {border-radius: 8px;}
    div[data-testid="stHorizontalBlock"] > div {padding: 0 4px;}
    /* Mobile responsive */
    @media (max-width: 640px) {
        [data-testid="stMetricValue"] {font-size: 0.9rem !important;}
        [data-testid="stMetricLabel"] {font-size: 0.65rem !important;}
        div[data-testid="stHorizontalBlock"] > div {padding: 0 2px !important;}
        section[data-testid="stSidebar"] {min-width: 0 !important;}
    }
    /* Clean chart containers */
    .stPlotlyChart {border-radius: 8px; overflow: hidden;}
    [data-testid="collapsedControl"] {display: flex !important;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar — System Status Panel
# ---------------------------------------------------------------------------


def _render_sidebar() -> None:
    st.sidebar.title("Control Panel")

    # API status
    api_key_set = bool(config.OPENAI_API_KEY or config.AZURE_OPENAI_API_KEY)
    if not api_key_set:
        st.sidebar.error("API key not configured")
    elif st.session_state.api_ok is None:
        st.sidebar.success("API key configured")
    elif st.session_state.api_ok:
        st.sidebar.success("API connected")
    else:
        st.sidebar.error("API unreachable — check key / network")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Session Metrics")

    summary = get_summary(st.session_state.metrics)
    col1, col2 = st.sidebar.columns(2)
    col1.metric("Requests", summary["requests"])
    col2.metric("Errors", summary["errors"])
    st.sidebar.metric("Avg latency", f"{summary['avg_latency_ms']} ms")
    st.sidebar.metric("Tokens used", f"{summary['total_tokens']:,}")
    st.sidebar.metric("Est. cost (USD)", f"${summary['estimated_cost_usd']:.6f}")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Configuration")
    provider = "Azure OpenAI" if config.USE_AZURE else "OpenAI"
    model = config.AZURE_OPENAI_DEPLOYMENT if config.USE_AZURE else config.MODEL_NAME
    st.sidebar.markdown(f"**Provider:** {provider}")
    st.sidebar.markdown(f"**Model:** `{model}`")

    if st.session_state.analysis_results:
        filename = st.session_state.loaded_filename or "dataset"
        st.sidebar.success(f"Analysis loaded: {filename}")
    else:
        st.sidebar.info("No analysis loaded yet")

    st.sidebar.markdown("---")
    st.sidebar.caption(
        "All responses are for educational purposes only and do not constitute "
        "financial, legal, or investment advice."
    )


# ---------------------------------------------------------------------------
# CSV template for download
# ---------------------------------------------------------------------------

_CSV_TEMPLATE = """date,category,amount,description
2026-01-01,food,45.50,Grocery store
2026-01-02,transport,12.00,Bus pass top-up
2026-01-03,utilities,85.00,Electricity bill
2026-01-04,food,22.30,Lunch at cafe
2026-01-05,entertainment,18.00,Streaming subscription
2026-01-06,savings,200.00,Monthly savings transfer
2026-01-07,health,55.00,Pharmacy
2026-01-08,food,67.80,Weekly groceries
2026-01-09,transport,45.00,Fuel
2026-01-10,food,14.50,Coffee and snacks
"""


# ---------------------------------------------------------------------------
# Helper: Initialise chatbot (lazy — requires API key)
# ---------------------------------------------------------------------------

def _get_chatbot() -> FinanceChatbot:
    """Return the session chatbot instance, creating it if needed."""
    if st.session_state.chatbot is None:
        session_id = f"st_{int(time.time())}"
        st.session_state.chatbot = FinanceChatbot(session_id=session_id)
    return st.session_state.chatbot


def _safe_render(text: str) -> None:
    """Render LLM output as clean plain text — no dollar signs, no markdown artefacts."""
    import re
    # Replace currency symbols with plain equivalents
    safe = text.replace("$", "USD ")
    # Collapse any accidental double spaces introduced
    safe = re.sub(r"  +", " ", safe)
    # Strip backtick code spans/blocks
    safe = re.sub(r"`+", "", safe)
    st.markdown(safe)


# ---------------------------------------------------------------------------
# Helper: Run the full analysis pipeline on a DataFrame
# ---------------------------------------------------------------------------

def _run_analysis(df: pd.DataFrame) -> None:
    """
    Run all analysis functions, build the insight object, format the prompt
    context, and store results in session state.
    """
    # Drop zero-amount rows — they don't represent real spend
    df = df[df["amount"] > 0].copy()

    results = {
        "aggregation": aggregate_spending(df),
        "top_transactions": get_top_transactions(df),
        "segmentation": segment_user(df),
        "rolling_averages": compute_rolling_averages(df).to_dict(orient="records"),
    }
    insight = build_insight(results)

    st.session_state.analysis_results = results
    st.session_state.insight = insight
    st.session_state.analysis_context = format_for_prompt(insight)
    st.session_state.loaded_categories = sorted(df["category"].unique().tolist())
    st.session_state.ai_insight_reply = None  # clear stale AI reply on new data
    st.session_state.follow_ups = []
    st.session_state.last_suggestion_idx = None


# ---------------------------------------------------------------------------
# Tab 1 — Spending Analyser
# ---------------------------------------------------------------------------

def _render_analyser_tab() -> None:
    # ------------------------------------------------------------------
    # Results view: shown immediately when data is loaded (no scrolling).
    # The upload UI is replaced by a compact "Change data" button.
    # ------------------------------------------------------------------
    if st.session_state.analysis_results is not None:
        results = st.session_state.analysis_results
        insight = st.session_state.insight
        agg = results["aggregation"]

        # Compact data-loaded header
        fn = st.session_state.loaded_filename or "dataset"
        hdr_col, btn_col = st.columns([5, 1])
        with hdr_col:
            st.caption(
                f"\U0001f4c2 **{fn}** · {agg['transaction_count']} transactions · "
                f"{agg['date_range']['start']} → {agg['date_range']['end']}"
            )
        with btn_col:
            if st.button("Change data", use_container_width=True):
                st.session_state.analysis_results = None
                st.session_state.insight = None
                st.session_state.analysis_context = None
                st.session_state.loaded_categories = []
                st.rerun()

        # --- Categories detected ---
        cats = st.session_state.get("loaded_categories", [])
        if cats:
            with st.expander(f"📋 {len(cats)} categories detected in your file — click to review", expanded=False):
                st.write("  ·  ".join(cats))
                st.caption(
                    "Tip: For accurate totals, use one consistent label per category throughout your CSV. "
                    "For example, use a single entry \'savings\' each month rather than mixing "
                    "\'savings\', \'savings account\', and \'monthly savings\'."
                )

        # --- Summary metrics ---
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Spend", f"${agg['total_spend']:,.2f}")
        col2.metric("Transactions", agg["transaction_count"])
        col3.metric("Top Category", insight["top_category"].capitalize())
        segment_colours = {"concentrated": "red", "moderate": "orange", "diversified": "green"}
        segment = insight["segment"]
        col4.markdown(
            f"**Segment**  \n:{segment_colours.get(segment, 'grey')}[{segment.upper()}]"
        )
        st.markdown("---")

        # Shared palette + category dataframe
        _PALETTE = px.colors.qualitative.Set2
        cat_df = pd.DataFrame(
            [
                {"Category": k.capitalize(), "Amount ($)": round(v, 2)}
                for k, v in sorted(agg["by_category"].items(), key=lambda x: -x[1])
            ]
        )

        # --- Charts: horizontal bar (left) + donut (right) ---
        left, right = st.columns(2)

        with left:
            st.subheader("Spending by Category")
            fig_bar = px.bar(
                cat_df,
                x="Amount ($)",
                y="Category",
                orientation="h",
                color="Category",
                color_discrete_sequence=_PALETTE,
            )
            fig_bar.update_layout(
                showlegend=False,
                height=320,
                xaxis_title="",
                yaxis_title="",
                margin=dict(l=10, r=20, t=10, b=10),
                xaxis=dict(showgrid=True, gridcolor="#f0f0f0", tickformat="$,.0f"),
                yaxis=dict(showgrid=False, autorange="reversed"),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
            )
            fig_bar.update_traces(
                texttemplate="",
                hovertemplate="%{y}<br>$%{x:,.2f}<extra></extra>",
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with right:
            st.subheader("Spending Share")
            fig_donut = px.pie(
                cat_df,
                values="Amount ($)",
                names="Category",
                hole=0.55,
                color_discrete_sequence=_PALETTE,
            )
            fig_donut.update_traces(
                textinfo="none",
                hovertemplate="%{label}<br>$%{value:,.2f}  (%{percent})<extra></extra>",
            )
            fig_donut.update_layout(
                showlegend=True,
                legend=dict(
                    orientation="v",
                    yanchor="middle",
                    y=0.5,
                    xanchor="left",
                    x=1.02,
                    font=dict(size=11),
                ),
                height=360,
                margin=dict(l=10, r=120, t=20, b=20),
                paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_donut, use_container_width=True)

        # --- Time series trend ---
        st.subheader("Daily Spending Trend")
        rolling_df = pd.DataFrame(results["rolling_averages"]).rename(columns={
            "daily_total": "Daily Spend ($)",
            "rolling_avg": "7-day Average ($)",
        })
        fig_line = px.line(
            rolling_df,
            x="date",
            y=["Daily Spend ($)", "7-day Average ($)"],
            labels={"value": "Amount ($)", "date": "", "variable": ""},
            color_discrete_map={
                "Daily Spend ($)": "#aec7e8",
                "7-day Average ($)": "#1f77b4",
            },
        )
        fig_line.update_layout(
            height=280,
            legend_title_text="",
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.2,
                xanchor="center",
                x=0.5,
            ),
            xaxis_title="",
            yaxis_title="Amount ($)",
            margin=dict(l=0, r=0, t=10, b=40),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        fig_line.update_xaxes(tickangle=0, showgrid=False)
        fig_line.update_yaxes(showgrid=True, gridcolor="#f0f0f0", tickformat="$,.0f")
        st.plotly_chart(fig_line, use_container_width=True)

        # --- Top Categories ---
        st.subheader("Top 3 Categories")
        by_cat = agg.get("by_category", {})
        by_cat_pct = agg.get("by_category_pct", {})
        if by_cat:
            top3 = sorted(by_cat.items(), key=lambda x: -x[1])[:3]
            top3_df = pd.DataFrame([
                {"Category": cat.capitalize(), "Total Spend": f"${amt:,.2f}", "% of Total": f"{by_cat_pct.get(cat, 0):.1f}%"}
                for cat, amt in top3
            ])
            st.dataframe(top3_df, hide_index=True, use_container_width=True)
            st.caption("Your three highest-spend categories for the period.")

        # --- Download report ---
        st.markdown("---")
        _col_dl, _col_spacer = st.columns([1, 3])
        with _col_dl:
            report_lines = [
                "Finance Intelligence System — Analysis Report",
                f"Period: {agg['date_range']['start']} to {agg['date_range']['end']}",
                f"Total spend: ${agg['total_spend']:,.2f}",
                f"Transactions: {agg['transaction_count']}",
                f"Segment: {insight['segment'].upper()}",
                "",
                "Primary finding:",
                f"  {insight['finding']}",
                "",
                "Category breakdown:",
            ]
            for cat, pct in sorted(agg["by_category_pct"].items(), key=lambda x: -x[1]):
                report_lines.append(f"  {cat}: {pct:.1f}% (${agg['by_category'][cat]:,.2f})")
            report_lines += ["", "Top 3 categories:"]
            for cat, amt in sorted(agg["by_category"].items(), key=lambda x: -x[1])[:3]:
                report_lines.append(f"  {cat}: {agg['by_category_pct'].get(cat, 0):.1f}% (${amt:,.2f})")
            st.download_button(
                label="⬇️ Download report (.txt)",
                data="\n".join(report_lines),
                file_name="finance_analysis_report.txt",
                mime="text/plain",
            )

        # --- AI Insights ---
        st.markdown("---")
        st.subheader("Get AI Insights")
        st.write(
            "Click below to get a plain-language summary of your key findings "
            "and actionable suggestions from the AI."
        )

        if not (config.OPENAI_API_KEY or config.AZURE_OPENAI_API_KEY):
            st.warning("Set your API key in the .env file to enable AI explanations.")
            return

        if st.button("Analyse with AI", type="primary"):
            allowed, limit_reason = check_rate_limit(st.session_state.request_count)
            if not allowed:
                st.error(limit_reason)
                return

            prompt = (
                "Based on the financial analysis provided, give me a concise plain-language "
                "summary of the most important findings and 2-3 actionable suggestions. "
                "Be direct and educational."
            )

            with st.spinner("Analysing your spending..."):
                try:
                    bot = _get_chatbot()
                    reply, tokens, latency = bot.chat(
                        user_message=prompt,
                        analysis_context=st.session_state.analysis_context,
                    )
                    governed_reply = apply_governance(reply, "stop", bot.session_id)
                    st.session_state.ai_insight_reply = governed_reply
                    st.session_state.api_ok = True
                    st.session_state.request_count += 1
                    record_request(
                        st.session_state.metrics,
                        latency_ms=latency,
                        prompt_tokens=tokens // 2,
                        completion_tokens=tokens - tokens // 2,
                        model=config.MODEL_NAME,
                        success=True,
                    )
                    st.rerun()
                except Exception as exc:
                    st.session_state.ai_insight_reply = None
                    st.error(f"AI explanation failed: {exc}")
                    st.session_state.api_ok = False
                    record_request(
                        st.session_state.metrics,
                        latency_ms=0,
                        prompt_tokens=0,
                        completion_tokens=0,
                        model=config.MODEL_NAME,
                        success=False,
                    )

        if st.session_state.ai_insight_reply:
            _safe_render(st.session_state.ai_insight_reply)

        return

    # ------------------------------------------------------------------
    # Upload UI: shown when no data is loaded yet
    # ------------------------------------------------------------------
    st.header("Your Spending Analyser")
    st.write(
        "Upload your bank transactions or try the sample dataset to instantly see "
        "where your money is going, spot unusual spending, and understand your financial habits."
    )

    with st.expander("📂  How to use your own data", expanded=False):
        st.markdown(
            """
**Your CSV must contain these columns:**

| Column | Required | Example | Notes |
|--------|----------|---------|-------|
| `date` | ✅ Yes | `2026-03-15` | YYYY-MM-DD, DD/MM/YYYY, or MM/DD/YYYY |
| `category` | ✅ Yes | `food` | Case-insensitive — any name works |
| `amount` | ✅ Yes | `45.50` | Positive numbers only — no £ or $ symbols |
| `description` | Optional | `Grocery store` | Helpful but not required |

**Tips:**
- Export directly from your banking app or copy-paste into the template
- Keep amounts positive — if your bank shows debits as negative, remove the minus sign
- Dates in any common format are supported
- File size limit: **5 MB** (split into separate files if larger)
            """
        )
        st.download_button(
            label="⬇️ Download CSV template",
            data=_CSV_TEMPLATE,
            file_name="transactions_template.csv",
            mime="text/csv",
            help="Download a ready-to-fill template with the correct column structure",
        )

    data_source = st.radio(
        "Data source",
        options=["Use sample dataset", "Upload my own CSV"],
        horizontal=True,
    )

    if data_source == "Use sample dataset":
        if st.button("Load sample dataset", type="primary"):
            try:
                df = load_transactions(SAMPLE_DATA_PATH)
                st.session_state.loaded_filename = "sample_transactions.csv"
                _run_analysis(df)
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to load sample data: {exc}")

    else:
        uploaded = st.file_uploader(
            "Upload transactions CSV",
            type=["csv"],
            help="Max 5 MB · Must include date, category, and amount columns",
        )
        if uploaded is not None:
            raw_bytes = uploaded.read()
            validation = validate_csv_upload(raw_bytes, uploaded.name)

            # Show all warnings (non-blocking) before proceeding
            for w in validation.warnings:
                st.warning(f"⚠️ {w}")

            if not validation.ok:
                # Show each error distinctly with an actionable fix
                for err in validation.errors:
                    st.error(f"❌ {err}")
                st.info(
                    "**How to fix it:** Correct the issue in your spreadsheet, "
                    "save as CSV, and re-upload. "
                    "Download the template above if you need a clean starting point."
                )
            else:
                # Validation passed — parse and run analysis
                try:
                    import io as _io
                    import pandas as _pd
                    for enc in ("utf-8-sig", "utf-8", "latin-1"):
                        try:
                            df = _pd.read_csv(_io.BytesIO(raw_bytes), encoding=enc)
                            break
                        except Exception:
                            continue

                    # Normalise columns
                    df.columns = [c.strip().lower() for c in df.columns]
                    df = df.dropna(how="all")
                    df["date"] = _pd.to_datetime(
                        df["date"].astype(str).str.strip(),
                        errors="coerce",
                    )
                    df["amount"] = (
                        _pd.to_numeric(
                            df["amount"].astype(str).str.strip().str.replace(",", "", regex=False),
                            errors="coerce",
                        )
                    )
                    df["category"] = df["category"].astype(str).str.lower().str.strip().apply(_normalise_category)

                    st.session_state.loaded_filename = uploaded.name
                    _run_analysis(df)
                    st.rerun()

                except Exception as exc:
                    st.error(
                        "Something unexpected went wrong while reading your file. "
                        "Please try exporting it again from your bank or spreadsheet app."
                    )
                    st.caption(f"Technical detail: {exc}")

    st.info("Load a dataset above to see the analysis.")


# ---------------------------------------------------------------------------
# Tab 2 — Finance Assistant
# ---------------------------------------------------------------------------

def _get_personalized_suggestions(insight: dict) -> list:
    """Return 3 questions tailored to the user's actual spending data."""
    top_cat = insight.get("top_category", "your highest category").lower()
    return [
        f"Why is my {top_cat} spending so high and what can I do about it?",
        "Am I on track financially or am I spending too much overall?",
        "What single change would improve my finances the most?",
    ]


def _get_follow_ups(suggestion_idx, insight: dict) -> list:
    """Return 2 follow-up questions for a given suggestion topic."""
    top_cat = insight.get("top_category", "this category").lower()
    follow_up_map = {
        0: [
            f"What percentage of my budget should go to {top_cat}?",
            f"Which other category should I cut to offset my {top_cat} spend?",
        ],
        1: [
            "What is a realistic monthly savings target given my spending?",
            "Which of my categories is most worth reducing?",
        ],
        2: [
            "How do I know if my spending is well-balanced across categories?",
            "What habits lead to better financial health over time?",
        ],
    }
    return follow_up_map.get(suggestion_idx, [
        "What is the most important thing I can improve about my spending?",
        "How do I build a simple monthly budget from my data?",
    ])


def _render_assistant_tab() -> None:
    st.header("Finance Assistant")
    st.write("Ask anything about your spending, budgeting, or financial habits.")

    if st.session_state.analysis_context:
        st.info("\U0001f4ca Your spending data is loaded — questions will get specific, personalised answers.")

    if not (config.OPENAI_API_KEY or config.AZURE_OPENAI_API_KEY):
        st.warning("API key not configured. Add OPENAI_API_KEY to your .env file and restart.")
        return

    # --- Chat history ---
    chat_container = st.container()
    with chat_container:
        for role, text in st.session_state.chat_display:
            with st.chat_message(role):
                if role == "assistant":
                    _safe_render(text)
                else:
                    st.markdown(text)

    # --- Suggested questions (personalised, shown only when chat is empty) ---
    insight = st.session_state.insight
    if not st.session_state.chat_display:
        if insight:
            suggestions = _get_personalized_suggestions(insight)
        else:
            suggestions = [
                "Where am I spending the most?",
                "How can I save more each month?",
                "What should I do about my highest expense?",
            ]
        cols = st.columns(3)
        for i, suggestion in enumerate(suggestions):
            if cols[i].button(suggestion, key=f"sq_{i}", use_container_width=True):
                st.session_state.suggested_question = suggestion
                st.session_state.last_suggestion_idx = i
                st.rerun()

    # --- Follow-up buttons (shown after first exchange, while follow_ups set) ---
    elif st.session_state.follow_ups:
        st.markdown("**Follow-up:**")
        fu_cols = st.columns(2)
        for j, fq in enumerate(st.session_state.follow_ups):
            if fu_cols[j].button(fq, key=f"fu_{j}", use_container_width=True):
                st.session_state.suggested_question = fq
                st.session_state.follow_ups = []
                st.rerun()

    # --- Pick up a pending question ---
    _pending_question = st.session_state.suggested_question
    if _pending_question:
        st.session_state.suggested_question = None

    # --- Input ---
    user_input = st.chat_input(
        placeholder=f"Ask a finance question (max {config.MAX_INPUT_LENGTH} characters)..."
    ) or _pending_question

    if user_input:
        is_valid, reason = validate_input(user_input)
        if not is_valid:
            st.warning(reason)
            return

        allowed, limit_reason = check_rate_limit(st.session_state.request_count)
        if not allowed:
            st.error(limit_reason)
            return

        st.session_state.chat_display.append(("user", user_input))

        with st.spinner("Thinking..."):
            try:
                bot = _get_chatbot()
                reply, tokens, latency = bot.chat(
                    user_message=user_input,
                    analysis_context=st.session_state.analysis_context,
                )
                governed_reply = apply_governance(reply, "stop", bot.session_id)
                st.session_state.api_ok = True
                st.session_state.request_count += 1
                record_request(
                    st.session_state.metrics,
                    latency_ms=latency,
                    prompt_tokens=tokens // 2,
                    completion_tokens=tokens - tokens // 2,
                    model=config.MODEL_NAME,
                    success=True,
                )
                st.session_state.chat_display.append(("assistant", governed_reply))
                # Set follow-ups for the topic just answered
                if insight:
                    st.session_state.follow_ups = _get_follow_ups(
                        st.session_state.last_suggestion_idx, insight
                    )
                st.session_state.last_suggestion_idx = None
                st.rerun()

            except Exception as exc:
                fallback_text = (
                    "The assistant is temporarily unavailable. "
                    "Please try again in a moment."
                )
                st.session_state.chat_display.append(("assistant", fallback_text))
                st.error(f"Request failed: {exc}")
                st.session_state.api_ok = False
                record_request(
                    st.session_state.metrics,
                    latency_ms=0,
                    prompt_tokens=0,
                    completion_tokens=0,
                    model=config.MODEL_NAME,
                    success=False,
                )
                st.rerun()

    # --- Clear conversation ---
    if st.session_state.chat_display:
        if st.button("Clear conversation"):
            st.session_state.chat_display = []
            st.session_state.follow_ups = []
            st.session_state.last_suggestion_idx = None
            if st.session_state.chatbot:
                st.session_state.chatbot.reset()
            st.rerun()

    limit_remaining = config.MAX_REQUESTS_PER_SESSION - st.session_state.request_count
    st.caption(f"Questions remaining: {limit_remaining}")


# ---------------------------------------------------------------------------
# Main layout — tabs
# ---------------------------------------------------------------------------

tab1, tab2 = st.tabs(["Spending Analyser", "Finance Assistant"])

with tab1:
    _render_analyser_tab()

with tab2:
    _render_assistant_tab()

# Sidebar renders LAST so it reads all session_state updates made during
# button/upload handlers above (API status, metrics, analysis context).
_render_sidebar()

