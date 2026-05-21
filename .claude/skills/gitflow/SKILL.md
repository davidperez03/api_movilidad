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
main
  └── develop
        └── feature/XXX-descripcion   ← aquí se trabaja
              │
              └──→ develop             ← merge cuando el feature está listo
                    └── release/vX.Y.Z ← cuando develop está listo para salir
                          │  chore(release) commit va AQUÍ, en esta rama
                          ├──→ main + tag vX.Y.Z   ← merge --no-ff
                          └──→ develop              ← merge --no-ff desde release (NO desde main)
```

**REGLA CRÍTICA — orden del release:**
```
release/vX.Y.Z
  → chore(release): prepare vX.Y.Z   ← el commit vive en release, no en main
  → merge --no-ff → main + tag
  → merge --no-ff → develop          ← desde release, nunca "git merge main"
```

**Hotfix** es el único caso que no pasa por feature ni release:
```
main
  └── hotfix/XXX-descripcion
        ├──→ main + tag de parche
        └──→ develop
```

---

## Ramas

### Permanentes (nunca se borran, nunca se commitea directo)

| Rama | Propósito |
|------|-----------|
| `main` | Producción estable — solo recibe merges de `release/` y `hotfix/` |
| `develop` | Integración — solo recibe merges de `feature/`, `bugfix/` y `release/` |

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

# 3. Merge a develop (--no-ff conserva el contexto de la rama)
git checkout develop
git merge --no-ff feature/001-descripcion -m "merge(develop): feature/001-descripcion"
git push origin develop

# 4. Borrar rama
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

# 2. El chore(release) va AQUÍ, en la rama release — nunca en main
git commit --allow-empty -m "chore(release): prepare vX.Y.Z"
# (si hay cambios reales: bump version en pyproject.toml, actualizar CHANGELOG)

# 3. Merge a main + tag
git checkout main && git pull origin main
git merge --no-ff release/vX.Y.Z -m "merge(main): release/vX.Y.Z"
git tag vX.Y.Z
git push origin main --tags

# 4. Merge de vuelta a develop — DESDE RELEASE, no desde main
git checkout develop
git merge --no-ff release/vX.Y.Z -m "merge(develop): release/vX.Y.Z"
git push origin develop

# 5. Borrar rama release
git branch -d release/vX.Y.Z
git push origin --delete release/vX.Y.Z
```

**Por qué merge desde release y no desde main:**
Si haces `git merge main` en develop obtienes todos los merges históricos de main en el grafo de develop, contaminando el historial. El merge desde la rama release lleva solo los commits de esa release.

---

## Flujo 3 — Bugfix (corrección en desarrollo)

Igual que feature, pero el prefijo indica que es una corrección no urgente.

```bash
git checkout develop && git pull origin develop
git checkout -b bugfix/002-descripcion

git add src/archivo.py
git commit -m "fix(scope): descripción"

git checkout develop
git merge --no-ff bugfix/002-descripcion -m "merge(develop): bugfix/002-descripcion"
git push origin develop

git branch -d bugfix/002-descripcion
git push origin --delete bugfix/002-descripcion
```

---

## Flujo 4 — Hotfix (corrección urgente en producción)

El único flujo que sale de `main`.

```bash
git checkout main && git pull origin main
git checkout -b hotfix/003-descripcion

git add src/archivo.py
git commit -m "fix(scope): corrección urgente"

# Merge a main + tag
git checkout main
git merge --no-ff hotfix/003-descripcion -m "merge(main): hotfix/003-descripcion"
git tag vX.Y.Z
git push origin main --tags

# Merge a develop — desde hotfix, no desde main
git checkout develop
git merge --no-ff hotfix/003-descripcion -m "merge(develop): hotfix/003-descripcion"
git push origin develop

git branch -d hotfix/003-descripcion
git push origin --delete hotfix/003-descripcion
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
feat(api)!: cambiar formato de respuesta

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
| `parqueadero` | Módulo de parqueadero |
| `nunc` | Módulo NUNC |

---

## Versionamiento Semántico

| Incremento | Cuándo | Ejemplo |
|------------|--------|---------|
| PATCH x.y.**Z** | Solo `fix`, `security`, `perf`, `chore` | v0.2.0 → v0.2.1 |
| MINOR x.**Y**.0 | Al menos un `feat` sin breaking changes | v0.1.1 → v0.2.0 |
| MAJOR **X**.0.0 | Cualquier `BREAKING CHANGE` | v0.9.0 → v1.0.0 |

```bash
# Ver commits desde el último tag
git log $(git describe --tags --abbrev=0)..HEAD --oneline
```

---

## Checklist antes de hacer release

```
[ ] PYTHONPATH=src venv/Scripts/python.exe -m pytest tests/unit/ -q  → 0 fallos
[ ] PYTHONPATH=src venv/Scripts/python.exe -c "from app.main import app; print('OK')"
[ ] Sin archivos sensibles (.env con secretos reales)
[ ] Historial de commits limpio (sin WIP)
```

---

## Comandos Útiles

```bash
git branch -a                          # todas las ramas
git log --oneline --all                # historial completo con ramas
git log --oneline -10                  # historial reciente

# Borrar ramas tras merge
git branch -d nombre-rama
git push origin --delete nombre-rama
```
