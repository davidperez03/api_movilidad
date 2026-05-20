import pytest
from uuid6 import uuid7
from app.infrastructure.security.auth.jwt_service import JWTService
from app.domain.exceptions import TokenInvalido, TokenExpirado


@pytest.fixture
def jwt():
    return JWTService()


def test_crear_y_verificar_access_token(jwt):
    usuario_id = str(uuid7())
    token, jti = jwt.crear_access_token(usuario_id, "x@x.com", ["usuarios:leer"])

    payload = jwt.verificar_token(token, tipo="access")

    assert payload["sub"] == usuario_id
    assert payload["email"] == "x@x.com"
    assert "usuarios:leer" in payload["permisos"]
    assert payload["jti"] == jti


def test_crear_y_verificar_refresh_token(jwt):
    usuario_id = str(uuid7())
    token, jti = jwt.crear_refresh_token(usuario_id)

    payload = jwt.verificar_token(token, tipo="refresh")

    assert payload["sub"] == usuario_id
    assert payload["jti"] == jti


def test_tipo_incorrecto_lanza_token_invalido(jwt):
    usuario_id = str(uuid7())
    access_token, _ = jwt.crear_access_token(usuario_id, "x@x.com", [])

    with pytest.raises(TokenInvalido):
        jwt.verificar_token(access_token, tipo="refresh")


def test_token_malformado_lanza_token_invalido(jwt):
    with pytest.raises(TokenInvalido):
        jwt.verificar_token("esto.no.es.un.jwt", tipo="access")


def test_token_alterado_lanza_token_invalido(jwt):
    usuario_id = str(uuid7())
    token, _ = jwt.crear_access_token(usuario_id, "x@x.com", [])
    token_alterado = token[:-5] + "XXXXX"

    with pytest.raises(TokenInvalido):
        jwt.verificar_token(token_alterado, tipo="access")
