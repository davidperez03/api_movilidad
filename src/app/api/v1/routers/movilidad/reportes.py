"""
Reportes operativos y dashboard de movilidad.
Todos los endpoints son solo-lectura y requieren permiso movilidad.reportes:leer.
Las queries usan SQL nativo para aprovechar las funciones PostgreSQL de días hábiles.
"""
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.persistence.database import get_session
from app.domain.entities.auth.usuario import Usuario
from app.api.v1.schemas.movilidad.reporte import (
    ContadoresDashboardResponse,
    ProcesoActivoResponse,
    ProcesoVencidoResponse,
    ProcesoCompletadoResponse,
)
from app.api.v1.schemas.paginacion import PaginaResponse
from app.dependencies import requiere_permiso, get_organization_id

router = APIRouter()

_PERMISO = "movilidad.reportes:leer"


def _filtro_org(org_id: UUID | None, alias_tra: str = "t", alias_rad: str = "r") -> tuple[str, str, dict]:
    """Devuelve (filtro_traslado, filtro_radicacion, params) para el org_id dado."""
    if not org_id:
        return "", "", {}
    return (
        f"AND {alias_tra}.organization_id = :org_id",
        f"AND {alias_rad}.organization_id = :org_id",
        {"org_id": org_id},
    )

# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard/contadores", response_model=ContadoresDashboardResponse)
async def contadores_dashboard(
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso(_PERMISO)),
    org_id: UUID | None = Depends(get_organization_id),
):
    """7 KPIs de movilidad en una sola consulta."""
    org_filter_tra = "AND t.organization_id = :org" if org_id else ""
    org_filter_rad = "AND r.organization_id = :org" if org_id else ""
    org_filter_nov = "AND n.organization_id = :org" if org_id else ""
    params = {"org": org_id} if org_id else {}

    result = await session.execute(text(f"""
        SELECT
            (SELECT COUNT(*) FROM mov_traslados t
             WHERE t.estado NOT IN ('trasladado','devuelto') {org_filter_tra}) AS traslados_activos,
            (SELECT COUNT(*) FROM mov_radicaciones r
             WHERE r.estado NOT IN ('radicado','devuelto') {org_filter_rad}) AS radicaciones_activas,
            (SELECT COUNT(*) FROM mov_novedades n
             WHERE n.estado != 'resuelta' {org_filter_nov}) AS novedades_pendientes,
            (SELECT COUNT(*) FROM (
                SELECT t2.id FROM mov_traslados t2
                WHERE t2.estado NOT IN ('trasladado','devuelto') {org_filter_tra}
                UNION ALL
                SELECT r2.id FROM mov_radicaciones r2
                WHERE r2.estado NOT IN ('radicado','devuelto') {org_filter_rad}
            ) activos) AS activos,
            (SELECT COUNT(*) FROM (
                SELECT t3.id FROM mov_traslados t3
                WHERE t3.estado NOT IN ('trasladado','devuelto')
                  AND t3.fecha_vencimiento IS NOT NULL
                  AND t3.fecha_vencimiento::date >= current_date
                  AND contar_dias_habiles(current_date, t3.fecha_vencimiento::date) BETWEEN 0 AND 10
                  {org_filter_tra}
                UNION ALL
                SELECT r3.id FROM mov_radicaciones r3
                WHERE r3.estado NOT IN ('radicado','devuelto')
                  AND r3.fecha_vencimiento IS NOT NULL
                  AND r3.fecha_vencimiento::date >= current_date
                  AND contar_dias_habiles(current_date, r3.fecha_vencimiento::date) BETWEEN 0 AND 10
                  {org_filter_rad}
            ) pv) AS por_vencer,
            (SELECT COUNT(*) FROM (
                SELECT t4.id FROM mov_traslados t4
                WHERE t4.estado NOT IN ('trasladado','devuelto')
                  AND t4.fecha_vencimiento IS NOT NULL
                  AND t4.fecha_vencimiento::date < current_date
                  {org_filter_tra}
                UNION ALL
                SELECT r4.id FROM mov_radicaciones r4
                WHERE r4.estado NOT IN ('radicado','devuelto')
                  AND r4.fecha_vencimiento IS NOT NULL
                  AND r4.fecha_vencimiento::date < current_date
                  {org_filter_rad}
            ) venc) AS vencidos,
            (SELECT COUNT(*) FROM (
                SELECT t5.id FROM mov_traslados t5
                WHERE t5.estado = 'trasladado'
                  AND t5.completado_en >= (NOW() - INTERVAL '30 days')
                  {org_filter_tra}
                UNION ALL
                SELECT r5.id FROM mov_radicaciones r5
                WHERE r5.estado = 'radicado'
                  AND r5.completado_en >= (NOW() - INTERVAL '30 days')
                  {org_filter_rad}
            ) comp) AS completados_30d
    """), params)

    row = result.fetchone()
    return ContadoresDashboardResponse(
        traslados_activos=row.traslados_activos or 0,
        radicaciones_activas=row.radicaciones_activas or 0,
        novedades_pendientes=row.novedades_pendientes or 0,
        activos=row.activos or 0,
        por_vencer=row.por_vencer or 0,
        vencidos=row.vencidos or 0,
        completados_30d=row.completados_30d or 0,
    )


