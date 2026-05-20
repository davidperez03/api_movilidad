from __future__ import annotations
import logging
import json
from typing import Optional, Set
import redis.asyncio as aioredis
from app.config import config
from app.domain.ports.outbound.auth.servicio_cache import ServicioCache

logger = logging.getLogger(__name__)

_pool: aioredis.ConnectionPool | None = None


def get_redis_client() -> aioredis.Redis:
    global _pool
    if _pool is None:
        _pool = aioredis.ConnectionPool.from_url(
            config.REDIS_URL,
            max_connections=config.REDIS_POOL_SIZE,
            decode_responses=True,
        )
    return aioredis.Redis(connection_pool=_pool)


async def close_redis_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


class RedisService(ServicioCache):

    def _client(self) -> aioredis.Redis:
        return get_redis_client()

    async def set(self, clave: str, valor: str, ttl_segundos: int) -> None:
        await self._client().setex(clave, ttl_segundos, valor)

    async def get(self, clave: str) -> Optional[str]:
        return await self._client().get(clave)

    async def delete(self, clave: str) -> None:
        await self._client().delete(clave)

    async def exists(self, clave: str) -> bool:
        return bool(await self._client().exists(clave))

    async def incr(self, clave: str, ttl_segundos: int = 60) -> int:
        # SET NX fija el TTL solo en la primera llamada (ventana fija).
        # Las siguientes solo incrementan sin resetear el TTL,
        # evitando el sliding window que permite evadir el lockout.
        pipe = self._client().pipeline(transaction=True)
        pipe.set(clave, 0, nx=True, ex=ttl_segundos)
        pipe.incr(clave)
        resultado = await pipe.execute()
        return resultado[1]

    async def sadd(self, clave: str, *valores: str, ttl_segundos: int = 0) -> None:
        async with self._client().pipeline(transaction=True) as pipe:
            pipe.sadd(clave, *valores)
            if ttl_segundos > 0:
                pipe.expire(clave, ttl_segundos)
            await pipe.execute()

    async def smembers(self, clave: str) -> Set[str]:
        return await self._client().smembers(clave)

    async def set_nx(self, clave: str, valor: str, ttl_segundos: int) -> bool:
        result = await self._client().set(clave, valor, nx=True, ex=ttl_segundos)
        return result is not None

    async def ttl(self, clave: str) -> int:
        return await self._client().ttl(clave)
