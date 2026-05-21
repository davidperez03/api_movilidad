from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from app.domain.entities.nunc.sesion import EstadoSesionNunc


class CrearSesionNuncRequest(BaseModel):
    nombre_entidad: str = Field(..., min_length=3, max_length=300)
    nombre_perito: str = Field(..., min_length=3, max_length=300)
    departamento: str = Field(..., min_length=1, max_length=10)
    municipio: str = Field(..., min_length=1, max_length=10)
    entidad: str = Field(..., min_length=1, max_length=10)
    unidad: str = Field(..., min_length=1, max_length=10)
    ano: str = Field(..., min_length=4, max_length=4, pattern=r"^\d{4}$")


class SesionNuncResponse(BaseModel):
    id: str                     # public_id
    codigo_sesion: str
    nombre_entidad: str
    nombre_perito: str
    estado: EstadoSesionNunc
    expiracion: datetime
    creado_en: datetime

    model_config = {"from_attributes": True}


class ValidarSesionRequest(BaseModel):
    codigo: str = Field(..., min_length=4, max_length=15)


class ValidarSesionResponse(BaseModel):
    valida: bool
    codigo: str
    expiracion: datetime | None = None
    mensaje: str = ""


class CrearRegistroRequest(BaseModel):
    sesion_codigo: str = Field(..., min_length=4, max_length=15)
    placa: str = Field(..., min_length=5, max_length=10)
    departamento: str = Field(..., min_length=1, max_length=10)
    municipio: str = Field(..., min_length=1, max_length=10)
    entidad: str = Field(..., min_length=1, max_length=10)
    unidad: str = Field(..., min_length=1, max_length=10)
    ano: str = Field(..., min_length=4, max_length=4, pattern=r"^\d{4}$")


class RegistroNuncResponse(BaseModel):
    id: str                     # public_id
    sesion_id: UUID
    placa: str
    departamento: str
    municipio: str
    entidad: str
    unidad: str
    ano: str
    numero_secuencial: int
    creado_en: datetime

    model_config = {"from_attributes": True}
