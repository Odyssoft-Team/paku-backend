# Arquitectura actual: Paku Backend, Culqi Python y pagos

**Alcance:** lectura estática del código actual de `paku-backend`, `culqi-python` y las llamadas de `paku-web`. Describe lo implementado, no un diseño propuesto. No se inspeccionó la configuración desplegada de DNS, gateway, firewall o Cloud Run; por tanto, la topología de red efectiva no se puede confirmar solo con estos repositorios.

## Diagrama

```mermaid
flowchart LR
    FE[Frontend paku-web]
    PK[API paku-backend<br/>usuarios, wallet, órdenes y estado de pago]
    PKDB[(Postgres Paku<br/>users, wallet_cards, orders)]
    CP[API culqi-python<br/>adaptador de Culqi]
    CPDB[(Postgres Culqi Python<br/>payment_methods, payments)]
    SEC[Culqi Token API<br/>secure.culqi.com/v2/tokens]
    CA[Culqi API v2<br/>customers, cards, charges]

    FE -->|Login / registro / social| PK
    PK -->|Verifica Firebase ID token<br/>solo login social| FB[Firebase Auth]
    PK -->|Lee / escribe| PKDB
    FE -->|JWT Paku: orders, wallet| PK

    FE -->|PAN, CVV, vencimiento + public key| SEC
    SEC -->|tkn_*| FE

    FE -.->|Código web aún llama POST customers / cards<br/>no alineado con el contrato nuevo| CP
    FE -->|POST /wallet/cards<br/>JWT Paku + token_id| PK
    FE -->|POST /orders, GET /orders/{id}<br/>POST /orders/{id}/pay| PK

    PK -->|POST customers / cards / charges<br/>GET payments<br/>Bearer service API key| CP
    CP -->|lee / escribe| CPDB
    CP -->|Bearer secret key Culqi<br/>RSA/AES si está configurado| CA
    CP -->|POST /customers, /cards, /charges| CA
    CA -->|cus_*, crd_*, chr_*| CP
    CP -->|Resultado charge / pagos para reconciliar| PK
    PK -->|payment_status, culqi_charge_id| PKDB

    classDef risk stroke:#c33,stroke-width:2px,stroke-dasharray:5 5;
    class FE risk;
```

La línea discontinua representa el código de wallet que todavía existe en `paku-web`; no está alineado con el contrato nuevo del backend. El camino implementado en Paku recibe JWT + `token_id` y llama a `culqi-python` servidor-a-servidor. No se modificó el frontend en esta tarea.

## Responsabilidades actuales

| Componente | Responsabilidad observada |
|---|---|
| `paku-backend` | Fuente de verdad de usuario, mapping usuario-proveedor-Customer, propiedad de órdenes, monto/estado de pago y relación de wallet card con el usuario. Orquesta alta de Customer/Card y el cobro principal. |
| `culqi-python` | Adaptador HTTP de Culqi: usa la secret key, opcionalmente cifra solicitudes, valida payloads de proveedor, normaliza errores, crea Customer/Card/Charge y mantiene registros auxiliares de tarjetas y pagos. |
| `paku-web` | Recoge datos de tarjeta y los tokeniza directamente con la public key de Culqi; inicia login, crea órdenes, envía el token o ID de tarjeta y presenta estados. Para guardar tarjetas también llama directamente a rutas de `culqi-python`. |
| Culqi | Procesador externo y autoridad de los objetos `cus_*`, `crd_*`, `tkn_*` y `chr_*`. |

En términos de separación de responsabilidades, la identidad Paku, la autorización de qué wallet/card puede usar un usuario, el precio que se cobra y el estado de la orden pertenecen al dominio de `paku-backend`. La comunicación con endpoints y credenciales específicas de Culqi, el cifrado exigido por el proveedor y la traducción de errores son responsabilidad de `culqi-python`. Esto describe el límite que el código ya intenta establecer, no una propuesta de cambio.

## Endpoints de cara al frontend

