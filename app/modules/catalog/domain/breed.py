from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Breed:
    id: str          # slug canónico, ej: "afghan_hound"
    name: str        # nombre de display, ej: "Afghan Hound"
    species: str     # "dog" | "cat"
    is_active: bool
