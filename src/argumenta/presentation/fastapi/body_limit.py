"""A cap on the request body that counts the bytes that actually arrive."""

from fastapi import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_REFUSAL = b'{"detail":"RequestTooLarge"}'


class LimitRequestBody:
    """Content-Length is a hint a client may simply not send: a chunked body
    declares nothing, and FastAPI materializes and json-parses the whole thing
    before validation or auth, so 60 MB is hundreds of MB of RSS."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self._app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
        elif self._declared(scope) > self._max_bytes:
            await self._refuse(send)
        else:
            await self._app(scope, self._counted(receive), send)

    def _declared(self, scope: Scope) -> int:
        """The cheap path: a declared oversize body is refused without reading."""
        for name, value in scope.get("headers", ()):
            if name == b"content-length" and value.isdigit():
                return int(value)
        return 0

    def _counted(self, receive: Receive) -> Receive:
        """Raised from inside the read, which FastAPI re-raises untouched for an
        HTTPException, so the client gets the 413 and not a parse error."""
        received = 0

        async def counted() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self._max_bytes:
                    raise HTTPException(status_code=413, detail="RequestTooLarge")
            return message

        return counted

    async def _refuse(self, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(_REFUSAL)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": _REFUSAL})
