"""
Structured JSON logging for production.
Outputs machine-parseable JSON so log aggregators (ELK, Grafana Loki)
can index fields like request_id, status_code, duration_ms directly.
"""
import logging
import json
import time
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Formats every log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        log = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            log["exc"] = self.formatException(record.exc_info)
        # Attach any extra fields (e.g. request_id, path, duration_ms)
        for key, val in record.__dict__.items():
            if key not in (
                "msg", "args", "levelname", "name", "exc_info",
                "exc_text", "stack_info", "lineno", "funcName",
                "pathname", "filename", "module", "created",
                "msecs", "relativeCreated", "thread", "threadName",
                "processName", "process", "message", "taskName",
            ):
                if not key.startswith("_"):
                    log[key] = val
        return json.dumps(log, default=str)


def configure_logging(debug: bool = False) -> None:
    """Wire up JSON logging for the entire application."""
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(handlers=[handler], level=level, force=True)
    # Silence noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
