import logging
import sys
from typing import Any, cast

import orjson
import structlog
from structlog.typing import EventDict, FilteringBoundLogger

_REDACTED_KEYS = frozenset({"payload", "text", "result", "original", "masked", "body", "content"})

_CURRENT_LEVEL = logging.INFO

_METHOD_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "warn": logging.WARNING,
    "error": logging.ERROR,
    "exception": logging.ERROR,
    "critical": logging.CRITICAL,
    "fatal": logging.CRITICAL,
}


def _filter_by_level(_logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    level = _METHOD_LEVELS.get(method_name, logging.INFO)
    if level < _CURRENT_LEVEL:
        raise structlog.DropEvent
    return event_dict


def _redact_sensitive(_logger: Any, _method_name: str, event_dict: EventDict) -> EventDict:
    for key in _REDACTED_KEYS:
        event_dict.pop(key, None)
    return event_dict


def _orjson_serializer(_logger: Any, _method_name: str, event_dict: EventDict) -> str:
    return orjson.dumps(event_dict, default=str).decode()


class _StdoutLogger:
    def msg(self, message: str) -> None:
        sys.stdout.write(message + "\n")
        sys.stdout.flush()

    debug = msg
    info = msg
    warning = msg
    error = msg
    critical = msg
    exception = msg
    fatal = msg
    failure = msg
    log = msg
    err = msg


class _StdoutLoggerFactory:
    def __call__(self, *args: Any, **kwargs: Any) -> _StdoutLogger:
        return _StdoutLogger()


def configure_logging(level: str) -> None:
    global _CURRENT_LEVEL
    _CURRENT_LEVEL = getattr(logging, level.upper(), logging.INFO)

    structlog.configure(
        processors=[
            _filter_by_level,
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact_sensitive,
            _orjson_serializer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.NOTSET),
        logger_factory=_StdoutLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> FilteringBoundLogger:
    return cast(FilteringBoundLogger, structlog.get_logger(name))