Las rutas del backend FastAPI no declaran por sí mismas un prefijo global `/api/v1`; `paku-web` configura una URL base que sí contiene `/paku/api/v1`. El rewrite o gateway entre ambas formas no está en estos repositorios y no se afirma aquí cómo está desplegado.

| Endpoint de Paku | Uso | Autenticación en el backend |
|---|---|---|
| `POST /auth/register` | Registro con email/contraseña | Pública |
| `POST /auth/login` | Login con credenciales Paku; devuelve access/refresh JWT | Pública |
| `POST /auth/refresh` | Renovar access token usando refresh token | Pública, valida el refresh token |
| `POST /auth/social` | Login/registro social: Firebase ID token a Paku, JWT Paku de vuelta | Pública, valida el token Firebase |
| `POST /orders` | Crear orden desde carrito y dirección; Paku calcula/congela el total | JWT Paku |
| `GET /orders`, `GET /orders/{id}` | Consultar órdenes y estado de pago | JWT Paku; consulta de orden limitada al dueño |
| `POST /orders/{id}/pay` | Solicitar cobro de una orden enviando solo `source_id` | JWT Paku; orden limitada al dueño |
| `POST /wallet/cards` | Recibir `token_id`, resolver Customer por usuario autenticado, crear Card y guardarla en wallet | JWT Paku; user ID solo de `CurrentUser` |
| `POST /orders/{id}/confirm-payment` | Confirmación manual/fallback con `culqi_charge_id` | JWT Paku; no es el flujo normal del web |
| `POST /orders/{id}/fail-payment`, `POST /orders/{id}/retry-payment` | Fallback de estado y reintento | JWT Paku |
| `GET /wallet/cards`, `DELETE /wallet/cards/{id}`, `PUT /wallet/cards/{id}/default` | Consultar y administrar las tarjetas del wallet Paku | JWT Paku; operaciones limitadas al usuario autenticado |

`GET /orders/{id}` es la consulta frontend disponible para conocer `payment_status`, `culqi_charge_id` y `payment_method`. Las rutas de administración y de aliados no son endpoints de pago para el usuario final.

## Endpoints de `culqi-python`

El router `/api` aplica `require_service_api_key` a todas sus rutas. Soporta `Authorization: Bearer <service-key>` o `X-API-Key: <service-key>`.

| Endpoint | Propósito actual | Consumidor observado |
|---|---|---|
| `GET /health` | Health check | Infraestructura; no requiere API key |
| `GET /api/config-check` | Diagnóstico no sensible, si `ENABLE_CONFIG_CHECK=true` | No usado por el flujo de pago |
| `GET /api/culqi/test` | Prueba credenciales consultando un charge a Culqi | Operación/smoke test |
| `POST /api/culqi/customers` | Crear un Culqi Customer | `paku-backend` vía cliente interno; el código web antiguo todavía lo llama directamente |
| `POST /api/culqi/cards` | Asociar token a Customer y registrar un PaymentMethod best-effort | `paku-backend` vía cliente interno; el código web antiguo todavía lo llama directamente |
| `POST /api/culqi/charges` | Crear cargo, aplicar idempotencia y registrar Payment best-effort | `paku-backend` |
| `GET /api/culqi/payments?order_id=...` | Leer intentos persistidos para reconciliar una orden | `paku-backend` |

La intención documentada del servicio es que sus rutas `/api` sean internas. El código por sí solo no prueba que el host sea inaccesible desde Internet. Además, `REQUIRE_API_KEY` tiene default `false`; con `false` y sin keys configuradas, `require_service_api_key` deja pasar requests sin credenciales. El ejemplo de entorno usa ese default, mientras que el README indica que producción debe configurarlo en `true`.

## Flujos paso a paso

### 1. Login y autenticación

1. Con email/contraseña, el frontend envía credenciales a `POST /auth/login` de Paku. Paku valida la cuenta local y devuelve access y refresh JWT firmados con HS256.
2. Para login social, el cliente obtiene un Firebase ID token y lo envía a `POST /auth/social`. Paku lo verifica con Firebase Admin, identifica o crea el usuario local y emite sus propios JWT.
3. El frontend usa el JWT Paku como Bearer en las rutas de órdenes y wallet. Culqi no autentica al usuario Paku; el flujo normal de cobro llega a `culqi-python` con una clave de servicio independiente.
4. No hay llamada a Culqi durante login ni un vínculo de Customer Culqi creado en el registro de usuario.

