---
name: gitflow
description: >
  Flujo de trabajo Git completo para el proyecto. Usa esta skill siempre que el usuario
  mencione ramas, commits, releases, hotfixes, versiones, PRs, changelog, o cualquier operación
  Git. Incluye comandos exactos, convención de commits, versionamiento semántico y checklist
  de release. Activar también cuando el usuario pregunte "cómo hago un fix", "cómo subo un
  feature", "qué versión va ahora", "cómo preparo el release" o similares.
---

> **Instrucciones de respuesta:** Responder siempre en español. Ir directo al resultado — sin texto conversacional ni introducciones.
>
> **Flujo interactivo:** Un paso a la vez. Esperar confirmación antes de continuar. Al inicio identificar el tipo de operación (feature, bugfix, hotfix, release) y pedir los datos necesarios.

# GitFlow

---

## Flujo Completo — La Única Estructura Válida

Todo cambio sigue este camino sin excepción:

```
main (vacío / init)
  └── develop
        └── feature/XXX-descripcion   ← aquí se trabaja
              │
              └──→ develop             ← merge cuando el feature está listo
                    └── release/vX.Y.Z ← cuando develop está listo para salir
                          ├──→ main    ← merge + tag vX.Y.Z
                          └──→ develop ← merge de vuelta
```

**Hotfix** es el único caso que no pasa por feature ni release:
```
main
  └── hotfix/XXX-descripcion
        ├──→ main    ← merge + tag de parche
        └──→ develop ← merge de vuelta
```

---

## Ramas

### Permanentes (nunca se borran, nunca se commitea directo)

| Rama | Propósito |
|------|-----------|
| `main` | Producción estable — solo recibe merges de `release/` y `hotfix/` |
| `develop` | Integración — solo recibe merges de `feature/`, `bugfix/` y `hotfix/` |

### Temporales (se crean y se borran tras el merge)

| Tipo | Prefijo | Sale de | Mergea a |
|------|---------|---------|----------|
| Feature | `feature/` | develop | develop |
| Bugfix | `bugfix/` | develop | develop |
| Release | `release/` | develop | main + develop |
| Hotfix | `hotfix/` | main | main + develop |

### Nomenclatura

```
feature/[ticket-id]-descripcion-corta
bugfix/[ticket-id]-descripcion-corta
hotfix/[ticket-id]-descripcion-corta
release/vX.Y.Z
```

---

## Flujo 1 — Feature (nueva funcionalidad)

```bash
# 1. Partir siempre desde develop actualizado
git checkout develop && git pull origin develop
git checkout -b feature/001-descripcion

# 2. Trabajar — commits atómicos
git add src/archivo1.py src/archivo2.py
git commit -m "feat(scope): descripción"

# 3. Subir y abrir PR hacia develop
git push -u origin feature/001-descripcion

# 4. Después del merge: borrar rama
git branch -d feature/001-descripcion
git push origin --delete feature/001-descripcion
```

---

## Flujo 2 — Release (sacar versión a producción)

Solo cuando `develop` tiene todo lo que va en la versión.

```bash
# 1. Partir desde develop actualizado
git checkout develop && git pull origin develop
git checkout -b release/vX.Y.Z

# 2. Actualizar versión y CHANGELOG
#    - pyproject.toml → version = "X.Y.Z"
#    - CHANGELOG.md   → agregar sección [X.Y.Z]

git add pyproject.toml CHANGELOG.md
git commit -m "chore(release): prepare vX.Y.Z"

# 3. Subir y abrir PR hacia main
git push -u origin release/vX.Y.Z

# 4. Tras merge a main: tag anotado
git checkout main && git pull origin main
git tag -a vX.Y.Z -m "Release vX.Y.Z — descripción breve"
git push origin main --tags

# 5. Merge de vuelta a develop
git checkout develop
git merge main
git push origin develop

# 6. Borrar rama release
git branch -d release/vX.Y.Z
git push origin --delete release/vX.Y.Z
```

