import logging
from dataclasses import dataclass
from uuid import UUID
from app.domain.ports.outbound.auth.repositorio_usuario import RepositorioUsuario
from app.domain.ports.outbound.auth.repositorio_rol import RepositorioRol
from app.domain.entities.auth.usuario import Usuario, EstadoUsuario
from app.domain.exceptions import EntidadNoEncontrada, UsuarioInactivo, VerificacionPendiente

logger = logging.getLogger(__name__)


@dataclass
class ComandoRefrescarToken:
    usuario_id: UUID


class RefrescarTokenUseCase:
    def __init__(
        self,
        repo: RepositorioUsuario,
        repo_rol: RepositorioRol,
    ) -> None:
        self._repo = repo
        self._repo_rol = repo_rol

    async def ejecutar(self, cmd: ComandoRefrescarToken) -> Usuario:
        usuario = await self._repo.buscar_por_id(cmd.usuario_id)
        if not usuario:
            raise EntidadNoEncontrada("Usuario no encontrado")

        if usuario.estado == EstadoUsuario.PENDIENTE_VERIFICACION:
            raise VerificacionPendiente("Debes verificar tu correo electrónico para continuar")

        if not usuario.puede_autenticarse():
            raise UsuarioInactivo(f"La cuenta está {usuario.estado.value}")

        permisos = await self._repo_rol.obtener_permisos_de_usuario(usuario.id)
        usuario.cargar_permisos(permisos)

        return usuario