### 2. Crear un Culqi Customer

1. El contrato actual del backend obtiene el `user_id` del JWT y busca `user_payment_customers` por usuario + `provider="culqi"`.
2. Si no hay fila, Paku crea y confirma una fila `provisioning` antes de llamar a `POST /api/culqi/customers` en `culqi-python`.
3. Paku envía datos de perfil con la service API key; no envía datos de tarjeta. `culqi-python` llama a Culqi con su secret key.
4. Si recibe un `cus_*` válido, Paku actualiza la reserva a `ready`. Si el resultado es ambiguo, deja `provisioning`; los retries se bloquean para no crear automáticamente otro Customer.
5. **El cliente web no se migró todavía:** su código conserva el flujo anterior de `localStorage` y la llamada directa. Hasta coordinar el contrato, web y backend no operan el mismo camino de alta.

### 3. Tokenizar tarjeta

1. El formulario de tarjeta envía número, CVV, vencimiento y email directamente desde el navegador a `https://secure.culqi.com/v2/tokens`, con la public key de Culqi.
2. Culqi devuelve un token temporal `tkn_*`. El PAN/CVV no pasa por ninguno de los dos backends según el código.
3. En checkout, el web envía ese `tkn_*` a Paku como `source_id` en `POST /orders/{id}/pay`; Paku lo reenvía a `culqi-python` para el cargo.
4. En el nuevo contrato de Wallet, el token se envía a Paku como `POST /wallet/cards`; Paku lo reenvía a `culqi-python` para asociarlo al Customer resuelto server-side.

### 4. Asociar tarjeta al Culqi Customer

1. Paku obtiene el `customer_id` desde `user_payment_customers`; no lo acepta en el body público.
2. Paku envía `customer_id` y `token_id` a `POST /api/culqi/cards` en `culqi-python` con Bearer de servicio.
3. `culqi-python` llama `POST /cards` a Culqi y devuelve `crd_*` y metadatos visibles de la fuente.
4. En el contrato vigente, Paku no envía `metadata.user_id` a `culqi-python`; su PaymentMethod auxiliar, si persiste, queda con user ID vacío. La fila autoritativa del usuario es `wallet_cards` en Paku.

### 5. Guardar tarjeta en el wallet Paku

1. El frontend nuevo debe enviar solo `token_id`; `CardIn` rechaza campos extra como `user_id` o `customer_id`.
2. Paku determina `user_id` exclusivamente desde `CurrentUser`, crea la Card por servicio interno y persiste `wallet_cards` con metadatos no sensibles. `payment_method_id` conserva el `crd_*` que el checkout usa como source.
3. `CardOut` no expone `culqi_customer_id` ni `culqi_card_id`; mantiene `payment_method_id` por compatibilidad de consumo.
4. **El frontend actual aún usa el request anterior** (metadatos e IDs proporcionados por cliente) y no está alineado con `CardIn`; requiere migración separada antes de desplegar juntos los cambios.
5. `wallet_cards` tiene índice único parcial `(provider, culqi_card_id)` para impedir guardar localmente dos veces el mismo ID externo. El delete de wallet no revoca Card en Culqi.

### 6. Crear orden y realizar pago

