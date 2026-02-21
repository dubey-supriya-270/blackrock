# ── Stage 1: Builder — compile dependencies with build tools ──────────────────
FROM python:3.12-slim AS builder

# Install build tools needed for some native extensions (e.g. hiredis)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Runtime — minimal image, no build tools ─────────────────────────
FROM python:3.12-slim AS runtime

# OS-level tuning for high-throughput networking:
# - PYTHONOPTIMIZE: strip assert statements and docstrings (-O flag)
# - PYTHONUNBUFFERED: immediate stdout/stderr flush (important for logs)
# - PYTHONDONTWRITEBYTECODE: no .pyc clutter in container
# - MALLOC_ARENA_MAX: limit glibc memory arenas (reduces RSS under load)
# - MALLOC_TRIM_THRESHOLD: return freed memory to OS sooner
ENV PYTHONOPTIMIZE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MALLOC_ARENA_MAX=2 \
    MALLOC_TRIM_THRESHOLD_=131072 \
    REDIS_URL=redis://redis:6379/0 \
    CACHE_TTL_SECONDS=60 \
    REDIS_POOL_SIZE=50 \
    L1_CACHE_MAXSIZE=4096

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

WORKDIR /app
COPY . .

EXPOSE 5477

# OS-aware worker count:
#   Workers = 2 × CPU cores + 1  (Gunicorn formula, valid for uvicorn too)
#   With 8 CPUs → 17 workers; we cap at 16 for safety.
#   --loop uvloop: C-based asyncio loop, 2–4× faster than CPython default
#   --http httptools: C-based HTTP parser (replaces h11 pure-Python parser)
#   --backlog 4096: matches kernel's net.core.somaxconn
#   --timeout-keep-alive 5: recycle idle connections faster
#   --limit-concurrency 1000: prevent worker saturation
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "5477", \
     "--workers", "16", \
     "--loop", "uvloop", \
     "--http", "httptools", \
     "--backlog", "4096", \
     "--timeout-keep-alive", "5", \
     "--limit-concurrency", "1000"]
