from __future__ import annotations

from typing import Final
from uuid import UUID


# Stable service UUIDs for grooming add-ons (used as cart ref_id and for quote validation).
ADDON_CEPILLADO_ID: Final[UUID] = UUID("66666666-6666-6666-6666-666666666666")
ADDON_DESLANADO_ID: Final[UUID] = UUID("77777777-7777-7777-7777-777777777777")
ADDON_DESMOTADO_ID: Final[UUID] = UUID("88888888-8888-8888-8888-888888888888")


# Breed IDs come from `app/modules/catalog/domain/breeds_data.py`.
# We intentionally keep these as plain strings to avoid coupling modules.

# Cepillado: universal (no breed filter).

# Deslanado rules
DESLANADO_REQUIRED_BREEDS: Final[set[str]] = {
    "akita",
    "alaskan_malamute",
    "chow_chow",
    "golden_retriever",
    "husky",
    "labrador",
    "pastor_aleman",
    "samoyedo",
    "san_bernardo",
    "terranova",
    "border_collie",
    "collie",
    "corgi",
    "pomeranian",
}

DESLANADO_OPTIONAL_BREEDS: Final[set[str]] = {
    "mixed",
    "beagle",
}

# Desmotado (de-matting) rules
# NOTE: “Sí o sí si no se cepillan” is operationally hard to infer from the API.
# We treat these as *applicable* breeds; enforcement can be tightened later if desired.
DESMOTADO_HIGH_RISK_BREEDS: Final[set[str]] = {
    "afghan_hound",
    "bichon_frise",
    "poodle",
    "shih_tzu",
    "yorkshire",
    "maltese",
    "collie",
    "cocker_spaniel",
    "cocker_americano",
    "schnauzer",
}

DESMOTADO_MEDIUM_RISK_BREEDS: Final[set[str]] = {
    "golden_retriever",
    "samoyedo",
    "terranova",
    "san_bernardo",
}


def deslanado_applicable_breeds() -> set[str]:
    return set(DESLANADO_REQUIRED_BREEDS) | set(DESLANADO_OPTIONAL_BREEDS)


def desmotado_applicable_breeds() -> set[str]:
    return set(DESMOTADO_HIGH_RISK_BREEDS) | set(DESMOTADO_MEDIUM_RISK_BREEDS)
