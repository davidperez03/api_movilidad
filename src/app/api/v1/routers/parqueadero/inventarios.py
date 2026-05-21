"""
Módulo de inventarios parqueadero.
Catálogo de insumos, stock por ubicación, rangos numéricos,
movimientos (log inmutable) y cierres de turno por grúa.
"""
import hashlib
import json
from datetime import date, datetime, timezone
from uuid import UUID, uuid4
from typing import Optional, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.modelos.parqueadero.inventario_modelos import (
    InsumoModelo, StockModelo, RangoModelo, MovimientoInventarioModelo,
    CierreTurnoModelo, CierreTurnoDetalleModelo,
)
from app.domain.entities.auth.usuario import Usuario
from app.api.v1.schemas.paginacion import PaginaResponse
from app.dependencies import requiere_permiso, get_organization_id

router = APIRouter()

_PERM_GESTIONAR = "parqueadero.vehiculos:gestionar"
_PERM_LEER     = "parqueadero.reportes:leer"


# ── Schemas ───────────────────────────────────────────────────────────────────

class InsumoResponse(BaseModel):
    id: str
    nombre: str
    categoria: str
    unidad: str
    stock_minimo: int
    tipo_tracking: str
    modulo: str
    activo: bool


class CrearInsumoRequest(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=200)
    categoria: str = Field(..., min_length=2, max_length=100)
    unidad: str = Field(..., min_length=1, max_length=50)
    stock_minimo: int = Field(0, ge=0)
    tipo_tracking: Literal["ubicacion", "rango"] = "ubicacion"
    modulo: str = Field("parqueadero", max_length=50)


class StockResponse(BaseModel):
    item_id: UUID
    ubicacion: str
    cantidad: int
    alerta_minimo: bool


class RangoResponse(BaseModel):
    item_id: UUID
    rango_inicio: int
    rango_fin: int
    usados: int
    disponibles: int


class MovimientoRequest(BaseModel):
    item_id: UUID
    tipo: Literal["ingreso", "traslado"]
    destino: str = Field(..., min_length=1)
    cantidad: int = Field(..., gt=0)
    origen: Optional[str] = None
    notas: Optional[str] = None


class MovimientoResponse(BaseModel):
    id: UUID
    item_id: UUID
    tipo: str
    origen: Optional[str]
    destino: str
    cantidad: int
    notas: Optional[str]
    creado_en: datetime


class CierreItemRequest(BaseModel):
    item_id: UUID
    cantidad_inicial: int = Field(..., ge=0)
    cantidad_final: int = Field(..., ge=0)


class CierreTurnoRequest(BaseModel):
    vehiculo_id: UUID
    fecha: date
    items: list[CierreItemRequest] = Field(..., min_length=1)


class CierreTurnoResponse(BaseModel):
    id: UUID
    vehiculo_id: UUID
    fecha: date
    creado_en: datetime
    items: list[dict]


# ── Insumos ───────────────────────────────────────────────────────────────────

@router.get("/inventarios/insumos", response_model=list[InsumoResponse])
async def listar_insumos(
    categoria: str | None = Query(None),
    tipo_tracking: str | None = Query(None, pattern="^(ubicacion|rango)$"),
    solo_activos: bool = Query(True),
    tamanio: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso(_PERM_LEER)),
    org_id: UUID | None = Depends(get_organization_id),
):
    stmt = select(InsumoModelo)
    if solo_activos:
        stmt = stmt.where(InsumoModelo.activo.is_(True))
    if categoria:
        stmt = stmt.where(InsumoModelo.categoria == categoria)
    if tipo_tracking:
        stmt = stmt.where(InsumoModelo.tipo_tracking == tipo_tracking)
    if org_id:
        stmt = stmt.where(
            (InsumoModelo.organization_id == org_id) | (InsumoModelo.organization_id.is_(None))
        )
    stmt = stmt.order_by(InsumoModelo.categoria, InsumoModelo.nombre).offset(offset).limit(tamanio)
    filas = (await session.execute(stmt)).scalars().all()
    return [InsumoResponse(id=f.public_id, nombre=f.nombre, categoria=f.categoria,
                           unidad=f.unidad, stock_minimo=f.stock_minimo,
                           tipo_tracking=f.tipo_tracking, modulo=f.modulo, activo=f.activo)
            for f in filas]


