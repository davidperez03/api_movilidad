from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.entities.auth.auditoria import (
    CategoriaEvento,
    NivelEvento,
    RegistroAuditoria,
    ResultadoAuditoria,
)


@dataclass
class FiltrosAuditoria:
    # ── Filtros por actor ─────────────────────────────────────────────────────
    actor_id:    UUID | None = None
    actor_ip:    str | None  = None
    sesion_id:   str | None  = None

    # ── Filtros por recurso ───────────────────────────────────────────────────
    recurso_tipo: str | None = None
    recurso_id:   str | None = None

    # ── Filtros por evento ────────────────────────────────────────────────────
    accion:      str | None                  = None
    categoria:   CategoriaEvento | None      = None
    nivel:       NivelEvento | None          = None
    resultado:   ResultadoAuditoria | None   = None
    metodo_http: str | None                  = None

    # ── Filtros por respuesta HTTP ────────────────────────────────────────────
    codigo_respuesta: int | None = None   # código exacto

    # ── Rango temporal ────────────────────────────────────────────────────────
    desde: datetime | None = None
    hasta: datetime | None = None

    # ── Paginación ────────────────────────────────────────────────────────────
    tamanio: int        = 50
    cursor:  str | None = None


@dataclass
class EstadisticasAuditoria:
    total_eventos:            int
    por_categoria:            dict[str, int]
    por_nivel:                dict[str, int]
    por_resultado:            dict[str, int]
    eventos_seguridad_24h:    int
    eventos_criticos_24h:     int
    intentos_fallidos_login_24h: int
    periodo_desde:            datetime
    periodo_hasta:            datetime


@dataclass
class ResultadoVerificacion:
    total_verificados: int
    total_ok:          int
    total_fallidos:    int
    total_sin_firma:   int        # registros de trigger BD (firma vacía)
    integro:           bool       # True si total_fallidos == 0
    ids_fallidos:      list[UUID] = field(default_factory=list)
    verificado_en:     datetime   = field(default_factory=datetime.utcnow)


class RepositorioAuditoria(ABC):
    """
    Interfaz append-only para la tabla de auditoría.
    Nunca expone UPDATE ni DELETE — el audit log es inmutable por diseño.
    """

    @abstractmethod
    async def registrar(self, registro: RegistroAuditoria) -> None: ...

    @abstractmethod
    async def listar(
        self,
        filtros: FiltrosAuditoria,
        organization_id: UUID | None = None,
    ) -> tuple[list[RegistroAuditoria], int, str | None]: ...

    @abstractmethod
    async def obtener_por_id(self, id: UUID) -> RegistroAuditoria | None: ...

    @abstractmethod
    async def estadisticas(
        self,
        organization_id: UUID | None = None,
        desde: datetime | None = None,
        hasta: datetime | None = None,
    ) -> EstadisticasAuditoria: ...

    @abstractmethod
    async def verificar_integridad(
        self,
        organization_id: UUID | None = None,
        desde: datetime | None = None,
        hasta: datetime | None = None,
        limite: int = 5000,
    ) -> ResultadoVerificacion: ...

    @abstractmethod
    async def exportar(
        self,
        organization_id: UUID | None = None,
        desde: datetime | None = None,
        hasta: datetime | None = None,
        limite: int = 10_000,
    ) -> list[RegistroAuditoria]: ...
