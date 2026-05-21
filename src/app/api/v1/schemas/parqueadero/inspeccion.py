from datetime import date, time, datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field
from app.domain.entities.parqueadero.inspeccion import TurnoInspeccion


class CrearInspeccionRequest(BaseModel):
    vehiculo_public_id: str = Field(..., min_length=5)
    operador_id: UUID
    inspector_id: UUID
    auxiliar_id: Optional[UUID] = None
    fecha: date
    hora: time
    turno: TurnoInspeccion
    observaciones: str = Field("", max_length=2000)
    fotos: list[str] = Field(default_factory=list, max_length=5)
    soat_vencimiento_snap: Optional[date] = None
    tecnomecanica_vencimiento_snap: Optional[date] = None
    licencia_vencimiento_snap: Optional[date] = None


class AprobarInspeccionRequest(BaseModel):
    es_apto: bool
    firma_operador: str = Field("", max_length=5000)
    firma_inspector: str = Field("", max_length=5000)
    observaciones: str = Field("", max_length=2000)


class InspeccionResponse(BaseModel):
    id: str                     # public_id
    codigo: str
    vehiculo_id: UUID
    operador_id: UUID
    inspector_id: UUID
    auxiliar_id: Optional[UUID]
    fecha: date
    hora: time
    turno: TurnoInspeccion
    es_apto: bool
    observaciones: str
    firma_operador: str
    firma_inspector: str
    fotos: list[str]
    soat_vencimiento_snap: Optional[date]
    tecnomecanica_vencimiento_snap: Optional[date]
    licencia_vencimiento_snap: Optional[date]
    creado_en: datetime

    model_config = {"from_attributes": True}
