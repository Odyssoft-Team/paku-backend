---
feature: 0014-dashboard-gerencial
estado: in-progress   # draft | approved | in-progress | done | abandoned
repos: [paku-backend, paku-admin]
creado: 2026-10-29
---

# Dashboard gerencial v1 (solo lectura)

## Problema

El gerente pidió un dashboard con lo esencial del mes. Hoy esos datos existen (órdenes, cupos, tiempos,
clientes y costeo por orden), pero están repartidos en varias pantallas y nadie los compara con el mes anterior.

## Objetivo

Una pantalla con las cifras del mes al día, comparadas con el mismo corte del mes anterior. Cada cifra dice si
es **real**, **estimada** o **sin datos**.

## Fuera de alcance

- Meta mensual, conversión a reserva pagada, adquisición por canal, reclamos, cobros por fecha de abono o
  liquidación de la pasarela: no se registran o no tienen regla definida.
- Porcentaje de llegadas "a tiempo": falta definir la tolerancia (ver preguntas).
- Reglas nuevas de negocio: todo sale de reglas que ya existen.
- Escribir datos. Es solo lectura, sin migración.

## Definiciones

- **Día de un servicio:** cuando terminó, en hora de Lima. Si no hay, el programado y si no, la creación
  (la misma regla que Clientes, feature 0011).
- **Mes al día:** del día 1 al día de corte (hoy por defecto), ambos incluidos. **Mes anterior:** del día 1 al
  mismo día del mes anterior. Si ese mes es más corto, se usa su último día (31 de marzo → 28 o 29 de febrero).
- **Servicio realizado:** una orden de servicio terminada (`done`, sin orden padre).
- **Ingreso por servicios realizados:** el total neto de la orden (con el descuento de campaña ya restado) más
  sus cargos extra pagados. Cuenta el día del servicio, no el del cobro. **Por cobrar:** la parte de esos
  servicios que no está pagada.
- **Cancelación:** una orden de servicio cancelada que estaba pagada o en verificación. Su día es la última
  actualización de la orden (cancelar es definitivo).
- **Servicio programado:** un "servicio solicitado" (feature 0003): orden de servicio pagada o en
  verificación, no terminada ni cancelada. Su día es el de la reserva o, si no hay, el programado.
- **Ocupación:** cupos tomados ÷ capacidad de los días activos del período, sumando todos los servicios.
  Los cupos tomados incluyen los carritos vigentes (2 h), como en Fechas.
- **Cliente nuevo del período:** su primer servicio realizado cae en el período. **Recompra:** tuvo un
  servicio en el período y uno anterior al período.
- **Tiempos:** traslado = salida → llegada; servicio = llegada → fin (los de la pantalla Tiempos). **Llegada
  respecto a la hora programada:** llegada − hora programada, en minutos (negativo = llegó antes).
- **Contribución estimada:** ingreso − insumos − mano de obra estimada, con el costeo por orden que ya existe
  (feature 0009 y 0012). Insumos: los registrados o, si no hay, los de la receta. Mano de obra: minutos de la
  receta × costo por hora del groomer (o de referencia).
  Una orden sin receta para el servicio o algún adicional, o sin costo por hora, queda **sin datos** y no suma.

## Calidad de cada cifra

- **real:** sale directo de los registros.
- **estimado:** usa recetas o tarifas (contribución). Trae cuántas órdenes se pudieron estimar del total.
- **sin datos:** no hay nada que medir (sin cupos, sin tiempos registrados, ninguna orden costeable).
  El valor viene vacío, nunca 0.

## Comportamiento esperado

1. **Dado** un corte, **cuando** el admin abre el dashboard, **entonces** ve cada cifra del mes al día, la del
   mes anterior al mismo corte, la diferencia y su calidad.
2. **Dado** que hay órdenes terminadas sin receta, **entonces** la contribución dice "N de M órdenes estimadas"
   y no inventa el resto.
3. **Dado** un período sin cupos configurados, **entonces** la ocupación sale "sin datos".
4. **Dados** los próximos 7 días desde el corte, **entonces** ve por día: capacidad, cupos tomados, ocupación y
   servicios programados.
5. **Dado** el mes en curso, **entonces** ve los servicios programados que faltan realizar hasta fin de mes.

## Criterios de aceptación

- [ ] Un endpoint de admin con todas las cifras, el período y los próximos 7 días.
- [ ] Sin migración; tests de las reglas de período, calidad y cifras.
- [ ] Pantalla en el admin sin datos de ejemplo.

## Impacto en el dominio

Módulo nuevo `dashboard`, solo lectura sobre `orders`, `booking`, `inventory` y `groomer_costs`.

## Supuestos (decididos sin preguntar, revisables)

- La contribución usa el ingreso con los cargos extra pagados. El costeo de una orden suelta (Inventario)
  compara solo con el total de la orden; por eso pueden diferir cuando hubo cargo extra.
- Las cancelaciones solo cuentan reservas pagadas o en verificación. Las órdenes que nunca se pagaron son
  carritos abandonados, no cancelaciones.

## Preguntas abiertas

- [ ] ¿Desde cuántos minutos de retraso una llegada cuenta como tarde? Con eso se agrega "% a tiempo".
- [ ] ¿Meta mensual de ingresos o servicios? Se podría guardar en Parámetros generales.
