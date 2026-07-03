"""Request body size limiting middleware to mitigate payload-based DoS attacks."""
from __future__ import annotations

import json
from typing import Iterable, Optional

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class _RequestSizeExceededError(Exception):
    """Raised when incoming request body exceeds configured maximum size."""


class RequestSizeLimitMiddleware:
    """
    ASGI middleware that enforces a maximum HTTP request body size.

    The middleware applies two checks:
    1. Fast fail using Content-Length (when present)
    2. Streaming byte count check for chunked/unknown-length payloads
    """

    def __init__(
        self,
        app: ASGIApp,
        max_content_length: int,
        exclude_paths: Optional[Iterable[str]] = None,
    ) -> None:
        self.app = app
        self.max_content_length = max(1, int(max_content_length))
        self.exclude_paths = tuple(exclude_paths or ())

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if self._is_excluded_path(path):
            await self.app(scope, receive, send)
            return

        content_length = self._get_content_length(scope)
        if content_length is not None and content_length > self.max_content_length:
            await self._send_payload_too_large(send)
            return

        bytes_received = 0
        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal response_started
            if message.get("type") == "http.response.start":
                response_started = True
            await send(message)

        async def receive_wrapper() -> Message:
            nonlocal bytes_received
            message = await receive()
            if message.get("type") == "http.request":
                bytes_received += len(message.get("body", b""))
                if bytes_received > self.max_content_length:
                    raise _RequestSizeExceededError
            return message

        try:
            await self.app(scope, receive_wrapper, send_wrapper)
        except _RequestSizeExceededError:
            if not response_started:
                await self._send_payload_too_large(send)

    def _is_excluded_path(self, path: str) -> bool:
        return any(path == excluded or path.startswith(excluded + "/") for excluded in self.exclude_paths)

    @staticmethod
    def _get_content_length(scope: Scope) -> Optional[int]:
        for key, value in scope.get("headers", []):
            if key == b"content-length":
                try:
                    return int(value.decode("latin-1"))
                except (TypeError, ValueError):
                    return None
        return None

    async def _send_payload_too_large(self, send: Send) -> None:
        payload = {
            "error": "payload_too_large",
            "error_code": "REQ_001",
            "message": f"Request body exceeds maximum allowed size ({self.max_content_length} bytes)",
            "max_bytes": self.max_content_length,
        }
        body = json.dumps(payload).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body, "more_body": False})
