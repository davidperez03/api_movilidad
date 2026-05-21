from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.persistence.modelos.movilidad.notificacion_radicacion_modelo import NotificacionRadicacionModelo


class NotificacionRadicacionRepositorioSQL:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def crear(self, radicacion_id: UUID, creado_por: UUID | None = None) -> NotificacionRadicacionModelo:
        modelo = NotificacionRadicacionModelo(
            id=uuid4(),
            radicacion_id=radicacion_id,
            solicitante_notificado=False,
            creado_por=creado_por,
        )
        self._session.add(modelo)
        await self._session.flush()
        return modelo

    async def buscar_por_radicacion(self, radicacion_id: UUID) -> Optional[NotificacionRadicacionModelo]:
        result = await self._session.execute(
            select(NotificacionRadicacionModelo).where(
                NotificacionRadicacionModelo.radicacion_id == radicacion_id
            )
        )
        return result.scalar_one_or_none()

    async def marcar_notificado(
        self,
        radicacion_id: UUID,
        observaciones: str | None,
        actor_id: UUID | None,
    ) -> NotificacionRadicacionModelo:
        modelo = await self.buscar_por_radicacion(radicacion_id)
        if not modelo:
            modelo = await self.crear(radicacion_id, creado_por=actor_id)
        modelo.solicitante_notificado = True
        modelo.notificado_en = datetime.now(timezone.utc)
        modelo.observaciones = observaciones
        modelo.actualizado_por = actor_id
        modelo.actualizado_en = datetime.now(timezone.utc)
        await self._session.flush()
        return modelo
