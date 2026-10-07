"""Búsqueda de direcciones (feature 0002): contrato del proveedor y reglas puras.

El proveedor (hoy Google) queda detrás de `AddressProvider` para poder cambiarlo
(LocationIQ, Geoapify…) sin tocar los endpoints ni la app.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Optional, Protocol


# Largo mínimo del texto para buscar sugerencias: con menos, los resultados no
# sirven y solo suman costo.
MIN_QUERY_LENGTH = 3
MAX_SUGGESTIONS = 5
# Radio del sesgo de búsqueda alrededor del centro del distrito elegido.
DISTRICT_BIAS_RADIUS_M = 3000.0


class AddressProviderUnavailable(Exception):
    """El proveedor no respondió, rechazó la clave o se quedó sin cuota."""


@dataclass(frozen=True)
class PlaceSuggestion:
    place_id: str
    main_text: str
    secondary_text: Optional[str] = None


@dataclass(frozen=True)
class PlaceDetails:
    lat: float
    lng: float
    formatted_address: Optional[str] = None
    address_line: Optional[str] = None
    building_number: Optional[str] = None
    # Nombres de zona que devolvió el proveedor (distrito, localidad…), del más
    # específico al más general. Se cruzan contra nuestro catálogo de distritos.
    area_names: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BiasCircle:
    lat: float
    lng: float
    radius_m: float = DISTRICT_BIAS_RADIUS_M


class AddressProvider(Protocol):
    async def autocomplete(
        self, query: str, *, bias: Optional[BiasCircle], session_token: Optional[str]
    ) -> list[PlaceSuggestion]: ...

    async def place_details(self, place_id: str, *, session_token: Optional[str]) -> Optional[PlaceDetails]: ...

    async def geocode(self, address: str) -> Optional[tuple[float, float]]: ...


def normalize_text(value: str) -> str:
    """Minúsculas, sin tildes ni espacios repetidos (para comparar y cachear)."""
    decomposed = unicodedata.normalize("NFD", value)
    without_marks = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return " ".join(without_marks.lower().split())


def match_district(area_names: list[str], districts: list[dict]) -> Optional[dict]:
    """Primer distrito del catálogo cuyo nombre coincide con alguna zona del proveedor.

    Acepta prefijos comunes de Google ("Distrito de Miraflores") y el alias
    "Cercado de Lima" para el distrito Lima.
    """
    by_name = {normalize_text(d["name"]): d for d in districts}
    by_name.setdefault("cercado de lima", by_name.get("lima"))
    for raw in area_names:
        name = normalize_text(raw)
        for prefix in ("distrito de ", "provincia de "):
            if name.startswith(prefix):
                name = name[len(prefix):]
        district = by_name.get(name)
        if district is not None:
            return district
    return None
