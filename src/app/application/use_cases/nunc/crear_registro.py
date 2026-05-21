import logging
from dataclasses import dataclass
from uuid import UUID
from app.domain.entities.nunc.registro import RegistroNunc
from app.domain.ports.outbound.nunc.repositorio_sesion import RepositorioSesionNunc
from app.domain.exceptions import EntidadNoEncontrada, ReglaDeNegocioViolada

logger = logging.getLogger(__name__)


@dataclass
class ComandoCrearRegistroNunc:
    sesion_codigo: str
    placa: str
    departamento: str
    municipio: str
    entidad: str
    unidad: str
    ano: str
    organization_id: UUID | None = None


class CrearRegistroNuncUseCase:
    def __init__(self, repo: RepositorioSesionNunc) -> None:
        self._repo = repo

    async def ejecutar(self, cmd: ComandoCrearRegistroNunc) -> RegistroNunc:
        sesion = await self._repo.buscar_sesion_por_codigo(cmd.sesion_codigo)
        if not sesion:
            raise EntidadNoEncontrada("Código de sesión NUNC no encontrado")
        if not sesion.esta_activa:
            raise ReglaDeNegocioViolada("La sesión NUNC no está activa o ha expirado")

        registro = RegistroNunc(
            sesion_id=sesion.id,
            placa=cmd.placa,
            departamento=cmd.departamento,
            municipio=cmd.municipio,
            entidad=cmd.entidad,
            unidad=cmd.unidad,
            ano=cmd.ano,
            organization_id=cmd.organization_id or sesion.organization_id,
        )
        registro = await self._repo.guardar_registro(registro)
        logger.info("Registro NUNC creado", extra={"registro_id": str(registro.id), "placa": registro.placa})
        return registro
