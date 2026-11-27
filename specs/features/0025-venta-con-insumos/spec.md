---
feature: 0025-venta-con-insumos
estado: in-progress   # draft | approved | in-progress | done | abandoned
repos: [paku-backend, paku-web]
creado: 2026-11-26
---

# No vender un servicio sin insumos

## Problema

El stock de un insumo puede quedar negativo: el consumo se registra al terminar el servicio aunque no alcance
(feature 0009). Nada impide vender un servicio para el que no hay insumos.

## Objetivo

Un servicio o adicional no se vende si algún insumo de su receta no alcanza, descontando lo ya vendido que aún no se
realiza. La web lo muestra «no disponible por ahora» y el backend no cobra.

## Reglas (dueño, 2026-11-26)

1. **No disponible** = algún insumo de la receta (celda del pelaje y peso de la mascota, como el precio) no alcanza.
   Un servicio o adicional **sin receta** (o sin celda para esa mascota) se sigue vendiendo.
2. **Disponible = stock − consumo comprometido.** Comprometido: el de las recetas vigentes de las órdenes de servicio
   **pagadas o en verificación** que no están realizadas ni canceladas (peso declarado de la mascota).
3. Un **adicional** se evalúa junto con su servicio (base + adicional deben alcanzar a la vez).
4. **Al pagar** (`POST /orders/{id}/pay`), antes de llamar a Culqi, se revisa la orden completa (servicio y
   adicionales, sin contar su propio consumo). Si no alcanza: 409 `OUT_OF_STOCK` y **no hay cobro**.
5. Al realizarse un servicio el consumo se registra igual, aunque el stock quede negativo (el servicio ya se hizo).
6. Si la revisión misma falla (error técnico), no bloquea la venta ni el cobro: se registra en el log.

## Fuera de alcance

- App de clientes (paku-vet-dev): no muestra «no disponible»; la protege el rechazo al pagar.
- `POST /orders/{id}/confirm-payment` (el cobro ya ocurrió en Culqi) y el efectivo (se confirma al entregar).
- Bloquear salidas manuales de inventario que dejen stock negativo.
- Reservar insumos en el carrito (2 h) antes de pagar.

## Comportamiento esperado

1. **Dados** 500 ml de shampoo, 100 ml por baño y 4 baños pagados sin realizar, **entonces** se puede vender 1 baño
   más; con 5, el baño sale «no disponible» («Falta Shampoo»).
2. **Dada** una compra de shampoo, **entonces** el baño vuelve a estar disponible.
3. **Dado** un adicional cuyo insumo no alcanza junto con el del servicio, **entonces** el adicional sale no disponible.
4. **Dado** que otro cliente pagó primero el último stock, **cuando** el cliente paga, **entonces** 409
   `OUT_OF_STOCK` con el insumo que falta y sin cobro.

## Contrato

- `GET /store/categories/{slug}/products?pet_id=…` y `GET /store/products/{id}?pet_id=…`: cada servicio y cada
  adicional traen `stock_available` (bool, true sin mascota) y `stock_message` («Falta Shampoo»). Compatible.
- `POST /orders/{id}/pay`: nuevo 409 `{"code": "OUT_OF_STOCK", "message", "supplies"}`. C-57.

## Criterios de aceptación

- [x] Disponibilidad en la tienda y rechazo al pagar, con tests. Sin migración.
- [x] Web: servicio y adicionales «No disponible por ahora», sin poder elegirlos; mensaje del 409 al pagar.

## Supuestos (revisables)

- El consumo comprometido usa las recetas vigentes y el peso declarado (el medido se conoce al hacer el servicio).
- Lo comprometido incluye las órdenes saltadas (se reprograman).
