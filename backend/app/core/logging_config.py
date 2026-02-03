"""
Central logging configuration.

Goals:
- One shared logging setup for FastAPI + Celery.
- JSON logs to stdout for easy aggregation.
- Correlate logs with request_id / task_id / guide_id.

Prototype-friendly (no external deps).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from logging.config import dictConfig

from app.core.request_context import get_context


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # Include contextvars (request/task/guide)
        base.update(get_context())

        # Include any `extra={...}` fields (best-effort)
        # (Avoid dumping huge objects.)
        for k, v in record.__dict__.items():
            if k in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
            }:
                continue
            if k.startswith("_"):
                continue
            if k in base:
                continue
            try:
                json.dumps(v)
                base[k] = v
            except Exception:
                base[k] = str(v)

        if record.exc_info:
            base["exc"] = self.formatException(record.exc_info)

        return json.dumps(base, ensure_ascii=False)


def configure_logging() -> None:
    """
    Call once at process startup (FastAPI + Celery).
    """
    level = os.getenv("LOG_LEVEL", "INFO").upper()

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {"()": "app.core.logging_config.JsonFormatter"},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "stream": sys.stdout,
            }
        },
        "root": {"level": level, "handlers": ["console"]},
        "loggers": {
            # Uvicorn loggers
            "uvicorn": {"level": level, "handlers": ["console"], "propagate": False},
            "uvicorn.error": {"level": level, "handlers": ["console"], "propagate": False},
            "uvicorn.access": {"level": level, "handlers": ["console"], "propagate": False},
            # Celery loggers
            "celery": {"level": level, "handlers": ["console"], "propagate": False},
        },
    }

    dictConfig(logging_config)
