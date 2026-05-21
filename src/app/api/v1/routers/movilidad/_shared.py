from datetime import date
from typing import Optional


def dias_restantes(vencimiento: Optional[date], esta_activo: bool) -> Optional[int]:
    if not esta_activo or vencimiento is None:
        return None
    return max((vencimiento - date.today()).days, 0)
