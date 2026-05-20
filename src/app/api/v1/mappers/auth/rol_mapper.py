from app.domain.entities.auth.rol import Rol, Permiso
from app.api.v1.schemas.auth.rol import RolResponse, PermisoResponse


def map_permiso(p: Permiso) -> PermisoResponse:
    return PermisoResponse(
        clave=p.clave,
        recurso=p.recurso,
        accion=p.accion,
        descripcion=p.descripcion,
    )


def map_rol(r: Rol) -> RolResponse:
    return RolResponse(
        id=r.public_id,
        nombre=r.nombre,
        descripcion=r.descripcion,
        es_sistema=r.es_sistema,
        permisos=[map_permiso(p) for p in r.permisos],
        creado_en=r.creado_en,
    )
