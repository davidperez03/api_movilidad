import hashlib
from fastapi import HTTPException, Request, status
from app.infrastructure.cache.redis_service import get_redis_client


def _extraer_ip_real(request: Request) -> str:
    """
    Usa la IP que Uvicorn ya validó contra --forwarded-allow-ips.
    No leer X-Forwarded-For directamente: cualquier cliente puede falsificarlo,
    permitiendo bypasear el rate limiter con headers inventados.
    """
    return request.client.host if request.client else "127.0.0.1"


class AsyncRateLimiter:
    """
    Rate limiter distribuido con Redis (fixed window).
    Compartido entre todas las instancias/workers — apto para Kubernetes.
    La IP se obtiene de request.client.host (ya validada por Uvicorn contra FORWARDED_ALLOW_IPS).
    """

    def __init__(self, times: int, seconds: int):
        self.times = times
        self.seconds = seconds

    async def __call__(self, request: Request) -> None:
        ip = _extraer_ip_real(request)
        key = f"ratelimit:{ip}:{request.url.path}:{self.times}:{self.seconds}"
        client = get_redis_client()

        pipe = client.pipeline(transaction=True)
        pipe.set(key, 0, nx=True, ex=self.seconds)
        pipe.incr(key)
        results = await pipe.execute()
        current = results[1]

        if current > self.times:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiadas solicitudes. Intenta de nuevo más tarde.",
            )


class AsyncLoginRateLimiter:
    """
    Rate limiter específico para login: clave = hash(email + IP).
    Previene credential stuffing distribuido incluso detrás de proxies.
    """

    def __init__(self, times: int, seconds: int):
        self.times = times
        self.seconds = seconds

    async def __call__(self, request: Request) -> None:
        ip = _extraer_ip_real(request)

        try:
            import json
            body_bytes = await request.body()
            data = json.loads(body_bytes)
            email_raw = str(data.get("email", "")).lower().strip()[:200]
        except Exception:
            email_raw = ""

        ctx = hashlib.sha256(f"{email_raw}:{ip}".encode()).hexdigest()[:32]
        key = f"ratelimit_login:{ctx}:{self.times}:{self.seconds}"
        client = get_redis_client()

        pipe = client.pipeline(transaction=True)
        pipe.set(key, 0, nx=True, ex=self.seconds)
        pipe.incr(key)
        results = await pipe.execute()
        current = results[1]

        if current > self.times:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiadas solicitudes. Intenta de nuevo más tarde.",
            )
