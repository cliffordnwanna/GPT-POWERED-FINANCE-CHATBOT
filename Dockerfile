# syntax=docker/dockerfile:1
#
# Finance Intelligence System
# Multi-stage build: keeps the final image lean by excluding dev tools.
#
# Build:  docker build -t finance-intelligence .
# Run:    docker run -p 8501:8501 -e OPENAI_API_KEY=sk-... finance-intelligence

FROM python:3.11-slim AS base

WORKDIR /app

# Security: run as non-root user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Copy dependency manifest first to leverage Docker layer cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Ownership
RUN chown -R appuser:appgroup /app

USER appuser

# Streamlit runs on 8501 by default
EXPOSE 8501

# Healthcheck — Cloud Run / Azure Container Apps will use this
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", \
  "--server.port=8501", \
  "--server.address=0.0.0.0", \
  "--server.headless=true"]
