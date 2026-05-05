from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Optional
from uuid import UUID, uuid4


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RecordType(str, Enum):
    check_up = "check_up"
    vaccine = "vaccine"
    deworming = "deworming"
    medication = "medication"
    bath = "bath"
    grooming = "grooming"
    weight_record = "weight_record"
    nutrition = "nutrition"
    disease_condition = "disease_condition"
    surgery = "surgery"
    study_test = "study_test"
    note = "note"


class RecordRole(str, Enum):
    owner = "owner"
    admin = "admin"
    system = "system"


# ---------------------------------------------------------------------------
# Validation schema — required fields per RecordType
# ---------------------------------------------------------------------------

RECORD_TYPE_SCHEMA: dict[RecordType, list[str]] = {
    RecordType.check_up:          ["vet_name", "diagnosis"],
    RecordType.vaccine:           ["vaccine_name", "next_dose_date"],
    RecordType.deworming:         ["product_name", "next_due_date"],
    RecordType.medication:        ["drug_name", "dose", "frequency", "duration_days"],
    RecordType.bath:              ["performed_by"],
    RecordType.grooming:          ["service_type", "performed_by"],
    RecordType.weight_record:     ["weight_kg"],
    RecordType.nutrition:         ["food_brand", "food_type"],
    RecordType.disease_condition: ["condition_name", "status"],
    RecordType.surgery:           ["procedure_name", "vet_name"],
    RecordType.study_test:        ["test_name", "result_summary"],
    RecordType.note:              ["text"],
}


def validate_record_data(record_type: RecordType, data: dict) -> list[str]:
    """Devuelve lista de campos faltantes o inválidos.

    No lanza excepciones — la responsabilidad de convertirlos en HTTP errors
    recae en el use case.
    """
    required = RECORD_TYPE_SCHEMA.get(record_type, [])
    missing = [f for f in required if not data.get(f)]

    # Validación adicional de rango para weight_record
    if record_type == RecordType.weight_record and "weight_kg" not in missing:
        try:
            if float(data["weight_kg"]) <= 0:
                missing.append("weight_kg (debe ser mayor que 0)")
        except (TypeError, ValueError):
            missing.append("weight_kg (debe ser un número válido)")

    return missing


# ---------------------------------------------------------------------------
# Title generators
# ---------------------------------------------------------------------------

def _safe(data: dict, key: str, fallback: str = "") -> str:
    return str(data.get(key) or fallback)


TITLE_GENERATORS: dict[RecordType, Callable[[dict], str]] = {
    RecordType.check_up: lambda d: (
        f"Consulta veterinaria — {_safe(d, 'vet_name', 'veterinario')}"
    ),
    RecordType.vaccine: lambda d: (
        f"Vacuna: {_safe(d, 'vaccine_name', 'N/A')}"
        + (f" — próxima dosis: {_safe(d, 'next_dose_date')}" if d.get("next_dose_date") else "")
    ),
    RecordType.deworming: lambda d: (
        f"Desparasitación: {_safe(d, 'product_name', 'N/A')}"
    ),
    RecordType.medication: lambda d: (
        f"Medicamento: {_safe(d, 'drug_name', 'N/A')}"
    ),
    RecordType.bath: lambda d: "Baño",
    RecordType.grooming: lambda d: (
        f"Peluquería: {_safe(d, 'service_type', 'servicio')}"
    ),
    RecordType.weight_record: lambda d: (
        f"Peso registrado: {_safe(d, 'weight_kg', '?')} kg"
    ),
    RecordType.nutrition: lambda d: (
        f"Nutrición: {_safe(d, 'food_brand', 'N/A')} — {_safe(d, 'food_type', '')}"
    ),
    RecordType.disease_condition: lambda d: (
        f"Condición: {_safe(d, 'condition_name', 'N/A')}"
    ),
    RecordType.surgery: lambda d: (
        f"Cirugía: {_safe(d, 'procedure_name', 'N/A')}"
    ),
    RecordType.study_test: lambda d: (
        f"Estudio: {_safe(d, 'test_name', 'N/A')}"
    ),
    RecordType.note: lambda d: "Nota",
}


def generate_title(record_type: RecordType, data: dict) -> str:
    """Genera un título automático basado en el tipo y los datos.

    Siempre devuelve un string no vacío — tiene fallback seguro.
    """
    generator = TITLE_GENERATORS.get(record_type)
    if generator is None:
        return record_type.value.replace("_", " ").capitalize()
    try:
        result = generator(data)
        return result.strip() or record_type.value.replace("_", " ").capitalize()
    except Exception:
        return record_type.value.replace("_", " ").capitalize()


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PetRecord:
    id: UUID
    pet_id: UUID
    type: RecordType
    title: str
    occurred_at: datetime
    created_at: datetime
    updated_at: datetime
    recorded_by_role: RecordRole
    data: dict
    attachment_ids: list[UUID]
    recorded_by_user_id: Optional[UUID] = None
    deleted_at: Optional[datetime] = None

    @staticmethod
    def new(
        *,
        pet_id: UUID,
        type: RecordType,
        occurred_at: datetime,
        data: dict,
        recorded_by_role: RecordRole,
        recorded_by_user_id: Optional[UUID] = None,
        title: Optional[str] = None,
        attachment_ids: Optional[list[UUID]] = None,
    ) -> "PetRecord":
        now = datetime.now(timezone.utc)

        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)

        if occurred_at > now:
            raise ValueError("occurred_at no puede ser posterior a la fecha actual")

        ids = list(attachment_ids or [])
        if len(ids) > 10:
            raise ValueError("attachment_ids no puede tener más de 10 elementos")

        resolved_title = (title or "").strip() or generate_title(type, data)

        return PetRecord(
            id=uuid4(),
            pet_id=pet_id,
            type=type,
            title=resolved_title,
            occurred_at=occurred_at,
            created_at=now,
            updated_at=now,
            recorded_by_user_id=recorded_by_user_id,
            recorded_by_role=recorded_by_role,
            data=data,
            attachment_ids=ids,
            deleted_at=None,
        )
