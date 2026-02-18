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
            {"id": "afghan_hound", "name": "Afghan Hound"},
            {"id": "akita", "name": "Akita"},
            {"id": "alaskan_malamute", "name": "Alaskan Malamute"},
            {"id": "basset_hound", "name": "Basset Hound"},
            {"id": "beagle", "name": "Beagle"},
            {"id": "bichon_frise", "name": "Bichón Frisé"},
            {"id": "border_collie", "name": "Border Collie"},
            {"id": "boxer", "name": "Boxer"},
            {"id": "bulldog", "name": "Bulldog"},
            {"id": "french_bulldog", "name": "Bulldog Francés"},
            {"id": "bull_terrier", "name": "Bull Terrier"},
            {"id": "chihuahua", "name": "Chihuahua"},
            {"id": "chow_chow", "name": "Chow Chow"},
            {"id": "cocker_americano", "name": "Cocker Americano"},
            {"id": "cocker_spaniel", "name": "Cocker Spaniel"},
            {"id": "collie", "name": "Collie"},
            {"id": "corgi", "name": "Corgi"},
            {"id": "dachshund", "name": "Dachshund (Salchicha)"},
            {"id": "dalmata", "name": "Dálmata"},
            {"id": "doberman", "name": "Doberman"},
            {"id": "galgo", "name": "Galgo"},
            {"id": "golden_retriever", "name": "Golden Retriever"},
            {"id": "husky", "name": "Husky Siberiano"},
            {"id": "labrador", "name": "Labrador Retriever"},
            {"id": "maltese", "name": "Maltés"},
            {"id": "mixed", "name": "Mestizo"},
            {"id": "pastor_aleman", "name": "Pastor Alemán"},
            {"id": "pitbull", "name": "Pitbull"},
            {"id": "pomeranian", "name": "Pomerania"},
            {"id": "poodle", "name": "Poodle"},
            {"id": "pug", "name": "Pug"},
            {"id": "rottweiler", "name": "Rottweiler"},
            {"id": "samoyedo", "name": "Samoyedo"},
            {"id": "san_bernardo", "name": "San Bernardo"},
            {"id": "schnauzer", "name": "Schnauzer"},
            {"id": "shar_pei", "name": "Shar Pei"},
            {"id": "shih_tzu", "name": "Shih Tzu"},
            {"id": "terranova", "name": "Terranova"},
            {"id": "west_highland", "name": "West Highland White Terrier"},
            {"id": "yorkshire", "name": "Yorkshire Terrier"},
        ],
    },
    {
        "species": SPECIES_CAT,
        "breeds": [
            {"id": "abyssinian", "name": "Abisinio"},
            {"id": "bengal", "name": "Bengalí"},
            {"id": "birman", "name": "Birmano"},
            {"id": "british_shorthair", "name": "British Shorthair"},
            {"id": "burmese", "name": "Burmés"},
            {"id": "exotic_shorthair", "name": "Exotic Shorthair"},
            {"id": "maine_coon", "name": "Maine Coon"},
            {"id": "mixed", "name": "Mestizo"},
            {"id": "norwegian_forest", "name": "Noruego de Bosque"},
            {"id": "persian", "name": "Persa"},
            {"id": "ragdoll", "name": "Ragdoll"},
            {"id": "russian_blue", "name": "Azul Ruso"},
            {"id": "scottish_fold", "name": "Scottish Fold"},
            {"id": "siamese", "name": "Siamés"},
            {"id": "sphynx", "name": "Sphynx (Sin Pelo)"},
            {"id": "american_shorthair", "name": "American Shorthair"},
            {"id": "munchkin", "name": "Munchkin"},
            {"id": "oriental", "name": "Oriental"},
        ],
    },
]
