from datetime import date, datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel


class ContadoresDashboardResponse(BaseModel):
    traslados_activos: int
    radicaciones_activas: int
    novedades_pendientes: int
    activos: int
    por_vencer: int
    vencidos: int
    completados_30d: int


class ProcesoActivoResponse(BaseModel):
    proceso_tipo: str                   # 'traslado' | 'radicacion'
    proceso_id: str                     # public_id
    placa: str
    numero_cuenta: str
    estado: str
    ciudad: Optional[str]               # nombre del organismo
    responsable: Optional[str]          # nombre del usuario creador
    fecha_vencimiento: Optional[date]
    dias_restantes: Optional[int]
    creado_en: datetime


class ProcesoVencidoResponse(BaseModel):
    proceso_tipo: str
    proceso_id: str
    placa: str
    numero_cuenta: str
    estado: str
    ciudad: Optional[str]
    responsable: Optional[str]
    fecha_vencimiento: date
    dias_vencido: int


class ProcesoCompletadoResponse(BaseModel):
    proceso_tipo: str
    proceso_id: str
    placa: str
    numero_cuenta: str
    ciudad: Optional[str]
    responsable: Optional[str]
    fecha_completado: datetime
    duracion_dias: Optional[int]        # días hábiles desde creado_en hasta completado_en


class OrganismoResponse(BaseModel):
    id: str
    nombre: str
    tipo: str
    municipio: str
    departamento: str
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    activo: bool


class EmpresaResponse(BaseModel):
    id: str
    nombre: str
    activo: bool
