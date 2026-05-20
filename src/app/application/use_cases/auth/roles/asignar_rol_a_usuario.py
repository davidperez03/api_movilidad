import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from app.domain.entities.auth.rol import AsignacionRol
from app.domain.ports.outbound.auth.repositorio_rol import RepositorioRol
from app.domain.ports.outbound.auth.repositorio_usuario import RepositorioUsuario
from app.domain.ports.outbound.auth.servicio_cache import ServicioCache
from app.domain.exceptions import RolNoEncontrado, EntidadNoEncontrada, ReglaDeNegocioViolada

logger = logging.getLogger(__name__)


@dataclass
class ComandoAsignarRolAUsuario:
    usuario_id: UUID
    rol_id: UUID
    asignado_por_id: UUID
    vigente_hasta: datetime | None = None


class AsignarRolAUsuarioUseCase:
    def __init__(self, repo: RepositorioRol, repo_usuario: RepositorioUsuario, cache: ServicioCache) -> None:
        self._repo = repo
        self._repo_usuario = repo_usuario
        self._cache = cache

    async def ejecutar(self, cmd: ComandoAsignarRolAUsuario) -> AsignacionRol:
        usuario = await self._repo_usuario.buscar_por_id(cmd.usuario_id)
        if not usuario:
            raise EntidadNoEncontrada(f"Usuario {cmd.usuario_id} no encontrado")

        rol = await self._repo.buscar_rol_por_id(cmd.rol_id)
        if not rol:
            raise RolNoEncontrado(f"Rol {cmd.rol_id} no encontrado")

        roles_actuales = await self._repo.obtener_roles_de_usuario(cmd.usuario_id)
        if any(r.id == cmd.rol_id for r in roles_actuales):
            raise ReglaDeNegocioViolada(f"El usuario ya tiene el rol '{rol.nombre}' asignado")

        asignacion = AsignacionRol(
            usuario_id=cmd.usuario_id,
            rol_id=cmd.rol_id,
            asignado_por_id=cmd.asignado_por_id,
            vigente_hasta=cmd.vigente_hasta,
        )
        asignacion = await self._repo.asignar_rol_a_usuario(asignacion)

        await self._cache.delete(f"permisos_usuario:{cmd.usuario_id}")

        logger.info(
            "Rol asignado a usuario",
            extra={"usuario_id": str(cmd.usuario_id), "rol": rol.nombre},
        )
        return asignacion
