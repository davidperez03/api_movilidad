from pydantic import BaseModel, EmailStr, Field, SecretStr, field_validator
from app.api.v1.schemas.auth.usuario import _validar_fortaleza_password


class LoginRequest(BaseModel):
    email: EmailStr
    password: SecretStr = Field(..., min_length=1, max_length=128)

    model_config = {
        "json_schema_extra": {
            "example": {"email": "admin@movilidad.gov.co", "password": "SuperSegura123!"}
        }
    }


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., max_length=2048)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., max_length=2048)


class VerificarEmailRequest(BaseModel):
    token: str = Field(..., max_length=256)


class ReenviarVerificacionRequest(BaseModel):
    email: EmailStr


class SolicitarResetPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., max_length=256)
    nueva_password: SecretStr = Field(..., min_length=8, max_length=128)

    @field_validator("nueva_password", mode="before")
    @classmethod
    def validar_password(cls, v: str) -> str:
        _validar_fortaleza_password(v)
        return v
