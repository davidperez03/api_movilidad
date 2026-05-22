from datetime import date, datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field
from app.domain.entities.movilidad.cuenta import TipoServicio


class CrearCuentaRequest(BaseModel):
    placa: str = Field(..., min_length=5, max_length=10, pattern=r"^[A-Za-z0-9]+$")
    tipo_servicio: TipoServicio

    model_config = {
        "json_schema_extra": {
            "example": {"placa": "ABC123", "tipo_servicio": "particular"}
        }
    }


class CuentaResponse(BaseModel):
    id: str                     # public_id
    numero_cuenta: str
    placa: str
    tipo_servicio: TipoServicio
    creado_en: datetime

    model_config = {"from_attributes": True}


class ConsultaPublicaCuentaResponse(BaseModel):
    numero_cuenta: str
    placa: str
    tipo_servicio: TipoServicio
    proceso_tipo: Optional[str] = None          # 'traslado' | 'radicacion' | None
    proceso_estado: Optional[str] = None
    fecha_vencimiento: Optional[date] = None
    dias_restantes: Optional[int] = None
    ciudad: Optional[str] = None                # nombre del organismo destino/origen
    observaciones: Optional[str] = None
    empresa_transporte: Optional[str] = None
    numero_guia: Optional[str] = None
