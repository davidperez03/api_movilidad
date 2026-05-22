import json
import logging
import time
from datetime import datetime, timezone
from uuid import UUID
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.repositorios.auth.usuario_repo import UsuarioRepositorioSQL
from app.infrastructure.persistence.repositorios.auth.rol_repo import RolRepositorioSQL
from app.infrastructure.security.auth.jwt_service import JWTService
from app.infrastructure.cache.redis_service import RedisService
from app.domain.entities.auth.usuario import Usuario, EstadoUsuario
from app.config import config

jwt_service = JWTService()
logger = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)

_NO_AUTENTICADO = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Token de autenticación requerido",
    headers={"WWW-Authenticate": "Bearer"},
)


async def _extraer_token(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    if not creds:
        raise _NO_AUTENTICADO
    return creds.credentials

_PERM_LOCAL: dict[str, tuple[set[str], float]] = {}


def _perm_local_get(key: str) -> set[str] | None:
    entry = _PERM_LOCAL.get(key)
    if not entry:
        return None
    permisos, ts = entry
    if time.monotonic() - ts > config.PERMISSIONS_LOCAL_CACHE_TTL:
        _PERM_LOCAL.pop(key, None)
        return None
    return permisos


def _perm_local_set(key: str, permisos: set[str]) -> None:
    if len(_PERM_LOCAL) >= config.PERM_LOCAL_CACHE_MAX:
        oldest = min(_PERM_LOCAL, key=lambda k: _PERM_LOCAL[k][1])
        _PERM_LOCAL.pop(oldest, None)
    _PERM_LOCAL[key] = (permisos, time.monotonic())


def _serializar_usuario(u: Usuario) -> str:
    return json.dumps({
        "id": str(u.id),
        "public_id": u.public_id,
        "email": u.email,
        "nombre": u.nombre,
        "apellido": u.apellido,
        "estado": u.estado.value,
        "email_verificado": u.email_verificado,
        "ultimo_login": u.ultimo_login.isoformat() if u.ultimo_login else None,
        "creado_en": u.creado_en.isoformat(),
        "actualizado_en": u.actualizado_en.isoformat(),
        "organization_id": str(u.organization_id) if u.organization_id else None,
    })


def _deserializar_usuario(data: str) -> Usuario:
    d = json.loads(data)

    def _dt(s: str | None) -> datetime | None:
        if not s:
            return None
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    org_id_str = d.get("organization_id")
    return Usuario(
        id=UUID(d["id"]),
        public_id=d["public_id"],
        email=d["email"],
        nombre=d["nombre"],
        apellido=d["apellido"],
        estado=EstadoUsuario(d["estado"]),
        email_verificado=d["email_verificado"],
        ultimo_login=_dt(d["ultimo_login"]),
        creado_en=_dt(d["creado_en"]),
        actualizado_en=_dt(d["actualizado_en"]),
        organization_id=UUID(org_id_str) if org_id_str else None,
    )


def get_organization_id(request: Request) -> UUID | None:
    """Extrae el organization_id del request.state (seteado por TenantResolutionMiddleware)."""
    return getattr(request.state, "organization_id", None)


async def get_usuario_actual(
    request: Request,
    token: str = Depends(_extraer_token),
    session: AsyncSession = Depends(get_session),
) -> Usuario:
    payload = jwt_service.verificar_token(token, tipo="access")

    cache = RedisService()
    jti = payload.get("jti", "")
    if jti and await cache.exists(f"token_revocado:{jti}"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revocado")

    usuario_id = UUID(payload["sub"])

    cambiado_str = await cache.get(f"password_cambiado:{usuario_id}")
    if cambiado_str:
        iat = payload.get("iat", 0)
        if float(iat) < float(cambiado_str):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesión invalidada. Inicia sesión de nuevo.",
            )

    permisos_key = f"permisos_usuario:{usuario_id}"

    # 1. Cache local en memoria (hit más rápido, sin latencia de red)
    permisos = _perm_local_get(permisos_key)
    if permisos is None:
        # 2. Cache Redis (compartido entre instancias/workers)
        permisos_cached = await cache.smembers(permisos_key)
        if permisos_cached:
            permisos = permisos_cached
            _perm_local_set(permisos_key, permisos)
        else:
            # 3. Base de datos
            repo_rol = RolRepositorioSQL(session)
            permisos = await repo_rol.obtener_permisos_de_usuario(usuario_id)
            if permisos:
                await cache.sadd(permisos_key, *permisos, ttl_segundos=config.PERMISSIONS_CACHE_TTL)
                _perm_local_set(permisos_key, permisos)

    perfil_key = f"usuario_perfil:{usuario_id}"
    perfil_cached = await cache.get(perfil_key)
    if perfil_cached:
        usuario = _deserializar_usuario(perfil_cached)
    else:
        repo = UsuarioRepositorioSQL(session)
        usuario = await repo.buscar_por_id(usuario_id)
        if not usuario:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no válido")
        await cache.set(perfil_key, _serializar_usuario(usuario), config.USUARIO_PERFIL_CACHE_TTL)

    if not usuario:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no válido")
    if usuario.estado == EstadoUsuario.PENDIENTE_VERIFICACION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debes verificar tu correo electrónico antes de acceder",
        )
    if not usuario.puede_autenticarse():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no válido")

    # Validar que el tenant del JWT coincide con el tenant real del usuario
    if config.MULTITENANCY_ENABLED:
        claimed_org_str = payload.get("org_id")
        claimed_org = UUID(claimed_org_str) if claimed_org_str else None
        if claimed_org and usuario.organization_id and claimed_org != usuario.organization_id:
            logger.warning(
                "Tenant mismatch en JWT",
                extra={
                    "usuario_id": str(usuario_id),
                    "claimed_org": str(claimed_org),
                    "real_org": str(usuario.organization_id),
                },
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Contexto de tenant inválido")

    usuario.cargar_permisos(set(permisos))

    request.state.usuario_id = usuario.id
    request.state.usuario_email = usuario.email

    await session.execute(
        text("SELECT set_config('app.current_user_id', :uid, true)"),
        {"uid": str(usuario.id)},
    )

    return usuario


def requiere_permiso(permiso: str):
    async def verificar(usuario: Usuario = Depends(get_usuario_actual)) -> Usuario:
        if not usuario.tiene_permiso(permiso):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso requerido: '{permiso}'",
            )
        return usuario
    return verificar


async def get_usuario_por_api_key(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Usuario:
    raw_key = request.headers.get("X-API-Key", "")
    if not raw_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-API-Key requerida")

    from app.infrastructure.persistence.repositorios.auth.api_key_repo import ApiKeyRepositorioSQL
    from app.infrastructure.persistence.repositorios.auth.usuario_repo import UsuarioRepositorioSQL
    from app.application.use_cases.auth.api_keys.validar_api_key import ValidarApiKeyUseCase, ComandoValidarApiKey

    repo_key = ApiKeyRepositorioSQL(session)
    api_key = await ValidarApiKeyUseCase(repo_key).ejecutar(ComandoValidarApiKey(raw_key=raw_key))

    repo_usuario = UsuarioRepositorioSQL(session)
    usuario = await repo_usuario.buscar_por_id(api_key.propietario_id)
    if not usuario or not usuario.puede_autenticarse():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Propietario de la API Key inválido")

    usuario.cargar_permisos(set(api_key.permisos))

    request.state.usuario_id = usuario.id
    request.state.usuario_email = usuario.email

    return usuario
