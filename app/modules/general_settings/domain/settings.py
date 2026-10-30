"""Parámetros generales de la empresa (feature 0010). Una sola empresa: un valor por parámetro.

Cada parámetro tiene tipo, valor por defecto y validación aquí; en la BD solo se guardan los que el admin
cambió (`general_settings`, clave → valor JSON). Algunos son de solo lectura porque el código depende de
ellos (zona horaria, moneda, tiempo para pagar = vida del carrito) y cambiarlos no tendría efecto.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from app.modules.cart.domain.cart import CART_TTL_HOURS


class SettingInvalid(ValueError):
    def __init__(self, key: str, message: str) -> None:
        super().__init__(message)
        self.key = key
        self.message = message


@dataclass(frozen=True)
class SettingField:
    key: str
    section: str
    label: str
    type: str                    # text | ruc | email | phone | time | percent | int | readonly
    default: Any = None
    editable: bool = True
    help: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None


SECTIONS: dict[str, str] = {
    "company": "Empresa",
    "operation": "Operación",
    "booking": "Reservas",
}

FIELDS: tuple[SettingField, ...] = (
    SettingField("company_name", "company", "Nombre comercial", "text", default="Paku"),
    SettingField("company_ruc", "company", "RUC", "ruc"),
    SettingField("contact_phone", "company", "Teléfono de contacto", "phone"),
    SettingField("contact_email", "company", "Correo de contacto", "email"),
    SettingField("timezone", "operation", "Zona horaria", "readonly", default="America/Lima", editable=False,
                 help="Fija: todo el negocio corre en hora de Lima."),
    SettingField("currency", "operation", "Moneda", "readonly", default="PEN", editable=False,
                 help="Fija: los precios y cobros son en soles (S/)."),
    SettingField("business_hours_open", "operation", "Hora de apertura", "time"),
    SettingField("business_hours_close", "operation", "Hora de cierre", "time"),
    SettingField("igv_percent", "operation", "IGV (%)", "percent", default=18, min=0, max=100,
                 help="Referencial para reportes; los precios ya lo incluyen."),
    SettingField("booking_min_days_ahead", "booking", "Anticipación mínima para reservar (días)", "int",
                 default=0, min=0, max=30, help="0 = se puede reservar para hoy."),
    SettingField("reservation_ttl_minutes", "booking", "Tiempo para pagar una reserva (minutos)", "readonly",
                 default=CART_TTL_HOURS * 60, editable=False,
                 help="Es la vida del carrito: la reserva vence con él."),
)
FIELDS_BY_KEY: dict[str, SettingField] = {f.key: f for f in FIELDS}

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE = re.compile(r"^\+?[0-9 ()-]{6,20}$")
_TIME = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")


def validate_value(key: str, value: Any) -> Any:
    """Valor normalizado para guardar, o `SettingInvalid`. `None` (o texto vacío) vuelve al valor por defecto."""
    field = FIELDS_BY_KEY.get(key)
    if field is None:
        raise SettingInvalid(key, f"Parámetro desconocido: {key}.")
    if not field.editable:
        raise SettingInvalid(key, f"«{field.label}» no se puede cambiar.")
    if isinstance(value, str):
        value = value.strip()
    if value is None or value == "":
        return None
    if field.type in ("text", "ruc", "email", "phone", "time") and not isinstance(value, str):
        raise SettingInvalid(key, f"«{field.label}» debe ser texto.")
    if field.type == "text" and len(value) > 200:
        raise SettingInvalid(key, f"«{field.label}» admite hasta 200 caracteres.")
    if field.type == "ruc" and not (value.isdigit() and len(value) == 11):
        raise SettingInvalid(key, "El RUC tiene 11 dígitos.")
    if field.type == "email" and not _EMAIL.match(value):
        raise SettingInvalid(key, "Correo inválido.")
    if field.type == "phone" and not _PHONE.match(value):
        raise SettingInvalid(key, "Teléfono inválido.")
    if field.type == "time" and not _TIME.match(value):
        raise SettingInvalid(key, f"«{field.label}» va en formato HH:MM (24 h).")
    if field.type in ("percent", "int"):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SettingInvalid(key, f"«{field.label}» debe ser un número.")
        if field.type == "int" and int(value) != value:
            raise SettingInvalid(key, f"«{field.label}» debe ser un número entero.")
        if (field.min is not None and value < field.min) or (field.max is not None and value > field.max):
            raise SettingInvalid(key, f"«{field.label}» va de {field.min:g} a {field.max:g}.")
        value = int(value) if field.type == "int" else float(value)
    return value


def resolve(stored: dict[str, Any]) -> dict[str, Any]:
    """Valor efectivo de cada parámetro: lo guardado, o su valor por defecto."""
    return {
        f.key: (stored[f.key] if f.editable and stored.get(f.key) is not None else f.default)
        for f in FIELDS
    }


def check_consistency(values: dict[str, Any]) -> None:
    """Reglas entre parámetros (sobre los valores efectivos)."""
    open_, close = values.get("business_hours_open"), values.get("business_hours_close")
    if open_ and close and open_ >= close:
        raise SettingInvalid("business_hours_close", "La hora de cierre debe ser posterior a la de apertura.")
