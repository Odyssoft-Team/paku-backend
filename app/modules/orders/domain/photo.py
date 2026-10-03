from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class OrderPhotoKind(str, Enum):
    initial = "initial"    # en recepción (obligatoria para avanzar desde "reception")
    final = "final"        # antes de devolver a la mascota
    incident = "incident"  # "Registrar incidencia/foto", en cualquier momento


@dataclass(frozen=True)
class OrderPhoto:
    id: UUID
    order_id: UUID
    kind: OrderPhotoKind
    object_name: str
    uploaded_by: UUID
    created_at: datetime
    note: Optional[str] = None

    @staticmethod
    def new(*, order_id: UUID, kind: OrderPhotoKind, object_name: str, uploaded_by: UUID,
            note: Optional[str] = None) -> "OrderPhoto":
        return OrderPhoto(
            id=uuid4(), order_id=order_id, kind=kind, object_name=object_name, uploaded_by=uploaded_by,
            created_at=datetime.now(timezone.utc), note=note,
        )
