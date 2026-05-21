from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "templates" / "movilidad"


def _build_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )

    def formato_fecha(valor) -> str:
        if valor is None:
            return "—"
        if isinstance(valor, datetime):
            return valor.astimezone(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
        if isinstance(valor, date):
            return valor.strftime("%d/%m/%Y")
        return str(valor)

    def formato_fecha_corta(valor) -> str:
        if valor is None:
            return "—"
        d = valor.date() if isinstance(valor, datetime) else valor
        return d.strftime("%d/%m/%Y") if isinstance(d, date) else str(valor)

    env.filters["formato_fecha"] = formato_fecha
    env.filters["formato_fecha_corta"] = formato_fecha_corta
    return env


_ENV: Environment = _build_env()


def generar_pdf_remision(
    traslado,
    cuenta,
    organismo_destino: Optional[str],
    empresa_transportadora: Optional[str],
) -> bytes:
    dias: Optional[int] = None
    if traslado.vencimiento and traslado.esta_activo:
        dias = max((traslado.vencimiento - date.today()).days, 0)

    contexto = {
        "traslado": traslado,
        "cuenta": cuenta,
        "organismo_destino": organismo_destino,
        "empresa_transportadora": empresa_transportadora,
        "dias_restantes": dias,
        "generado_en": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
    }

    html_str = _ENV.get_template("remision_traslado.html").render(**contexto)
    pdf_bytes = HTML(string=html_str, base_url=str(_TEMPLATES_DIR)).write_pdf()
    logger.info("PDF generado", extra={"traslado_id": traslado.public_id, "bytes": len(pdf_bytes)})
    return pdf_bytes
