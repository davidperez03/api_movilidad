"""
Servicio de tokens seguros para verificación de email y reset de contraseña.

Diseño: token aleatorio (en URL) + HMAC del token (en Redis como clave).
- Redis comprometido: revela solo HMACs, no los tokens originales → no se pueden reutilizar.
- Sin HMAC_SECRET: no se pueden forjar tokens aunque se conozca el esquema.
"""
import hashlib
import hmac
import secrets
from app.config import config


def _secret() -> bytes:
    return config.JWT_SECRET_KEY.get_secret_value().encode()


def generar_token_seguro() -> str:
    """Genera token aleatorio de 256 bits, apto para URLs."""
    return secrets.token_urlsafe(32)


def firmar_token(token: str) -> str:
    """Retorna HMAC-SHA256 del token. Se usa como clave en Redis."""
    return hmac.new(_secret(), token.encode(), hashlib.sha256).hexdigest()


def verificar_formato(token: str) -> bool:
    """Valida que el token tenga el formato esperado (evita consultas Redis innecesarias)."""
    return len(token) >= 32 and token.replace("-", "").replace("_", "").isalnum()
