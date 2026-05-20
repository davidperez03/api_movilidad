import hashlib
import json
import re
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.infrastructure.cache.redis_service import RedisService
from app.config import config

METODOS_IDEMPOTENTES = {"POST", "PATCH", "DELETE", "PUT"}
_KEY_PATTERN     = re.compile(r"^[a-zA-Z0-9\-_]{1,256}$")

# Endpoints excluidos: manejan estado propio (tokens con expiración, etc.)
_EXCLUIR_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/logout",
    "/api/v1/auth/refresh",
    "/api/v1/auth/verificar-email",
    "/api/v1/auth/reenviar-verificacion",
    "/api/v1/auth/solicitar-reset-password",
    "/api/v1/auth/reset-password",
}


class IdempotencyMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method not in METODOS_IDEMPOTENTES:
            return await call_next(request)

        if request.url.path in _EXCLUIR_PATHS:
            return await call_next(request)

        body_bytes = await request.body()
        body_hash  = hashlib.sha256(body_bytes).hexdigest()

        explicit_key = request.headers.get("Idempotency-Key")

        if explicit_key:
            # ── Modo explícito: key enviada por el cliente ─────────────────────
            if not _KEY_PATTERN.match(explicit_key):
                return JSONResponse(
                    status_code=400,
                    content={"detalle": "Idempotency-Key inválida. Use UUID o alfanumérico (máx 256 chars)."},
                )
            auth = request.headers.get("Authorization", "")
            ctx  = hashlib.sha256(auth.encode()).hexdigest()[:24] if auth else \
                   hashlib.sha256(f"{request.client.host if request.client else ''}:{request.headers.get('User-Agent','')}".encode()).hexdigest()[:24]
            cache_key    = f"idempotency:{ctx}:{request.url.path}:{explicit_key}"
            ttl          = config.IDEMPOTENCY_TTL
            check_body   = True   # en modo explícito validamos que el body no cambió

        else:
            # ── Modo automático: fingerprint del request ───────────────────────
            # Detecta doble-click o reenvío accidental dentro de la ventana corta.
            # El front no necesita hacer nada — el backend lo maneja solo.
            auth        = request.headers.get("Authorization", "")
            fingerprint = hashlib.sha256(
                f"{auth}:{request.method}:{request.url.path}:{body_hash}".encode()
            ).hexdigest()[:32]
            cache_key  = f"idempotency_auto:{fingerprint}"
            ttl        = config.IDEMPOTENCY_AUTO_TTL
            check_body = False  # el body ya está en el fingerprint, no hay nada que validar

        cache = RedisService()

        # ── Verificar cache existente ─────────────────────────────────────────
        cached = await cache.get(cache_key)
        if cached:
            data = json.loads(cached)

            if data.get("estado") == "en_vuelo":
                return JSONResponse(
                    status_code=409,
                    content={"detalle": "Solicitud duplicada en progreso. Esperá unos segundos."},
                    headers={"Retry-After": str(config.IDEMPOTENCY_IN_FLIGHT_TTL)},
                )

            # Solo en modo explícito: detectar reuso de key con body distinto
            if check_body and data.get("body_hash") and data["body_hash"] != body_hash:
                return JSONResponse(
                    status_code=422,
                    content={"detalle": "Idempotency-Key ya fue utilizada con parámetros distintos."},
                )

            if data.get("status") == 204:
                return Response(
                    status_code=204,
                    headers={"Idempotent-Replayed": "true"},
                )
            return JSONResponse(
                content=data["body"],
                status_code=data["status"],
                headers={"Idempotent-Replayed": "true"},
            )

        # ── Adquirir lock atómico ─────────────────────────────────────────────
        lock_adquirido = await cache.set_nx(
            cache_key,
            json.dumps({"estado": "en_vuelo"}),
            config.IDEMPOTENCY_IN_FLIGHT_TTL,
        )
        if not lock_adquirido:
            return JSONResponse(
                status_code=409,
                content={"detalle": "Solicitud duplicada en progreso. Esperá unos segundos."},
                headers={"Retry-After": str(config.IDEMPOTENCY_IN_FLIGHT_TTL)},
            )

        # ── Ejecutar handler ──────────────────────────────────────────────────
        try:
            response = await call_next(request)
        except Exception:
            await cache.delete(cache_key)
            raise

        # ── Cachear respuestas exitosas ───────────────────────────────────────
        if 200 <= response.status_code < 300:

            if response.status_code == 204:
                await cache.set(
                    cache_key,
                    json.dumps({"status": 204, "body": None, "body_hash": body_hash}),
                    ttl,
                )
                return Response(status_code=204, headers={"Idempotent-Replayed": "false"})

            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk

            if len(response_body) <= config.IDEMPOTENCY_MAX_BODY_CACHE_KB * 1024:
                try:
                    body = json.loads(response_body)
                    await cache.set(
                        cache_key,
                        json.dumps({"status": response.status_code, "body": body, "body_hash": body_hash}),
                        ttl,
                    )
                except (json.JSONDecodeError, Exception):
                    await cache.delete(cache_key)

            headers = dict(response.headers)
            headers.pop("content-length", None)
            headers["Idempotent-Replayed"] = "false"
            return Response(
                content=response_body,
                status_code=response.status_code,
                media_type=response.media_type,
                headers=headers,
            )

        # Error: liberar lock para que el cliente pueda reintentar
        await cache.delete(cache_key)
        return response