---

## Flujo 3 — Bugfix (corrección en desarrollo)

Igual que feature, pero el prefijo indica que es una corrección no urgente.

```bash
git checkout develop && git pull origin develop
git checkout -b bugfix/002-descripcion

git add src/archivo.py
git commit -m "fix(scope): descripción"

git push -u origin bugfix/002-descripcion
# PR hacia develop
```

---

## Flujo 4 — Hotfix (corrección urgente en producción)

El único flujo que sale de `main`.

```bash
git checkout main && git pull origin main
git checkout -b hotfix/003-descripcion

git add src/archivo.py
git commit -m "fix(scope): corrección urgente"

git push -u origin hotfix/003-descripcion

# PR hacia main Y hacia develop (los dos son obligatorios)

# Tras merge a main: tag de parche
git checkout main && git pull origin main
git tag -a vX.Y.Z -m "Hotfix vX.Y.Z"
git push origin main --tags

# Merge a develop
git checkout develop && git merge main && git push origin develop
```

---

## Convención de Commits

```
<tipo>[scope opcional]: <descripción>

[cuerpo opcional]

[footer opcional]
```

### Tipos

| Tipo | Uso | Versión |
|------|-----|---------|
| `feat` | Nueva funcionalidad | MINOR |
| `fix` | Corrección de bug | PATCH |
| `security` | Corrección de seguridad | PATCH |
| `perf` | Mejora de rendimiento | PATCH |
| `refactor` | Refactorización sin cambio funcional | — |
| `test` | Tests | — |
| `docs` | Documentación | — |
| `chore` | Mantenimiento, deps | — |
| `ci` | CI/CD | — |
| `build` | Build o dependencias | — |
| `revert` | Revertir commit | — |

### Breaking Change

```bash
# Con ! en el tipo
feat(api)!: cambiar formato de respuesta

# O con footer
feat(api): cambiar formato de respuesta

BREAKING CHANGE: el campo data ahora es array
```

### Scopes del proyecto

| Scope | Qué cubre |
|-------|-----------|
| `auth` | Autenticación, JWT, sesiones |
| `usuarios` | Entidad y lógica de usuarios |
| `roles` | Permisos y control de acceso |
| `auditoria` | Sistema de auditoría |
| `api` | Routers, schemas Pydantic |
| `dominio` | Entidades, puertos, excepciones |
| `infra` | Repositorios, ORM, servicios externos |
| `bd` | Migraciones Alembic |
| `config` | Settings, variables de entorno |
| `tests` | Suite de pruebas |
| `movilidad` | Módulo de movilidad vehicular |

---

## Versionamiento Semántico

| Incremento | Cuándo | Ejemplo |
|------------|--------|---------|
| PATCH x.y.**Z** | Solo `fix`, `security`, `perf`, `chore` | v0.1.0 → v0.1.1 |
| MINOR x.**Y**.0 | Al menos un `feat` sin breaking changes | v0.1.1 → v0.2.0 |
| MAJOR **X**.0.0 | Cualquier `BREAKING CHANGE` | v0.9.0 → v1.0.0 |

```bash
# Ver commits desde el último tag
git log $(git describe --tags --abbrev=0)..HEAD --oneline
```

---

## Checklist antes de PR

```
[ ] pytest --tb=short        → todos pasan
[ ] ruff check .             → sin errores
[ ] ruff format --check .    → código formateado
[ ] Squash de commits WIP    → historial limpio
[ ] Sin archivos sensibles   → no .env con secretos reales
```

---

## Comandos Útiles

```bash
git branch -a                          # todas las ramas
git log --oneline -10                  # historial reciente
git log origin/develop..HEAD --oneline # commits de la rama actual vs develop

# Squash antes del PR (N = número de commits a unir)
git rebase -i HEAD~N

# Rebase sobre develop actualizado
git fetch origin && git rebase origin/develop

# Borrar ramas tras merge
git branch -d nombre-rama
git push origin --delete nombre-rama
```
