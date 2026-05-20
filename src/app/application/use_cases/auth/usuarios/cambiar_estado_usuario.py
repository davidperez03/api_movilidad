import logging
from dataclasses import dataclass
from uuid import UUID
from app.domain.entities.auth.usuario import Usuario, EstadoUsuario
from app.domain.ports.outbound.auth.repositorio_usuario import RepositorioUsuario
from app.domain.exceptions import EntidadNoEncontrada, PermisoDenegado, ReglaDeNegocioViolada

logger = logging.getLogger(__name__)

_TRANSICIONES_VALIDAS: dict[EstadoUsuario, set[EstadoUsuario]] = {
    EstadoUsuario.ACTIVO:                   {EstadoUsuario.SUSPENDIDO, EstadoUsuario.INACTIVO},
    EstadoUsuario.SUSPENDIDO:               {EstadoUsuario.ACTIVO, EstadoUsuario.INACTIVO},
    EstadoUsuario.INACTIVO:                 {EstadoUsuario.ACTIVO},
    EstadoUsuario.PENDIENTE_VERIFICACION:   {EstadoUsuario.ACTIVO, EstadoUsuario.INACTIVO},
}


@dataclass
class ComandoCambiarEstado:
    usuario_id: UUID
    solicitante_id: UUID
    nuevo_estado: EstadoUsuario
    puede_administrar_usuarios: bool
    razon: str | None = None


class CambiarEstadoUsuarioUseCase:
    def __init__(self, repo: RepositorioUsuario) -> None:
        self._repo = repo

    async def ejecutar(self, cmd: ComandoCambiarEstado) -> tuple[Usuario, EstadoUsuario]:
        if not cmd.puede_administrar_usuarios:
            raise PermisoDenegado("Se requiere permiso para gestionar usuarios")

        if cmd.solicitante_id == cmd.usuario_id:
            raise PermisoDenegado("No puedes cambiar tu propio estado")

        usuario = await self._repo.buscar_por_id(cmd.usuario_id)
        if not usuario:
            raise EntidadNoEncontrada(f"Usuario {cmd.usuario_id} no encontrado")

        estado_anterior = usuario.estado

        if usuario.estado == cmd.nuevo_estado:
            raise ReglaDeNegocioViolada(f"El usuario ya está en estado '{cmd.nuevo_estado.value}'")

        estados_permitidos = _TRANSICIONES_VALIDAS.get(usuario.estado, set())
        if cmd.nuevo_estado not in estados_permitidos:
            raise ReglaDeNegocioViolada(
                f"Transición inválida: '{usuario.estado.value}' → '{cmd.nuevo_estado.value}'"
            )

        if cmd.nuevo_estado == EstadoUsuario.ACTIVO:
            usuario.activar()
        elif cmd.nuevo_estado == EstadoUsuario.SUSPENDIDO:
            usuario.suspender()
        elif cmd.nuevo_estado == EstadoUsuario.INACTIVO:
            usuario.desactivar()

        usuario = await self._repo.actualizar(usuario)

        logger.info(
            "Estado de usuario cambiado",
            extra={
                "usuario_id": str(cmd.usuario_id),
                "estado_anterior": estado_anterior.value,
                "nuevo_estado": cmd.nuevo_estado.value,
                "solicitante_id": str(cmd.solicitante_id),
                "razon": cmd.razon,
            },
        )
        return usuario, estado_anterior
