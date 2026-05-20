import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape as _esc

import aiosmtplib

from app.config import config
from app.domain.ports.outbound.auth.servicio_email import ServicioEmail

logger = logging.getLogger(__name__)


class SmtpEmailService(ServicioEmail):

    async def _enviar(self, destinatario: str, asunto: str, html: str) -> None:
        mensaje = MIMEMultipart("alternative")
        mensaje["Subject"] = asunto
        mensaje["From"] = config.SMTP_FROM
        mensaje["To"] = destinatario
        mensaje.attach(MIMEText(html, "html", "utf-8"))

        await aiosmtplib.send(
            mensaje,
            hostname=config.SMTP_HOST,
            port=config.SMTP_PORT,
            username=config.SMTP_USER,
            password=config.SMTP_PASS.get_secret_value(),
            start_tls=config.SMTP_TLS,
            timeout=10,
        )
        logger.info("Email enviado", extra={"destinatario": destinatario, "asunto": asunto})

    async def enviar_verificacion(self, destinatario: str, nombre: str, token: str) -> None:
        enlace = f"{config.FRONTEND_URL}/verificar-email?token={token}"
        html = _template_verificacion(nombre, enlace)
        await self._enviar(destinatario, "Verifica tu correo electrónico", html)

    async def enviar_reset_password(self, destinatario: str, nombre: str, token: str) -> None:
        enlace = f"{config.FRONTEND_URL}/reset-password?token={token}"
        html = _template_reset_password(nombre, enlace)
        await self._enviar(destinatario, "Restablece tu contraseña", html)


def _template_verificacion(nombre: str, enlace: str) -> str:
    return f"""
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 0;">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08);">
        <tr><td style="background:#1d4ed8;padding:32px 40px;">
          <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:700;">Users API</h1>
        </td></tr>
        <tr><td style="padding:40px;">
          <p style="margin:0 0 16px;font-size:16px;color:#374151;">Hola, <strong>{_esc(nombre)}</strong></p>
          <p style="margin:0 0 24px;font-size:15px;color:#6b7280;line-height:1.6;">
            Gracias por registrarte. Para activar tu cuenta y comenzar a usar la plataforma, necesitas verificar tu correo electrónico.
          </p>
          <div style="text-align:center;margin:32px 0;">
            <a href="{enlace}"
               style="background:#1d4ed8;color:#ffffff;padding:14px 32px;border-radius:6px;font-size:15px;font-weight:600;text-decoration:none;display:inline-block;">
              Verificar mi correo
            </a>
          </div>
          <p style="margin:24px 0 0;font-size:13px;color:#9ca3af;line-height:1.6;">
            Este enlace expira en 24 horas. Si no creaste una cuenta, puedes ignorar este mensaje.
          </p>
          <p style="margin:8px 0 0;font-size:12px;color:#d1d5db;">
            Si el botón no funciona, copia y pega este enlace en tu navegador:<br>
            <span style="color:#6b7280;word-break:break-all;">{enlace}</span>
          </p>
        </td></tr>
        <tr><td style="padding:20px 40px;background:#f9fafb;border-top:1px solid #e5e7eb;">
          <p style="margin:0;font-size:12px;color:#9ca3af;text-align:center;">
            Este es un mensaje automático, por favor no respondas a este correo.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""


def _template_reset_password(nombre: str, enlace: str) -> str:
    return f"""
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 0;">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08);">
        <tr><td style="background:#dc2626;padding:32px 40px;">
          <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:700;">Users API</h1>
        </td></tr>
        <tr><td style="padding:40px;">
          <p style="margin:0 0 16px;font-size:16px;color:#374151;">Hola, <strong>{_esc(nombre)}</strong></p>
          <p style="margin:0 0 24px;font-size:15px;color:#6b7280;line-height:1.6;">
            Recibimos una solicitud para restablecer la contraseña de tu cuenta. Haz clic en el botón para crear una nueva contraseña.
          </p>
          <div style="text-align:center;margin:32px 0;">
            <a href="{enlace}"
               style="background:#dc2626;color:#ffffff;padding:14px 32px;border-radius:6px;font-size:15px;font-weight:600;text-decoration:none;display:inline-block;">
              Restablecer contraseña
            </a>
          </div>
          <p style="margin:24px 0 0;font-size:13px;color:#9ca3af;line-height:1.6;">
            Este enlace expira en 1 hora. Si no solicitaste esto, ignora este mensaje — tu contraseña no cambiará.
          </p>
          <p style="margin:8px 0 0;font-size:12px;color:#d1d5db;">
            Si el botón no funciona, copia y pega este enlace en tu navegador:<br>
            <span style="color:#6b7280;word-break:break-all;">{enlace}</span>
          </p>
        </td></tr>
        <tr><td style="padding:20px 40px;background:#f9fafb;border-top:1px solid #e5e7eb;">
          <p style="margin:0;font-size:12px;color:#9ca3af;text-align:center;">
            Este es un mensaje automático, por favor no respondas a este correo.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""