# ── Reportes ──────────────────────────────────────────────────────────────────

@router.get("/reportes/activos", response_model=PaginaResponse[ProcesoActivoResponse])
async def reporte_activos(
    organismo_id: UUID | None = Query(None),
    proceso_tipo: str | None = Query(None, pattern="^(traslado|radicacion)$"),
    tamanio: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso(_PERMISO)),
    org_id: UUID | None = Depends(get_organization_id),
):
    """Todos los procesos activos con organismo, responsable y días restantes."""
    org_filter_tra, org_filter_rad, params = _filtro_org(org_id)

    organismo_filter_tra = ""
    organismo_filter_rad = ""
    if organismo_id:
        organismo_filter_tra = "AND t.organismo_destino_id = :organismo_id"
        organismo_filter_rad = "AND r.organismo_origen_id  = :organismo_id"
        params["organismo_id"] = organismo_id

    tipo_filter_tra = "AND FALSE" if proceso_tipo == "radicacion" else ""
    tipo_filter_rad = "AND FALSE" if proceso_tipo == "traslado" else ""

    sql = text(f"""
        SELECT *
        FROM (
            SELECT
                'traslado' AS proceso_tipo,
                t.public_id AS proceso_id,
                cv.placa,
                cv.numero_cuenta,
                t.estado,
                ot.nombre AS ciudad,
                (u.nombre || ' ' || u.apellido) AS responsable,
                t.fecha_vencimiento,
                CASE
                  WHEN t.fecha_vencimiento IS NOT NULL
                  THEN contar_dias_habiles(current_date, t.fecha_vencimiento::date)
                  ELSE NULL
                END AS dias_restantes,
                t.creado_en
            FROM mov_traslados t
            JOIN mov_cuentas_vehiculos cv ON t.cuenta_id = cv.id
            LEFT JOIN mov_organismos_transito ot ON t.organismo_destino_id = ot.id
            LEFT JOIN usuarios u ON t.creado_por = u.id
            WHERE t.estado NOT IN ('trasladado','devuelto')
            {org_filter_tra} {organismo_filter_tra} {tipo_filter_tra}

            UNION ALL

            SELECT
                'radicacion' AS proceso_tipo,
                r.public_id AS proceso_id,
                cv.placa,
                cv.numero_cuenta,
                r.estado,
                ot.nombre AS ciudad,
                (u.nombre || ' ' || u.apellido) AS responsable,
                r.fecha_vencimiento,
                CASE
                  WHEN r.fecha_vencimiento IS NOT NULL
                  THEN contar_dias_habiles(current_date, r.fecha_vencimiento::date)
                  ELSE NULL
                END AS dias_restantes,
                r.creado_en
            FROM mov_radicaciones r
            JOIN mov_cuentas_vehiculos cv ON r.cuenta_id = cv.id
            LEFT JOIN mov_organismos_transito ot ON r.organismo_origen_id = ot.id
            LEFT JOIN usuarios u ON r.creado_por = u.id
            WHERE r.estado NOT IN ('radicado','devuelto')
            {org_filter_rad} {organismo_filter_rad} {tipo_filter_rad}
        ) p
        ORDER BY dias_restantes ASC NULLS LAST, creado_en ASC
        LIMIT :limit OFFSET :offset
    """)
    params["limit"] = tamanio + 1
    params["offset"] = offset

    filas = (await session.execute(sql, params)).fetchall()
    tiene_siguiente = len(filas) > tamanio
    filas = filas[:tamanio]

    items = [
        ProcesoActivoResponse(
            proceso_tipo=r.proceso_tipo,
            proceso_id=r.proceso_id,
            placa=r.placa,
            numero_cuenta=r.numero_cuenta,
            estado=r.estado,
            ciudad=r.ciudad,
            responsable=r.responsable,
            fecha_vencimiento=r.fecha_vencimiento,
            dias_restantes=r.dias_restantes,
            creado_en=r.creado_en,
        ) for r in filas
    ]
    return PaginaResponse(items=items, siguiente_cursor=None if not tiene_siguiente else "has_more", total=len(items))


