"""
Alertas de vencimiento de documentos en parqueadero.
UNION de SOAT, tecnomecánica de vehículos y licencias de operadores venciendo en los próximos N días.
"""
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.persistence.database import get_session
from app.domain.entities.auth.usuario import Usuario
from app.dependencies import requiere_permiso, get_organization_id
from uuid import UUID

router = APIRouter()

_PERM = "parqueadero.reportes:leer"


class AlertaVencimientoResponse(BaseModel):
    tipo: str                           # 'vehiculo' | 'operador'
    entidad_id: str                     # public_id del vehículo o del operador
    identificador: str                  # placa o nombre del operador
    documento: str                      # 'SOAT' | 'Tecnomecánica' | 'Licencia X'
    fecha_vencimiento: date
    estado: str                         # 'vigente' | 'vence_pronto' | 'vencido'
    dias_restantes: int                 # negativo si ya venció


def _estado_doc(fecha_vencimiento: date) -> tuple[str, int]:
    dias = (fecha_vencimiento - date.today()).days
    if dias < 0:
        estado = "vencido"
    elif dias <= 10:
        estado = "vence_pronto"
    else:
        estado = "vigente"
    return estado, dias


@router.get("/alertas", response_model=list[AlertaVencimientoResponse])
async def alertas_vencimiento(
    dias: int = Query(30, ge=1, le=90, description="Alertas de documentos que vencen en los próximos N días"),
    tipo: str | None = Query(None, pattern="^(vehiculo|operador)$"),
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso(_PERM)),
    org_id: UUID | None = Depends(get_organization_id),
):
    """
    UNION de SOAT, tecnomecánica de vehículos y licencias de operadores
    cuyos documentos vencen en los próximos N días (o ya vencieron).
    Ordenados por fecha de vencimiento ascendente (más urgentes primero).
    """
    params: dict = {"dias": dias}
    org_filter_v = ""
    org_filter_p = ""
    if org_id:
        org_filter_v = "AND v.organization_id = :org_id"
        org_filter_p = "AND dp.organization_id = :org_id"
        params["org_id"] = org_id

    tipo_filter = ""
    if tipo == "vehiculo":
        tipo_filter = "WHERE tipo = 'vehiculo'"
    elif tipo == "operador":
        tipo_filter = "WHERE tipo = 'operador'"

    sql = text(f"""
        SELECT *
        FROM (
            SELECT
                'vehiculo' AS tipo,
                v.public_id AS entidad_id,
                v.placa AS identificador,
                'SOAT' AS documento,
                v.soat_vencimiento AS fecha_vencimiento
            FROM parq_vehiculos v
            WHERE v.activo
              AND v.soat_vencimiento IS NOT NULL
              AND v.soat_vencimiento <= current_date + (:dias || ' days')::INTERVAL
              {org_filter_v}

            UNION ALL

            SELECT
                'vehiculo',
                v.public_id,
                v.placa,
                'Tecnomecánica',
                v.tecnomecanica_vencimiento
            FROM parq_vehiculos v
            WHERE v.activo
              AND v.tecnomecanica_vencimiento IS NOT NULL
              AND v.tecnomecanica_vencimiento <= current_date + (:dias || ' days')::INTERVAL
              {org_filter_v}

            UNION ALL

            SELECT
                'operador',
                u.public_id,
                (u.nombre || ' ' || u.apellido),
                ('Licencia ' || COALESCE(dp.licencia_categoria, '')),
                dp.licencia_vencimiento
            FROM parq_datos_personal dp
            JOIN usuarios u ON u.id = dp.usuario_id
            WHERE dp.licencia_vencimiento IS NOT NULL
              AND dp.licencia_vencimiento <= current_date + (:dias || ' days')::INTERVAL
              {org_filter_p}
        ) alertas
        {tipo_filter}
        ORDER BY fecha_vencimiento ASC
        LIMIT 200
    """)

    filas = (await session.execute(sql, params)).fetchall()
    resultado = []
    for r in filas:
        estado, dias_rest = _estado_doc(r.fecha_vencimiento)
        resultado.append(AlertaVencimientoResponse(
            tipo=r.tipo,
            entidad_id=r.entidad_id,
            identificador=r.identificador,
            documento=r.documento,
            fecha_vencimiento=r.fecha_vencimiento,
            estado=estado,
            dias_restantes=dias_rest,
        ))
    return resultado
