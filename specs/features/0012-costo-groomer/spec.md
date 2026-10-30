---
feature: 0012-costo-groomer
estado: in-progress   # draft | approved | in-progress | done | abandoned
repos: [paku-backend, paku-admin]
creado: 2026-10-29
---

# Costo del groomer y mano de obra en las recetas

## Problema

Para saber cuánto cuesta cada servicio falta la mano de obra. El dueño pidió registrar el sueldo del groomer y
sus horas, para estimar su costo por hora y usar el tiempo del groomer como un valor más de la receta.

## Objetivo

Cada groomer tiene un costo por hora de servicio, con historial; las recetas tienen minutos por celda y el
costeo suma la mano de obra estimada y la real.

## Fuera de alcance

- Planilla, boletas o cálculo legal de beneficios: los cargos los define el admin.
- Variable del groomer (pago por puntos): sigue como maqueta hasta que el dueño la defina.

## Comportamiento esperado

1. **Dado** un registro de costo (sueldo, cargos de la empresa en % del sueldo o S/ al mes, horas al mes y
   bolsón de manejo y reposo), **entonces**: costo mensual = sueldo + cargos; horas de servicio = horas −
   bolsón; costo por hora de servicio = costo mensual ÷ horas de servicio.
2. **Dado** que el sueldo cambia, **entonces** se registra otro desde una fecha; los servicios anteriores se
   costean con el registro de su fecha. Guardar en una fecha que ya tiene registro lo corrige.
3. **Dada** una orden, **entonces** la mano de obra usa la tarifa del groomer de la orden en la fecha en que
   terminó; si no tiene registro, la de referencia (promedio de los groomers con registro vigente).
4. **Dada** una receta, **entonces** el costo de cada celda incluye minutos × tarifa de referencia.
5. **Dado** el admin, **entonces** ve una explicación de por qué el costo no es solo el sueldo.

## Criterios de aceptación

- [x] `GET /admin/groomer-costs`, `GET` / `POST /admin/groomer-costs/{groomer_id}`.
- [x] Minutos en las celdas de receta y mano de obra estimada y real en el costeo (0009).
- [x] Admin: columna y panel "Costo" en Groomers con la explicación.
- [x] Migración (no ejecutada) y tests.

## Decisiones (dueño, 2026-10-29)

- Se considera todo lo que paga la empresa, con una sección que explique por qué no se muestra solo el sueldo.
- No hay CTS por ahora.
- Las horas se usan para estimar el costo del servicio; el manejo y el reposo van en un bolsón aparte.
- El admin estima los minutos de cada receta y luego se comparan con el tiempo registrado.

## Supuestos (revisables)

- Cargos sugeridos al primer registro: EsSalud 9 % y vacaciones 4,17 % (15 días al año); el admin los cambia.
- Horas por defecto 192 al mes (48 h × 4 semanas).
- Mano de obra real = tiempo llegada → fin (como Tiempos) × la misma tarifa; el traslado real se muestra
  aparte porque ya está repartido en la tarifa (bolsón).

## Preguntas abiertas

- [ ] Confirmar con el contador los cargos según el régimen laboral (micro o pequeña empresa del REMYPE; el
      régimen MYPE tributario es de impuestos y no define CTS ni gratificaciones).
- [ ] Variable del groomer: ¿se suma al costo del servicio cuando se defina?
