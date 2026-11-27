---
feature: 0024-pnl-mensual
estado: in-progress   # draft | approved | in-progress | done | abandoned
repos: [paku-backend, paku-admin]
creado: 2026-11-26
---

# Cierre mensual / P&L con datos reales (etapa 1)

## Problema

«Cierre mensual / P&L» del admin es una maqueta con datos de ejemplo (`lib/mock/finanzas.ts`). Los datos para
armarlo ya existen en parte (órdenes, comprobantes, consumos de inventario, recetas y costo del groomer), pero nadie
los junta por mes ni se puede saber de dónde sale cada importe.

## Objetivo

Un P&L de un mes, de solo lectura, con las líneas que hoy tienen datos reales, cada una rastreable hasta las órdenes
y movimientos que la forman. Lo que aún no se registra sale «no configurado», nunca 0.

## Fuera de alcance (etapas siguientes)

- Variable del groomer por puntos (etapa 3), gastos operativos, depreciación e impuestos (etapa 4).
- Foto del cierre o bloqueo del mes: en esta etapa el mes queda «abierto» (lo registrado después puede cambiarlo).
- Pagos y conciliación con Culqi, fecha de pago, reembolsos y notas de crédito.
- Centros de costo en el P&L.

## Decisiones (dueño, 2026-11-26)

1. **Mes de la venta = mes en que se realizó el servicio** (la boleta sale con esa fecha; feature 0023, regla 1b).
2. **Venta sin IGV = la del comprobante** (`taxable_amount`). Si la orden aún no tiene comprobante vigente, se
   calcula total ÷ (1 + IGV de Parámetros generales) y se marca «pendiente de boleta».
3. **Pagado y cancelado no es venta:** se reprograma o queda pendiente de reembolso (Términos y condiciones). Se
   muestra aparte.
4. **Mano de obra:** minutos de la receta × costo por hora de servicio del groomer. La receta es la **versión vigente
   el día del servicio** (si se actualiza la receta, los meses anteriores no cambian). El tiempo real (llegada → fin)
   se muestra al lado, con la variación en S/.
5. **Mano de obra no utilizada** (costo mensual del groomer − lo asignado a servicios) va dentro del costo del
   servicio. Así la mano de obra suma el costo real del groomer y no se cuenta dos veces.
6. **Mermas y ajustes de salida** van dentro del costo del servicio, en una línea propia.
7. **Comisión de la pasarela:** % de tarjeta y % de Yape en Parámetros generales (sección Finanzas). Sin % no se
   calcula esa línea.
8. Gastos operativos, depreciación, impuestos y variable del groomer: «no configurado»; la utilidad es «parcial».

## Definiciones

- **Servicio del mes:** orden de servicio (sin orden padre) en estado `done` cuyo día de término (en Lima;
  `completed_at`, o `updated_at` si faltara) cae en el mes. Es el mismo día con el que Inventario registra el consumo
  y se toma la tarifa del groomer.
- **Ajuste por peso:** orden de ajuste **pagada** de un servicio del mes; suma a la venta de ese servicio (como el
  Dashboard). Un ajuste sin pagar va a «por cobrar».
- **Ventas sin IGV:** suma de las ventas sin IGV de los servicios y ajustes del mes (decisión 2). También se
  informan el total con IGV y los descuentos de campaña (ya restados en el total).
- **Por cobrar:** servicios del mes sin pagar y ajustes sin pagar de esos servicios.
- **Insumos consumidos:** movimientos `consumption` vigentes con fecha en el mes (costo = cantidad × costo por unidad
  registrado). Las compras no son costo: entran al stock y salen como consumo.
- **Mermas y diferencias de inventario:** movimientos `waste` y ajustes de salida vigentes con fecha en el mes. Los
  ajustes de entrada se informan aparte y no restan (pregunta abierta).
- **Mano de obra (receta):** por servicio, minutos de las celdas de su receta × tarifa del día del servicio (la del
  groomer o, si no tiene registro, la de referencia). Un servicio sin receta (base o algún adicional) o sin tarifa no
  suma y se cuenta como «sin receta».
- **Mano de obra no utilizada:** por cada groomer con registro de costo vigente al último día del período: costo
  mensual − mano de obra asignada a sus servicios del mes (puede ser negativa si trabajó más de lo pagado).
- **Comisión de la pasarela:** total cobrado × % del medio (tarjeta o Yape) de los servicios y ajustes pagados del
  mes. El efectivo no paga comisión.
- **Margen bruto:** ventas sin IGV − costo del servicio (insumos + mermas + mano de obra + no utilizada + comisión).
- **Utilidad (parcial):** margen bruto − gastos operativos − depreciación − impuestos; mientras esas líneas no estén
  configuradas, es igual al margen bruto y se marca parcial.
- **Cobrado pendiente de reprogramar o reembolsar:** órdenes de servicio canceladas y pagadas cuya última
  actualización (la cancelación) cae en el mes, como en el Dashboard.

## Período (dueño, 2026-11-26)

- Se consulta un **mes**, **hoy** o un **rango de fechas** (ambos días incluidos, hasta 366 días). Ventas, costos,
  movimientos y canceladas se filtran por día igual que en un mes.
- El costo del groomer de un rango es el costo mensual de cada mes que cubre × días cubiertos ÷ días de ese mes (la
  misma regla que el mes en curso). Un mes cerrado completo va entero.

## Comportamiento esperado

1. **Dado** un mes, **cuando** el admin pide el P&L, **entonces** recibe cada línea con su importe, su estado
   (`real`, `estimated`, `partial` o `not_configured`) y las órdenes o movimientos que la forman.
2. **Dado** un servicio terminado el 01/12 y contratado el 30/11, **entonces** su venta y sus costos están en
   diciembre.
3. **Dada** una orden con boleta, **entonces** su venta sin IGV es la de la boleta; sin boleta, la calculada, y la
   línea indica cuántas faltan.
4. **Dada** una receta actualizada después del servicio, **entonces** la mano de obra del servicio usa la versión
   que regía ese día.
5. **Dado** el mes en curso, **entonces** el P&L dice «mes abierto» y el costo mensual del groomer se prorratea por
   los días transcurridos.
6. **Dada** una compra del mes, **entonces** no aparece como costo; solo sus consumos.

## Criterios de aceptación

- [x] `GET /admin/finance/pnl?month=YYYY-MM` o `?date_from&date_to`, solo lectura, sin migración (C-56, C-58).
- [x] Parámetros generales: «Comisión de Culqi con tarjeta (%)» y «Comisión de Culqi con Yape (%)».
- [x] Tests de período, venta sin IGV, receta por fecha, mano de obra no utilizada, mermas y comisión.
- [x] Admin: «Cierre mensual / P&L» con datos reales y detalle por línea (sin «Demo»).
- [ ] Probado contra la base real (montos de un mes conocido).

## Supuestos (revisables)

- El % de comisión se ingresa **sin IGV**, como lo publica Culqi; el IGV de la comisión no es costo (crédito
  fiscal). Confirmar con el contador.
- Mes en curso: costo mensual del groomer × días transcurridos ÷ días del mes.
- Si un groomer cambió de costo a mitad de mes, se usa el registro vigente al último día del período.
- Si un servicio es anterior a la primera versión de su receta, se usa la primera versión.
- Cuenta el costo mensual de los groomers activos o que hicieron servicios en el mes.

## Preguntas abiertas

- [ ] ¿Los ajustes de entrada (sobrantes en el conteo) restan del costo como diferencia de inventario?
- [ ] ¿El IGV de la comisión de Culqi es crédito fiscal (no costo)? Confirmar con el contador.
