from datetime import datetime
from pydantic import BaseModel, Field


class CrearRolRequest(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)
    descripcion: str = Field("", max_length=255)


class PermisoResponse(BaseModel):
    clave: str
    recurso: str
    accion: str
    descripcion: str

    model_config = {"from_attributes": True}


class RolResponse(BaseModel):
    id: str
    nombre: str
    descripcion: str
    es_sistema: bool
    permisos: list[PermisoResponse]
    creado_en: datetime

    model_config = {"from_attributes": True}


class AsignarPermisoRequest(BaseModel):
    permiso_clave: str = Field(..., pattern=r"^[a-z_]+:[a-z_]+$")


class AsignarRolRequest(BaseModel):
    rol_public_id: str
    usuario_public_id: str
    vigente_hasta: datetime | None = None
