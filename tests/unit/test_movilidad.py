import pytest
from datetime import datetime, timezone
from uuid import uuid4
from app.domain.entities.movilidad.cuenta import CuentaVehiculo, TipoServicio
from app.domain.entities.movilidad.traslado import Traslado, EstadoTraslado
from app.domain.entities.movilidad.radicacion import Radicacion, EstadoRadicacion
from app.domain.entities.movilidad.novedad import Novedad, TipoNovedad, EstadoNovedad
from app.domain.exceptions import ReglaDeNegocioViolada


# ── Cuenta ────────────────────────────────────────────────────────────────────

def test_cuenta_crea_public_id_con_prefijo():
    cuenta = CuentaVehiculo(
        placa="ABC123",
        tipo_servicio=TipoServicio.PARTICULAR,
        propietario_nombre="Juan Pérez",
        propietario_documento="123456789",
    )
    assert cuenta.public_id.startswith("cue_")


def test_cuenta_normaliza_placa_a_mayusculas():
    cuenta = CuentaVehiculo(
        placa="abc123",
        tipo_servicio=TipoServicio.PUBLICO,
        propietario_nombre="Test",
        propietario_documento="111",
    )
    assert cuenta.placa == "ABC123"


def test_cuenta_asignar_numero_dos_veces_lanza_excepcion():
    cuenta = CuentaVehiculo(
        placa="XYZ999",
        tipo_servicio=TipoServicio.OFICIAL,
        propietario_nombre="Empresa",
        propietario_documento="900123456",
    )
    cuenta.asignar_numero_cuenta("20240101-00001")
    with pytest.raises(ReglaDeNegocioViolada):
        cuenta.asignar_numero_cuenta("20240101-00002")


# ── Traslado — máquina de estados ─────────────────────────────────────────────

def test_traslado_transicion_valida_sin_asignar_a_revisado():
    t = Traslado(cuenta_id=uuid4(), organismo_destino_id=uuid4())
    t.cambiar_estado(EstadoTraslado.REVISADO)
    assert t.estado == EstadoTraslado.REVISADO


def test_traslado_transicion_invalida_lanza_excepcion():
    t = Traslado(cuenta_id=uuid4(), organismo_destino_id=uuid4())
    with pytest.raises(ReglaDeNegocioViolada):
        t.cambiar_estado(EstadoTraslado.TRASLADADO)


def test_traslado_completado_en_se_marca_al_trasladar():
    t = Traslado(cuenta_id=uuid4(), organismo_destino_id=uuid4())
    t.cambiar_estado(EstadoTraslado.REVISADO)
    t.cambiar_estado(EstadoTraslado.APROBADO)
    t.cambiar_estado(EstadoTraslado.ENVIADO_ORGANISMO)
    t.cambiar_estado(EstadoTraslado.TRASLADADO)
    assert t.completado_en is not None
    assert t.estado == EstadoTraslado.TRASLADADO


def test_traslado_transiciones_disponibles():
    t = Traslado(cuenta_id=uuid4(), organismo_destino_id=uuid4())
    assert EstadoTraslado.REVISADO in t.transiciones_disponibles()
    assert EstadoTraslado.TRASLADADO not in t.transiciones_disponibles()


# ── Radicación — máquina de estados ──────────────────────────────────────────

def test_radicacion_transicion_valida_sin_asignar_a_pendiente():
    r = Radicacion(cuenta_id=uuid4(), traslado_id=uuid4(), organismo_id=uuid4())
    r.cambiar_estado(EstadoRadicacion.PENDIENTE_RADICAR)
    assert r.estado == EstadoRadicacion.PENDIENTE_RADICAR


def test_radicacion_transicion_invalida_lanza_excepcion():
    r = Radicacion(cuenta_id=uuid4(), traslado_id=uuid4(), organismo_id=uuid4())
    with pytest.raises(ReglaDeNegocioViolada):
        r.cambiar_estado(EstadoRadicacion.RADICADO)


def test_radicacion_completado_en_al_radicar():
    r = Radicacion(cuenta_id=uuid4(), traslado_id=uuid4(), organismo_id=uuid4())
    r.cambiar_estado(EstadoRadicacion.PENDIENTE_RADICAR)
    r.cambiar_estado(EstadoRadicacion.RADICADO)
    assert r.completado_en is not None


def test_radicacion_asigna_numero_radicado():
    r = Radicacion(cuenta_id=uuid4(), traslado_id=uuid4(), organismo_id=uuid4())
    r.asignar_numero_radicado("RAD-2024-001")
    assert r.numero_radicado == "RAD-2024-001"


# ── Novedad ───────────────────────────────────────────────────────────────────

def test_novedad_resolver_vacia_lanza_excepcion():
    n = Novedad(cuenta_id=uuid4(), tipo=TipoNovedad.DOCUMENTAL, descripcion="Falta documento")
    with pytest.raises(ReglaDeNegocioViolada):
        n.resolver("")


def test_novedad_resolver_correctamente():
    n = Novedad(cuenta_id=uuid4(), tipo=TipoNovedad.JURIDICA, descripcion="Lío jurídico")
    n.resolver("Se subsanó con poder notarial")
    assert n.estado == EstadoNovedad.RESUELTA
    assert n.resuelto_en is not None


def test_novedad_cerrar_sin_resolver_lanza_excepcion():
    n = Novedad(cuenta_id=uuid4(), tipo=TipoNovedad.FISCAL, descripcion="Deuda tributaria")
    with pytest.raises(ReglaDeNegocioViolada):
        n.cerrar()
