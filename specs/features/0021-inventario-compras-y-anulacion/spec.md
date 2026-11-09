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
   (cero, uno o varios; no es un catálogo compartido). Cada proveedor: nombre (obligatorio), código del
   producto (el que usa el proveedor, se ingresa a mano), teléfono, dirección, cuenta bancaria y RUC
   (11 dígitos), todos opcionales.
2. **Dado** el formulario del insumo, **entonces** la unidad de consumo puede ser `ml`, `L`, `g` o `unidad`.
   Las recetas y el stock de ese insumo se miden en esa unidad.
3. **Dada** una compra, **entonces** se ingresa la **cantidad real** en unidad de consumo (100 L, no «0,5
   recargas de 200 L») y el **total pagado** (obligatorio). Costo por unidad del movimiento = total ÷ cantidad.
   (Cambiado el 2026-11-09: antes se ingresaban unidades de compra y precio por unidad de compra.)
4. **Dado** un stock inicial, **entonces** el total pagado es opcional; sin total se usa el costo de la ficha.
5. **Dada** una entrada con precio, **entonces** el costo del insumo pasa al **promedio ponderado**:
   (stock × costo actual + cantidad × precio nuevo) ÷ (stock + cantidad). Un stock negativo cuenta como 0.
   Lo ya registrado no cambia de costo.
6. **Dado** un movimiento manual (stock inicial, compra, ajuste, merma o consumo manual), **entonces** se puede
   **anular** con motivo obligatorio: queda en el historial con quién, cuándo y por qué, y deja de contar en
   el stock, el valor y el consumo. No se borra. El consumo generado por la receta de una orden no se anula.
7. **Dada** la lista de movimientos, **entonces** por defecto oculta los anulados; se pueden ver con un filtro.
9. **Dado** un movimiento manual vigente, **entonces** se puede **editar** todo menos el tipo (fecha, insumo,
   cantidad, total pagado, entrada/salida de un ajuste, motivo, ubicación, centro de costo, lote, vencimiento) con
   motivo de edición obligatorio. Cada edición guarda quién, cuándo, el motivo y los valores antes y después. El
   stock se recalcula solo y, si toca una entrada, el costo promedio (regla 10). No se editan los anulados ni el
   consumo por receta de una orden. Para cambiar el tipo: anular y registrar de nuevo.

8. **Dada** una celda de receta con precio, **entonces** el margen = precio sin IGV − costo (insumos + minutos ×
   costo por hora). Los precios incluyen IGV: precio sin IGV = precio ÷ (1 + IGV de Parámetros generales);
   S/ 75 con 18 % → S/ 63,56. **Solo en Recetas** (2026-11-09): Simulador, costo de una orden y Resultados de
   campañas siguen restando del precio con IGV.

10. **Dado** que se anula o se edita una entrada (confirmado por el dueño 2026-11-09), **entonces** el costo
    promedio del insumo se **recalcula** repasando en orden (fecha y número) todos sus movimientos vigentes: cada
    entrada pondera con su costo (con total pagado: total ÷ cantidad; si no, el costo con que se registró) y las
    salidas solo bajan el stock (un stock negativo cuenta como 0). Sin entradas vigentes, la ficha no cambia. El
    recálculo reemplaza una corrección manual hecha en la ficha. Lo ya registrado no cambia de costo.

## Fuera de alcance

Catálogo compartido de proveedores, órdenes de compra, editar un movimiento, recalcular el promedio al anular.