@router.get("/reportes/por-vencer", response_model=PaginaResponse[ProcesoActivoResponse])
async def reporte_por_vencer(
    dias: int = Query(10, ge=1, le=30, description="Procesos que vencen en los próximos N días hábiles"),
    tamanio: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso(_PERMISO)),
    org_id: UUID | None = Depends(get_organization_id),
):
    """Procesos que vencen hoy o en los próximos N días hábiles, ordenados por urgencia."""
    org_filter_tra, org_filter_rad, params = _filtro_org(org_id)
    params.update({"dias": dias, "limit": tamanio + 1, "offset": offset})

    sql = text(f"""
        SELECT *
        FROM (
            SELECT
                'traslado' AS proceso_tipo,
                t.public_id AS proceso_id,
                cv.placa,
                cv.numero_cuenta,
                t.estado,
                ot.nombre AS ciudad,
                (u.nombre || ' ' || u.apellido) AS responsable,
                t.fecha_vencimiento,
                contar_dias_habiles(current_date, t.fecha_vencimiento::date) AS dias_restantes,
                t.creado_en
            FROM mov_traslados t
            JOIN mov_cuentas_vehiculos cv ON t.cuenta_id = cv.id
            LEFT JOIN mov_organismos_transito ot ON t.organismo_destino_id = ot.id
            LEFT JOIN usuarios u ON t.creado_por = u.id
            WHERE t.estado NOT IN ('trasladado','devuelto')
              AND t.fecha_vencimiento IS NOT NULL
              AND t.fecha_vencimiento::date >= current_date
              AND contar_dias_habiles(current_date, t.fecha_vencimiento::date) <= :dias
              {org_filter_tra}

            UNION ALL

            SELECT
                'radicacion' AS proceso_tipo,
                r.public_id AS proceso_id,
                cv.placa,
                cv.numero_cuenta,
                r.estado,
                ot.nombre AS ciudad,
                (u.nombre || ' ' || u.apellido) AS responsable,
                r.fecha_vencimiento,
                contar_dias_habiles(current_date, r.fecha_vencimiento::date) AS dias_restantes,
                r.creado_en
            FROM mov_radicaciones r
            JOIN mov_cuentas_vehiculos cv ON r.cuenta_id = cv.id
            LEFT JOIN mov_organismos_transito ot ON r.organismo_origen_id = ot.id
            LEFT JOIN usuarios u ON r.creado_por = u.id
            WHERE r.estado NOT IN ('radicado','devuelto')
              AND r.fecha_vencimiento IS NOT NULL
              AND r.fecha_vencimiento::date >= current_date
              AND contar_dias_habiles(current_date, r.fecha_vencimiento::date) <= :dias
              {org_filter_rad}
        ) p
        ORDER BY dias_restantes ASC, creado_en ASC
        LIMIT :limit OFFSET :offset
    """)

    filas = (await session.execute(sql, params)).fetchall()
    tiene_siguiente = len(filas) > tamanio
    filas = filas[:tamanio]

    items = [
        ProcesoActivoResponse(
            proceso_tipo=r.proceso_tipo, proceso_id=r.proceso_id,
            placa=r.placa, numero_cuenta=r.numero_cuenta, estado=r.estado,
            ciudad=r.ciudad, responsable=r.responsable,
            fecha_vencimiento=r.fecha_vencimiento, dias_restantes=r.dias_restantes,
            creado_en=r.creado_en,
        ) for r in filas
    ]
    return PaginaResponse(items=items, siguiente_cursor=None if not tiene_siguiente else "has_more", total=len(items))


