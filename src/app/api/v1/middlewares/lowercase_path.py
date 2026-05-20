from starlette.types import ASGIApp, Receive, Scope, Send


class LowerCasePathMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            scope["path"] = scope["path"].lower()
            scope["raw_path"] = scope["path"].encode("latin-1")
        await self.app(scope, receive, send)
