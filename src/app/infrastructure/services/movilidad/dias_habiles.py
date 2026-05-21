from datetime import date, timedelta
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.ports.outbound.movilidad.servicio_dias_habiles import ServicioDiasHabilesPort


class DiasHabilesService(ServicioDiasHabilesPort):
    """Delega al motor PostgreSQL (funciones es_dia_habil / sumar_dias_habiles)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def es_dia_habil(self, fecha: date) -> bool:
        result = await self._session.execute(
            text("SELECT es_dia_habil(:f)"), {"f": fecha}
        )
        return bool(result.scalar_one())

    async def sumar_dias_habiles(self, desde: date, dias: int) -> date:
        result = await self._session.execute(
            text("SELECT sumar_dias_habiles(:d, :n)"), {"d": desde, "n": dias}
        )
        return result.scalar_one()

    async def contar_dias_habiles(self, desde: date, hasta: date) -> int:
        result = await self._session.execute(
            text("SELECT contar_dias_habiles(:d, :h)"), {"d": desde, "h": hasta}
        )
        return int(result.scalar_one())
