# Changelog

Todos los cambios notables de este proyecto se documentan aquí.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/).
Versionamiento según [Semantic Versioning](https://semver.org/lang/es/).

---

## [v0.3.1] - 2026-05-22

### Fixed
- Botón Authorize en Swagger UI habilitado con HTTPBearer
- ReDoc pinado a versión 2.1.3 estable (CDN @next estaba caído)
- CSP extendido con font-src, worker-src blob: y fonts.googleapis.com para ReDoc
- /health y /ready visibles en el schema bajo tag Sistema

### Changed
- Descripción general de la API simplificada con guía de autenticación y paginación
- Tags con descripción por módulo en OpenAPI docs
- Ejemplos en schemas de login, cuentas, traslados y radicaciones

---

## [v0.3.0] - 2026-05-21

### Added
- Estado `devuelto` en traslados (desde `aprobado`, `en_transito`, `recibido`) y radicaciones (desde `en_revision`, `aprobada`, `radicada`)
- Migración 003: `ALTER TYPE` para agregar valor `devuelto` a ambos enums de estado
- Módulo inventarios parqueadero completo: insumos, stock, rangos, movimientos y cierres con detalle
- Migración 004: tablas `inv_insumos`, `inv_stock`, `inv_rangos`, `inv_movimientos`, `parq_inv_cierres` con RLS por tenant
- Router `GET /parqueadero/alertas`: UNION query SOAT + tecnomecánica + licencias venciendo en N días
- Router `GET /movilidad/dashboard`: contadores de traslados y radicaciones por estado
- Reportes de movilidad: activos, por_vencer, vencidos, completados con filtros de fecha y organismo
- Catálogos: CRUD de organismos de tránsito y empresas transportadoras
- Módulo novedades: crear, listar, obtener y resolver con máquina de estados
- Notificaciones de radicación: endpoint `PATCH /radicaciones/{id}/notificacion`
- PDF de remisión: `GET /traslados/{id}/remision.pdf` con Jinja2 + WeasyPrint
- Consulta pública de placa enriquecida con proceso activo, días restantes y ciudad del organismo
- `PaginaResponse[T]` genérico compartido entre todos los módulos
- `dias_restantes` en responses de traslados y radicaciones

### Changed
- `ReglaDeNegocioViolada` devuelve HTTP 409 en lugar de 422
- Permisos extraídos a constantes de módulo en todos los routers (`_PERM_LEER`, `_PERM_CREAR`, etc.)
- `listar_novedades` y `obtener_novedad` usan permiso `leer` en lugar de `resolver`

### Fixed
- Migración 002: RLS en tablas catálogo (`organismos`, `empresas`) sin `organization_id` usaba política abierta incorrecta
- `crear_superadmin.py`: `await` faltante en `hash_svc.hashear()`
- `auditoria_repo.py`: definiciones locales de `encode_cursor`/`decode_cursor` tapaban el import correcto causando `NameError`

### Refactored
- `_cursor.py`: encode/decode de cursor centralizado, elimina duplicados en 9 repositorios
- `_shared.py`: `dias_restantes()` compartido entre routers de traslados y radicaciones
- Todos los imports inline movidos al encabezado de cada módulo

---

## [v0.2.1] - 2026-05-20

### Fixed
- Alineación de la API con migración 002: campos y enums corregidos en movilidad y parqueadero
- Módulo parqueadero completado tras corrección de migración

---

## [v0.2.0] - 2026-05-19

### Added
- Módulo movilidad: cuentas, traslados y radicaciones con arquitectura hexagonal completa
- Módulo parqueadero: vehículos, operadores e inspecciones
- Módulo NUNC: sesiones
- Migración 002: tablas de movilidad, parqueadero y NUNC con RLS por tenant
- Paginación cursor-based en todos los listados
- `organization_id` en todas las entidades multi-tenant

---

## [v0.1.0] - 2026-05-19

### Added
- Arquitectura hexagonal base (domain / application / infrastructure / api)
- Autenticación enterprise: JWT access + refresh tokens, API Keys, blacklist Redis
- RBAC: roles, permisos granulares, caché de permisos en Redis
- Rate limiting por IP y por usuario autenticado
- Sistema de auditoría con firma criptográfica y paginación cursor-based
- Middlewares: seguridad, CORS, trazabilidad con correlation ID
- Migración 001: tablas de usuarios, roles, permisos, API keys, auditoría con RLS
- Script `crear_superadmin.py`
- Suite de pruebas: unitarias y de integración contra BD real
