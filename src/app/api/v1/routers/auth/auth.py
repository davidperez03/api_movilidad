import logging
from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.repositorios.auth.usuario_repo import UsuarioRepositorioSQL
from app.infrastructure.persistence.repositorios.auth.rol_repo import RolRepositorioSQL
from app.infrastructure.security.auth.jwt_service import JWTService
from app.infrastructure.security.auth.hash_service import BcryptHashService
from app.infrastructure.cache.redis_service import RedisService
from app.application.use_cases.auth.usuarios.autenticar_usuario import AutenticarUsuarioUseCase, ComandoAutenticar
from app.application.use_cases.auth.usuarios.refrescar_token import RefrescarTokenUseCase, ComandoRefrescarToken
from app.application.use_cases.auth.usuarios.verificar_email import VerificarEmailUseCase, ComandoVerificarEmail
from app.application.use_cases.auth.usuarios.solicitar_reset_password import SolicitarResetPasswordUseCase, ComandoSolicitarReset
from app.application.use_cases.auth.usuarios.reset_password import ResetPasswordUseCase, ComandoResetPassword
from app.api.v1.schemas.auth.auth import (
    LoginRequest, TokenResponse, RefreshTokenRequest, LogoutRequest,
    VerificarEmailRequest, ReenviarVerificacionRequest,
    SolicitarResetPasswordRequest, ResetPasswordRequest,
)
from app.config import config
from app.api.v1.middlewares.rate_limiter import AsyncRateLimiter, AsyncLoginRateLimiter
from app.application.use_cases.auth.usuarios._tasks import enviar_verificacion_email_bg

_limite_auth = AsyncLoginRateLimiter(times=config.RATE_LIMIT_AUTH_PER_MINUTE, seconds=60)
_limite_email = AsyncRateLimiter(times=3, seconds=60)

router = APIRouter()
logger = logging.getLogger(__name__)
jwt_service = JWTService()


async def _solicitar_reset_bg(email: str) -> None:
    from app.infrastructure.persistence.database import AsyncSessionFactory
    from app.infrastructure.persistence.repositorios.auth.usuario_repo import UsuarioRepositorioSQL as _UsuarioRepo
    from app.infrastructure.messaging.smtp_email_service import SmtpEmailService
    try:
        async with AsyncSessionFactory() as session:
            repo = _UsuarioRepo(session)
            await SolicitarResetPasswordUseCase(repo, RedisService(), SmtpEmailService()).ejecutar(
                ComandoSolicitarReset(email=email)
            )
            await session.commit()
    except Exception:
        logger.error("Error en solicitud de reset", exc_info=True)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
    _rl: None = Depends(_limite_auth),
):
    repo = UsuarioRepositorioSQL(session)
    repo_rol = RolRepositorioSQL(session)
    cache = RedisService()

    usuario = await AutenticarUsuarioUseCase(repo, repo_rol, BcryptHashService(), cache).ejecutar(
        ComandoAutenticar(email=body.email, password=body.password.get_secret_value())
    )

    permisos = list(usuario.obtener_permisos())
    access_token, _ = jwt_service.crear_access_token(
        str(usuario.id),
        usuario.email,
        permisos,
        organization_id=str(usuario.organization_id) if usuario.organization_id else None,
    )
    refresh_token, _ = jwt_service.crear_refresh_token(str(usuario.id))

    await cache.set(f"sesion_activa:{usuario.id}", "1", config.INACTIVIDAD_TIMEOUT_MINUTOS * 60)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    body: RefreshTokenRequest,
    session: AsyncSession = Depends(get_session),
    _rl: None = Depends(_limite_auth),
):
    payload = jwt_service.verificar_token(body.refresh_token, tipo="refresh")
    old_jti = payload["jti"]
    usuario_id = UUID(payload["sub"])
    cache = RedisService()

    claimed = await cache.set_nx(f"token_revocado:{old_jti}", "1", config.TOKEN_BLACKLIST_TTL)
    if not claimed:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token ya utilizado o revocado")

    sesion_key = f"sesion_activa:{usuario_id}"
    if not await cache.exists(sesion_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión cerrada por inactividad. Iniciá sesión de nuevo.",
        )
    await cache.set(sesion_key, "1", config.INACTIVIDAD_TIMEOUT_MINUTOS * 60)

    repo = UsuarioRepositorioSQL(session)
    repo_rol = RolRepositorioSQL(session)

    usuario = await RefrescarTokenUseCase(repo, repo_rol).ejecutar(
        ComandoRefrescarToken(usuario_id=usuario_id)
    )

    permisos = list(usuario.obtener_permisos())
    access_token, _ = jwt_service.crear_access_token(
        str(usuario.id),
        usuario.email,
        permisos,
        organization_id=str(usuario.organization_id) if usuario.organization_id else None,
    )
    nuevo_refresh, _ = jwt_service.crear_refresh_token(str(usuario.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=nuevo_refresh,
        expires_in=config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", status_code=204)
async def logout(body: LogoutRequest):
    try:
        payload = jwt_service.verificar_token(body.refresh_token, tipo="refresh")
        cache = RedisService()
        await cache.set(
            f"token_revocado:{payload['jti']}",
            "1",
            config.TOKEN_BLACKLIST_TTL,
        )
        await cache.delete(f"sesion_activa:{payload['sub']}")
    except Exception:
        logger.debug("Logout con token inválido o expirado — se ignora")


@router.post("/verificar-email", status_code=200)
async def verificar_email(
    body: VerificarEmailRequest,
    session: AsyncSession = Depends(get_session),
):
    repo = UsuarioRepositorioSQL(session)
    cache = RedisService()
    await VerificarEmailUseCase(repo, cache).ejecutar(ComandoVerificarEmail(token=body.token))
    return {"mensaje": "Email verificado correctamente. Ya puedes iniciar sesión."}


@router.post("/reenviar-verificacion", status_code=202)
async def reenviar_verificacion(
    request: Request,
    body: ReenviarVerificacionRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    _rl: None = Depends(_limite_email),
):
    repo = UsuarioRepositorioSQL(session)
    usuario = await repo.buscar_por_email(body.email.lower())
    if usuario and not usuario.email_verificado:
        background_tasks.add_task(enviar_verificacion_email_bg, usuario.id, usuario.email, usuario.nombre)
    return {"mensaje": "Si el correo está registrado y pendiente de verificación, recibirás un nuevo enlace."}


@router.post("/solicitar-reset-password", status_code=202)
async def solicitar_reset_password(
    request: Request,
    body: SolicitarResetPasswordRequest,
    background_tasks: BackgroundTasks,
    _rl: None = Depends(_limite_email),
):
    background_tasks.add_task(_solicitar_reset_bg, body.email)
    return {"mensaje": "Si el correo está registrado, recibirás las instrucciones para restablecer tu contraseña."}


@router.post("/reset-password", status_code=200)
async def reset_password(
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_session),
):
    repo = UsuarioRepositorioSQL(session)
    cache = RedisService()
    await ResetPasswordUseCase(repo, cache, BcryptHashService()).ejecutar(
        ComandoResetPassword(token=body.token, nueva_password=body.nueva_password.get_secret_value())
    )
    return {"mensaje": "Contraseña restablecida correctamente. Ya puedes iniciar sesión."}
