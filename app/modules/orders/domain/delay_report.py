from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

MIN_DELAY_MINUTES = 1
MAX_DELAY_MINUTES = 180


@dataclass(frozen=True)
class DelayReport:
    """Aviso de demora (tráfico) del groomer para una orden (pedido 5)."""
    id: UUID
    order_id: UUID
    groomer_id: UUID
    delay_minutes: int
    created_at: datetime
    note: Optional[str] = None

    @staticmethod
    def new(*, order_id: UUID, groomer_id: UUID, delay_minutes: int, note: Optional[str] = None) -> "DelayReport":
        if not MIN_DELAY_MINUTES <= delay_minutes <= MAX_DELAY_MINUTES:
            raise ValueError("delay_minutes_out_of_range")
        return DelayReport(
            id=uuid4(), order_id=order_id, groomer_id=groomer_id, delay_minutes=delay_minutes,
            created_at=datetime.now(timezone.utc), note=note,
        )
