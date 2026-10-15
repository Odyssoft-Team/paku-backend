"""Requisitos de un servicio para la mascota (feature 0005): peso y edad máximos.

Ej.: Express sin agua solo para cachorros de hasta 4 meses y 10 kg de peso real (regla BR-006 del
documento de precios del cliente). Los límites son datos del producto (`max_weight_kg`,
`max_age_months`), editables desde el admin; `None` = sin límite.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional


def age_in_months(birth_date: Optional[date], today: Optional[date] = None) -> Optional[int]:
    """Meses cumplidos a `today` (hoy por defecto); None si no hay fecha de nacimiento."""
    if birth_date is None:
        return None
    if isinstance(birth_date, datetime):
        birth_date = birth_date.date()
    today = today or date.today()
    months = (today.year - birth_date.year) * 12 + (today.month - birth_date.month)
    if today.day < birth_date.day:
        months -= 1
    return max(months, 0)


def _fmt_kg(value: float) -> str:
    return f"{value:g}"


def ineligibility(
    product,
    *,
    weight: Optional[float],
    birth_date: Optional[date],
    today: Optional[date] = None,
) -> Optional[tuple[str, str]]:
    """None si la mascota cumple los requisitos del producto; si no, (código, mensaje al cliente).

    Sin peso no se evalúa el límite de peso (la cotización ya exige peso). Con límite de edad y sin
    fecha de nacimiento no se puede verificar: no es elegible y se pide la fecha.
    """
    max_weight = getattr(product, "max_weight_kg", None)
    if max_weight is not None and weight is not None and float(weight) > float(max_weight):
        return (
            "PET_TOO_HEAVY",
            f"{product.name} es solo para mascotas de hasta {_fmt_kg(float(max_weight))} kg.",
        )
    max_age = getattr(product, "max_age_months", None)
    if max_age is not None:
        months = age_in_months(birth_date, today)
        if months is None:
            return (
                "PET_AGE_UNKNOWN",
                f"{product.name} es solo para mascotas de hasta {max_age} meses. "
                "Agrega la fecha de nacimiento de tu mascota para poder reservarlo.",
            )
        if months > max_age:
            return "PET_TOO_OLD", f"{product.name} es solo para mascotas de hasta {max_age} meses."
    return None
