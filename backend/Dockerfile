# ── Base image ───────────────────────────────────────────────────────
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# System dependencies (for httpx, cryptography, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ───────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ──────────────────────────────────────────────────
COPY . .

# ── Expose port ───────────────────────────────────────────────────────
EXPOSE 8000

# ── Default: run the FastAPI server ──────────────────────────────────
# To run the Celery worker instead, override CMD in Render:
#   CMD ["celery", "-A", "app.core.celery_app", "worker", "--loglevel=info"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
