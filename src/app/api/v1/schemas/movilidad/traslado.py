from datetime import date, datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field
from app.domain.entities.movilidad.traslado import EstadoTraslado


class CrearTrasladoRequest(BaseModel):
    cuenta_public_id: str = Field(..., min_length=5)
    organismo_destino_id: UUID
    empresa_transportadora_id: Optional[UUID] = None


class CambiarEstadoTrasladoRequest(BaseModel):
    nuevo_estado: EstadoTraslado
    motivo: str = Field("", max_length=1000)
    numero_guia: str = Field("", max_length=100)
    organismo_destino_id: Optional[UUID] = None
    empresa_transportadora_id: Optional[UUID] = None


class TrasladoResponse(BaseModel):
    id: str                                         # public_id
    cuenta_id: UUID
    organismo_destino_id: Optional[UUID]
    empresa_transportadora_id: Optional[UUID]
    estado: EstadoTraslado
    numero_guia: str
    observaciones: str
    aprobado_en: Optional[datetime]
    vencimiento: Optional[date]
    completado_en: Optional[datetime]
    creado_en: datetime
    transiciones_disponibles: list[EstadoTraslado] = []
    dias_restantes: Optional[int] = None

    model_config = {"from_attributes": True}
