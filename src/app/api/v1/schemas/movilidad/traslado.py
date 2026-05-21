from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field
from app.domain.entities.movilidad.traslado import EstadoTraslado


class CrearTrasladoRequest(BaseModel):
    cuenta_public_id: str = Field(..., min_length=5)
    organismo_destino_id: UUID


class CambiarEstadoTrasladoRequest(BaseModel):
    nuevo_estado: EstadoTraslado
    motivo: str = Field("", max_length=500)


class TrasladoResponse(BaseModel):
    id: str
    cuenta_id: UUID
    organismo_destino_id: UUID
    estado: EstadoTraslado
    observaciones: str
    vence_en: Optional[datetime]
    completado_en: Optional[datetime]
    creado_en: datetime
    transiciones_disponibles: list[EstadoTraslado] = []

    model_config = {"from_attributes": True}
