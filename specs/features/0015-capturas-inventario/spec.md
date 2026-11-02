---
feature: 0015-capturas-inventario
estado: in-progress   # draft | approved | in-progress | done | abandoned
repos: [paku-backend, paku-admin]
creado: 2026-11-01
---

# Capturas periódicas del inventario

## Problema

El stock se calcula al momento desde los movimientos. Si alguien registra después un movimiento con fecha
pasada, el stock de ese día cambia. Para cerrar períodos piden una foto fija del inventario en fechas
regulares, que quede guardada y se pueda consultar, aparte de las consultas manuales.

## Objetivo

En la fecha de corte configurada (cada domingo, el 15 y el fin de mes, o solo el fin de mes), el sistema guarda
solo el estado del inventario. Las capturas se consultan y exportan en una pestaña de Inventario.

## Fuera de alcance

- Stock por ubicación o por lote (el stock sigue siendo global).
- Comparar dos capturas o corregir una captura. Una captura no se edita ni se borra.

## Comportamiento esperado

1. **Dada** la frecuencia en Parámetros generales (`Cada domingo`, `Día 15 y fin de mes`, `Fin de mes` o
   `Sin captura automática`; por defecto `Fin de mes`), **cuando** termina un día de corte (hora de Lima),
   **entonces** el sistema guarda una captura con fecha de corte ese día.
2. **Dada** una captura, **entonces** el stock de cada insumo es la suma de sus movimientos con fecha hasta el
   corte, incluido. Guarda una copia del insumo (código, nombre, categoría, unidad), stock, mínimo, costo por
   unidad, valor (stock × costo, sin negativos) y estado (`ok`, `low`, `out`), con las mismas reglas que Insumos.
3. **Dada** una captura, **entonces** incluye los insumos activos y los inactivos que aún tienen stock.
4. **Dado** que el servidor estuvo apagado, **cuando** vuelve, **entonces** toma la captura del último corte si
   no pasaron más de 3 días; si pasaron más, ese corte se pierde (no se inventa una foto tardía).
5. **Dado** un corte, **entonces** hay como máximo una captura automática (aunque corran varias instancias).
6. **Cuando** el admin pulsa "Tomar captura ahora", **entonces** se guarda una captura manual con corte hoy.
7. **Dada** la pestaña Capturas, **entonces** se filtran por rango de fechas de corte, se ve el detalle con
   filtros (texto, categoría, estado) y se exporta a CSV. Insumos y Movimientos también se exportan.

## Criterios de aceptación

- [ ] Tablas nuevas para capturas y sus líneas (migración).
- [ ] Parámetro de frecuencia en Parámetros generales.
- [ ] Tarea programada idempotente; endpoints de lista, detalle y captura manual.
- [ ] Pestaña Capturas y botones Exportar en Insumos, Movimientos y Capturas.

## Supuestos (decididos sin preguntar, revisables)

- El costo por unidad de la captura es el del insumo en el momento de tomarla (el mismo que muestra Insumos).
- La captura del corte se toma después de que termina el día de corte (la tarea revisa cada 30 minutos).
- El margen de recuperación es de 3 días.
