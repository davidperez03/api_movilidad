"""Tests del servicio de tokens HMAC para email y reset de contraseña."""
import pytest
from unittest.mock import patch
from app.infrastructure.security.auth.token_service import (
    generar_token_seguro,
    firmar_token,
    verificar_formato,
)


def test_generar_token_es_unico():
    tokens = {generar_token_seguro() for _ in range(100)}
    assert len(tokens) == 100, "Cada token debe ser único"


def test_generar_token_longitud_minima():
    token = generar_token_seguro()
    assert len(token) >= 32


def test_generar_token_solo_caracteres_url_safe():
    import re
    for _ in range(20):
        token = generar_token_seguro()
        assert re.match(r"^[A-Za-z0-9_\-]+$", token), f"Token con caracteres inválidos: {token}"


def test_firmar_token_deterministico():
    token = generar_token_seguro()
    firma1 = firmar_token(token)
    firma2 = firmar_token(token)
    assert firma1 == firma2, "La misma entrada siempre produce la misma firma"


def test_firmar_tokens_distintos_producen_firmas_distintas():
    t1 = generar_token_seguro()
    t2 = generar_token_seguro()
    assert firmar_token(t1) != firmar_token(t2)


def test_firmar_token_no_reversible():
    token = generar_token_seguro()
    firma = firmar_token(token)
    assert token not in firma, "La firma no debe contener el token original"


def test_firma_es_hexadecimal():
    import re
    firma = firmar_token("test-token-123")
    assert re.match(r"^[a-f0-9]{64}$", firma), "La firma debe ser SHA256 hex de 64 chars"


def test_verificar_formato_token_valido():
    token = generar_token_seguro()
    assert verificar_formato(token) is True


def test_verificar_formato_token_demasiado_corto():
    assert verificar_formato("corto") is False
    assert verificar_formato("abc") is False


def test_verificar_formato_token_vacio():
    assert verificar_formato("") is False


def test_verificar_formato_token_con_espacios():
    assert verificar_formato("token con espacios") is False


def test_firmar_token_sensible_al_secreto():
    token = "mismo-token"
    with patch("app.infrastructure.security.auth.token_service._secret", return_value=b"secreto-A"):
        firma_a = firmar_token(token)
    with patch("app.infrastructure.security.auth.token_service._secret", return_value=b"secreto-B"):
        firma_b = firmar_token(token)
    assert firma_a != firma_b, "Diferentes secretos deben producir diferentes firmas"
