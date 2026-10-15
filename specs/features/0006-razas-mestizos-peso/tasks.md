---
feature: 0006-razas-mestizos-peso
plan: ./plan.md
---

# Tasks

## Backend
- [x] 1. Precio desde `breeds.coat_type` (repo + llamadores) y redondeo de peso.
- [x] 2. Admin de razas: pelaje, mestizo, foto, descripción.
- [x] 3. Catálogo: mestizos 1–6, variantes, cambios del documento + migración.
- [x] 4. Peso: `weight_updated_at`, regla de 30 días, `weight_editable_from`.
- [x] 5. Seguridad y perfume en el perfil.
- [x] 6. Tests (`test_breeds_admin_coat.py`, `test_weight_balance.py`).
- [x] 7. C-27 en `docs/cambios-api-para-front.md`.

## Frontend
- [ ] Admin: asignar pelaje por categoría (asignación inversa), foto y descripción de mestizos.
- [ ] App de clientes: elegir mestizo por foto; mensaje de `PET_WEIGHT_COOLDOWN`; seguridad y perfume.
- [ ] App de groomers: alertas de seguridad y perfume en la ficha.

## Cierre
- [ ] Spec a `done`, commit referencia la carpeta.
