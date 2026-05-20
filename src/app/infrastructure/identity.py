from uuid6 import uuid7  # re-exportado — usado por modelos, middlewares y servicios
from ulid import ULID


def generar_public_id(prefijo: str) -> str:
    return f"{prefijo}_{ULID()}"
