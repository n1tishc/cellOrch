"""Structured JSON logging configuration.

All application logs are emitted as JSON lines so they are machine-parseable in
production. Extra context fields (request_id, run_id, stage, event_type, attempt,
error, path) are serialized when provided via the `extra=` keyword.
"""
import json
import logging
import sys
from contextvars import ContextVar

# Per-request correlation id; set by the HTTP middleware.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class JSONFormatter(logging.Formatter):
    """Format log records as JSON, preserving any extra context fields."""

    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Extra context fields that callers may attach.
        for key in ("request_id", "run_id", "stage", "event_type", "attempt", "error", "path"):
            value = getattr(record, key, None)
            if value is not None:
                data[key] = value

        # Attach the request id from the async context if it was not provided explicitly.
        if "request_id" not in data:
            request_id = request_id_var.get()
            if request_id is not None:
                data["request_id"] = request_id

        if record.exc_info:
            data["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(data)


def configure_logging(level: int | str = logging.INFO) -> None:
    """Configure the root logger to emit JSON lines to stdout."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.handlers = []
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Return a logger that will emit JSON when configure_logging() was called."""
    return logging.getLogger(name)
