from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.repositorios.auth.api_key_repo import ApiKeyRepositorioSQL
from app.infrastructure.persistence.repositorios.auth.usuario_repo import UsuarioRepositorioSQL
from app.application.use_cases.auth.api_keys.crear_api_key import CrearApiKeyUseCase, ComandoCrearApiKey
from app.application.use_cases.auth.api_keys.listar_api_keys import ListarApiKeysUseCase, ComandoListarApiKeys
from app.application.use_cases.auth.api_keys.revocar_api_key import RevocarApiKeyUseCase, ComandoRevocarApiKey
from app.api.v1.schemas.auth.api_key import CrearApiKeyRequest, ApiKeyResponse, ApiKeyCreada
from app.domain.entities.auth.usuario import Usuario
from app.dependencies import get_usuario_actual, requiere_permiso
from app.api.v1.mappers.auth.api_key_mapper import map_api_key

router = APIRouter()


@router.post("", response_model=ApiKeyCreada, status_code=201)
async def crear_api_key(
    body: CrearApiKeyRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    usuario_actual: Usuario = Depends(get_usuario_actual),
):
    if body.permisos:
        permisos_usuario = usuario_actual.obtener_permisos()
        no_autorizados = set(body.permisos) - permisos_usuario
        if no_autorizados:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No puedes otorgar permisos que no posees: {sorted(no_autorizados)}",
            )

    repo = ApiKeyRepositorioSQL(session)
    repo_usuario = UsuarioRepositorioSQL(session)
    resultado = await CrearApiKeyUseCase(repo, repo_usuario).ejecutar(
        ComandoCrearApiKey(
            nombre=body.nombre,
            propietario_id=usuario_actual.id,
            permisos=body.permisos,
            expira_en=body.expira_en,
        )
    )
    request.state.audit_recurso_id = resultado.api_key.public_id
    request.state.audit_valor_nuevo = {"nombre": body.nombre, "permisos": body.permisos}
    return ApiKeyCreada(
        **map_api_key(resultado.api_key).model_dump(),
        full_key=resultado.full_key,
    )


@router.get("", response_model=list[ApiKeyResponse])
async def listar_api_keys(
    session: AsyncSession = Depends(get_session),
    usuario_actual: Usuario = Depends(get_usuario_actual),
):
    repo = ApiKeyRepositorioSQL(session)
    keys = await ListarApiKeysUseCase(repo).ejecutar(
        ComandoListarApiKeys(propietario_id=usuario_actual.id)
    )
    return [map_api_key(k) for k in keys]


@router.delete("/{public_id}", status_code=204)
async def revocar_api_key(
    public_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    usuario_actual: Usuario = Depends(get_usuario_actual),
):
    repo = ApiKeyRepositorioSQL(session)
    key = await repo.buscar_por_public_id(public_id)
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"API Key '{public_id}' no encontrada")

    await RevocarApiKeyUseCase(repo).ejecutar(
        ComandoRevocarApiKey(
            api_key_id=key.id,
            solicitante_id=usuario_actual.id,
            es_admin=usuario_actual.tiene_permiso("api_keys:administrar"),
        )
    )
    request.state.audit_recurso_id = public_id
    request.state.audit_valor_nuevo = {"estado": "revocada"}
