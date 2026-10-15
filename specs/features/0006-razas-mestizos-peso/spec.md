---
feature: 0006-razas-mestizos-peso
estado: in-progress   # draft | approved | in-progress | done | abandoned
repos: [paku-backend, paku-admin, paku-monorepo]
creado: 2026-10-14
---

# Pelaje administrable, mestizos por foto, variantes de pelo y reglas de peso

## Problema

Respuestas del cliente (2026-10-14) al documento de precios:

1. El cobro por diferencia de peso se mantiene, pero el cliente no puede cambiar el peso a cada rato ni
   durante un servicio; el groomer sí.
2. Debe haber 6 mestizos, uno por tipo de pelaje; la app muestra fotos y la elegida define el mestizo.
4. El pelaje de cada raza lo asigna el negocio ("ingresas raza y asignas tipo de pelo"). Hoy está fijo en
   código (`breeds_data.py`): una raza creada en el admin se cobra como mestizo.
7. Las razas con variantes de pelo van como razas separadas.

Además (documento, BR-014/BR-019): datos de seguridad (reactiva, mordidas, bozal) y perfume en el perfil.

## Objetivo

El precio usa el pelaje que el admin asigna a cada raza; los mestizos se eligen por foto; el dueño cambia el
peso como máximo una vez cada 30 días.

## Fuera de alcance

- Fotos antes del pago (BR-008), cancelaciones, agenda por duración, versión de precios en la orden.

## Comportamiento esperado

1. **Dado** una raza, **cuando** el admin cambia su pelaje, **entonces** las cotizaciones siguientes usan
   ese pelaje. Sin pelaje → fila "mestizo".
2. **Dado** el catálogo público, **entonces** cada raza trae `is_mixed`, `photo_url` y `description`; hay 6
   razas mestizas (`dog_mixed_1..6`), una por pelaje, y "Mestizo" (`dog_mixed`) queda inactivo.
3. **Dado** un dueño que cambió el peso hace menos de 30 días (configurable), **cuando** lo cambia de nuevo,
   **entonces** 409 `PET_WEIGHT_COOLDOWN` con la fecha desde la que podrá. El peso del registro inicial no
   cuenta. El groomer y el admin pueden siempre. Con servicio solicitado sigue el 409 `PET_WEIGHT_LOCKED`.
4. **Dado** el perfil, **entonces** acepta `reactive`, `bite_history`, `muzzle_required`, `fragrance`.
5. **Dado** un peso con más de 2 decimales (5.004), **entonces** cae en el tramo siguiente (no queda sin precio).

## Criterios de aceptación

- [x] Precio desde `breeds.coat_type`; admin crea/edita pelaje, mestizo, foto y descripción.
- [x] 6 mestizos, variantes, migración.
- [x] Regla de 30 días + `weight_updated_at` / `weight_editable_from` en `PetOut`.
- [x] Campos de seguridad y perfume.
- [x] Tests.
