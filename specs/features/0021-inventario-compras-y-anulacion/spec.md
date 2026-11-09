---
feature: 0021-inventario-compras-y-anulacion
estado: in-progress
repos: [paku-backend, paku-admin]
creado: 2026-11-09
---

# Inventario: ficha del insumo, precio en la compra y anulación de movimientos

## Problema

- La ficha del insumo no guarda marca, descripción ni proveedores, y la unidad de consumo no admite litros.
- El costo del insumo se ingresa una vez en la ficha; si una compra sale más cara o más barata, no hay dónde
  registrarlo.
- Un movimiento manual mal registrado solo se podía corregir con un ajuste compensatorio.

## Comportamiento esperado (reglas confirmadas por el dueño, 2026-11-09)

1. **Dado** un insumo, **entonces** tiene marca y descripción opcionales y una lista propia de proveedores
   (cero, uno o varios; no es un catálogo compartido). Cada proveedor: nombre (obligatorio), teléfono,
   dirección, cuenta bancaria y RUC (11 dígitos), todos opcionales.
2. **Dado** el formulario del insumo, **entonces** la unidad de consumo puede ser `ml`, `L`, `g` o `unidad`.
   Las recetas y el stock de ese insumo se miden en esa unidad.
3. **Dada** una compra, **entonces** se ingresa la cantidad en unidades de compra (p. ej. 2 galones) y el
   precio pagado por unidad de compra (obligatorio). El movimiento queda a ese precio.
4. **Dado** un stock inicial, **entonces** el precio es opcional; sin precio se usa el costo de la ficha.
5. **Dada** una entrada con precio, **entonces** el costo del insumo pasa al **promedio ponderado**:
   (stock × costo actual + cantidad × precio nuevo) ÷ (stock + cantidad). Un stock negativo cuenta como 0.
   Lo ya registrado no cambia de costo.
6. **Dado** un movimiento manual (stock inicial, compra, ajuste, merma o consumo manual), **entonces** se puede
   **anular** con motivo obligatorio: queda en el historial con quién, cuándo y por qué, y deja de contar en
   el stock, el valor y el consumo. No se borra. El consumo generado por la receta de una orden no se anula.
7. **Dada** la lista de movimientos, **entonces** por defecto oculta los anulados; se pueden ver con un filtro.

## Pendiente de confirmar

- Anular una compra **no recalcula** el costo promedio (las compras posteriores ya lo usaron). Si hace falta,
  el costo se corrige a mano en la ficha. Propuesta por defecto, no aprobada.

## Fuera de alcance

Catálogo compartido de proveedores, órdenes de compra, editar un movimiento, recalcular el promedio al anular.
