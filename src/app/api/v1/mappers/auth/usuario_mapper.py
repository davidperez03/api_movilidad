from app.domain.entities.auth.usuario import Usuario
from app.domain.entities.auth.rol import Rol
from app.api.v1.schemas.auth.usuario import UsuarioResponse, UsuarioDetalleResponse, RolResumen


def map_usuario(u: Usuario) -> UsuarioResponse:
    return UsuarioResponse(
        id=u.public_id,
        email=u.email,
        nombre=u.nombre,
        apellido=u.apellido,
        nombre_completo=u.nombre_completo,
        estado=u.estado,
        email_verificado=u.email_verificado,
        ultimo_login=u.ultimo_login,
        creado_en=u.creado_en,
    )


def map_usuario_detalle(u: Usuario, roles: list[Rol]) -> UsuarioDetalleResponse:
    return UsuarioDetalleResponse(
        id=u.public_id,
        email=u.email,
        nombre=u.nombre,
        apellido=u.apellido,
        nombre_completo=u.nombre_completo,
        estado=u.estado,
        email_verificado=u.email_verificado,
        ultimo_login=u.ultimo_login,
        creado_en=u.creado_en,
        roles=[RolResumen(id=r.public_id, nombre=r.nombre, descripcion=r.descripcion) for r in roles],
    )
