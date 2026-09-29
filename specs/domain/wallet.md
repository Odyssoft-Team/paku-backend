# Dominio — Wallet

> Módulo backend: `app/modules/wallet/`
> Estado del doc: 🟡 parcial
> Última verificación contra código: 2026-09-28

## Qué es

Wallet relaciona los métodos de pago guardados con el usuario Paku. El backend es dueño del vínculo usuario-tarjeta; el proveedor conserva los datos de pago y sus identificadores externos.

## Modelo

- `Card`: tarjeta no sensible guardada en Paku. Pertenece a un `user_id` y contiene proveedor, método, marca, últimos cuatro dígitos, expiración y si es predeterminada.
- `PaymentCustomer`: asociación única por `(user_id, provider)` entre un usuario Paku y el customer ID externo. Durante la provisión tiene `status=provisioning` y `customer_id` nulo; al completarse queda en `ready`. `provider` es extensible; `customer_id` no es un atributo de `users`.
- `culqi_card_id` identifica la tarjeta del proveedor usada para cobros con tarjeta guardada. El token recibido al agregar tarjeta es transitorio y no se persiste.

## Reglas de negocio

- La identidad del usuario para las operaciones del wallet se obtiene del access token Paku.
- Para guardar una tarjeta, Wallet reutiliza o crea el customer del usuario con el proveedor correspondiente, solicita la asociación de la tarjeta y persiste la tarjeta en `wallet_cards`.
- El Customer externo es una relación interna del backend y no lo determina el cliente.
- No se guardan PAN ni CVV en Paku.
- Como máximo existe un Customer por usuario y proveedor.
- Una reserva `provisioning` bloquea nuevos intentos de Customer mientras el resultado anterior no pueda reconciliarse; no se mantiene una transacción SQL abierta durante HTTP.
- `wallet_cards` impide repetir localmente el mismo `(provider, culqi_card_id)` cuando el ID no es nulo.
- Una respuesta externa ambigua no se reintenta automáticamente: el adaptador actual no expone búsqueda de Customers o Cards para reconciliarla.

## Endpoints

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| POST | `/wallet/cards` | user | Recibe un token de proveedor, crea/asocia una tarjeta y la guarda en el wallet autenticado. |
| GET | `/wallet/cards` | user | Lista las tarjetas del usuario autenticado. |
| DELETE | `/wallet/cards/{id}` | user | Elimina una tarjeta del wallet del usuario. |
| PUT | `/wallet/cards/{id}/default` | user | Marca una tarjeta propia como predeterminada. |

Errores de negocio: `404` tarjeta o usuario no encontrado; `409` tarjeta Culqi ya vinculada a otro usuario; `502` rechazo explícito del proveedor; `503` resultado externo o persistencia local que requiere reconciliación.

## Consumidores

- **paku-web**: envía token de tarjeta a `POST /wallet/cards`; usa el identificador de tarjeta devuelto para pagos posteriores. No administra el Customer externo.
- **paku-admin**: sin uso identificado.
- **paku-vet-dev**: sin uso identificado.

## Preguntas abiertas

- [ ] Coordinar el cambio de request de `POST /wallet/cards` con los clientes antes del despliegue.
- [ ] Definir el procedimiento operativo para reconciliar reservas `provisioning` y altas de Card con resultado ambiguo; no hay endpoint de búsqueda en el contrato actual de `culqi-python`.