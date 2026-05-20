from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, SecretStr, field_validator, model_validator
from app.domain.entities.auth.usuario import EstadoUsuario

_ESPECIALES = set("!@#$%^&*()_+-=[]{}|;':\",./<>?")


def _validar_fortaleza_password(v: str) -> None:
    errores = []
    if not any(c.isupper() for c in v):
        errores.append("al menos una mayúscula")
    if not any(c.islower() for c in v):
        errores.append("al menos una minúscula")
    if not any(c.isdigit() for c in v):
        errores.append("al menos un número")
    if not any(c in _ESPECIALES for c in v):
        errores.append("al menos un carácter especial (!@#$%...)")
    if errores:
        raise ValueError("La contraseña debe contener: " + ", ".join(errores))


class CrearUsuarioRequest(BaseModel):
    email: EmailStr
    nombre: str = Field(..., min_length=2, max_length=100)
    apellido: str = Field(..., min_length=2, max_length=100)
    password: SecretStr = Field(..., min_length=8, max_length=128)

    @field_validator("password", mode="before")
    @classmethod
    def validar_password(cls, v: str) -> str:
        _validar_fortaleza_password(v)
        return v


class ActualizarUsuarioRequest(BaseModel):
    nombre: str | None = Field(None, min_length=2, max_length=100)
    apellido: str | None = Field(None, min_length=2, max_length=100)
    password_actual: SecretStr | None = None
    nueva_password: SecretStr | None = Field(None, min_length=8, max_length=128)

    @model_validator(mode="after")
    def validar_cambio_password(self) -> "ActualizarUsuarioRequest":
        if self.nueva_password and not self.password_actual:
            raise ValueError("Se requiere la contraseña actual para cambiarla")
        return self

    @field_validator("nueva_password", mode="before")
    @classmethod
    def validar_nueva_password(cls, v: str | None) -> str | None:
        if v is None:
            return v
        _validar_fortaleza_password(v)
        return v


class CambiarEstadoRequest(BaseModel):
    estado: EstadoUsuario
    razon: str | None = Field(None, max_length=500)


class RolResumen(BaseModel):
    id: str
    nombre: str
    descripcion: str

    model_config = {"from_attributes": True}


class UsuarioResponse(BaseModel):
    id: str
    email: str
    nombre: str
    apellido: str
    nombre_completo: str
    estado: EstadoUsuario
    email_verificado: bool
    ultimo_login: datetime | None
    creado_en: datetime

    model_config = {"from_attributes": True}


class UsuarioDetalleResponse(UsuarioResponse):
    roles: list[RolResumen] = []


class UsuarioResumen(BaseModel):
    id: str
    email: str
    nombre_completo: str
    estado: EstadoUsuario

    model_config = {"from_attributes": True}


class PaginaUsuariosResponse(BaseModel):
    items: list[UsuarioResumen]
    siguiente_cursor: str | None
    tamanio: int
    tiene_siguiente: bool
