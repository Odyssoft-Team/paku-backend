---
feature: 0003-saldo-por-peso
plan: ./plan.md
---

# Tasks — Saldo por diferencia de peso

## Backend
- [x] Peso declarado en `meta.pet_weight_kg` al cotizar el servicio base
- [x] Migración Alembic: `measured_weight_kg`, `measured_weight_at`, `extra_charge`, `adjustment_order_id` (`5e6f7a8b9c0d`, sin ejecutar)
- [x] Modelo, repo y `OrderOut` con los campos nuevos (+ `declared_weight_kg`)
- [x] Vista del groomer con peso declarado
- [x] `weight_locked` en `PetOut` + 409 `PET_WEIGHT_LOCKED` para el dueño
- [x] Peso medido en la orden + `extra_charge` + avisos a cliente y admins
- [x] `create-adjustment`: solo admin, monto guardado, una vez por orden
- [x] `GET /orders/pending-balance`
- [x] 409 `PENDING_BALANCE` en `POST /holds` y `POST /orders`
- [x] Tests pytest (`tests/unit/test_weight_balance.py`, `test_orders_adjustment_access.py`, `test_cart_pricing.py`)
- [x] Actualizar `docs/cambios-api-para-front.md` (C-24) y `docs/pendientes-pagos-culqi.md` (punto 10)

## paku-admin
- [x] Tipos y servicios con los campos nuevos
- [x] Badges en la lista de órdenes
- [x] Detalle: pesos, monto extra, generar cobro, estado del ajuste

## paku-web
- [x] Tipos y capa API (`pending-balance`, campos nuevos, errores 409)
- [x] Peso bloqueado en mascotas
- [x] Aviso de saldo y pago del ajuste
- [x] Reserva bloqueada con saldo
- [x] Ajustes en "Mis pedidos"

## App del groomer (dev front)
- [ ] Ver `docs/guia-groomer-saldo-por-peso.md`

## Cierre
- [ ] Ejecutar la migración en desarrollo y probar el flujo completo
- [ ] Spec a estado `done`
- [ ] Índice de `features/README.md` actualizado
- [ ] Commits referencian `specs/features/0003-saldo-por-peso/`
