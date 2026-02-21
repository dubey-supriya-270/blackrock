import time
import threading
import psutil
import os
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/blackrock/challenge/v1", tags=["Performance"])


class PerformanceResponse(BaseModel):
    time_ms: float
    memory_mb: float
    threads: int


@router.get("/performance", response_model=PerformanceResponse)
def performance(request: Request) -> PerformanceResponse:
    """Report current server performance metrics."""
    start = time.perf_counter()

    process = psutil.Process(os.getpid())
    memory_mb = process.memory_info().rss / (1024 * 1024)
    thread_count = threading.active_count()

    elapsed_ms = (time.perf_counter() - start) * 1000

    return PerformanceResponse(
        time_ms=round(elapsed_ms, 3),
        memory_mb=round(memory_mb, 2),
        threads=thread_count,
    )
