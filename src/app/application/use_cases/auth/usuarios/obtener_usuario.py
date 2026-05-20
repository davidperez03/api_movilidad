from uuid import UUID
from app.domain.ports.outbound.auth.repositorio_usuario import RepositorioUsuario
from app.domain.ports.outbound.auth.repositorio_rol import RepositorioRol
from app.domain.entities.auth.usuario import Usuario
from app.domain.exceptions import EntidadNoEncontrada


class ObtenerUsuarioUseCase:
    def __init__(self, repo: RepositorioUsuario, repo_rol: RepositorioRol) -> None:
        self._repo = repo
        self._repo_rol = repo_rol

    async def ejecutar(self, usuario_id: UUID) -> Usuario:
        usuario = await self._repo.buscar_por_id(usuario_id)
        if not usuario:
            raise EntidadNoEncontrada(f"Usuario {usuario_id} no encontrado")

        permisos = await self._repo_rol.obtener_permisos_de_usuario(usuario_id)
        usuario.cargar_permisos(permisos)
        return usuario
