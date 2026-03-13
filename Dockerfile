# ═══════════════════════════════════════════════════════════════════════
#  MindVault — Multi-Stage Dockerfile
#
#  Stage 1 (builder): install deps into a venv
#  Stage 2 (runtime): minimal image, copy venv only
#
#  Build:  docker build -t mindvault:latest .
#  Run:    docker run -p 8000:8000 --env-file config/.env mindvault:latest
# ═══════════════════════════════════════════════════════════════════════

# ── Stage 1: Builder ──────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps for pdfplumber (poppler) and compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpoppler-cpp-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Create isolated venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python deps — layer-cached unless requirements.txt changes
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Runtime ──────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Non-root user for security
RUN groupadd -r mindvault && useradd -r -g mindvault -d /app -s /sbin/nologin mindvault

# Runtime system deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

# Copy application code (no tests, no docs)
COPY app/ ./app/
COPY scripts/init_db.py ./scripts/init_db.py
COPY config/.env.example ./config/.env.example

# Create data directory for SQLite
RUN mkdir -p /app/data /app/logs && \
    chown -R mindvault:mindvault /app

# Switch to non-root
USER mindvault

# Expose port
EXPOSE 8000

# Health check — hits the /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Init DB then start server
CMD ["sh", "-c", "python scripts/init_db.py && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --loop uvloop --log-level info"]
