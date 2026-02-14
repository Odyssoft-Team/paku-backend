"""Hardcoded breeds catalog for Paku.

Design goals:
- Keep it minimal and safe: no DB, no migrations.
- Stable keys: use `id` as the canonical identifier.
- Compatible with existing contracts: pets still store `breed` as a string.

NOTE: This is a starter list to unblock the frontend. It can be expanded and/or
moved to a DB-backed catalog later without breaking the endpoint contract.
"""

from __future__ import annotations

from typing import Final


# Canonical species identifiers used across the backend.
# Commerce already uses `Species` enum, but this catalog endpoint stays simple
# and uses plain strings to avoid coupling.
SPECIES_DOG: Final[str] = "dog"
SPECIES_CAT: Final[str] = "cat"


BREEDS_CATALOG: Final[list[dict]] = [
    {
        "species": SPECIES_DOG,
        "breeds": [
            {"id": "labrador", "name": "Labrador Retriever"},
            {"id": "husky", "name": "Husky Siberiano"},
            {"id": "poodle", "name": "Poodle"},
            {"id": "bulldog", "name": "Bulldog"},
            {"id": "golden_retriever", "name": "Golden Retriever"},
            {"id": "mixed", "name": "Mestizo"},
        ],
    },
    {
        "species": SPECIES_CAT,
        "breeds": [
            {"id": "siamese", "name": "Siamés"},
            {"id": "persian", "name": "Persa"},
            {"id": "maine_coon", "name": "Maine Coon"},
            {"id": "mixed", "name": "Mestizo"},
        ],
    },
]
