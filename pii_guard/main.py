import re
import time
import traceback
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from pii_guard.api import admin, errors, health, mask, metrics, process, ui
from pii_guard.config.loader import ConfigStore
from pii_guard.core.engine import Engine
from pii_guard.core.policy import CHECKER_PROFILE
from pii_guard.observability.logging import configure_logging, get_logger
from pii_guard.observability.metrics import (
    endpoint_label,
    observe_request,
    set_store_degraded,
)
from pii_guard.services.process import ProcessService
from pii_guard.settings import Settings, get_settings
from pii_guard.store.base import MappingStore
from pii_guard.store.crypto import RecordCipher, decode_key
from pii_guard.store.failover import FailoverStore
from pii_guard.store.memory import MemoryStore
from pii_guard.store.redis_store import RedisStore, create_redis_client

logger = get_logger("pii_guard.request")

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def warm_up(engine: Engine) -> None:
    from pii_guard.recognizers.names import get_morph

    get_morph()
    engine.mask("тест", CHECKER_PROFILE)


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = self._extract_request_id(scope)
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.perf_counter()
        status = 500
        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status = message.get("status", 500)
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            if not response_started:
                await self._send_error(send, request_id)
            self._log_unhandled(exc)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            endpoint = endpoint_label(scope.get("path", ""))
            observe_request(endpoint, status, duration_ms / 1000)
            logger.info(
                "request",
                method=scope.get("method"),
                path=scope.get("path"),
                status=status,
                duration_ms=round(duration_ms, 3),
            )
            structlog.contextvars.unbind_contextvars("request_id")

    @staticmethod
    def _extract_request_id(scope: Scope) -> str:
        for name, value in scope.get("headers", []):
            if name == b"x-request-id":
                candidate: str = value.decode("latin-1")
                if _REQUEST_ID_RE.match(candidate):
                    return candidate
                break
        return uuid.uuid4().hex

    @staticmethod
    def _log_unhandled(exc: Exception) -> None:
        tb = traceback.extract_tb(exc.__traceback__)
        frame = tb[-1] if tb else None
        location = f"{frame.filename}:{frame.lineno}" if frame else "unknown"
        logger.error(
            "unhandled_exception",
            exc_type=type(exc).__name__,
            location=location,
        )

    @staticmethod
    async def _send_error(send: Send, request_id: str) -> None:
        body = b'{"error": "internal_error", "request_id": "' + request_id.encode("latin-1") + b'"}'
        await send(
            {
                "type": "http.response.start",
                "status": 500,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"x-request-id", request_id.encode("latin-1")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_body_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.max_body_bytes:
                    await self._reject(send)
                    return
            except ValueError:
                pass

        await self.app(scope, receive, send)

    async def _reject(self, send: Send) -> None:
        body = b'{"error": "payload_too_large"}'
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def create_app(
    settings: Settings | None = None,
) -> FastAPI:
    if settings is None:
        settings = get_settings()

    encryption_key = decode_key(
        settings.encryption_key.get_secret_value() if settings.encryption_key else None
    )
    hmac_key = decode_key(settings.hmac_key.get_secret_value() if settings.hmac_key else None)
    if settings.encryption_key is None or settings.hmac_key is None:
        logger.warning("crypto keys not configured, generated ephemeral keys")

    cipher = RecordCipher(encryption_key, hmac_key)
    config_store = ConfigStore(settings.config_dir, settings.recognizer_modules)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.log_level)
        store: MappingStore
        if settings.redis_url:
            store = FailoverStore(
                RedisStore(create_redis_client(settings.redis_url), cipher),
                MemoryStore(cipher),
            )
        else:
            store = MemoryStore(cipher)
        service = ProcessService(
            config_store,
            store,
            cipher,
            settings.mapping_ttl_seconds,
        )
        app.state.store = store
        app.state.process_service = service
        app.state.cipher = cipher
        app.state.config_store = config_store
        set_store_degraded(store.backend == "redis-degraded")
        _, engine = config_store.current()
        warm_up(engine)
        try:
            yield
        finally:
            await store.close()

    app = FastAPI(
        title="PII Guard",
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.add_middleware(BodyLimitMiddleware, max_body_bytes=settings.max_body_bytes)
    app.add_middleware(RequestContextMiddleware)

    errors.register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(process.router)
    app.include_router(mask.router)
    app.include_router(admin.router)
    app.include_router(metrics.router)
    app.include_router(ui.router)
    app.mount("/static", StaticFiles(directory=ui.STATIC_DIR), name="static")

    return app


app = create_app()
