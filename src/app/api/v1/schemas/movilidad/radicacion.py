from datetime import date, datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field
from app.domain.entities.movilidad.radicacion import EstadoRadicacion


class CrearRadicacionRequest(BaseModel):
    cuenta_public_id: str = Field(..., min_length=5)
    organismo_origen_id: Optional[UUID] = None
    empresa_transportadora_id: Optional[UUID] = None


class CambiarEstadoRadicacionRequest(BaseModel):
    nuevo_estado: EstadoRadicacion
    motivo: str = Field("", max_length=1000)
    numero_guia: str = Field("", max_length=100)
    numero_guia_devolucion: str = Field("", max_length=100)
    organismo_origen_id: Optional[UUID] = None
    empresa_transportadora_id: Optional[UUID] = None


class RadicacionResponse(BaseModel):
    id: str                                         # public_id
    cuenta_id: UUID
    organismo_origen_id: Optional[UUID]
    empresa_transportadora_id: Optional[UUID]
    estado: EstadoRadicacion
    numero_guia: str
    numero_guia_devolucion: str
    observaciones: str
    radicado_en: Optional[datetime]
    vencimiento: Optional[date]
    completado_en: Optional[datetime]
    creado_en: datetime
    transiciones_disponibles: list[EstadoRadicacion] = []

    model_config = {"from_attributes": True}
