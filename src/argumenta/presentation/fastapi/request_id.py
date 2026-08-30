"""One request id per request, trusted from the caller or minted, so every log
line during it carries the same correlator (issue #51). Raw ASGI, matching
LimitRequestBody: BaseHTTPMiddleware buffers streaming responses."""

import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from argumenta.adapters.observability.logging import request_id_var

_HEADER = b"x-request-id"


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        request_id = self._incoming(scope) or str(uuid.uuid4())
        token = request_id_var.set(request_id)
        try:
            await self._app(scope, receive, self._tagged(send, request_id))
        finally:
            request_id_var.reset(token)

    def _incoming(self, scope: Scope) -> str | None:
        for name, value in scope.get("headers", ()):
            if name == _HEADER:
                decoded: str = value.decode()
                return decoded
        return None

    def _tagged(self, send: Send, request_id: str) -> Send:
        async def tagged(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"].append((_HEADER, request_id.encode()))
            await send(message)

        return tagged
