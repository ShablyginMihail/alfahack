import logging
import sys
from typing import Any, cast

import orjson
import structlog
from structlog.typing import EventDict, FilteringBoundLogger

_REDACTED_KEYS = frozenset({"payload", "text", "result", "original", "masked", "body", "content"})


def _redact_sensitive(_logger: Any, _method_name: str, event_dict: EventDict) -> EventDict:
    for key in _REDACTED_KEYS:
        event_dict.pop(key, None)
    return event_dict


def _orjson_serializer(_logger: Any, _method_name: str, event_dict: EventDict) -> str:
    return orjson.dumps(event_dict, default=str).decode()


def configure_logging(level: str) -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact_sensitive,
            _orjson_serializer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> FilteringBoundLogger:
    return cast(FilteringBoundLogger, structlog.get_logger(name))