@router.post("/inventarios/insumos", response_model=InsumoResponse, status_code=201)
async def crear_insumo(
    body: CrearInsumoRequest,
    session: AsyncSession = Depends(get_session),
    usuario: Usuario = Depends(requiere_permiso(_PERM_GESTIONAR)),
    org_id: UUID | None = Depends(get_organization_id),
):
    from app.infrastructure.identity import generar_public_id
    modelo = InsumoModelo(
        id=uuid4(),
        public_id=generar_public_id("inv"),
        nombre=body.nombre,
        categoria=body.categoria,
        unidad=body.unidad,
        stock_minimo=body.stock_minimo,
        tipo_tracking=body.tipo_tracking,
        modulo=body.modulo,
        activo=True,
        organization_id=org_id,
        creado_por=usuario.id,
    )
    session.add(modelo)
    await session.flush()
    return InsumoResponse(id=modelo.public_id, nombre=modelo.nombre, categoria=modelo.categoria,
                          unidad=modelo.unidad, stock_minimo=modelo.stock_minimo,
                          tipo_tracking=modelo.tipo_tracking, modulo=modelo.modulo, activo=modelo.activo)


# ── Stock ─────────────────────────────────────────────────────────────────────

@router.get("/inventarios/stock", response_model=list[StockResponse])
async def listar_stock(
    ubicacion: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso(_PERM_LEER)),
):
    stmt = select(StockModelo, InsumoModelo.stock_minimo).join(
        InsumoModelo, StockModelo.item_id == InsumoModelo.id
    )
    if ubicacion:
        stmt = stmt.where(StockModelo.ubicacion == ubicacion)
    stmt = stmt.order_by(StockModelo.ubicacion, StockModelo.item_id)
    filas = (await session.execute(stmt)).all()
    return [StockResponse(
        item_id=f.StockModelo.item_id,
        ubicacion=f.StockModelo.ubicacion,
        cantidad=f.StockModelo.cantidad,
        alerta_minimo=f.StockModelo.cantidad < f.stock_minimo,
    ) for f in filas]


# ── Rangos ────────────────────────────────────────────────────────────────────

@router.get("/inventarios/rangos", response_model=list[RangoResponse])
async def listar_rangos(
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso(_PERM_LEER)),
):
    filas = (await session.execute(select(RangoModelo))).scalars().all()
    return [RangoResponse(
        item_id=f.item_id,
        rango_inicio=f.rango_inicio,
        rango_fin=f.rango_fin,
        usados=f.usados,
        disponibles=max(f.rango_fin - f.usados, 0),
    ) for f in filas]


@router.patch("/inventarios/rangos/{item_id}/ampliar", response_model=RangoResponse)
async def ampliar_rango(
    item_id: UUID,
    nuevo_fin: int = Query(..., gt=0, description="Nuevo rango_fin (debe ser mayor al actual)"),
    session: AsyncSession = Depends(get_session),
    usuario: Usuario = Depends(requiere_permiso(_PERM_GESTIONAR)),
):
    """Amplía el rango_fin cuando llega un nuevo lote de stickers."""
    resultado = await session.execute(
        select(RangoModelo).where(RangoModelo.item_id == item_id)
    )
    rango = resultado.scalar_one_or_none()
    if not rango:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rango no encontrado")
    if nuevo_fin <= rango.rango_fin:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"El nuevo rango_fin ({nuevo_fin}) debe ser mayor al actual ({rango.rango_fin})")
    rango.rango_fin = nuevo_fin
    rango.updated_at = datetime.now(timezone.utc)
    rango.updated_by = usuario.id
    await session.flush()
    return RangoResponse(item_id=rango.item_id, rango_inicio=rango.rango_inicio,
                         rango_fin=rango.rango_fin, usados=rango.usados,
                         disponibles=max(rango.rango_fin - rango.usados, 0))


