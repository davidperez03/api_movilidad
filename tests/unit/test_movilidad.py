import pytest
from datetime import date, timezone
from uuid import uuid4
from app.domain.entities.movilidad.cuenta import CuentaVehiculo, TipoServicio
from app.domain.entities.movilidad.traslado import Traslado, EstadoTraslado
from app.domain.entities.movilidad.radicacion import Radicacion, EstadoRadicacion
from app.domain.entities.movilidad.novedad import Novedad, TipoNovedad, EstadoNovedad
from app.domain.entities.parqueadero.vehiculo import VehiculoParqueadero, TipoVehiculoParqueadero
from app.domain.entities.nunc.sesion import SesionNunc
from app.domain.exceptions import ReglaDeNegocioViolada


# ── Cuenta ────────────────────────────────────────────────────────────────────

def test_cuenta_public_id_con_prefijo():
    c = CuentaVehiculo(placa="ABC123", tipo_servicio=TipoServicio.PARTICULAR)
    assert c.public_id.startswith("cue_")


def test_cuenta_normaliza_placa():
    c = CuentaVehiculo(placa="abc123", tipo_servicio=TipoServicio.PUBLICO)
    assert c.placa == "ABC123"


def test_cuenta_tipo_servicio_valores_correctos():
    assert TipoServicio.PARTICULAR.value == "particular"
    assert TipoServicio.PUBLICO.value == "publico"
    assert TipoServicio.OTRO.value == "otro"


# ── Traslado — máquina de estados ─────────────────────────────────────────────

def test_traslado_transicion_valida():
    t = Traslado(cuenta_id=uuid4())
    t.cambiar_estado(EstadoTraslado.REVISADO)
    assert t.estado == EstadoTraslado.REVISADO


def test_traslado_transicion_invalida_lanza_excepcion():
    t = Traslado(cuenta_id=uuid4())
    with pytest.raises(ReglaDeNegocioViolada):
        t.cambiar_estado(EstadoTraslado.TRASLADADO)


def test_traslado_flujo_completo():
    t = Traslado(cuenta_id=uuid4())
    t.cambiar_estado(EstadoTraslado.REVISADO)
    t.cambiar_estado(EstadoTraslado.APROBADO)
    t.cambiar_estado(EstadoTraslado.ENVIADO_ORGANISMO)
    t.cambiar_estado(EstadoTraslado.TRASLADADO)
    assert t.estado == EstadoTraslado.TRASLADADO
    assert not t.esta_activo


def test_traslado_vencimiento_es_date():
    t = Traslado(cuenta_id=uuid4(), vencimiento=date.today())
    assert isinstance(t.vencimiento, date)


def test_traslado_transiciones_disponibles_sin_asignar():
    t = Traslado(cuenta_id=uuid4())
    disponibles = t.transiciones_disponibles()
    assert EstadoTraslado.REVISADO in disponibles
    assert EstadoTraslado.CON_NOVEDADES in disponibles
    assert EstadoTraslado.APROBADO in disponibles


def test_traslado_flujo_con_devuelto_desde_aprobado():
    t = Traslado(cuenta_id=uuid4())
    t.cambiar_estado(EstadoTraslado.REVISADO)
    t.cambiar_estado(EstadoTraslado.APROBADO)
    t.cambiar_estado(EstadoTraslado.DEVUELTO)
    assert t.estado == EstadoTraslado.DEVUELTO
    assert not t.esta_activo


def test_traslado_devuelto_es_terminal():
    t = Traslado(cuenta_id=uuid4())
    t.cambiar_estado(EstadoTraslado.REVISADO)
    t.cambiar_estado(EstadoTraslado.DEVUELTO)
    with pytest.raises(ReglaDeNegocioViolada):
        t.cambiar_estado(EstadoTraslado.APROBADO)


def test_traslado_con_novedades_puede_volver_a_revisado():
    t = Traslado(cuenta_id=uuid4())
    t.cambiar_estado(EstadoTraslado.CON_NOVEDADES)
    t.cambiar_estado(EstadoTraslado.REVISADO)
    assert t.estado == EstadoTraslado.REVISADO


def test_traslado_sin_asignar_directo_a_con_novedades():
    t = Traslado(cuenta_id=uuid4())
    t.cambiar_estado(EstadoTraslado.CON_NOVEDADES)
    assert t.estado == EstadoTraslado.CON_NOVEDADES


def test_traslado_devuelto_desde_enviado_organismo():
    t = Traslado(cuenta_id=uuid4())
    t.cambiar_estado(EstadoTraslado.REVISADO)
    t.cambiar_estado(EstadoTraslado.APROBADO)
    t.cambiar_estado(EstadoTraslado.ENVIADO_ORGANISMO)
    t.cambiar_estado(EstadoTraslado.DEVUELTO)
    assert not t.esta_activo


