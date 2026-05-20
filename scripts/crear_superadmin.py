"""
Script de bootstrap: crea el primer usuario superadmin.

Uso:
    python scripts/crear_superadmin.py

    # O con variables de entorno:
    SUPERADMIN_EMAIL=admin@miempresa.com python scripts/crear_superadmin.py

Requisitos previos:
    1. alembic upgrade head (migraciones 001, 002, 003 aplicadas)
    2. DATABASE_URL configurada en .env

Seguridad:
    - La contraseña se pide interactivamente (no queda en bash history)
    - El hash se calcula con bcrypt igual que el sistema
    - El usuario nace como ACTIVO (email ya verificado por ser bootstrap)
"""
import asyncio
import getpass
import os
import sys

# Agregar src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


async def main() -> None:
    from sqlalchemy import text
    from app.infrastructure.persistence.database import engine, AsyncSessionFactory
    from app.infrastructure.security.auth.hash_service import BcryptHashService

    print("\n=== Crear primer Superadmin ===\n")

    # ─── Recolectar datos ─────────────────────────────────────────────────────
    email = os.getenv("SUPERADMIN_EMAIL") or input("Email: ").strip().lower()
    nombre = os.getenv("SUPERADMIN_NOMBRE") or input("Nombre: ").strip()
    apellido = os.getenv("SUPERADMIN_APELLIDO") or input("Apellido: ").strip()

    if os.getenv("SUPERADMIN_PASSWORD"):
        password = os.getenv("SUPERADMIN_PASSWORD")
    else:
        password = getpass.getpass("Contraseña (oculta): ")
        confirmar = getpass.getpass("Confirmar contraseña: ")
        if password != confirmar:
            print("ERROR: Las contraseñas no coinciden.")
            sys.exit(1)

    if len(password) < 8:
        print("ERROR: La contraseña debe tener al menos 8 caracteres.")
        sys.exit(1)

    # ─── Validar que el email no existe ──────────────────────────────────────
    async with engine.connect() as conn:
        existe = await conn.execute(
            text("SELECT COUNT(*) FROM usuarios WHERE email = :email"),
            {"email": email},
        )
        if existe.scalar() > 0:
            print(f"ERROR: Ya existe un usuario con el email '{email}'.")
            sys.exit(1)

        rol = await conn.execute(
            text("SELECT id FROM roles WHERE nombre = 'superadmin'")
        )
        rol_id = rol.scalar()
        if not rol_id:
            print("ERROR: El rol 'superadmin' no existe. Ejecuta: alembic upgrade head")
            sys.exit(1)

    # ─── Crear usuario ────────────────────────────────────────────────────────
    from app.infrastructure.identity import uuid7
    hash_svc = BcryptHashService()
    hash_password = hash_svc.hashear(password)

    user_id = uuid7()
    public_id = f"usr_{uuid7().hex[:27]}"

    async with AsyncSessionFactory() as session:
        async with session.begin():
            # Insertar usuario directamente (estado ACTIVO, email verificado)
            await session.execute(text("""
                INSERT INTO usuarios
                    (id, public_id, email, nombre, apellido, hash_password,
                     estado, email_verificado)
                VALUES
                    (:id, :public_id, :email, :nombre, :apellido, :hash_password,
                     'activo', true)
            """), {
                "id": user_id,
                "public_id": public_id,
                "email": email,
                "nombre": nombre,
                "apellido": apellido,
                "hash_password": hash_password,
            })

            # Asignar rol superadmin
            await session.execute(text("""
                INSERT INTO usuario_roles (id, usuario_id, rol_id)
                VALUES (gen_random_uuid(), :usuario_id, :rol_id)
            """), {"usuario_id": user_id, "rol_id": rol_id})

    print(f"""
[OK] Superadmin creado exitosamente
  ID        : {user_id}
  Public ID : {public_id}
  Email     : {email}
  Nombre    : {nombre} {apellido}
  Rol       : superadmin (17 permisos + comodin *:*)
  Estado    : activo

Ahora puedes iniciar sesion en:
  POST /api/v1/auth/login
  {{ "email": "{email}", "password": "..." }}
""")


if __name__ == "__main__":
    asyncio.run(main())
