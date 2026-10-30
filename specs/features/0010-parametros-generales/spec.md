---
feature: 0010-parametros-generales
estado: in-progress   # draft | approved | in-progress | done | abandoned
repos: [paku-backend, paku-admin]
creado: 2026-10-29
---

# Parámetros generales de la empresa

## Problema

El admin tiene una maqueta de "Parámetros generales" (Empresa, Operación, Reservas) que no guarda nada. El
sistema es para una sola empresa, así que basta un valor por parámetro.

## Objetivo

El admin ve y cambia los datos de la empresa y los valores por defecto; el backend valida y guarda, y los
parámetros que el código ya usa se aplican de verdad.

## Fuera de alcance

- Varias empresas o sucursales.
- Cambiar zona horaria, moneda o el tiempo para pagar (ver supuestos).
- Usar el IGV o el horario de atención en cálculos (hoy solo se guardan).

## Comportamiento esperado

1. **Dado** que nadie cambió un parámetro, **entonces** vale su valor por defecto (nombre "Paku", IGV 18 %,
   anticipación 0 días).
2. **Dado** un cambio, **cuando** algún valor no es válido (RUC de 11 dígitos, correo, teléfono, hora
   HH:MM, rangos numéricos, cierre después de apertura), **entonces** 422 `SETTING_INVALID` con la clave y
   no se guarda ninguno.
3. **Dado** `null` (o texto vacío) para un parámetro, **entonces** vuelve a su valor por defecto.
4. **Dados** zona horaria (`America/Lima`), moneda (`PEN`) y tiempo para pagar una reserva (120 min = vida
   del carrito), **entonces** se muestran pero no se pueden cambiar.
5. **Dada** una anticipación mínima de N días, **entonces** el cliente no ve en `GET /availability` los
   días antes de hoy + N y `POST /holds` responde 422 `DATE_TOO_SOON` con `earliest_date`. Con 0 todo
   sigue como antes. No aplica al admin (asignar o reprogramar).

## Criterios de aceptación

- [x] `GET /admin/settings` (valores y secciones) y `PATCH /admin/settings`.
- [x] Validación todo o nada; `null` restaura el valor por defecto.
- [x] Anticipación mínima aplicada en disponibilidad y reserva.
- [x] Migración (no ejecutada) y tests.

## Impacto en el dominio

Módulo nuevo `general_settings`. `booking` lee `booking_min_days_ahead`.

## Supuestos (decididos sin preguntar, revisables)

- **Solo lectura:** zona horaria y moneda (el código asume Lima y soles) y el tiempo para pagar, que hoy es la
  vida del carrito (2 h, `CART_TTL_HOURS`). Volverlo editable cambia cuánto dura el carrito en las apps:
  queda como pedido aparte si se necesita.
- **IGV como porcentaje** (18), referencial para reportes; los precios ya lo incluyen.
- **Horario de atención** como apertura y cierre (HH:MM). No limita reservas ni asignaciones.

## Preguntas abiertas

- [ ] ¿El tiempo para pagar debe ser independiente de la vida del carrito?
- [ ] ¿El horario de atención debe limitar la hora que el admin asigna?
