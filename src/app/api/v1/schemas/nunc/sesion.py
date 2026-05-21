from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from app.domain.entities.nunc.sesion import EstadoSesionNunc


class SesionNuncResponse(BaseModel):
    id: str
    codigo: str
    estado: EstadoSesionNunc
    expira_en: datetime
    creado_en: datetime

    model_config = {"from_attributes": True}


class ValidarSesionRequest(BaseModel):
    codigo: str = Field(..., min_length=10, max_length=20)


class ValidarSesionResponse(BaseModel):
    valida: bool
    codigo: str
    expira_en: datetime | None = None
    mensaje: str = ""


class CrearRegistroRequest(BaseModel):
    sesion_codigo: str = Field(..., min_length=10, max_length=20)
    placa: str = Field(..., min_length=5, max_length=10)
    nombre_conductor: str = Field(..., min_length=3, max_length=200)
    documento_conductor: str = Field(..., min_length=5, max_length=30)
    datos_forenses: dict = Field(default_factory=dict)


class RegistroNuncResponse(BaseModel):
    id: str
    sesion_id: UUID
    placa: str
    nombre_conductor: str
    documento_conductor: str
    numero_secuencial: int
    creado_en: datetime

    model_config = {"from_attributes": True}
