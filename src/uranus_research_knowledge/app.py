"""Authenticated offline query runtime. Provisioning is never imported here."""

import asyncio
import hmac
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from .clients import Clients, UpstreamError
from .config import Settings
from .evidence import answer, query
from .models import AnswerRequest, AnswerResponse, QueryRequest, QueryResponse


def error(code, status):
    return JSONResponse(
        {"error": {"code": code}}, status_code=status, headers={"Cache-Control": "no-store"}
    )


class Boundary:
    def __init__(self, app, settings):
        self.app, self.settings = app, settings
        self.slots = asyncio.Semaphore(settings.concurrency)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def safe_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [
                    (b"cache-control", b"no-store")
                ]
            await send(message)

        headers = dict(scope["headers"])
        keys = [v for k, v in scope["headers"] if k.lower() == b"authorization"]
        expected = ("Bearer " + self.settings.api_key.get_secret_value()).encode()
        if len(keys) != 1 or not hmac.compare_digest(keys[0], expected):
            return await error("unauthorized", 401)(scope, receive, safe_send)
        if scope["query_string"] or b"content-encoding" in headers:
            return await error("invalid_request", 422)(scope, receive, safe_send)
        if self.slots.locked():
            return await error("busy", 503)(scope, receive, safe_send)
        async with self.slots:
            body = bytearray()
            try:
                async with asyncio.timeout(5):
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        body.extend(message.get("body", b""))
                        if len(body) > 16 * 1024:
                            return await error("request_too_large", 413)(scope, receive, safe_send)
                        if not message.get("more_body", False):
                            break
            except TimeoutError:
                return await error("invalid_request", 422)(scope, receive, safe_send)
            if (
                scope["method"] == "POST"
                and headers.get(b"content-type", b"").split(b";")[0] != b"application/json"
            ):
                return await error("invalid_request", 422)(scope, receive, safe_send)
            consumed = False

            async def replay():
                nonlocal consumed
                if consumed:
                    return await receive()
                consumed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}

            await self.app(scope, replay, safe_send)


def create_app(settings: Settings | None = None, client=None):
    settings = settings or Settings()
    upstream = client or Clients(settings)

    @asynccontextmanager
    async def lifespan(app):
        yield
        await upstream.close()

    app = FastAPI(
        title="Kulturbytes Project Knowledge",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        redirect_slashes=False,
    )
    app.add_middleware(Boundary, settings=settings)

    @app.exception_handler(RequestValidationError)
    async def invalid(_request, _exc):
        return error("invalid_request", 422)

    @app.exception_handler(UpstreamError)
    async def unavailable(_request, _exc):
        return error("knowledge_unavailable", 503)

    @app.exception_handler(TimeoutError)
    async def timeout(_request, _exc):
        return error("knowledge_unavailable", 503)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/ready")
    async def ready():
        async with asyncio.timeout(settings.timeout_seconds):
            await upstream.check_collection()
        return {"status": "ready"}

    @app.post("/query", response_model=QueryResponse)
    async def search(body: QueryRequest):
        async with asyncio.timeout(settings.timeout_seconds):
            return await query(upstream, body)

    @app.post("/evidence-answer", response_model=AnswerResponse)
    async def fact_answer(body: AnswerRequest):
        async with asyncio.timeout(settings.timeout_seconds):
            return await answer(upstream, body)

    return app
