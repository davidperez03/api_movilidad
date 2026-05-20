import logging
from dataclasses import dataclass
from uuid import UUID
from app.domain.ports.outbound.auth.repositorio_usuario import RepositorioUsuario
from app.domain.ports.outbound.auth.servicio_hash import ServicioHash
from app.domain.exceptions import EntidadNoEncontrada, CredencialesInvalidas, PermisoDenegado

logger = logging.getLogger(__name__)


@dataclass
class ComandoActualizarUsuario:
    usuario_id: UUID
    solicitante_id: UUID
    puede_editar_cualquier_usuario: bool
    nombre: str | None = None
    apellido: str | None = None
    password_actual: str | None = None
    nueva_password: str | None = None


class ActualizarUsuarioUseCase:
    def __init__(self, repo: RepositorioUsuario, hash_service: ServicioHash) -> None:
        self._repo = repo
        self._hash = hash_service

    async def ejecutar(self, cmd: ComandoActualizarUsuario):
        usuario = await self._repo.buscar_por_id(cmd.usuario_id)
        if not usuario:
            raise EntidadNoEncontrada(f"Usuario {cmd.usuario_id} no encontrado")

        es_propio = cmd.solicitante_id == cmd.usuario_id
        if not es_propio and not cmd.puede_editar_cualquier_usuario:
            raise PermisoDenegado("No puedes editar este perfil")

        if cmd.nombre or cmd.apellido:
            usuario.actualizar_perfil(cmd.nombre, cmd.apellido)

        if cmd.nueva_password:
            if not cmd.puede_editar_cualquier_usuario:
                if not cmd.password_actual:
                    raise CredencialesInvalidas("Debes proporcionar la contraseña actual")
                hash_actual = await self._repo.obtener_hash_password(cmd.usuario_id)
                if not await self._hash.verificar(cmd.password_actual, hash_actual or ""):
                    raise CredencialesInvalidas("Contraseña actual incorrecta")
            nuevo_hash = await self._hash.hashear(cmd.nueva_password)
            await self._repo.actualizar_password(cmd.usuario_id, nuevo_hash)

        usuario = await self._repo.actualizar(usuario)
        logger.info("Usuario actualizado", extra={"usuario_id": str(cmd.usuario_id)})
        return usuario
