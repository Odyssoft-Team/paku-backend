from dataclasses import dataclass
from typing import List, Optional

from app.modules.commerce.domain.service import Service, Species
from app.modules.commerce.infra.service_repository import list_services


@dataclass
class ListServices:
    def execute(self, *, species: Species, breed: Optional[str] = None) -> List[Service]:
        items = list_services()
        out: List[Service] = []

        for s in items:
            if not s.is_active:
                continue
            if s.species != species:
                continue

            if s.allowed_breeds:
                if breed is None:
                    continue
                if breed not in s.allowed_breeds:
                    continue

            out.append(s)

        return out
