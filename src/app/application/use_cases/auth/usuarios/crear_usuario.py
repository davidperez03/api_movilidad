import logging
from dataclasses import dataclass, field
from uuid import UUID
from app.domain.entities.auth.usuario import Usuario
from app.domain.ports.outbound.auth.repositorio_usuario import RepositorioUsuario
from app.domain.ports.outbound.auth.repositorio_rol import RepositorioRol
from app.domain.ports.outbound.auth.servicio_hash import ServicioHash
from app.domain.exceptions import EmailYaRegistrado, RolNoEncontrado

logger = logging.getLogger(__name__)


@dataclass
class ComandoCrearUsuario:
    email: str
    nombre: str
    apellido: str
    password: str
    organization_id: UUID | None = field(default=None)


class CrearUsuarioUseCase:
    def __init__(
        self,
        repo_usuario: RepositorioUsuario,
        repo_rol: RepositorioRol,
        hash_service: ServicioHash,
    ) -> None:
        self._repo_usuario = repo_usuario
        self._repo_rol = repo_rol
        self._hash = hash_service

    async def ejecutar(self, cmd: ComandoCrearUsuario) -> Usuario:
        email = cmd.email.lower().strip()

        if await self._repo_usuario.existe_email(email):
            raise EmailYaRegistrado(f"El email '{email}' ya está registrado")

        rol = await self._repo_rol.buscar_rol_por_nombre("usuario")
        if not rol:
            raise RolNoEncontrado("El rol 'usuario' no existe en el sistema")

        usuario = Usuario(
            email=email,
            nombre=cmd.nombre.strip(),
            apellido=cmd.apellido.strip(),
            organization_id=cmd.organization_id,
        )

        hash_password = await self._hash.hashear(cmd.password)
        usuario = await self._repo_usuario.guardar(usuario, hash_password)

        from app.domain.entities.auth.rol import AsignacionRol
        asignacion = AsignacionRol(usuario_id=usuario.id, rol_id=rol.id)
        await self._repo_rol.asignar_rol_a_usuario(asignacion)

        logger.info("Usuario creado", extra={"usuario_id": str(usuario.id), "email": usuario.email})
        return usuario
