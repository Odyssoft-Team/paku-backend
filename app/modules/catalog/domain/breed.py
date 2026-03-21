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
