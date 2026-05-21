from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field
from app.domain.entities.movilidad.novedad import TipoNovedad, PrioridadNovedad, EstadoNovedad


class CrearNovedadRequest(BaseModel):
    proceso_tipo: str = Field(..., pattern="^(traslado|radicacion)$")
    proceso_public_id: str = Field(..., min_length=5)
    tipo_novedad: TipoNovedad
    descripcion: str = Field(..., min_length=5, max_length=2000)
    prioridad: PrioridadNovedad = PrioridadNovedad.MEDIA


class ResolverNovedadRequest(BaseModel):
    solucion: str = Field(..., min_length=5, max_length=2000)


class NovedadResponse(BaseModel):
    id: str                             # public_id
    proceso_tipo: str
    proceso_id: UUID
    tipo_novedad: TipoNovedad
    prioridad: PrioridadNovedad
    descripcion: str
    estado: EstadoNovedad
    solucion: str
    resuelto_por: Optional[UUID]
    resuelto_en: Optional[datetime]
    creado_en: datetime

    model_config = {"from_attributes": True}
