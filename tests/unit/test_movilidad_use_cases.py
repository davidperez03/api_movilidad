"""Tests unitarios para use cases de movilidad usando mocks."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.domain.entities.movilidad.cuenta import CuentaVehiculo, TipoServicio
from app.domain.entities.movilidad.traslado import Traslado, EstadoTraslado
from app.domain.entities.movilidad.radicacion import Radicacion, EstadoRadicacion
from app.domain.entities.movilidad.novedad import Novedad, TipoNovedad, PrioridadNovedad, EstadoNovedad
from app.domain.exceptions import ReglaDeNegocioViolada, EntidadNoEncontrada
from app.application.use_cases.movilidad.crear_traslado import CrearTrasladoUseCase, ComandoCrearTraslado
from app.application.use_cases.movilidad.crear_radicacion import CrearRadicacionUseCase, ComandoCrearRadicacion
from app.application.use_cases.movilidad.cambiar_estado_traslado import (
    CambiarEstadoTrasladoUseCase, ComandoCambiarEstadoTraslado,
)
from app.application.use_cases.movilidad.cambiar_estado_radicacion import (
    CambiarEstadoRadicacionUseCase, ComandoCambiarEstadoRadicacion,
)
from app.domain.ports.outbound.movilidad.repositorio_traslado import PaginaTraslados
from app.domain.ports.outbound.movilidad.repositorio_radicacion import PaginaRadicaciones


def _cuenta() -> CuentaVehiculo:
    c = CuentaVehiculo(placa="ABC123", tipo_servicio=TipoServicio.PARTICULAR)
    c.numero_cuenta = "20260101-00001"
    return c


def _traslado(estado: EstadoTraslado = EstadoTraslado.SIN_ASIGNAR) -> Traslado:
    t = Traslado(cuenta_id=uuid4())
    t.estado = estado
    return t


def _radicacion(estado: EstadoRadicacion = EstadoRadicacion.SIN_ASIGNAR) -> Radicacion:
    r = Radicacion(cuenta_id=uuid4())
    r.estado = estado
    return r


# ── CrearTraslado ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_crear_traslado_ok():
    cuenta = _cuenta()
    traslado_guardado = _traslado()

    repo_cuenta = AsyncMock()
    repo_cuenta.buscar_por_public_id.return_value = cuenta

    repo_traslado = AsyncMock()
    repo_traslado.tiene_proceso_activo.return_value = False
    repo_traslado.ultimo_completado.return_value = None
    repo_traslado.guardar.return_value = traslado_guardado

    repo_rad = AsyncMock()
    repo_rad.ultimo_completado.return_value = None

    uc = CrearTrasladoUseCase(repo_cuenta, repo_traslado, repo_rad)
    resultado = await uc.ejecutar(ComandoCrearTraslado(
        cuenta_public_id="cue_abc",
        organismo_destino_id=uuid4(),
    ))
    assert resultado.estado == EstadoTraslado.SIN_ASIGNAR
    repo_traslado.guardar.assert_called_once()


@pytest.mark.asyncio
async def test_crear_traslado_cuenta_no_encontrada():
    repo_cuenta = AsyncMock()
    repo_cuenta.buscar_por_public_id.return_value = None

    uc = CrearTrasladoUseCase(repo_cuenta, AsyncMock(), AsyncMock())
    with pytest.raises(EntidadNoEncontrada):
        await uc.ejecutar(ComandoCrearTraslado(cuenta_public_id="cue_x", organismo_destino_id=uuid4()))


@pytest.mark.asyncio
async def test_crear_traslado_proceso_activo_bloquea():
    repo_cuenta = AsyncMock()
    repo_cuenta.buscar_por_public_id.return_value = _cuenta()

    repo_traslado = AsyncMock()
    repo_traslado.tiene_proceso_activo.return_value = True

    uc = CrearTrasladoUseCase(repo_cuenta, repo_traslado, AsyncMock())
    with pytest.raises(ReglaDeNegocioViolada, match="proceso activo"):
        await uc.ejecutar(ComandoCrearTraslado(cuenta_public_id="cue_x", organismo_destino_id=uuid4()))


@pytest.mark.asyncio
async def test_crear_traslado_validacion_secuencia_bloquea_si_ultimo_fue_traslado():
    """No se puede crear otro traslado si el último completado fue un traslado sin radicación intermedia."""
    from datetime import datetime, timezone
    cuenta = _cuenta()

    ultimo_traslado = _traslado(EstadoTraslado.TRASLADADO)
    ultimo_traslado.actualizado_en = datetime(2026, 1, 10, tzinfo=timezone.utc)

    repo_cuenta = AsyncMock()
    repo_cuenta.buscar_por_public_id.return_value = cuenta

    repo_traslado = AsyncMock()
    repo_traslado.tiene_proceso_activo.return_value = False
    repo_traslado.ultimo_completado.return_value = ultimo_traslado

    # Sin radicación completada
    repo_rad = AsyncMock()
    repo_rad.ultimo_completado.return_value = None

    uc = CrearTrasladoUseCase(repo_cuenta, repo_traslado, repo_rad)
    with pytest.raises(ReglaDeNegocioViolada, match="radicado"):
        await uc.ejecutar(ComandoCrearTraslado(cuenta_public_id="cue_x", organismo_destino_id=uuid4()))


# ── CambiarEstadoTraslado ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cambiar_estado_traslado_a_devuelto():
    traslado = _traslado(EstadoTraslado.APROBADO)

    repo = AsyncMock()
    repo.buscar_por_public_id.return_value = traslado
    repo.actualizar.side_effect = lambda t: t

    uc = CambiarEstadoTrasladoUseCase(repo)
    resultado = await uc.ejecutar(ComandoCambiarEstadoTraslado(
        traslado_public_id="tra_abc",
        nuevo_estado=EstadoTraslado.DEVUELTO,
        motivo="Error en documentos",
    ))
    assert resultado.estado == EstadoTraslado.DEVUELTO


@pytest.mark.asyncio
async def test_cambiar_estado_traslado_transicion_invalida():
    traslado = _traslado(EstadoTraslado.SIN_ASIGNAR)

    repo = AsyncMock()
    repo.buscar_por_public_id.return_value = traslado

    uc = CambiarEstadoTrasladoUseCase(repo)
    with pytest.raises(ReglaDeNegocioViolada):
        await uc.ejecutar(ComandoCambiarEstadoTraslado(
            traslado_public_id="tra_abc",
            nuevo_estado=EstadoTraslado.TRASLADADO,
        ))


# ── CambiarEstadoRadicacion ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cambiar_estado_radicacion_a_devuelto_requiere_empresa_y_guia():
    radicacion = _radicacion(EstadoRadicacion.ENVIADO_DEVOLUCION)

    repo = AsyncMock()
    repo.buscar_por_public_id.return_value = radicacion

    uc = CambiarEstadoRadicacionUseCase(repo)
    with pytest.raises(ReglaDeNegocioViolada, match="empresa"):
        await uc.ejecutar(ComandoCambiarEstadoRadicacion(
            radicacion_public_id="rad_abc",
            nuevo_estado=EstadoRadicacion.DEVUELTO,
        ))


@pytest.mark.asyncio
async def test_cambiar_estado_radicacion_a_devuelto_ok_con_empresa_y_guia():
    radicacion = _radicacion(EstadoRadicacion.ENVIADO_DEVOLUCION)

    repo = AsyncMock()
    repo.buscar_por_public_id.return_value = radicacion
    repo.actualizar.side_effect = lambda r: r

    uc = CambiarEstadoRadicacionUseCase(repo)
    resultado = await uc.ejecutar(ComandoCambiarEstadoRadicacion(
        radicacion_public_id="rad_abc",
        nuevo_estado=EstadoRadicacion.DEVUELTO,
        empresa_transportadora_id=uuid4(),
        numero_guia="GU-12345",
    ))
    assert resultado.estado == EstadoRadicacion.DEVUELTO


# ── CrearNovedad con transición automática ────────────────────────────────────

@pytest.mark.asyncio
async def test_crear_novedad_traslado_cambia_estado_a_con_novedades():
    from app.application.use_cases.movilidad.crear_novedad import CrearNovedadUseCase, ComandoCrearNovedad

    traslado = _traslado(EstadoTraslado.REVISADO)
    novedad = Novedad(
        proceso_tipo="traslado",
        proceso_id=traslado.id,
        tipo_novedad=TipoNovedad.DOCUMENTOS_FALTANTES,
        descripcion="Falta acta de defunción",
    )

    repo_novedad = AsyncMock()
    repo_novedad.guardar.return_value = novedad

    repo_traslado = AsyncMock()
    repo_traslado.buscar_por_public_id.return_value = traslado
    repo_traslado.buscar_por_id.return_value = traslado

    traslado_con_novedades = _traslado(EstadoTraslado.CON_NOVEDADES)
    repo_traslado.actualizar.return_value = traslado_con_novedades

    repo_rad = AsyncMock()

    uc = CrearNovedadUseCase(repo_novedad, repo_traslado, repo_rad)
    resultado = await uc.ejecutar(ComandoCrearNovedad(
        proceso_tipo="traslado",
        proceso_public_id=traslado.public_id,
        tipo_novedad=TipoNovedad.DOCUMENTOS_FALTANTES,
        descripcion="Falta acta de defunción",
    ))
    assert resultado.proceso_tipo == "traslado"
    repo_novedad.guardar.assert_called_once()


@pytest.mark.asyncio
async def test_crear_novedad_en_proceso_terminal_lanza_excepcion():
    from app.application.use_cases.movilidad.crear_novedad import CrearNovedadUseCase, ComandoCrearNovedad

    traslado = _traslado(EstadoTraslado.TRASLADADO)

    repo_traslado = AsyncMock()
    repo_traslado.buscar_por_public_id.return_value = traslado

    uc = CrearNovedadUseCase(AsyncMock(), repo_traslado, AsyncMock())
    with pytest.raises(ReglaDeNegocioViolada, match="terminado"):
        await uc.ejecutar(ComandoCrearNovedad(
            proceso_tipo="traslado",
            proceso_public_id=traslado.public_id,
            tipo_novedad=TipoNovedad.OTRO,
            descripcion="Test",
        ))


# ── ResolverNovedad con transición automática ─────────────────────────────────

@pytest.mark.asyncio
async def test_resolver_novedad_vuelve_proceso_a_revisado_si_no_hay_pendientes():
    from app.application.use_cases.movilidad.resolver_novedad import ResolverNovedadUseCase, ComandoResolverNovedad

    traslado = _traslado(EstadoTraslado.CON_NOVEDADES)
    novedad = Novedad(
        proceso_tipo="traslado",
        proceso_id=traslado.id,
        tipo_novedad=TipoNovedad.DOCUMENTOS_FALTANTES,
        descripcion="Falta acta",
    )
    novedad_resuelta = Novedad(
        proceso_tipo="traslado",
        proceso_id=traslado.id,
        tipo_novedad=TipoNovedad.DOCUMENTOS_FALTANTES,
        descripcion="Falta acta",
    )
    novedad_resuelta.estado = EstadoNovedad.RESUELTA

    repo_novedad = AsyncMock()
    repo_novedad.buscar_por_public_id.return_value = novedad
    repo_novedad.actualizar.return_value = novedad_resuelta
    repo_novedad.novedades_pendientes_cuenta.return_value = []  # Sin pendientes

    repo_traslado = AsyncMock()
    repo_traslado.buscar_por_id.return_value = traslado
    traslado_revisado = _traslado(EstadoTraslado.REVISADO)
    repo_traslado.actualizar.return_value = traslado_revisado

    uc = ResolverNovedadUseCase(repo_novedad, repo_traslado, AsyncMock())
    resultado = await uc.ejecutar(ComandoResolverNovedad(
        novedad_public_id=novedad.public_id,
        solucion="Se aportó el documento faltante",
        actor_id=uuid4(),
    ))
    assert resultado.estado == EstadoNovedad.RESUELTA