# ── Movimientos ───────────────────────────────────────────────────────────────

def _calcular_hash(id_str: str, item_id: str, tipo: str, origen: str,
                   destino: str, cantidad: int, creado_en: str, hash_anterior: str) -> str:
    datos = f"{id_str}|{item_id}|{tipo}|{origen}|{destino}|{cantidad}|{creado_en}|{hash_anterior}"
    return hashlib.sha256(datos.encode()).hexdigest()


@router.post("/inventarios/movimientos", response_model=MovimientoResponse, status_code=201)
async def registrar_movimiento(
    body: MovimientoRequest,
    session: AsyncSession = Depends(get_session),
    usuario: Usuario = Depends(requiere_permiso(_PERM_GESTIONAR)),
    org_id: UUID | None = Depends(get_organization_id),
):
    if body.tipo == "ingreso" and body.origen:
        raise HTTPException(status_code=422, detail="Un ingreso no debe tener origen")
    if body.tipo == "traslado" and not body.origen:
        raise HTTPException(status_code=422, detail="Un traslado requiere origen")

    # Obtener hash del último movimiento para encadenar
    ultimo = (await session.execute(
        select(MovimientoInventarioModelo.hash_registro)
        .where(MovimientoInventarioModelo.item_id == body.item_id)
        .order_by(MovimientoInventarioModelo.creado_en.desc())
        .limit(1)
    )).scalar_one_or_none()

    mov_id = uuid4()
    ahora = datetime.now(timezone.utc)
    hash_ant = ultimo or ""
    hash_reg = _calcular_hash(
        str(mov_id), str(body.item_id), body.tipo,
        body.origen or "", body.destino, body.cantidad,
        ahora.isoformat(), hash_ant,
    )

    modelo = MovimientoInventarioModelo(
        id=mov_id,
        item_id=body.item_id,
        modulo="parqueadero",
        tipo=body.tipo,
        origen=body.origen,
        destino=body.destino,
        cantidad=body.cantidad,
        notas=body.notas,
        creado_por=usuario.id,
        organization_id=org_id,
        creado_en=ahora,
        hash_anterior=hash_ant or None,
        hash_registro=hash_reg,
    )
    session.add(modelo)

    # Actualizar stock
    if body.tipo == "ingreso":
        await _actualizar_stock(session, body.item_id, body.destino, body.cantidad)
    else:
        await _actualizar_stock(session, body.item_id, body.origen, -body.cantidad)
        await _actualizar_stock(session, body.item_id, body.destino, body.cantidad)

    await session.flush()
    return MovimientoResponse(id=modelo.id, item_id=modelo.item_id, tipo=modelo.tipo,
                               origen=modelo.origen, destino=modelo.destino,
                               cantidad=modelo.cantidad, notas=modelo.notas, creado_en=modelo.creado_en)


async def _actualizar_stock(session: AsyncSession, item_id: UUID, ubicacion: str, delta: int) -> None:
    stock = (await session.execute(
        select(StockModelo).where(StockModelo.item_id == item_id, StockModelo.ubicacion == ubicacion)
    )).scalar_one_or_none()
    if stock:
        nueva = stock.cantidad + delta
        if nueva < 0:
            raise HTTPException(status_code=409, detail=f"Stock insuficiente en '{ubicacion}': {stock.cantidad} disponibles")
        stock.cantidad = nueva
        stock.updated_at = datetime.now(timezone.utc)
    else:
        if delta < 0:
            raise HTTPException(status_code=409, detail=f"No hay stock registrado en '{ubicacion}'")
        session.add(StockModelo(item_id=item_id, modulo="parqueadero", ubicacion=ubicacion, cantidad=delta))