@router.get("/reportes/vencidos", response_model=PaginaResponse[ProcesoVencidoResponse])
async def reporte_vencidos(
    tamanio: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso(_PERMISO)),
    org_id: UUID | None = Depends(get_organization_id),
):
    """Procesos activos con fecha de vencimiento superada, ordenados por días vencido (más urgente primero)."""
    org_filter_tra, org_filter_rad, params = _filtro_org(org_id)
    params.update({"limit": tamanio + 1, "offset": offset})

    sql = text(f"""
        SELECT *
        FROM (
            SELECT
                'traslado' AS proceso_tipo,
                t.public_id AS proceso_id,
                cv.placa,
                cv.numero_cuenta,
                t.estado,
                ot.nombre AS ciudad,
                (u.nombre || ' ' || u.apellido) AS responsable,
                t.fecha_vencimiento,
                (current_date - t.fecha_vencimiento::date) AS dias_vencido
            FROM mov_traslados t
            JOIN mov_cuentas_vehiculos cv ON t.cuenta_id = cv.id
            LEFT JOIN mov_organismos_transito ot ON t.organismo_destino_id = ot.id
            LEFT JOIN usuarios u ON t.creado_por = u.id
            WHERE t.estado NOT IN ('trasladado','devuelto')
              AND t.fecha_vencimiento IS NOT NULL
              AND t.fecha_vencimiento::date < current_date
              {org_filter_tra}

            UNION ALL

            SELECT
                'radicacion' AS proceso_tipo,
                r.public_id AS proceso_id,
                cv.placa,
                cv.numero_cuenta,
                r.estado,
                ot.nombre AS ciudad,
                (u.nombre || ' ' || u.apellido) AS responsable,
                r.fecha_vencimiento,
                (current_date - r.fecha_vencimiento::date) AS dias_vencido
            FROM mov_radicaciones r
            JOIN mov_cuentas_vehiculos cv ON r.cuenta_id = cv.id
            LEFT JOIN mov_organismos_transito ot ON r.organismo_origen_id = ot.id
            LEFT JOIN usuarios u ON r.creado_por = u.id
            WHERE r.estado NOT IN ('radicado','devuelto')
              AND r.fecha_vencimiento IS NOT NULL
              AND r.fecha_vencimiento::date < current_date
              {org_filter_rad}
        ) p
        ORDER BY dias_vencido DESC
        LIMIT :limit OFFSET :offset
    """)

    filas = (await session.execute(sql, params)).fetchall()
    tiene_siguiente = len(filas) > tamanio
    filas = filas[:tamanio]

    items = [
        ProcesoVencidoResponse(
            proceso_tipo=r.proceso_tipo, proceso_id=r.proceso_id,
            placa=r.placa, numero_cuenta=r.numero_cuenta, estado=r.estado,
            ciudad=r.ciudad, responsable=r.responsable,
            fecha_vencimiento=r.fecha_vencimiento, dias_vencido=r.dias_vencido,
        ) for r in filas
    ]
    return PaginaResponse(items=items, siguiente_cursor=None if not tiene_siguiente else "has_more", total=len(items))


@router.get("/reportes/completados", response_model=PaginaResponse[ProcesoCompletadoResponse])
async def reporte_completados(
    dias: int = Query(30, ge=1, le=365, description="Procesos completados en los últimos N días"),
    tamanio: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso(_PERMISO)),
    org_id: UUID | None = Depends(get_organization_id),
):
    """Procesos completados (trasladado o radicado) con duración calculada en días hábiles."""
    org_filter_tra, org_filter_rad, params = _filtro_org(org_id)
    params.update({"dias": dias, "limit": tamanio + 1, "offset": offset})

    sql = text(f"""
        SELECT *
        FROM (
            SELECT
                'traslado' AS proceso_tipo,
                t.public_id AS proceso_id,
                cv.placa,
                cv.numero_cuenta,
                ot.nombre AS ciudad,
                (u.nombre || ' ' || u.apellido) AS responsable,
                t.completado_en,
                contar_dias_habiles(t.creado_en::date, t.completado_en::date) AS duracion_dias
            FROM mov_traslados t
            JOIN mov_cuentas_vehiculos cv ON t.cuenta_id = cv.id
            LEFT JOIN mov_organismos_transito ot ON t.organismo_destino_id = ot.id
            LEFT JOIN usuarios u ON t.creado_por = u.id
            WHERE t.estado = 'trasladado'
              AND t.completado_en >= (NOW() - (:dias || ' days')::INTERVAL)
              {org_filter_tra}

            UNION ALL

            SELECT
                'radicacion' AS proceso_tipo,
                r.public_id AS proceso_id,
                cv.placa,
                cv.numero_cuenta,
                ot.nombre AS ciudad,
                (u.nombre || ' ' || u.apellido) AS responsable,
                r.completado_en,
                contar_dias_habiles(r.creado_en::date, r.completado_en::date) AS duracion_dias
            FROM mov_radicaciones r
            JOIN mov_cuentas_vehiculos cv ON r.cuenta_id = cv.id
            LEFT JOIN mov_organismos_transito ot ON r.organismo_origen_id = ot.id
            LEFT JOIN usuarios u ON r.creado_por = u.id
            WHERE r.estado = 'radicado'
              AND r.completado_en >= (NOW() - (:dias || ' days')::INTERVAL)
              {org_filter_rad}
        ) p
        ORDER BY completado_en DESC
        LIMIT :limit OFFSET :offset
    """)

    filas = (await session.execute(sql, params)).fetchall()
    tiene_siguiente = len(filas) > tamanio
    filas = filas[:tamanio]

    items = [
        ProcesoCompletadoResponse(
            proceso_tipo=r.proceso_tipo, proceso_id=r.proceso_id,
            placa=r.placa, numero_cuenta=r.numero_cuenta,
            ciudad=r.ciudad, responsable=r.responsable,
            fecha_completado=r.completado_en, duracion_dias=r.duracion_dias,
        ) for r in filas
    ]
    return PaginaResponse(items=items, siguiente_cursor=None if not tiene_siguiente else "has_more", total=len(items))
