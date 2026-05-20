import hashlib
import hmac as _hmac

from app.domain.entities.auth.auditoria import RegistroAuditoria


def _secreto() -> bytes:
    from app.config import config
    base = config.JWT_SECRET_KEY.get_secret_value().encode()
    return _hmac.new(base, b"auditoria-v1", hashlib.sha256).digest()


def firmar(registro: RegistroAuditoria) -> tuple[str, str]:
    """Retorna (hash_registro, firma_hmac). Llamar antes de persistir."""
    hash_reg = registro.calcular_hash()
    firma = _hmac.new(_secreto(), hash_reg.encode(), hashlib.sha256).hexdigest()
    return hash_reg, f"v1:{firma}"


def verificar(registro: RegistroAuditoria) -> bool:
    """False si firma vacía (trigger BD), hash difiere, o HMAC no coincide."""
    if not registro.hash_registro or not registro.firma_hmac:
        return False
    if not _hmac.compare_digest(registro.calcular_hash(), registro.hash_registro):
        return False
    esperada = f"v1:{_hmac.new(_secreto(), registro.hash_registro.encode(), hashlib.sha256).hexdigest()}"
    return _hmac.compare_digest(esperada, registro.firma_hmac)