@router.get("/inventarios/movimientos", response_model=list[MovimientoResponse])
async def listar_movimientos(
    item_id: UUID | None = Query(None),
    tamanio: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso(_PERM_LEER)),
):
    stmt = select(MovimientoInventarioModelo).order_by(MovimientoInventarioModelo.creado_en.desc())
    if item_id:
        stmt = stmt.where(MovimientoInventarioModelo.item_id == item_id)
    stmt = stmt.offset(offset).limit(tamanio)
    filas = (await session.execute(stmt)).scalars().all()
    return [MovimientoResponse(id=f.id, item_id=f.item_id, tipo=f.tipo,
                                origen=f.origen, destino=f.destino, cantidad=f.cantidad,
                                notas=f.notas, creado_en=f.creado_en) for f in filas]


# ── Cierres de turno ──────────────────────────────────────────────────────────

@router.post("/inventarios/cierres", response_model=CierreTurnoResponse, status_code=201)
async def registrar_cierre_turno(
    body: CierreTurnoRequest,
    session: AsyncSession = Depends(get_session),
    usuario: Usuario = Depends(requiere_permiso(_PERM_GESTIONAR)),
    org_id: UUID | None = Depends(get_organization_id),
):
    """Registra el consumo diario de insumos por grúa. Solo un cierre por grúa/fecha."""
    for item in body.items:
        if item.cantidad_final > item.cantidad_inicial:
            raise HTTPException(status_code=422,
                detail=f"cantidad_final no puede superar cantidad_inicial (item {item.item_id})")

    cierre = CierreTurnoModelo(
        id=uuid4(),
        vehiculo_id=body.vehiculo_id,
        fecha=body.fecha,
        creado_por=usuario.id,
        organization_id=org_id,
        creado_en=datetime.now(timezone.utc),
    )
    session.add(cierre)
    await session.flush()

    detalles = []
    for item in body.items:
        det = CierreTurnoDetalleModelo(
            id=uuid4(),
            cierre_id=cierre.id,
            item_id=item.item_id,
            cantidad_inicial=item.cantidad_inicial,
            cantidad_final=item.cantidad_final,
        )
        session.add(det)
        detalles.append({
            "item_id": str(item.item_id),
            "cantidad_inicial": item.cantidad_inicial,
            "cantidad_final": item.cantidad_final,
            "cantidad_consumida": item.cantidad_inicial - item.cantidad_final,
        })
    await session.flush()

    return CierreTurnoResponse(id=cierre.id, vehiculo_id=cierre.vehiculo_id,
                                fecha=cierre.fecha, creado_en=cierre.creado_en, items=detalles)


@router.get("/inventarios/cierres", response_model=list[CierreTurnoResponse])
async def listar_cierres(
    vehiculo_id: UUID | None = Query(None),
    fecha_desde: date | None = Query(None),
    tamanio: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _: Usuario = Depends(requiere_permiso(_PERM_LEER)),
):
    stmt = select(CierreTurnoModelo).order_by(CierreTurnoModelo.fecha.desc())
    if vehiculo_id:
        stmt = stmt.where(CierreTurnoModelo.vehiculo_id == vehiculo_id)
    if fecha_desde:
        stmt = stmt.where(CierreTurnoModelo.fecha >= fecha_desde)
    stmt = stmt.offset(offset).limit(tamanio)
    cierres = (await session.execute(stmt)).scalars().all()
    if not cierres:
        return []

    cierre_ids = [c.id for c in cierres]
    todos_detalles = (await session.execute(
        select(CierreTurnoDetalleModelo).where(CierreTurnoDetalleModelo.cierre_id.in_(cierre_ids))
    )).scalars().all()

    detalles_por_cierre: dict = {}
    for d in todos_detalles:
        detalles_por_cierre.setdefault(d.cierre_id, []).append(d)

    return [
        CierreTurnoResponse(
            id=c.id, vehiculo_id=c.vehiculo_id, fecha=c.fecha, creado_en=c.creado_en,
            items=[{
                "item_id": str(d.item_id),
                "cantidad_inicial": d.cantidad_inicial,
                "cantidad_final": d.cantidad_final,
                "cantidad_consumida": d.cantidad_inicial - d.cantidad_final,
            } for d in detalles_por_cierre.get(c.id, [])]
        )
        for c in cierres
    ]
