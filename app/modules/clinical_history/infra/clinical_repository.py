from datetime import timedelta
from typing import List
from uuid import UUID

from app.modules.clinical_history.domain.clinical_entry import ClinicalEntry, utcnow


def list_by_pet(pet_id: UUID) -> List[ClinicalEntry]:
    now = utcnow()
    entries = [
        # Servicio de grooming reciente
        ClinicalEntry.new(
            pet_id=pet_id,
            type="grooming",
            summary="Baño completo y corte de uñas. Pelaje en excelente estado.",
            created_at=now - timedelta(days=2),
        ),
        # Servicio de grooming anterior
        ClinicalEntry.new(
            pet_id=pet_id,
            type="grooming",
            summary="Baño express con shampoo hipoalergénico. Sin incidencias.",
            created_at=now - timedelta(days=17),
        ),
        # Consulta médica reciente
        ClinicalEntry.new(
            pet_id=pet_id,
            type="checkup",
            summary="Control de rutina. Signos vitales normales. Peso estable.",
            created_at=now - timedelta(days=30),
        ),
        # Consulta médica anterior
        ClinicalEntry.new(
            pet_id=pet_id,
            type="checkup",
            summary="Revisión general. Vacunas al día. Se recomienda control en 6 meses.",
            created_at=now - timedelta(days=90),
        ),
        # Vacuna reciente
        ClinicalEntry.new(
            pet_id=pet_id,
            type="vaccine",
            summary="Vacuna antirrábica anual aplicada. Próxima dosis: 2027.",
            created_at=now - timedelta(days=45),
        ),
        # Vacuna del año pasado
        ClinicalEntry.new(
            pet_id=pet_id,
            type="vaccine",
            summary="Vacuna antirrábica anual. Sin reacciones adversas.",
            created_at=now - timedelta(days=365),
        ),
    ]
    entries.sort(key=lambda e: e.created_at, reverse=True)
    return entries
