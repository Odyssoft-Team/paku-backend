---
feature: 0005-requisitos-servicio
plan: ./plan.md
---

# Tasks — Requisitos del servicio

## Backend
- [x] 1. Campos en producto (dominio, modelo, repo, esquemas, rutas) + migración.
- [x] 2. `eligibility.py` y uso en cotización/carrito (no en saldo por peso).
- [x] 3. Listado y detalle con mascota ocultan lo que no aplica.
- [x] 4. Simulador respeta el peso máximo.
- [x] 5. Razas de la hoja 03.
- [x] 6. Tests (`tests/unit/test_store_requirements.py`).
- [x] 7. Entrada C-26 en `docs/cambios-api-para-front.md`.

## Frontend
- [x] Admin: campos "Peso máximo" y "Edad máxima" en el formulario de producto.
- [x] App de clientes: muestra `detail.message` de `PET_*` (ya lo hacía) y oculta adicionales sin precio.

## Datos (después del despliegue)
- [ ] Express sin agua: 10 kg y 4 meses.

## Cierre
- [ ] Spec a `done`, índice actualizado, commit referencia la carpeta.