1. `BookingWizard` completa carrito y dirección y llama primero `POST /orders`. Paku valida que la dirección pertenece al usuario, toma el total desde el carrito y crea la orden con `payment_status=pending`.
2. En `POST /orders/{id}/pay`, el frontend envía solo `source_id`: `tkn_*`, `ype_*` o `crd_*`. No envía monto, email, moneda ni order ID como parámetros confiables.
3. Paku valida la propiedad de la orden, toma el total/moneda/email del estado que ya conoce, construye antifraud details best-effort desde el perfil y la dirección y llama a `POST /api/culqi/charges` en `culqi-python` con una service API key.
4. La clave de idempotencia enviada por Paku es `order-{order_id}-payment`. `culqi-python` valida el payload, incorpora `order_id` en metadata, aplica idempotencia local, reenvía el cargo a Culqi y persiste el resultado `success` o `failed` best-effort.
5. Ante respuesta exitosa, Paku guarda el `chr_*` y actualiza la orden a `paid`. Ante rechazo definitivo marca `failed`. Ante timeout/respuesta ambigua consulta pagos por `order_id`; si no puede decidir, marca `verifying`.
6. Un job de Paku vuelve a consultar órdenes `verifying` cada cinco minutos. El pago en efectivo tiene una ruta independiente (`confirm-cash-payment`) y no pasa por Culqi.

### 7. Consultar pagos

1. El frontend puede consultar `GET /orders/{id}` o `GET /orders` en Paku con JWT. Esas respuestas incluyen `payment_status`, `culqi_charge_id` y método de pago.
2. `culqi-python` expone `GET /api/culqi/payments?order_id=...`, pero su consumidor en el código es el cliente interno de Paku para reconciliación, tanto inmediata como programada.
3. No hay una ruta de frontend que consulte directamente los registros internos `payments` de Culqi Python en el flujo actual.
4. El estado de negocio autoritativo es el de la orden Paku; el registro de `payments` de Culqi Python sirve como evidencia auxiliar para reconciliar el resultado del proveedor.

## Relaciones entre entidades

```text
Paku user (UUID)
  └── wallet_cards (user_id)
        ├── payment_method_id ── normalmente contiene Culqi crd_*
        └── culqi_card_id ────── crd_*

Paku user (UUID)
  └── user_payment_customers (user_id, provider, status)
        └── customer_id ── Culqi Customer (cus_*)

Culqi Customer (cus_*) ── Culqi Card (crd_*)
                               └── puede usarse como source_id de un charge

Paku order (UUID, user_id, total_snapshot, payment_status)
  └── culqi_charge_id (chr_*)
        └── culqi-python payments (order_id, user_id, amount, source_id, status)
```

No hay una base de datos compartida ni transacción distribuida. Paku persiste mapping y wallet por separado de los objetos Culqi. La reserva `provisioning` evita que retries creen otro Customer automáticamente si el resultado externo o su persistencia local son ambiguos; no permite descubrir el `cus_*` perdido. La reconciliación requiere intervención porque el contrato actual de `culqi-python` no expone búsqueda de Customers. Para Cards, un timeout o fallo de commit puede dejar una Card externa sin fila local; no existe endpoint de búsqueda de Cards ni idempotency key en esa ruta.

## Proxy, duplicación e inconsistencias observadas

