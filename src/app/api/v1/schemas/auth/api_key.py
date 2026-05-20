import re
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from app.config import PERMISOS_SISTEMA

_PATRON_PERMISO = re.compile(r"^[a-z_]+:[a-z_]+$")


class CrearApiKeyRequest(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=200)
    permisos: list[str] = Field(default_factory=list, max_length=20)
    expira_en: datetime | None = None

    @field_validator("permisos")
    @classmethod
    def validar_permisos(cls, v: list[str]) -> list[str]:
        invalidos = []
        for p in v:
            if len(p) > 100:
                raise ValueError(f"Permiso demasiado largo (máx 100 caracteres): '{p[:20]}...'")
            if not _PATRON_PERMISO.match(p):
                raise ValueError(f"Formato inválido: '{p}'. Use 'recurso:accion' (solo minúsculas y guión bajo)")
            if p not in PERMISOS_SISTEMA:
                invalidos.append(p)
        if invalidos:
            raise ValueError(
                f"Permisos no reconocidos: {invalidos}. "
                f"Permisos válidos: {sorted(PERMISOS_SISTEMA)}"
            )
        return v


class ApiKeyResponse(BaseModel):
    id: str
    nombre: str
    key_prefix: str
    permisos: list[str]
    activa: bool
    expira_en: datetime | None
    ultimo_uso: datetime | None
    creado_en: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreada(ApiKeyResponse):
    full_key: str
