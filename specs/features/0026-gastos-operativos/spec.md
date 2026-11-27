---
feature: 0026-gastos-operativos
estado: in-progress   # draft | approved | in-progress | done | abandoned
repos: [paku-backend, paku-admin]
creado: 2026-11-26
---

# Gastos operativos, vehículos e impuesto a la renta

## Problema

El P&L (0024) mostraba «Gastos operativos» e «Impuestos» sin dónde registrarlos: la utilidad quedaba parcial.

## Reglas (dueño, 2026-11-26)

1. **Tipos de gasto según cómo se pagan:** **único** (en su fecha; p. ej. combustible, según se consume), **mensual**
   (cada mes desde su inicio hasta su fecha de fin, sin fin = sigue; p. ej. internet) y **anual** (se paga una vez y se
   reparte en 12 meses desde su fecha; p. ej. el dominio). En un período parcial (rango o mes en curso) el mensual y el
   anual se reparten por días, como el costo del groomer.
2. **Monto:** lo pagado y si incluye IGV; el P&L usa el monto **sin IGV** (IGV de Parámetros generales al guardar).
3. **Categorías** fijas (vehículos: combustible, mantenimiento, seguro y SOAT, cochera y peajes, otros; servicios:
   internet y telefonía, luz y agua, alquiler; tecnología: dominio, hosting y software; publicidad; contador y legal;
   comisiones bancarias; útiles; otros).
4. **Vehículos:** nombre, placa (única), marca, modelo, año, activo. Un gasto se puede ligar a un vehículo.
5. Un gasto se **edita** o se **anula** con motivo (deja de contar); no se borra.
6. **No duplicar:** el sueldo del groomer (costo del servicio) y los insumos de inventario (agua, shampoo) no se
   registran como gastos.
7. **Impuesto a la renta:** Parámetros generales → Impuestos, «Impuesto a la renta (%)», **10 %** por defecto (régimen
   MYPE). En el P&L: utilidad antes de impuestos = margen bruto − gastos operativos; impuesto = % de esa utilidad (con
   pérdida, 0); utilidad neta = antes de impuestos − impuesto. Ejemplo: margen S/ 261.53 sin gastos → impuesto
   S/ 26.15, utilidad neta S/ 235.38.
8. **Depreciación:** no se considera por ahora.

## Contrato

`/admin/expenses` (config, lista con parte del período, crear, editar, anular) y `/admin/vehicles`. P&L: líneas
`operating_expenses` (real), `pre_tax_result`, `taxes` (estimado) y `net_result`; detalle `expenses`. C-65.

## Criterios de aceptación

- [x] Gastos y vehículos con tests; migración `3e4f5a6b7c8d`.
- [x] P&L con gastos e impuesto; impuesto configurable.
- [x] Admin: Finanzas → Gastos (gastos y vehículos) y detalle «Gastos» en el P&L.

## Supuestos (revisables)

- El 10 % se aplica a la utilidad de cada período como estimado mensual; el impuesto real es anual y lo define el
  contador (tramos MYPE).
- El monto de un gasto mensual que cambia de precio: se le pone fecha de fin y se registra uno nuevo.