1. **`POST /orders/{id}/pay` no es un proxy transparente.** Reenvía el cargo a Culqi Python, pero también autoriza al dueño, fija monto/moneda, deriva datos antifraude, decide estados de pago y dispara notificación. Es una orquestación del dominio Paku.
2. **El proxy de dominio para Customer/Card ya existe en `POST /wallet/cards`, pero el web no está migrado.** El endpoint valida JWT, decide Customer y orquesta tarjeta; `paku-web` conserva llamadas directas antiguas y un payload incompatible. El backend no acepta campos Customer enviados por el cliente.
3. **Autenticación incompatible en las llamadas browser → Culqi Python heredadas.** El código aún presente en `paymentFetch` envía `Authorization: Bearer <JWT Paku>` cuando hay sesión; `require_service_api_key` no valida ese JWT. En configuración que exige API key la llamada obtiene 401; sin keys configuradas y con el requerimiento apagado puede pasar sin autenticar identidad Paku. El nuevo camino del backend usa Bearer de servicio.
4. **Persistencia auxiliar duplicada.** Culqi Python continúa guardando PaymentMethod best-effort; las llamadas internas actuales no pasan `metadata.user_id`, por lo que esa tabla no queda ligada al usuario. El mapping autoritativo está en Paku. El backend tampoco revoca Card externa al borrar localmente.
5. **El frontend antiguo mantiene Customer ID en localStorage.** Esto es código de cliente sin migrar; el endpoint nuevo no lo consume ni lo expone.
6. **Tokenización duplicada al guardar tarjeta.** `usePayments.saveCard` tokeniza una vez, pero llama a `paymentsService.saveCard` con los datos raw, y esa función vuelve a tokenizar. El primer token no se usa para la asociación.
7. **No se comprueba pertenencia de una Card al wallet al cobrar.** `PayOrder` valida que la orden pertenezca al usuario, pero pasa el `source_id` recibido sin verificar que un `crd_*` esté en sus `wallet_cards`. El endpoint de wallet sí filtra por `user_id` para listar/borrar, pero ese control no participa en el cobro.
8. **Idempotencia de reintento potencialmente incompatible.** Paku genera una misma `Idempotency-Key` para todos los intentos de una orden. Culqi Python cachea éxitos y rechazos y responde 409 si esa misma key llega con otro payload. Por ello, tras un rechazo y un `retry-payment` con otro token/source, el nuevo payload puede chocar con la key anterior durante el TTL de 24 horas; el cliente Paku clasifica respuestas no 200/502 como ambiguas y vuelve a consultar el registro previo.
9. **Clasificación de fuente duplicada con distinta granularidad.** Culqi Python distingue `token`, `yape` y `card`; Paku reduce la clasificación a `card` o `yape` para el dominio de órdenes. En particular, un `tkn_*` se registra como `token` en Culqi Python y como método `card` en Paku.
10. **Documentación del web desfasada respecto del flujo ejecutable.** `paku-web/MIGRACION_CULQI.md` describe el cobro desde el navegador directamente a `POST /api/culqi/charges`, creación de orden después del pago y polling de estado. El código actual de `BookingWizard` crea la orden antes de pagar; `ordersService.pay` llama a Paku y Paku cobra servidor-a-servidor. El hook actual no expone el polling descrito por ese documento.
11. **La exposición de red no queda probada por el código.** `culqi-python` usa `http://culqi-backend:8080` como URL interna por default para llamadas desde Paku; el código web antiguo configura host público para Customer/Card. El firewall, gateway, DNS y políticas desplegadas no están verificados. CORS no sustituye autenticación ni aislamiento de red.

### ¿Qué hace de proxy y qué no?

- `culqi-python` es un adaptador/proxy de proveedor para sus rutas Customer, Card y Charge: valida y transforma el payload, llama a Culqi y devuelve el resultado; para cargos añade idempotencia y persistencia auxiliar. `GET /api/culqi/payments` no consulta Culqi: lee su propia base para reconciliación.
- `paku-backend` expone orquestación de Customer/Card por `POST /wallet/cards`, no un proxy genérico. `/orders/{id}/pay` delega el efecto externo y además mantiene decisiones de negocio de pago.
- El código actual de `paku-web` todavía evita ese endpoint para guardar tarjetas y accede directamente a Culqi Python; está pendiente alinear el cliente.

## Referencias de código

- Backend: [router de órdenes](../app/modules/orders/api/router.py), [caso de uso de pago](../app/modules/orders/app/use_cases_impl/payment.py), [cliente Culqi Python compartido](../app/core/culqi_client.py), [router de wallet](../app/modules/wallet/api/router.py), [caso de uso Wallet](../app/modules/wallet/app/use_cases.py), [autenticación Paku](../app/core/auth.py), [montaje de routers](../app/main.py), [reconciliación](../app/core/scheduler.py).
- Culqi Python: `culqi-python/app/api/routes.py`, `culqi-python/app/core/security.py`, `culqi-python/app/api/schemas.py`, `culqi-python/app/providers/culqi/client.py`, `culqi-python/app/db/models.py`.
- Web: `paku-web/lib/api/payments.ts`, `paku-web/hooks/usePayments.ts`, `paku-web/lib/api/orders.ts`, `paku-web/components/booking/BookingWizard.tsx`, `paku-web/components/booking/StepPaymentCulqi.tsx`.