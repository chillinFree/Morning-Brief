from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from daily_brief.config.settings import LoggingConfig

_STANDARD_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "event"):
            payload["event"] = record.event
        if hasattr(record, "run_id"):
            payload["run_id"] = record.run_id
        if hasattr(record, "source"):
            payload["source"] = record.source
        if hasattr(record, "stage"):
            payload["stage"] = record.stage
        if hasattr(record, "status"):
            payload["status"] = record.status
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in _STANDARD_ATTRS or key in payload:
                continue
            payload[key] = value
        return json.dumps(payload)


def configure_logging(config: LoggingConfig) -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(config.level.upper())

    handler = logging.StreamHandler()
    if config.json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root_logger.addHandler(handler)