# ── Radicación — máquina de estados ──────────────────────────────────────────

def test_radicacion_transicion_valida():
    r = Radicacion(cuenta_id=uuid4())
    r.cambiar_estado(EstadoRadicacion.PENDIENTE_RADICAR)
    assert r.estado == EstadoRadicacion.PENDIENTE_RADICAR


def test_radicacion_transicion_invalida():
    r = Radicacion(cuenta_id=uuid4())
    with pytest.raises(ReglaDeNegocioViolada):
        r.cambiar_estado(EstadoRadicacion.RADICADO)


def test_radicacion_asigna_radicado_en_al_radicar():
    r = Radicacion(cuenta_id=uuid4())
    r.cambiar_estado(EstadoRadicacion.PENDIENTE_RADICAR)
    r.cambiar_estado(EstadoRadicacion.RADICADO)
    assert r.radicado_en is not None
    assert not r.esta_activo


def test_radicacion_no_tiene_traslado_id():
    r = Radicacion(cuenta_id=uuid4())
    assert not hasattr(r, "traslado_id")


def test_radicacion_flujo_con_devolucion():
    r = Radicacion(cuenta_id=uuid4())
    r.cambiar_estado(EstadoRadicacion.PENDIENTE_RADICAR)
    r.cambiar_estado(EstadoRadicacion.ENVIADO_DEVOLUCION)
    r.cambiar_estado(EstadoRadicacion.DEVUELTO)
    assert r.estado == EstadoRadicacion.DEVUELTO
    assert not r.esta_activo


def test_radicacion_devuelto_es_terminal():
    r = Radicacion(cuenta_id=uuid4())
    r.cambiar_estado(EstadoRadicacion.PENDIENTE_RADICAR)
    r.cambiar_estado(EstadoRadicacion.ENVIADO_DEVOLUCION)
    r.cambiar_estado(EstadoRadicacion.DEVUELTO)
    with pytest.raises(ReglaDeNegocioViolada):
        r.cambiar_estado(EstadoRadicacion.PENDIENTE_RADICAR)


def test_radicacion_con_novedades_puede_volver_a_revisado():
    r = Radicacion(cuenta_id=uuid4())
    r.cambiar_estado(EstadoRadicacion.RECIBIDO)
    r.cambiar_estado(EstadoRadicacion.CON_NOVEDADES)
    r.cambiar_estado(EstadoRadicacion.REVISADO)
    assert r.estado == EstadoRadicacion.REVISADO


def test_radicacion_flujo_sin_asignar_a_recibido():
    r = Radicacion(cuenta_id=uuid4())
    r.cambiar_estado(EstadoRadicacion.RECIBIDO)
    r.cambiar_estado(EstadoRadicacion.REVISADO)
    r.cambiar_estado(EstadoRadicacion.PENDIENTE_RADICAR)
    r.cambiar_estado(EstadoRadicacion.RADICADO)
    assert not r.esta_activo


# ── Novedad ───────────────────────────────────────────────────────────────────

def test_novedad_proceso_tipo_valido():
    n = Novedad(proceso_tipo="traslado", proceso_id=uuid4(),
                tipo_novedad=TipoNovedad.DOCUMENTOS_FALTANTES, descripcion="Falta CC")
    assert n.estado == EstadoNovedad.PENDIENTE


def test_novedad_proceso_tipo_invalido():
    with pytest.raises(ReglaDeNegocioViolada):
        Novedad(proceso_tipo="otro_tipo", proceso_id=uuid4(),
                tipo_novedad=TipoNovedad.OTRO, descripcion="test")


def test_novedad_resolver_vacia_lanza_excepcion():
    n = Novedad(proceso_tipo="traslado", proceso_id=uuid4(),
                tipo_novedad=TipoNovedad.PLACA_INCORRECTA, descripcion="Placa mal")
    with pytest.raises(ReglaDeNegocioViolada):
        n.resolver("", uuid4())


def test_novedad_resolver_correctamente():
    n = Novedad(proceso_tipo="radicacion", proceso_id=uuid4(),
                tipo_novedad=TipoNovedad.DOCUMENTOS_INCORRECTOS, descripcion="Guía mal")
    n.resolver("Se corrigió la guía", uuid4())
    assert n.estado == EstadoNovedad.RESUELTA
    assert n.resuelto_en is not None


# ── Parqueadero ───────────────────────────────────────────────────────────────

def test_vehiculo_enum_valores_correctos():
    assert TipoVehiculoParqueadero.GRUA_PLATAFORMA.value == "grua_plataforma"
    assert TipoVehiculoParqueadero.FURGON.value == "furgon"


def test_vehiculo_placa_normalizada():
    v = VehiculoParqueadero(placa="abc123", tipo_vehiculo=TipoVehiculoParqueadero.CAMIONETA)
    assert v.placa == "ABC123"
