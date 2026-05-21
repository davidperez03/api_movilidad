from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from app.domain.entities.movilidad.cuenta import TipoServicio


class CrearCuentaRequest(BaseModel):
    placa: str = Field(..., min_length=5, max_length=10, pattern=r"^[A-Za-z0-9]+$")
    tipo_servicio: TipoServicio
    propietario_nombre: str = Field(..., min_length=3, max_length=200)
    propietario_documento: str = Field(..., min_length=5, max_length=30)


class CuentaResponse(BaseModel):
    id: str
    numero_cuenta: str
    placa: str
    tipo_servicio: TipoServicio
    propietario_nombre: str
    propietario_documento: str
    activo: bool
    creado_en: datetime

    model_config = {"from_attributes": True}


class ConsultaPublicaCuentaResponse(BaseModel):
    numero_cuenta: str
    placa: str
    tipo_servicio: TipoServicio
    activo: bool
