"""Adicionales que no se pueden combinar en una misma reserva (pedido del cliente, 2026-11-13).

Son alternativas o cubren el mismo trabajo; sumarlos cobraría dos veces lo mismo:
- Corte estético y Rapado corporal con máquina son alternativas.
- Desmotado localizado y extendido no se suman por el mismo desmotado.
- Retoque de carita no se suma a Retoque Paku (Retoque Paku ya incluye carita, patas y cola).
- Los retoques no se suman a un Corte estético ni a un Rapado corporal: ambos ya incluyen el acabado de carita,
  patas y cola (confirmado por el cliente el 2026-11-13).

Se identifican por código (`store_addons.code`): un adicional sin código no participa.
"""
from __future__ import annotations

from typing import Iterable, Optional

CONFLICTS: tuple[frozenset[str], ...] = (
    frozenset({"ADD_CORTE_EST", "ADD_CORTE_CORTO"}),
    frozenset({"ADD_DESMOTADO_LOC", "ADD_DESMOTADO_EXT"}),
    frozenset({"ADD_RETOQUE_CARITA", "ADD_RETOQUE"}),
    frozenset({"ADD_CORTE_EST", "ADD_RETOQUE"}),
    frozenset({"ADD_CORTE_EST", "ADD_RETOQUE_CARITA"}),
    frozenset({"ADD_CORTE_CORTO", "ADD_RETOQUE"}),
    frozenset({"ADD_CORTE_CORTO", "ADD_RETOQUE_CARITA"}),
)


def first_conflict(codes: Iterable[Optional[str]]) -> Optional[tuple[str, str]]:
    """El primer par de códigos elegidos que no se pueden combinar (en el orden de CONFLICTS), o None."""
    chosen = {c for c in codes if c}
    for pair in CONFLICTS:
        if pair <= chosen:
            a, b = sorted(pair)
            return a, b
    return None


def conflicts_of(code: Optional[str]) -> list[str]:
    """Códigos que no se pueden combinar con `code` (para que la app y la web los deshabiliten)."""
    if not code:
        return []
    return sorted({other for pair in CONFLICTS if code in pair for other in pair if other != code})
