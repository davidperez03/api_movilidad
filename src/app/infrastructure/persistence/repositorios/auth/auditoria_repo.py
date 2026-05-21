from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy import func, or_, and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.auth.auditoria import (
    CategoriaEvento,
    NivelEvento,
    RegistroAuditoria,
    ResultadoAuditoria,
    TipoActor,
)
from app.domain.ports.outbound.auth.repositorio_auditoria import (
    EstadisticasAuditoria,
    FiltrosAuditoria,
    RepositorioAuditoria,
    ResultadoVerificacion,
)
from app.infrastructure.persistence.modelos.auth.auditoria_modelo import AuditoriaModelo
from app.infrastructure.security.auth.cadena_auditoria import firmar, verificar
from app.infrastructure.persistence.repositorios._cursor import encode_cursor, decode_cursor


# ── Repositorio ────────────────────────────────────────────────────────────────

class AuditoriaRepositorioSQL(RepositorioAuditoria):

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    # ── Escritura ──────────────────────────────────────────────────────────────

    async def registrar(self, registro: RegistroAuditoria) -> None:
        hash_reg, firma = firmar(registro)
        registro.hash_registro = hash_reg
        registro.firma_hmac     = firma

        if registro.diferencia is None and registro.valor_anterior and registro.valor_nuevo:
            registro.diferencia = RegistroAuditoria.calcular_diferencia(
                registro.valor_anterior, registro.valor_nuevo
            )

        modelo = AuditoriaModelo(
            id                = registro.id,
            timestamp         = registro.timestamp,
            timestamp_unix_ms = registro.timestamp_unix_ms,
            correlation_id    = registro.correlation_id,
            actor_id          = registro.actor_id,
            actor_email       = registro.actor_email,
            actor_ip          = registro.actor_ip,
            actor_user_agent  = registro.actor_user_agent,
            actor_tipo        = registro.actor_tipo.value,
            sesion_id         = registro.sesion_id,
            api_key_id        = registro.api_key_id,
            categoria         = registro.categoria.value,
            nivel             = registro.nivel.value,
            accion            = registro.accion,
            resultado         = registro.resultado.value,
            resultado_detalle = registro.resultado_detalle,
            metodo_http       = registro.metodo_http,
            path              = registro.path,
            query_params      = registro.query_params,
            codigo_respuesta  = registro.codigo_respuesta,
            duracion_ms       = registro.duracion_ms,
            recurso_tipo      = registro.recurso_tipo,
            recurso_id        = registro.recurso_id,
            valor_anterior    = registro.valor_anterior,
            valor_nuevo       = registro.valor_nuevo,
            diferencia        = registro.diferencia,
            metadatos         = registro.metadatos,
            razon             = registro.razon,
            error_mensaje     = registro.error_mensaje,
            organization_id   = registro.organization_id,
            hash_registro     = registro.hash_registro,
            firma_hmac        = registro.firma_hmac,
        )
        self._s.add(modelo)
        await self._s.flush()

    # ── Lectura ────────────────────────────────────────────────────────────────

    async def listar(
        self,
        filtros: FiltrosAuditoria,
        organization_id: UUID | None = None,
    ) -> tuple[list[RegistroAuditoria], int, str | None]:
        stmt       = select(AuditoriaModelo)
        count_stmt = select(func.count()).select_from(AuditoriaModelo)

        def _w(cond):
            nonlocal stmt, count_stmt
            stmt       = stmt.where(cond)
            count_stmt = count_stmt.where(cond)

        if organization_id is not None:
            _w(AuditoriaModelo.organization_id == organization_id)
        if filtros.actor_id:
            _w(AuditoriaModelo.actor_id == filtros.actor_id)
        if filtros.actor_ip:
            _w(AuditoriaModelo.actor_ip == filtros.actor_ip)
        if filtros.sesion_id:
            _w(AuditoriaModelo.sesion_id == filtros.sesion_id)
        if filtros.recurso_tipo:
            _w(AuditoriaModelo.recurso_tipo == filtros.recurso_tipo)
        if filtros.recurso_id:
            _w(AuditoriaModelo.recurso_id == filtros.recurso_id)
        if filtros.accion:
            _w(AuditoriaModelo.accion == filtros.accion)
        if filtros.categoria:
            _w(AuditoriaModelo.categoria == filtros.categoria.value)
        if filtros.nivel:
            _w(AuditoriaModelo.nivel == filtros.nivel.value)
        if filtros.resultado:
            _w(AuditoriaModelo.resultado == filtros.resultado.value)
        if filtros.metodo_http:
            _w(AuditoriaModelo.metodo_http == filtros.metodo_http.upper())
        if filtros.codigo_respuesta is not None:
            _w(AuditoriaModelo.codigo_respuesta == filtros.codigo_respuesta)
        if filtros.desde:
            _w(AuditoriaModelo.timestamp >= filtros.desde)
        if filtros.hasta:
            _w(AuditoriaModelo.timestamp <= filtros.hasta)

        if filtros.cursor:
            try:
                cursor_ts, cursor_id = decode_cursor(filtros.cursor)
                stmt = stmt.where(
                    or_(
                        AuditoriaModelo.timestamp < cursor_ts,
                        and_(
                            AuditoriaModelo.timestamp == cursor_ts,
                            AuditoriaModelo.id < cursor_id,
                        ),
                    )
                )
            except Exception:
                pass

        total = (await self._s.execute(count_stmt)).scalar_one()

        stmt = (
            stmt
            .order_by(AuditoriaModelo.timestamp.desc(), AuditoriaModelo.id.desc())
            .limit(filtros.tamanio + 1)
        )
        modelos = list((await self._s.execute(stmt)).scalars().all())

        siguiente_cursor: str | None = None
        if len(modelos) > filtros.tamanio:
            modelos = modelos[: filtros.tamanio]
            ultimo  = modelos[-1]
            siguiente_cursor = encode_cursor(ultimo.timestamp, ultimo.id)

        return [self._a_entidad(m) for m in modelos], total, siguiente_cursor

    async def obtener_por_id(self, id: UUID) -> RegistroAuditoria | None:
        result = await self._s.execute(
            select(AuditoriaModelo).where(AuditoriaModelo.id == id)
        )
        m = result.scalar_one_or_none()
        return self._a_entidad(m) if m else None

    # ── Estadísticas ───────────────────────────────────────────────────────────

    async def estadisticas(
        self,
        organization_id: UUID | None = None,
        desde: datetime | None = None,
        hasta: datetime | None = None,
    ) -> EstadisticasAuditoria:
        ahora = datetime.now(timezone.utc)
        desde = desde or (ahora - timedelta(days=30))
        hasta = hasta or ahora

        def _base():
            q = select(AuditoriaModelo.categoria, func.count().label("n")).where(
                AuditoriaModelo.timestamp >= desde,
                AuditoriaModelo.timestamp <= hasta,
            )
            if organization_id:
                q = q.where(AuditoriaModelo.organization_id == organization_id)
            return q

        # Conteos por categoría
        rows = (await self._s.execute(_base().group_by(AuditoriaModelo.categoria))).all()
        por_categoria = {r.categoria: r.n for r in rows}
        total = sum(por_categoria.values())

        # Por nivel
        rows_n = (await self._s.execute(
            _base().with_only_columns(AuditoriaModelo.nivel, func.count().label("n"))
                   .group_by(AuditoriaModelo.nivel)
        )).all()
        por_nivel = {r.nivel: r.n for r in rows_n}

        # Por resultado
        rows_r = (await self._s.execute(
            _base().with_only_columns(AuditoriaModelo.resultado, func.count().label("n"))
                   .group_by(AuditoriaModelo.resultado)
        )).all()
        por_resultado = {r.resultado: r.n for r in rows_r}

        # Métricas de seguridad en las últimas 24h
        hace_24h = ahora - timedelta(hours=24)

        def _24h(extra_cond):
            q = select(func.count()).select_from(AuditoriaModelo).where(
                AuditoriaModelo.timestamp >= hace_24h
            )
            if organization_id:
                q = q.where(AuditoriaModelo.organization_id == organization_id)
            return q.where(extra_cond)

        seg_24h = (await self._s.execute(
            _24h(AuditoriaModelo.nivel == NivelEvento.SEGURIDAD.value)
        )).scalar_one()

        crit_24h = (await self._s.execute(
            _24h(AuditoriaModelo.nivel == NivelEvento.CRITICO.value)
        )).scalar_one()

        login_fail_24h = (await self._s.execute(
            _24h(and_(
                AuditoriaModelo.accion == "auth.login",
                AuditoriaModelo.resultado != ResultadoAuditoria.EXITOSO.value,
            ))
        )).scalar_one()

        return EstadisticasAuditoria(
            total_eventos=total,
            por_categoria=por_categoria,
            por_nivel=por_nivel,
            por_resultado=por_resultado,
            eventos_seguridad_24h=seg_24h,
            eventos_criticos_24h=crit_24h,
            intentos_fallidos_login_24h=login_fail_24h,
            periodo_desde=desde,
            periodo_hasta=hasta,
        )

    # ── Verificación de integridad ─────────────────────────────────────────────

    async def verificar_integridad(
        self,
        organization_id: UUID | None = None,
        desde: datetime | None = None,
        hasta: datetime | None = None,
        limite: int = 5000,
    ) -> ResultadoVerificacion:
        stmt = (
            select(AuditoriaModelo)
            .order_by(AuditoriaModelo.numero_secuencia.asc())
            .limit(limite)
        )
        if organization_id:
            stmt = stmt.where(AuditoriaModelo.organization_id == organization_id)
        if desde:
            stmt = stmt.where(AuditoriaModelo.timestamp >= desde)
        if hasta:
            stmt = stmt.where(AuditoriaModelo.timestamp <= hasta)

        modelos = list((await self._s.execute(stmt)).scalars().all())

        ok = fallidos = sin_firma = 0
        ids_fallidos: list[UUID] = []

        for m in modelos:
            registro = self._a_entidad(m)
            if not registro.hash_registro or not registro.firma_hmac:
                sin_firma += 1
                continue
            if verificar(registro):
                ok += 1
            else:
                fallidos += 1
                ids_fallidos.append(registro.id)

        return ResultadoVerificacion(
            total_verificados=len(modelos),
            total_ok=ok,
            total_fallidos=fallidos,
            total_sin_firma=sin_firma,
            integro=fallidos == 0,
            ids_fallidos=ids_fallidos,
        )

    # ── Exportación ────────────────────────────────────────────────────────────

    async def exportar(
        self,
        organization_id: UUID | None = None,
        desde: datetime | None = None,
        hasta: datetime | None = None,
        limite: int = 10_000,
    ) -> list[RegistroAuditoria]:
        stmt = select(AuditoriaModelo).order_by(AuditoriaModelo.timestamp.asc()).limit(limite)
        if organization_id:
            stmt = stmt.where(AuditoriaModelo.organization_id == organization_id)
        if desde:
            stmt = stmt.where(AuditoriaModelo.timestamp >= desde)
        if hasta:
            stmt = stmt.where(AuditoriaModelo.timestamp <= hasta)
        modelos = list((await self._s.execute(stmt)).scalars().all())
        return [self._a_entidad(m) for m in modelos]

    # ── Mapper privado ─────────────────────────────────────────────────────────

    @staticmethod
    def _a_entidad(m: AuditoriaModelo) -> RegistroAuditoria:
        return RegistroAuditoria(
            id                = m.id,
            timestamp         = m.timestamp,
            timestamp_unix_ms = m.timestamp_unix_ms,
            correlation_id    = m.correlation_id or "",
            actor_id          = m.actor_id,
            actor_email       = m.actor_email,
            actor_ip          = m.actor_ip or "",
            actor_user_agent  = m.actor_user_agent or "",
            actor_tipo        = TipoActor(m.actor_tipo),
            sesion_id         = m.sesion_id,
            api_key_id        = m.api_key_id,
            categoria         = CategoriaEvento(m.categoria),
            nivel             = NivelEvento(m.nivel),
            accion            = m.accion,
            resultado         = ResultadoAuditoria(m.resultado),
            resultado_detalle = m.resultado_detalle,
            metodo_http       = m.metodo_http or "",
            path              = m.path or "",
            query_params      = m.query_params,
            codigo_respuesta  = m.codigo_respuesta,
            duracion_ms       = m.duracion_ms,
            recurso_tipo      = m.recurso_tipo,
            recurso_id        = m.recurso_id,
            valor_anterior    = m.valor_anterior,
            valor_nuevo       = m.valor_nuevo,
            diferencia        = m.diferencia,
            metadatos         = m.metadatos or {},
            razon             = m.razon,
            error_mensaje     = m.error_mensaje,
            organization_id   = m.organization_id,
            numero_secuencia  = m.numero_secuencia,
            hash_registro     = m.hash_registro or "",
            firma_hmac        = m.firma_hmac or "",
        )
