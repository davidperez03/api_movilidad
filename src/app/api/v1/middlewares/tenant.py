"""
Middleware de resolución de tenant (multi-tenancy).

Extrae el organization_id del JWT claim 'org_id' y lo almacena en request.state.
Solo activo cuando MULTITENANCY_ENABLED=True en configuración.
"""
import logging
from uuid import UUID
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import config

logger = logging.getLogger(__name__)


class TenantResolutionMiddleware(BaseHTTPMiddleware):
    """Extrae el tenant (organización) desde el JWT y lo inyecta en request.state."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if not config.MULTITENANCY_ENABLED:
            return await call_next(request)

        request.state.organization_id = None

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from app.infrastructure.security.auth.jwt_service import JWTService
                token = auth_header[len("Bearer "):]
                payload = JWTService().verificar_token(token, tipo="access")
                org_id_str = payload.get("org_id")
                if org_id_str:
                    request.state.organization_id = UUID(org_id_str)
            except Exception:
                pass  # Token inválido o sin org_id — el endpoint lo rechazará si es requerido

        return await call_next(request)


def get_organization_id_opcional(request: Request) -> UUID | None:
    """Dependency: retorna org_id del tenant actual (None si no hay tenant)."""
    return getattr(request.state, "organization_id", None)


def requiere_tenant(request: Request) -> UUID:
    """Dependency: falla si no hay tenant resuelto en el request."""
    from fastapi import HTTPException, status
    org_id = getattr(request.state, "organization_id", None)
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este endpoint requiere un contexto de organización (org_id en JWT)",
        )
    return org_id
