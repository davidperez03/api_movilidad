# Patrones de Dominio — Arquitectura Hexagonal

## Value Objects

Objetos sin identidad propia, definidos por su valor. Inmutables.

```python
# domain/value_objects.py
from dataclasses import dataclass
from typing import ClassVar
import re

@dataclass(frozen=True)
class Email:
    valor: str
    _PATRON: ClassVar = re.compile(r"^[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}$")

    def __post_init__(self):
        if not self._PATRON.match(self.valor):
            raise ValueError(f"Email inválido: {self.valor}")
        object.__setattr__(self, "valor", self.valor.lower())

    def __str__(self) -> str:
        return self.valor

@dataclass(frozen=True)
class Dinero:
    monto: int          # En centavos para evitar problemas de punto flotante
    moneda: str = "COP"

    def __post_init__(self):
        if self.monto < 0:
            raise ValueError("El monto no puede ser negativo")
        if self.moneda not in {"COP", "USD", "EUR"}:
            raise ValueError(f"Moneda no soportada: {self.moneda}")

    def sumar(self, otro: "Dinero") -> "Dinero":
        if self.moneda != otro.moneda:
            raise ValueError("No se pueden sumar monedas distintas")
        return Dinero(self.monto + otro.monto, self.moneda)

    @property
    def como_decimal(self) -> float:
        return self.monto / 100
```

---

## Aggregate Root

Controla la consistencia de un conjunto de entidades.

```python
# domain/entities/documento.py
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID
from uuid6 import uuid7
from enum import Enum
from typing import List
from app.domain.entities.version import VersionDocumento
from app.domain.value_objects import Email
from app.domain.events import DocumentoPublicado, VersionCreada

class EstadoDocumento(str, Enum):
    BORRADOR = "borrador"
    EN_REVISION = "en_revision"
    PUBLICADO = "publicado"
    ARCHIVADO = "archivado"

@dataclass
class Documento:
    titulo: str
    propietario_email: Email
    id: UUID = field(default_factory=uuid7)
    estado: EstadoDocumento = EstadoDocumento.BORRADOR
    versiones: List[VersionDocumento] = field(default_factory=list)
    creado_en: datetime = field(default_factory=datetime.utcnow)
    _eventos: List = field(default_factory=list, repr=False)

    def agregar_version(self, contenido: str, autor_email: Email) -> VersionDocumento:
        if self.estado == EstadoDocumento.ARCHIVADO:
            raise ValueError("No se puede versionar un documento archivado")

        numero = len(self.versiones) + 1
        version = VersionDocumento(
            numero=numero,
            contenido=contenido,
            autor_email=autor_email,
        )
        self.versiones.append(version)
        self._eventos.append(VersionCreada(documento_id=self.id, numero_version=numero))
        return version

    def publicar(self) -> None:
        if not self.versiones:
            raise ValueError("No se puede publicar un documento sin versiones")
        if self.estado == EstadoDocumento.PUBLICADO:
            raise ValueError("El documento ya está publicado")
        self.estado = EstadoDocumento.PUBLICADO
        self._eventos.append(DocumentoPublicado(documento_id=self.id))

    def archivar(self) -> None:
        if self.estado == EstadoDocumento.ARCHIVADO:
            raise ValueError("El documento ya está archivado")
        self.estado = EstadoDocumento.ARCHIVADO

    def tomar_eventos(self) -> List:
        """Consume y retorna los eventos de dominio pendientes."""
        eventos = self._eventos.copy()
        self._eventos.clear()
        return eventos

    @property
    def version_actual(self) -> VersionDocumento | None:
        return self.versiones[-1] if self.versiones else None
```

---

## Domain Events

```python
# domain/events.py
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID
from uuid6 import uuid7

@dataclass(frozen=True)
class EventoDominio:
    id: UUID = field(default_factory=uuid7)
    ocurrido_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass(frozen=True)
class DocumentoPublicado(EventoDominio):
    documento_id: UUID = None

@dataclass(frozen=True)
class VersionCreada(EventoDominio):
    documento_id: UUID = None
    numero_version: int = 0

@dataclass(frozen=True)
class UsuarioRegistrado(EventoDominio):
    usuario_id: UUID = None
    email: str = ""
```

---

## Publicación de Eventos (Event Bus)

```python
# domain/ports/outbound/bus_eventos.py
from abc import ABC, abstractmethod
from app.domain.events import EventoDominio

class BusEventos(ABC):
    @abstractmethod
    async def publicar(self, evento: EventoDominio) -> None: ...

# infrastructure/messaging/redis_bus.py
import json
import redis.asyncio as redis
from app.domain.ports.outbound.bus_eventos import BusEventos
from app.domain.events import EventoDominio

class RedisBusEventos(BusEventos):
    def __init__(self, cliente: redis.Redis):
        self._redis = cliente

    async def publicar(self, evento: EventoDominio) -> None:
        canal = type(evento).__name__
        payload = json.dumps({
            "id": str(evento.id),
            "tipo": canal,
            "ocurrido_en": evento.ocurrido_en.isoformat(),
            "datos": {k: str(v) for k, v in vars(evento).items() if k not in ("id", "ocurrido_en")},
        })
        await self._redis.publish(canal, payload)
```

---

## Especificaciones (Patrón Specification)

```python
# domain/specifications.py
from abc import ABC, abstractmethod
from typing import TypeVar, Generic
from app.domain.entities.documento import Documento

T = TypeVar("T")

class Especificacion(ABC, Generic[T]):
    @abstractmethod
    def es_satisfecha_por(self, candidato: T) -> bool: ...

    def y(self, otra: "Especificacion[T]") -> "EspecificacionY[T]":
        return EspecificacionY(self, otra)

    def o(self, otra: "Especificacion[T]") -> "EspecificacionO[T]":
        return EspecificacionO(self, otra)

class EspecificacionY(Especificacion[T]):
    def __init__(self, izq: Especificacion[T], der: Especificacion[T]):
        self._izq = izq
        self._der = der

    def es_satisfecha_por(self, candidato: T) -> bool:
        return self._izq.es_satisfecha_por(candidato) and self._der.es_satisfecha_por(candidato)

# Uso concreto:
class DocumentoPublicable(Especificacion[Documento]):
    def es_satisfecha_por(self, doc: Documento) -> bool:
        return bool(doc.versiones) and doc.estado.value != "archivado"
```

---

## Repositorio con Paginación

```python
# domain/ports/outbound/repositorio_documento.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID
from typing import Generic, TypeVar, List, Optional

T = TypeVar("T")

@dataclass
class Pagina(Generic[T]):
    items: List[T]
    total: int
    pagina: int
    tam_pagina: int

    @property
    def total_paginas(self) -> int:
        return -(-self.total // self.tam_pagina)  # División con techo

    @property
    def hay_siguiente(self) -> bool:
        return self.pagina < self.total_paginas

class RepositorioDocumento(ABC):

    @abstractmethod
    async def guardar(self, doc) -> object: ...

    @abstractmethod
    async def buscar_por_id(self, id: UUID) -> Optional[object]: ...

    @abstractmethod
    async def listar(self, pagina: int = 1, tam_pagina: int = 20) -> Pagina: ...
```
