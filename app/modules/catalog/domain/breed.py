from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Breed:
    id: str                       # slug canónico, ej: "afghan_hound"
    name: str                     # nombre de display, ej: "Afghan Hound"
    species: str                  # "dog" | "cat"
    is_active: bool
    coat_group: Optional[str]     # "single" | "double"
    coat_type: Optional[str]      # "simple_short" | "simple_medium_long" | "curly_no_undercoat"
                                  # "double_short" | "double_long" | "mixed_curly_undercoat"
    # Feature 0006: el admin asigna el pelaje (define el precio). Los mestizos son 6 razas, una por
    # pelaje, con foto para que el cliente elija la que más se parece a su mascota.
    is_mixed: bool = False
    photo_url: Optional[str] = None
    description: Optional[str] = None


COAT_TYPES: tuple[str, ...] = (
    "simple_short", "simple_medium_long", "curly_no_undercoat",
    "double_short", "double_long", "mixed_curly_undercoat",
)


def coat_group_for(coat_type: Optional[str]) -> Optional[str]:
    """Grupo (single/double) derivado del pelaje."""
    if coat_type is None:
        return None
    return "single" if coat_type in ("simple_short", "simple_medium_long", "curly_no_undercoat") else "double"
