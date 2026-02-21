import uuid
import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.logging_config import configure_logging
from app.routers import transactions, returns, performance

settings = get_settings()
configure_logging(debug=settings.debug)
logger = logging.getLogger(__name__)


# ── Lifespan: startup / shutdown hooks ───────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up", extra={"version": settings.app_version})
    yield
    logger.info("Shutting down cleanly")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    description=(
        "Production-grade API for automated retirement savings using "
        "expense-based micro-investments. Supports NPS and Index Fund vehicles.\n\n"
        "**Base path:** `/blackrock/challenge/v1`"
    ),
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    servers=[
        {"url": "http://localhost:5477", "description": "Local direct (uvicorn)"},
        {"url": "http://localhost",      "description": "Local via Nginx (port 80)"},
    ],
)

# ── CORS — must be added BEFORE other middleware ──────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request ID + structured access logging (added AFTER CORS) ────────────────
class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = str(duration_ms)

        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response


app.add_middleware(RequestContextMiddleware)


# ── Global exception handler — never leak a stack trace to clients ────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.error(
        "Unhandled exception",
        exc_info=exc,
        extra={"request_id": request_id, "path": request.url.path},
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred. Use X-Request-ID to trace.",
            "request_id": request_id,
        },
    )


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(transactions.router)
app.include_router(returns.router)
app.include_router(performance.router)


# ── Health / readiness endpoints ──────────────────────────────────────────────
@app.get("/health", tags=["Health"], summary="Liveness probe")
def health():
    """Returns 200 if the process is alive. Used by Docker/K8s liveness probe."""
    return {"status": "ok", "version": settings.app_version}


@app.get("/ready", tags=["Health"], summary="Readiness probe")
async def ready():
    """Returns 200 if the app can serve traffic (Redis reachable).
    Used by K8s readiness probe — removes pod from load balancer if it fails.
    """
    from app.core.cache import _get_redis
    redis_ok = False
    try:
        r = await _get_redis()
        if r:
            await r.ping()
            redis_ok = True
    except Exception:
        pass

    if not redis_ok:
        # Still serve traffic but warn operators (Redis is optional)
        return JSONResponse(status_code=200, content={
            "status": "degraded",
            "redis": "unavailable",
            "note": "Serving without cache — performance reduced",
        })

    return {"status": "ready", "redis": "ok"}


@app.get("/", tags=["Health"], include_in_schema=False)
def root():
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}
