import json
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.datastructures import Headers
from app.config import config


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        content_length = headers.get("content-length")

        if content_length:
            try:
                if int(content_length) > config.MAX_REQUEST_BODY_SIZE:
                    await self._send_413(send)
                    return
            except ValueError:
                pass

        received_bytes = 0
        limit_exceeded = False

        async def guarded_receive() -> dict:
            nonlocal received_bytes, limit_exceeded
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > config.MAX_REQUEST_BODY_SIZE:
                    limit_exceeded = True
                    return {"type": "http.request", "body": b"", "more_body": False}
            return message

        response_started = False

        async def guarded_send(message: dict) -> None:
            nonlocal response_started
            if limit_exceeded:
                if not response_started and message["type"] == "http.response.start":
                    response_started = True
                    await self._send_413(send)
                return
            await send(message)

        await self.app(scope, guarded_receive, guarded_send)

    @staticmethod
    async def _send_413(send: Send) -> None:
        body = json.dumps({
            "detalle": f"El cuerpo excede el límite de {config.MAX_REQUEST_BODY_SIZE // (1024 * 1024)} MB"
        }).encode()
        await send({
            "type": "http.response.start",
            "status": 413,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(body)).encode()],
            ],
        })
        await send({"type": "http.response.body", "body": body, "more_body": False})
