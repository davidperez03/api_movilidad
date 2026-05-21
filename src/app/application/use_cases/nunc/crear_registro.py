import logging
from dataclasses import dataclass, field
from uuid import UUID
from app.domain.entities.nunc.registro import RegistroNunc
from app.domain.ports.outbound.nunc.repositorio_sesion import RepositorioSesionNunc
from app.domain.exceptions import EntidadNoEncontrada, ReglaDeNegocioViolada

logger = logging.getLogger(__name__)


@dataclass
class ComandoCrearRegistroNunc:
    sesion_codigo: str
    placa: str
    nombre_conductor: str
    documento_conductor: str
    datos_forenses: dict = field(default_factory=dict)
    creado_por: UUID | None = None
    organization_id: UUID | None = None


class CrearRegistroNuncUseCase:
    def __init__(self, repo: RepositorioSesionNunc) -> None:
        self._repo = repo

    async def ejecutar(self, cmd: ComandoCrearRegistroNunc) -> RegistroNunc:
        sesion = await self._repo.buscar_sesion_por_codigo(cmd.sesion_codigo)
        if not sesion:
            raise EntidadNoEncontrada("Sesión NUNC no encontrada")
        if not sesion.esta_activa:
            raise ReglaDeNegocioViolada("La sesión NUNC no está activa o ha expirado")

        registro = RegistroNunc(
            sesion_id=sesion.id,
            placa=cmd.placa,
            nombre_conductor=cmd.nombre_conductor,
            documento_conductor=cmd.documento_conductor,
            datos_forenses=cmd.datos_forenses,
            creado_por=cmd.creado_por,
            organization_id=cmd.organization_id or sesion.organization_id,
        )
        registro = await self._repo.guardar_registro(registro)
        logger.info("Registro NUNC creado", extra={"registro_id": str(registro.id), "placa": registro.placa})
        return registro
