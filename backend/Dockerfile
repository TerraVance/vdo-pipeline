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
# Uses $PORT if provided by the cloud provider (Render, Railway, Cloud Run), otherwise defaults to 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
