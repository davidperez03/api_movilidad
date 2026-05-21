import base64
import json
from datetime import datetime, timezone
from uuid import UUID


def encode_cursor(creado_en: datetime, id: UUID) -> str:
    return base64.urlsafe_b64encode(
        json.dumps([creado_en.isoformat(), str(id)]).encode()
    ).decode()


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    data = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    dt = datetime.fromisoformat(data[0])
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt, UUID(data[1])
