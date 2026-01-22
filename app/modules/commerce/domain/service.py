from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
from uuid import UUID


class ServiceType(str, Enum):
    base = "base"
    addon = "addon"


class Species(str, Enum):
    dog = "dog"
    cat = "cat"


@dataclass(frozen=True)
class Service:
    id: UUID
    name: str
    type: ServiceType
    species: Species
    allowed_breeds: Optional[List[str]]
    requires: Optional[List[UUID]]
    is_active: bool
