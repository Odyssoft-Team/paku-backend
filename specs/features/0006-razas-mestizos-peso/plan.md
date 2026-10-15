---
feature: 0006-razas-mestizos-peso
spec: ./spec.md
---

# Plan

## Datos (migración `6f7a8b9c0d1e`, compartida con 0005)

- `breeds`: `is_mixed` (bool), `photo_url`, `description`. Altas: `dog_mixed_1..6`, variantes `_largo`,
  Lagotto, Perro de Agua Portugués, Aussiedoodle. Cambios: Pug, Pekinés, Cocker (corte corto → pelo
  medio/largo), nombres "pelo corto". `dog_mixed` inactivo.
- `pets`: `weight_updated_at`, `reactive`, `bite_history`, `muzzle_required`, `fragrance`.
- Setting `PET_WEIGHT_CHANGE_COOLDOWN_DAYS` (30).

## Cambios

- `store`: `category_for_coat()`; `PostgresStoreRepository.price_category_for(breed_id)` lee `breeds`;
  `_breed_category` pasa a async con el repo (cotización, catálogo, simulador, saldo por peso). Redondeo
  hacia arriba del peso al centésimo en `price_detail_for`.
- `catalog`: `Breed` + `coat_group_for`; admin `POST/PATCH /admin/breeds` con `coat_type`, `is_mixed`,
  `photo_url`, `description` (PATCH: solo campos enviados; null quita). Público `/catalog/breeds` los devuelve.
- `pets`: `weight_policy.weight_editable_from`; `PetOut.weight_updated_at` y `weight_editable_from`;
  `PATCH /pets/{id}/optional` acepta los 4 campos nuevos.
- `pet_records`: weight_record del dueño → 409 `PET_WEIGHT_COOLDOWN`; todo cambio de peso guarda
  `weight_updated_at`.
