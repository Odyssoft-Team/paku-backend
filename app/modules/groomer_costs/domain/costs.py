"""Costo del groomer (feature 0012): cuánto cuesta una hora de servicio, para costear la mano de obra.

Cada groomer tiene un historial de registros de costo; cada registro rige desde una fecha (el sueldo cambia
y los servicios anteriores se siguen costeando con el registro de su fecha).

- Costo mensual = sueldo + cargos de la empresa (EsSalud, vacaciones, gratificaciones…, cada uno en % del
  sueldo o monto fijo). El costo por hora usa lo que la empresa paga en total, no solo el sueldo.
- Horas de servicio = horas al mes − bolsón de manejo y reposo. El traslado y el descanso no se costean por
  servicio: se reparten en el costo de la hora de servicio.
- Costo por hora de servicio = costo mensual ÷ horas de servicio. Es la tarifa con que se costean los
  minutos de las recetas.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
from uuid import UUID

ITEM_KINDS = ("percent", "amount")

# Cargos sugeridos al crear el primer registro (el admin los ajusta). Dependen del régimen laboral de la
# empresa: confirmarlos con el contador.
SUGGESTED_ITEMS: tuple[tuple[str, str, float], ...] = (
    ("EsSalud", "percent", 9.0),
    ("Vacaciones (15 días al año)", "percent", 4.17),
)


class CostProfileInvalid(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class CostItem:
    label: str
    kind: str        # percent (del sueldo) | amount (S/ al mes)
    value: float

    def monthly_amount(self, base_salary: float) -> float:
        return base_salary * self.value / 100 if self.kind == "percent" else self.value


@dataclass(frozen=True)
class CostProfile:
    id: UUID
    groomer_id: UUID
    effective_from: date
    base_salary: float            # S/ al mes
    items: list[CostItem]
    monthly_hours: float          # horas de trabajo al mes
    driving_rest_hours: float     # bolsón de manejo y reposo dentro de esas horas
    created_at: datetime
    notes: Optional[str] = None
    created_by: Optional[UUID] = None

    @property
    def monthly_cost(self) -> float:
        return self.base_salary + sum(i.monthly_amount(self.base_salary) for i in self.items)

    @property
    def service_hours(self) -> float:
        return self.monthly_hours - self.driving_rest_hours

    @property
    def cost_per_hour(self) -> float:
        """Costo de cualquier hora contratada (referencial)."""
        return self.monthly_cost / self.monthly_hours

    @property
    def cost_per_service_hour(self) -> float:
        """Costo de una hora de servicio: incluye el bolsón de manejo y reposo. Costea las recetas."""
        return self.monthly_cost / self.service_hours


def validate_profile(*, base_salary: float, items: list[CostItem], monthly_hours: float,
                     driving_rest_hours: float) -> None:
    if base_salary is None or base_salary <= 0:
        raise CostProfileInvalid("SALARY_INVALID", "El sueldo debe ser mayor que 0.")
    if monthly_hours is None or not 0 < monthly_hours <= 744:
        raise CostProfileInvalid("HOURS_INVALID", "Las horas al mes van de 1 a 744.")
    if driving_rest_hours is None or driving_rest_hours < 0 or driving_rest_hours >= monthly_hours:
        raise CostProfileInvalid(
            "DRIVING_HOURS_INVALID", "El bolsón de manejo y reposo debe ser menor que las horas al mes.",
        )
    for item in items:
        if not item.label.strip():
            raise CostProfileInvalid("ITEM_LABEL_REQUIRED", "Cada cargo necesita un nombre.")
        if item.kind not in ITEM_KINDS:
            raise CostProfileInvalid("ITEM_KIND_INVALID", "El cargo es un porcentaje (percent) o un monto (amount).")
        if item.value < 0 or (item.kind == "percent" and item.value > 100):
            raise CostProfileInvalid("ITEM_VALUE_INVALID", f"Valor no válido para «{item.label}».")


def profile_on(profiles: list[CostProfile], day: date) -> Optional[CostProfile]:
    """Registro vigente en `day`: el más reciente que rige desde esa fecha o antes."""
    valid = [p for p in profiles if p.effective_from <= day]
    return max(valid, key=lambda p: p.effective_from) if valid else None


def reference_rate(current: list[CostProfile]) -> Optional[float]:
    """Tarifa de referencia para estimar recetas: promedio del costo por hora de servicio de los groomers
    con registro vigente (hoy hay uno solo)."""
    if not current:
        return None
    return sum(p.cost_per_service_hour for p in current) / len(current)


def labor_cost(minutes: float, rate_per_hour: Optional[float]) -> Optional[float]:
    return None if rate_per_hour is None else minutes / 60 * rate_per_hour
