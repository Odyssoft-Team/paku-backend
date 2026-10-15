---
feature: 0005-requisitos-servicio
estado: in-progress   # draft | approved | in-progress | done | abandoned
repos: [paku-backend, paku-admin, paku-monorepo]
creado: 2026-10-14
---

# Requisitos del servicio y ocultar lo que no aplica

## Problema

El documento de precios del cliente (`PAKU_Pricing_Logica_App_V1.xlsx`, 2026-10-14) define reglas que hoy
no existen:

- **BR-006:** Express sin agua solo para cachorros de hasta 4 meses y 10 kg de **peso real**. Los tramos
  de peso son fijos (≤5, ≤15…), así que la tabla de precios no puede expresar "hasta 10 kg".
- **BR-010 / BR-011 / BR-012:** mostrar solo los adicionales que aplican al pelaje (deslanado solo en
  doble manto, corte estético en S2/S3/S6…). Hoy se muestran deshabilitados.
- **Hoja 03:** Pug es doble manto corto (S4) y Pekinés doble manto largo (S5); faltan Lagotto Romagnolo,
  Perro de Agua Portugués y Aussiedoodle.

## Objetivo

Cada servicio puede tener peso y edad máximos, editables desde el admin (BR-020: nada fijo en código).
Con una mascota elegida, el cliente solo ve los servicios que puede reservar y los adicionales que
aplican a su pelaje y peso.

## Fuera de alcance

- Selector de pelaje para mestizos y segmento en el perfil (BR-004/005): feature aparte.
- Fotos antes del pago (BR-008), seguridad, cancelaciones, agenda por duración.
- Razas fuera del documento y variantes de pelo: pendientes de respuesta del cliente.

## Comportamiento esperado

1. **Dado** un servicio con peso máximo, **cuando** la mascota pesa más, **entonces** no aparece en el
   listado con mascota y reservarlo da 422 `PET_TOO_HEAVY` con un mensaje para el cliente.
2. **Dado** un servicio con edad máxima, **cuando** la mascota es mayor, **entonces** 422 `PET_TOO_OLD`;
   si no tiene fecha de nacimiento, 422 `PET_AGE_UNKNOWN` (pide agregarla). En ambos casos no se lista.
3. **Dado** un servicio o adicional sin precio para el pelaje y peso de la mascota, **entonces** no
   aparece en el listado / detalle con mascota.
4. **Dado** el recálculo por peso medido (feature 0003), **entonces** los requisitos no se aplican (el
   servicio ya se hizo).
5. **Dado** el simulador del admin, **entonces** omite los servicios que superan el peso máximo.
6. Sin mascota, los listados muestran todo como antes.

## Criterios de aceptación

- [x] `max_weight_kg` / `max_age_months` en productos (admin crea/edita; null = sin límite).
- [x] Cotización y carrito exigen los requisitos; el saldo por peso no.
- [x] Listado y detalle con mascota ocultan lo que no puede comprar.
- [x] Catálogo de razas según la hoja 03 (Pug, Pekinés, 3 razas nuevas) + migración.
- [x] Tests.
