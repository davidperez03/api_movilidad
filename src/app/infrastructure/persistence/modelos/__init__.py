# Importar todos los modelos para que SQLAlchemy los registre en Base.metadata
# y Alembic pueda detectar cambios de esquema con autogenerate.
from app.infrastructure.persistence.modelos.auth.organizacion_modelo import OrganizacionModelo  # noqa: F401
from app.infrastructure.persistence.modelos.auth.usuario_modelo import UsuarioModelo            # noqa: F401
from app.infrastructure.persistence.modelos.auth.rol_modelo import RolModelo, PermisoModelo, UsuarioRolModelo  # noqa: F401
from app.infrastructure.persistence.modelos.auth.api_key_modelo import ApiKeyModelo             # noqa: F401
from app.infrastructure.persistence.modelos.auth.auditoria_modelo import AuditoriaModelo        # noqa: F401

__all__ = [
    "OrganizacionModelo",
    "UsuarioModelo",
    "RolModelo",
    "PermisoModelo",
    "UsuarioRolModelo",
    "ApiKeyModelo",
    "AuditoriaModelo",
]