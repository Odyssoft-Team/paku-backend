---
feature: 0009-inventario
estado: in-progress   # draft | approved | in-progress | done | abandoned
repos: [paku-backend, paku-admin]
creado: 2026-10-29
---

# Inventario: insumos, movimientos, recetas y costo por orden

## Problema

El admin tenía una maqueta de Inventario (Insumos, Movimientos, Recetas y costeo) con datos en memoria. El
backend no tenía nada: no se sabía cuánto stock hay, cuánto se consume por servicio ni cuánto cuesta cada
servicio (insumos y mano de obra).

## Objetivo

Llevar el stock de insumos como la suma de sus movimientos, descontar los insumos de cada servicio terminado
según su receta y dar el costo de cada orden (insumos + mano de obra del groomer, feature 0012).

## Fuera de alcance

- Comisión de pasarela, variable del groomer y otros costos directos del costeo (Finanzas).
- Stock por ubicación (hay una sola van): el stock es global; la ubicación queda como dato del movimiento.
- Lotes con stock propio, alertas de vencimiento, proveedores y órdenes de compra.
- Costo promedio ponderado: se usa el costo estándar del insumo.

## Comportamiento esperado

1. **Dado** un insumo nuevo, **entonces** recibe el código siguiente (`INS-001`…), el costo por unidad de
   consumo es costo de compra ÷ contenido y el stock es 0.
2. **Dado** un insumo, **entonces** su stock es la suma de sus movimientos; estado `out` (≤ 0), `low` (bajo
   el mínimo) u `ok`; valor = max(stock, 0) × costo por unidad.
3. **Dado** un movimiento manual, **entonces** compra y stock inicial suman, merma y consumo restan y el
   ajuste suma (entrada) o resta (salida). Motivo obligatorio. Nada se borra: se corrige con un ajuste.
4. **Dado** cada movimiento, **entonces** guarda el costo por unidad del momento.
5. **Dada** una receta, **entonces** tiene la misma forma que la tabla de precios: una por servicio y una
   por adicional (los adicionales existen por servicio, igual que sus precios), filas = tipo de pelaje +
   «Mestizo u otra raza», columnas = tramos de peso. Cada celda: insumos con cantidad y minutos de groomer.
6. **Dado** que el admin guarda la tabla, **entonces** se crea la versión siguiente (R1 → R2); sin cambios
   da 409. Las celdas vacías no se guardan.
7. **Dada** una orden que pasa a `done` (groomer con `/complete` o admin "cerrar a mano"), **entonces** se
   registran solos los consumos de su servicio base y de cada adicional, con la celda que da la regla del
   precio: fila del pelaje de la raza (o «Mestizo» si esa celda falta) y el tramo del **peso registrado por
   el groomer** (siempre se pesa; si faltara, el declarado). Una sola vez por orden; las órdenes de ajuste no
   consumen. Si falla, la orden termina igual y el admin lo registra después.
8. **Dado** un servicio o adicional sin celda que aplique, **entonces** no se descuenta nada y el costeo lo
   informa como "sin receta".
9. **Dada** una orden, **entonces** el costeo da insumos (registrados o estimados), mano de obra estimada
   (minutos de la receta × costo por hora de servicio del groomer de la orden, o el de referencia), mano de
   obra con el tiempo real (llegada → fin, como la pantalla Tiempos), el traslado real, la venta y los
   márgenes.
10. **Dada** la tabla de receta, **entonces** cada celda muestra costo de insumos, mano de obra, costo total,
    el precio de la misma celda y el margen.

## Criterios de aceptación

- [x] Maestro de insumos, movimientos (con ajuste de entrada y salida) y resumen.
- [x] Recetas como la tabla de precios, versionadas, con minutos de groomer.
- [x] Consumo automático al terminar una orden, idempotente; registro manual para órdenes anteriores.
- [x] Costeo por orden con mano de obra estimada y real.
- [x] Admin: Insumos, Movimientos y Recetas conectados a la API (sin "Demo").
- [x] Migración (no ejecutada) y tests.

## Impacto en el dominio

Módulo nuevo `inventory`. `orders` llama al consumo al pasar a `done`. Usa `store` (precios y categoría de
precio de la mascota) y `groomer_costs` (tarifa por hora).

## Decisiones (dueño, 2026-10-29)

- Las recetas siguen la estructura de precios (pelaje × peso por servicio y adicional), no las llaves de la maqueta.
- Siempre se pesa al perro: el tramo sale del peso registrado.
- Ubicaciones `Almacén central` y `Paku 01`; centros de costo `CC-PAKU01` (única unidad móvil), `CC-SPA-GEN`
  (general / almacén) y `CC-ADM`.
- Deslanado: solo doble manto (filas de pelaje doble), todos los pesos, el mismo tiempo.

## Supuestos (revisables)

- **Costo estándar** del insumo (el de su ficha); la compra no lo recalcula.
- **Adicionales comprados** se descuentan aunque el groomer no los marque como hechos.
- **Stock negativo permitido** en el consumo automático (el servicio ya se hizo).
- **Mano de obra estimada** usa siempre las recetas vigentes; los insumos ya registrados no cambian.

## Preguntas abiertas

- [ ] ¿Costo promedio ponderado en vez de costo estándar?
