class DomainException(Exception):
    """Raíz de todas las excepciones de dominio."""


class EntidadNoEncontrada(DomainException):
    """La entidad solicitada no existe."""


class EmailYaRegistrado(DomainException):
    """El email ya está en uso."""


class CredencialesInvalidas(DomainException):
    """Email o contraseña incorrectos."""


class CuentaBloqueada(DomainException):
    """Cuenta bloqueada temporalmente por intentos fallidos."""
    def __init__(self, segundos_restantes: int) -> None:
        self.segundos_restantes = segundos_restantes
        super().__init__(f"Cuenta bloqueada. Intentá de nuevo en {segundos_restantes} segundos.")


class UsuarioInactivo(DomainException):
    """La cuenta del usuario no está activa."""


class VerificacionPendiente(DomainException):
    """La cuenta requiere verificación de email antes de poder acceder."""


class TokenInvalido(DomainException):
    """El token JWT no es válido."""


class TokenExpirado(DomainException):
    """El token JWT ha expirado."""


class TokenRevocado(DomainException):
    """El token ha sido revocado (logout)."""


class PermisoDenegado(DomainException):
    """El actor no tiene permisos para esta acción."""


class ReglaDeNegocioViolada(DomainException):
    """Una regla de negocio fue violada."""


class ClaveIdempotenciaConflicto(DomainException):
    """La clave de idempotencia ya tiene una respuesta en curso."""


class FirmaInvalida(DomainException):
    """La firma HMAC del request no es válida."""


class ApiKeyInvalida(DomainException):
    """La API key no existe o está revocada."""


class RolNoEncontrado(DomainException):
    """El rol especificado no existe."""


class PermisoNoEncontrado(DomainException):
    """El permiso especificado no existe."""
