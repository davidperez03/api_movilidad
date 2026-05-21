from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field
from app.domain.entities.movilidad.radicacion import EstadoRadicacion


class CrearRadicacionRequest(BaseModel):
    traslado_public_id: str = Field(..., min_length=5)
    organismo_id: UUID


class CambiarEstadoRadicacionRequest(BaseModel):
    nuevo_estado: EstadoRadicacion
    motivo: str = Field("", max_length=500)
    numero_radicado: str = Field("", max_length=100)


class RadicacionResponse(BaseModel):
    id: str
    cuenta_id: UUID
    traslado_id: UUID
    organismo_id: UUID
    estado: EstadoRadicacion
    numero_radicado: str
    observaciones: str
    vence_en: Optional[datetime]
    completado_en: Optional[datetime]
    creado_en: datetime
    transiciones_disponibles: list[EstadoRadicacion] = []

    model_config = {"from_attributes": True}
