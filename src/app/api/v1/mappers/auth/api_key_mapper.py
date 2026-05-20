from app.domain.entities.auth.api_key import ApiKey
from app.api.v1.schemas.auth.api_key import ApiKeyResponse


def map_api_key(k: ApiKey) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=k.public_id,
        nombre=k.nombre,
        key_prefix=k.key_prefix,
        permisos=k.permisos,
        activa=k.activa,
        expira_en=k.expira_en,
        ultimo_uso=k.ultimo_uso,
        creado_en=k.creado_en,
    )
