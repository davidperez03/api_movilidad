from datetime import date, datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field
from app.domain.entities.parqueadero.vehiculo import TipoVehiculoParqueadero


class CrearVehiculoRequest(BaseModel):
    placa: str = Field(..., min_length=5, max_length=10, pattern=r"^[A-Za-z0-9]+$")
    tipo_vehiculo: TipoVehiculoParqueadero
    marca: str = Field("", max_length=100)
    modelo: str = Field("", max_length=100)
    soat_aseguradora: str = Field("", max_length=200)
    soat_vencimiento: Optional[date] = None
    tecnomecanica_vencimiento: Optional[date] = None


class ActualizarVehiculoRequest(BaseModel):
    marca: str | None = Field(None, max_length=100)
    modelo: str | None = Field(None, max_length=100)
    tipo_vehiculo: TipoVehiculoParqueadero | None = None
    soat_aseguradora: str | None = Field(None, max_length=200)
    soat_vencimiento: Optional[date] = None
    tecnomecanica_vencimiento: Optional[date] = None


class VehiculoResponse(BaseModel):
    id: str                     # public_id
    placa: str
    tipo_vehiculo: TipoVehiculoParqueadero
    marca: str
    modelo: str
    soat_aseguradora: str
    soat_vencimiento: Optional[date]
    tecnomecanica_vencimiento: Optional[date]
    activo: bool
    creado_en: datetime

    model_config = {"from_attributes": True}
