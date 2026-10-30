---
feature: 0013-campanas
estado: in-progress   # draft | approved | in-progress | done | abandoned
repos: [paku-backend, paku-admin, paku-monorepo]
creado: 2026-10-29
---

# Campañas y promociones (descuentos por segmento)

## Problema

La maqueta CRM · Campañas registra campañas que en la práctica son descuentos (% o monto fijo, o un
adicional gratis) para un segmento de clientes. El backend no tiene descuentos: el total de la orden es la
suma de precios.

## Objetivo

El admin crea campañas por público; al comprar, el backend aplica la mejor campaña que corresponde y el
total que se cobra ya trae el descuento.

## Fuera de alcance

- Enviar la campaña por push, WhatsApp o correo (los canales se guardan; el envío va con Recordatorios /
  Integraciones).
- Descuento en las órdenes de ajuste (cargo extra por peso).
- Devolución de dinero (no existe todavía en el backend).

## Comportamiento esperado

1. **Dada** una campaña, **entonces** tiene código único, público (segmento de Clientes, `todos`,
   `primera_compra` = sin servicios, `cumpleanos` = la mascota del servicio cumple años este mes), beneficio
   (`percent`, `amount` o `free_addon` por código de adicional), fechas, estado (borrador, activa, pausada,
   terminada), si es automática y límites de uso (por cliente y total).
2. **Dado** el estado mostrado, **entonces** es borrador, programada (antes del inicio), activa, pausada o
   finalizada (pasó la fecha de fin, la terminó el admin o llegó al tope de usos).
3. **Dada** una compra, **entonces** se consideran las campañas **automáticas** activas del público del
   cliente y, si escribió un cupón, esa campaña; se aplica **solo la de mayor descuento**.
4. **Dado** un cupón inválido, **entonces** 422 con el motivo (`CAMPAIGN_CODE_NOT_FOUND`,
   `CAMPAIGN_NOT_ACTIVE`, `CAMPAIGN_ALREADY_USED`, `CAMPAIGN_NOT_FOR_CUSTOMER`, `CAMPAIGN_NOT_APPLICABLE`) y
   la orden no se crea.
5. **Dado** el descuento, **entonces** nunca supera el subtotal; `free_addon` descuenta el precio del
   adicional solo si está en la compra.
6. **Dada** la orden, **entonces** guarda `discount_amount` y `campaign_id`; `total_snapshot` es el neto (lo
   que se cobra por Culqi). Queda un uso de la campaña.
7. **Dado** un uso, **entonces** cuenta para los límites mientras la orden esté pagada o en verificación, o
   pendiente dentro de las 2 h del carrito. Cancelar la orden libera el uso.
8. **Dado** el listado del admin, **entonces** cada campaña trae usos, descuento otorgado y ventas de las
   órdenes pagadas, y cuántos clientes están hoy en su público.
9. **Dado** el carrito, **entonces** `POST /campaigns/quote` muestra el descuento antes de pagar.

## Criterios de aceptación

- [x] `GET /admin/campaigns/config`, `GET` / `POST /admin/campaigns`, `PATCH /admin/campaigns/{id}`.
- [x] `POST /campaigns/quote` y `campaign_code` en `POST /orders`.
- [x] Descuento en la orden, usos y liberación al cancelar.
- [x] Migración (no ejecutada) y tests.

## Impacto en el dominio

Módulo nuevo `campaigns`. `orders`: dos columnas y el total neto. Usa `crm` (segmento) y `store` (código del
adicional). Gasto de Clientes y margen del costeo ya usan el neto.

## Decisiones (dueño, 2026-10-29)

- Automática o con código, según cada campaña.
- No se acumulan: solo la mejor.
- Usos configurables por campaña.
- Público "primera compra" para la bienvenida; el segmento "nuevo" de Clientes no cambia.

## Supuestos (revisables)

- Uso por cliente por defecto: 1 (vacío = sin límite).
- Un 100 % de descuento deja la orden en S/ 0 y Culqi no cobra 0: ver pregunta abierta.
- Cumpleaños = mes de nacimiento de la mascota del servicio (la plantilla dice "válido todo su mes").

## Preguntas abiertas

- [ ] Orden con total S/ 0 (100 % o monto mayor al precio): ¿se marca pagada sin cobrar o se pone un mínimo?
- [ ] ¿El descuento debe mostrarse por línea (servicio y adicional) en el comprobante?
