"""Disponibilidad de insumos para vender un servicio (feature 0025). Reglas puras, sin base de datos.

- Disponible = stock − consumo comprometido (el de las recetas de los servicios vendidos que aún no se realizan).
- Un servicio o adicional no se vende si algún insumo de su receta (celda del pelaje y peso de la mascota) no alcanza.
  Un adicional se evalúa junto con su servicio base. Sin receta o sin celda que aplique, se vende.
- Al realizarse un servicio el consumo se registra igual, aunque el stock quede negativo (el servicio ya se hizo).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from uuid import UUID

# Tolerancia para comparar cantidades decimales (ml, g)
EPS = 1e-6


@dataclass(frozen=True)
class Shortage:
    supply_id: UUID
    name: str
    unit: str
    needed: float
    available: float


def needs_of(lines: Iterable) -> dict[UUID, float]:
    """Cantidad por insumo de unas líneas de receta (`RecipeLine`)."""
    out: dict[UUID, float] = {}
    for line in lines:
        out[line.supply_id] = out.get(line.supply_id, 0.0) + float(line.quantity)
    return out


def merge(*needs: dict[UUID, float]) -> dict[UUID, float]:
    out: dict[UUID, float] = {}
    for n in needs:
        for k, v in n.items():
            out[k] = out.get(k, 0.0) + v
    return out


def shortages(needs: dict[UUID, float], available: dict[UUID, float], supplies: dict) -> list[Shortage]:
    """Insumos que no alcanzan. `supplies`: id → Supply (nombre y unidad)."""
    out = []
    for sid, qty in needs.items():
        have = available.get(sid, 0.0)
        if qty > have + EPS:
            s = supplies.get(sid)
            out.append(Shortage(sid, s.name if s else "insumo", s.consumption_unit if s else "", qty, have))
    return sorted(out, key=lambda s: s.name)


def shortage_message(items: list[Shortage]) -> str:
    return "Falta " + ", ".join(s.name for s in items) if items else ""
