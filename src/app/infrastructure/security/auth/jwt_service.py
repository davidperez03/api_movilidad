import logging
from datetime import datetime, timedelta, timezone
from app.infrastructure.identity import uuid7
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from app.config import config
from app.domain.exceptions import TokenInvalido, TokenExpirado

logger = logging.getLogger(__name__)


class JWTService:

    def crear_access_token(
        self,
        usuario_id: str,
        email: str,
        permisos: list[str],
        organization_id: str | None = None,
    ) -> tuple[str, str]:
        jti = str(uuid7())
        payload = {
            "sub": usuario_id,
            "email": email,
            "permisos": permisos,
            "type": "access",
            "jti": jti,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(
                minutes=config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
            ),
        }
        if organization_id:
            payload["org_id"] = organization_id
        token = jwt.encode(
            payload,
            config.JWT_SECRET_KEY.get_secret_value(),
            algorithm=config.JWT_ALGORITHM,
        )
        return token, jti

    def crear_refresh_token(self, usuario_id: str) -> tuple[str, str]:
        jti = str(uuid7())
        payload = {
            "sub": usuario_id,
            "type": "refresh",
            "jti": jti,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(
                days=config.JWT_REFRESH_TOKEN_EXPIRE_DAYS
            ),
        }
        token = jwt.encode(
            payload,
            config.JWT_SECRET_KEY.get_secret_value(),
            algorithm=config.JWT_ALGORITHM,
        )
        return token, jti

    def verificar_token(self, token: str, tipo: str = "access") -> dict:
        try:
            payload = jwt.decode(
                token,
                config.JWT_SECRET_KEY.get_secret_value(),
                algorithms=[config.JWT_ALGORITHM],
            )
            if payload.get("type") != tipo:
                raise TokenInvalido(f"Se esperaba token tipo '{tipo}'")
            return payload
        except ExpiredSignatureError as exc:
            raise TokenExpirado("El token ha expirado") from exc
        except InvalidTokenError as exc:
            raise TokenInvalido("Token inválido") from exc
