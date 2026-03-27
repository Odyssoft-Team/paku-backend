# Flujo de Compra de un Servicio — Paku Backend

> **Audiencia:** Equipo frontend / mobile  
> **Fecha:** 27 de marzo de 2026  
> **Base URL:** `https://api.paku.app` (o `http://localhost:8000` en local)

---

## Resumen visual del flujo

```
[1] Seleccionar mascota
        ↓
[2] Seleccionar servicio + addons (con fecha y hora)
        ↓
[3] Registrar / seleccionar dirección de entrega
        ↓
[4] Verificar disponibilidad del día (booking)
        ↓
[5] Agregar al carrito → POST /cart/items
        ↓
[6] Revisar carrito (puede abandonarse — persiste 2 h)
        ↓
[7] Validar carrito → POST /cart/{id}/validate
        ↓
[8] Checkout → POST /cart/{id}/checkout
        ↓
[9] Crear orden → POST /orders   ← se necesita address_id
        ↓
[10] Orden en estado "created" — espera asignación de ally
        ↓
[11] Admin asigna ally y fecha → la orden avanza a través de estados
```

---

## Prerrequisitos

El usuario debe estar **autenticado** (JWT en header `Authorization: Bearer <token>`) y tener el **perfil completo** antes de poder crear un carrito o un hold.

```
POST /auth/register   → registrar usuario
POST /auth/login      → obtener access_token + refresh_token
GET  /auth/me         → verificar perfil
```

---

## Paso 1 — Seleccionar la mascota

El usuario elige a cuál de sus mascotas va dirigido el servicio.

### Listar mascotas del usuario
```
GET /pets
```

**Response**
```json
[
  {
    "id": "uuid-mascota",
    "name": "Firulais",
    "species": "dog",
    "breed": "Labrador",
    "size": "large",
    "weight_kg": 28.5,
    ...
  }
]
```

> Si el usuario no tiene mascotas, debe crearla primero:
> ```
> POST /pets
> Body: { "name": "Firulais", "species": "dog", "breed": "Labrador", ... }
> ```

---

## Paso 2 — Seleccionar servicio, addons, fecha y hora

El usuario navega el catálogo de servicios y elige uno base + addons opcionales, junto con la fecha y hora deseada.

### Listar servicios disponibles
```
GET /store/services
GET /store/services?category_id=<uuid>   ← filtrar por categoría
GET /store/categories                    ← para el menú de filtros
```

**Response de un servicio**
```json
{
  "id": "uuid-servicio",
  "name": "Baño completo clásico",
  "description": "...",
  "base_price": 65.00,
  "category_id": "uuid-categoria",
  "addons": [
    { "id": "uuid-addon", "name": "Corte de uñas", "price": 15.00 },
    { "id": "uuid-addon-2", "name": "Limpieza dental", "price": 20.00 }
  ]
}
```

> **El usuario selecciona:** 1 servicio base + 0 o más addons + fecha (`YYYY-MM-DD`) + hora (`HH:MM`).

---

## Paso 3 — Seleccionar dirección de entrega

El servicio se presta **a domicilio**, por lo que se necesita una dirección válida dentro de un distrito activo de cobertura.

### Listar distritos con cobertura activa
```
GET /geo/districts
```

### Listar direcciones guardadas del usuario
```
GET /addresses
```

### Crear una nueva dirección (si no tiene ninguna)
```
POST /addresses
```
```json
{
  "district_id": "san-isidro",
  "address_line": "Av. Javier Prado 1234",
  "lat": -12.0906,
  "lng": -77.0553,
  "reference": "Edificio azul, piso 3",
  "building_number": "1234",
  "apartment_number": "301",
  "label": "Casa",
  "type": "home",
  "is_default": true
}
```

**Response**
```json
{
  "id": "uuid-direccion",
  "district_id": "san-isidro",
  "address_line": "Av. Javier Prado 1234",
  "lat": -12.0906,
  "lng": -77.0553,
  "reference": "Edificio azul, piso 3",
  "is_default": true,
  "created_at": "2026-03-27T12:00:00Z"
}
```

> **Reglas:**
> - La primera dirección creada queda como **default** automáticamente.
> - Si `is_default: true`, reemplaza la dirección default anterior.
> - El distrito debe estar activo en el sistema geo; si no, devuelve `422`.

---

## Paso 4 — Verificar disponibilidad del día (booking)

Antes de agregar al carrito, se recomienda verificar que el día elegido tiene cupos disponibles para el servicio seleccionado.

```
GET /availability?service_id=<uuid>&date_from=<YYYY-MM-DD>&days=7
```

**Response**
```json
[
  {
    "id": "uuid-slot",
    "service_id": "uuid-servicio",
    "date": "2026-04-01",
    "capacity": 10,
    "booked": 3,
    "available": 7,
    "is_active": true
  },
  {
    "id": "uuid-slot-2",
    "service_id": "uuid-servicio",
    "date": "2026-04-02",
    "capacity": 10,
    "booked": 10,
    "available": 0,
    "is_active": true
  }
]
```

| Campo | Descripción |
|---|---|
| `capacity` | Cupos totales del día |
| `booked` | Cupos ya reservados (holds activos + confirmados) |
| `available` | Cupos libres = `capacity - booked` |
| `is_active` | `false` = slot desactivado por admin, no acepta reservas |

> - Solo aparecen slots con `is_active: true`.
> - Si un día no aparece en la lista, **no tiene disponibilidad** (el admin no creó el slot o lo desactivó).
> - Si `available == 0`, el día está lleno → mostrar como no disponible en el calendario del frontend.

---

## Paso 5 — Agregar al carrito

Con todo seleccionado (mascota, servicio, addons, fecha, hora), se crea el carrito con todos los items de una sola llamada.

```
POST /cart/items
```

```json
{
  "items": [
    {
      "kind": "service_base",
      "ref_id": "uuid-servicio",
      "name": "Baño completo clásico",
      "qty": 1,
      "unit_price": 65.00,
      "meta": {
        "pet_id": "uuid-mascota",
        "scheduled_date": "2026-04-01",
        "scheduled_time": "10:00"
      }
    },
    {
      "kind": "service_addon",
      "ref_id": "uuid-addon",
      "name": "Corte de uñas",
      "qty": 1,
      "unit_price": 15.00,
      "meta": {
        "base_service_id": "uuid-servicio"
      }
    }
  ]
}
```

**Response**
```json
{
  "cart": {
    "id": "uuid-carrito",
    "user_id": "uuid-usuario",
    "status": "active",
    "expires_at": "2026-03-27T14:00:00Z",
    "created_at": "2026-03-27T12:00:00Z",
    "updated_at": "2026-03-27T12:00:00Z"
  },
  "items": [
    {
      "id": "uuid-item-1",
      "cart_id": "uuid-carrito",
      "kind": "service_base",
      "ref_id": "uuid-servicio",
      "name": "Baño completo clásico",
      "qty": 1,
      "unit_price": 65.00,
      "meta": {
        "pet_id": "uuid-mascota",
        "scheduled_date": "2026-04-01",
        "scheduled_time": "10:00"
      }
    },
    {
      "id": "uuid-item-2",
      "cart_id": "uuid-carrito",
      "kind": "service_addon",
      "ref_id": "uuid-addon",
      "name": "Corte de uñas",
      "qty": 1,
      "unit_price": 15.00,
      "meta": { "base_service_id": "uuid-servicio" }
    }
  ]
}
```

### Reglas de validación del carrito

| Regla | Detalle |
|---|---|
| Solo 1 `service_base` | No se puede tener dos servicios base en el mismo carrito |
| `meta.pet_id` requerido | El servicio base debe indicar a cuál mascota va dirigido |
| `meta.scheduled_date` requerido | Formato `YYYY-MM-DD` |
| `meta.scheduled_time` requerido | Formato `HH:MM` |
| Addons referencian al base | `meta.base_service_id` debe coincidir con el `ref_id` del `service_base` |

### Kinds de items

| Kind | Descripción |
|---|---|
| `service_base` | Servicio principal (baño, corte, etc.) |
| `service_addon` | Adicional al servicio base |
| `product` | Producto físico (shampoo, accesorio, etc.) |

---

## Paso 6 — Carrito guardado (abandono y recuperación)

El carrito **persiste en base de datos** por **2 horas** desde su creación.

### Si el usuario abandona la app y vuelve:
```
GET /cart
```

Este endpoint devuelve el **carrito activo** del usuario. Si el carrito expiró (pasaron más de 2 horas), se crea uno nuevo vacío automáticamente.

```json
{
  "cart": {
    "id": "uuid-carrito",
    "status": "active",
    "expires_at": "2026-03-27T14:00:00Z",
    ...
  },
  "items": [ ... ]
}
```

> **Frontend:** guardar el `cart.id` en estado local no es estrictamente necesario; `GET /cart` siempre devuelve el activo. Sin embargo, puede cachearse para evitar llamadas innecesarias.

### Estados del carrito

| Status | Descripción |
|---|---|
| `active` | En uso, acepta modificaciones |
| `checked_out` | Finalizado, listo para crear la orden |
| `expired` | TTL vencido (> 2 horas sin interacción) |
| `cancelled` | Cancelado manualmente |

### Modificar el carrito antes de hacer checkout

| Acción | Endpoint |
|---|---|
| Reemplazar todos los items | `PUT /cart/{id}/items` con nuevo array completo |
| Eliminar un item | `DELETE /cart/{id}/items/{item_id}` |
| Ver el carrito por ID | `GET /cart/{id}` |

---

## Paso 7 — Validar el carrito

Antes de proceder al pago, el frontend puede validar el carrito para mostrar errores al usuario sin aún procesar nada.

```
POST /cart/{id}/validate
```

**Response (válido)**
```json
{
  "valid": true,
  "errors": [],
  "warnings": [],
  "total": 80.00,
  "currency": "PEN"
}
```

**Response (inválido)**
```json
{
  "valid": false,
  "errors": [
    "Service 'Baño completo clásico' requires 'scheduled_date' in meta (format: YYYY-MM-DD)"
  ],
  "warnings": [],
  "total": 0.0,
  "currency": "PEN"
}
```

> Si `valid: false`, mostrar los errores al usuario y no avanzar al checkout.

---

## Paso 8 — Checkout del carrito

Cuando el usuario confirma el pedido y procede al pago, se hace el checkout del carrito. Esto **valida automáticamente** el carrito internamente y marca su estado como `checked_out`.

```
POST /cart/{id}/checkout
```

**Response (exitoso)**
```json
{
  "cart_id": "uuid-carrito",
  "status": "checked_out",
  "total": 80.00,
  "currency": "PEN",
  "items": [ ... ]
}
```

**Response (fallido — carrito inválido)**
```json
{
  "detail": {
    "message": "Cart validation failed",
    "errors": ["Cart must have at least one base service"],
    "warnings": []
  }
}
```

> **Nota:** El checkout NO procesa el pago. El flujo de pago es externo (gateway de pagos). Una vez el pago se aprueba, el frontend llama al Paso 9.

---

## Paso 9 — Crear la orden

Con el carrito en estado `checked_out` y el pago aprobado, se crea la orden definitiva. Aquí se vincula la **dirección de entrega**.

```
POST /orders
```

```json
{
  "cart_id": "uuid-carrito",
  "address_id": "uuid-direccion"
}
```

> Si se omite `address_id`, el sistema usa la **dirección default** del usuario.  
> Si no hay dirección default configurada, devuelve `422`.

**Response**
```json
{
  "id": "uuid-orden",
  "user_id": "uuid-usuario",
  "status": "created",
  "items_snapshot": [
    {
      "kind": "service_base",
      "ref_id": "uuid-servicio",
      "name": "Baño completo clásico",
      "qty": 1,
      "unit_price": 65.00,
      "meta": {
        "pet_id": "uuid-mascota",
        "scheduled_date": "2026-04-01",
        "scheduled_time": "10:00"
      }
    },
    {
      "kind": "service_addon",
      "name": "Corte de uñas",
      "qty": 1,
      "unit_price": 15.00
    }
  ],
  "total_snapshot": 80.00,
  "currency": "PEN",
  "delivery_address_snapshot": {
    "district_id": "san-isidro",
    "address_line": "Av. Javier Prado 1234",
    "lat": -12.0906,
    "lng": -77.0553,
    "reference": "Edificio azul, piso 3"
  },
  "ally_id": null,
  "scheduled_at": null,
  "hold_id": null,
  "created_at": "2026-03-27T12:30:00Z",
  "updated_at": "2026-03-27T12:30:00Z"
}
```

> **Importante:** `items_snapshot` y `delivery_address_snapshot` son **capturas inmutables** al momento de crear la orden. Si el usuario luego cambia su dirección, la orden no se ve afectada.

> **Notificación automática:** Al crear la orden, el sistema envía automáticamente una notificación push al usuario con el mensaje _"Tu pedido fue creado y está en preparación."_

---

## Paso 10 — Estados de la orden post-creación

Una vez creada la orden, el admin la gestiona asignando un **ally** (groomer) y programando la fecha/hora de ejecución.

### Flujo de estados de la orden

```
created → on_the_way → in_service → done
                 ↘
              cancelled  (solo admin, desde created / on_the_way)
```

| Estado | Actor | Descripción |
|---|---|---|
| `created` | Sistema | Orden creada, pendiente de asignación |
| `on_the_way` | Ally | Ally salió hacia el domicilio |
| `in_service` | Ally | Ally llegó, servicio en curso |
| `done` | Ally | Servicio finalizado |
| `cancelled` | Admin | Cancelado antes de iniciar el servicio |

### El usuario puede consultar sus órdenes
```
GET /orders            → lista todas sus órdenes
GET /orders/{id}       → detalle de una orden específica
```

---

## Resumen de endpoints del flujo completo

| # | Acción | Método | Endpoint |
|---|---|---|---|
| 1 | Listar mascotas | `GET` | `/pets` |
| 1 | Crear mascota | `POST` | `/pets` |
| 2 | Listar categorías | `GET` | `/store/categories` |
| 2 | Listar servicios | `GET` | `/store/services` |
| 3 | Listar distritos activos | `GET` | `/geo/districts` |
| 3 | Listar direcciones | `GET` | `/addresses` |
| 3 | Crear dirección | `POST` | `/addresses` |
| 4 | Verificar disponibilidad | `GET` | `/availability` |
| 5 | Crear carrito con items | `POST` | `/cart/items` |
| 6 | Recuperar carrito activo | `GET` | `/cart` |
| 6 | Reemplazar items del carrito | `PUT` | `/cart/{id}/items` |
| 6 | Eliminar item del carrito | `DELETE` | `/cart/{id}/items/{item_id}` |
| 7 | Validar carrito | `POST` | `/cart/{id}/validate` |
| 8 | Checkout del carrito | `POST` | `/cart/{id}/checkout` |
| 9 | Crear orden | `POST` | `/orders` |
| 10 | Listar mis órdenes | `GET` | `/orders` |
| 10 | Ver detalle de orden | `GET` | `/orders/{id}` |

---

## Diagrama de estados del carrito

```
        ┌─────────────────────────────────┐
        │          CARRITO ACTIVO         │
        │   status: active                │
        │   TTL: 2 horas desde creación   │
        └───────────┬─────────────────────┘
                    │
        ┌───────────▼──────────┐
        │  Usuario abandona    │  → El carrito sigue en BD
        │  GET /cart recupera  │    hasta que expire el TTL
        └───────────┬──────────┘
                    │
        ┌───────────▼──────────────────────────┐
        │  POST /cart/{id}/checkout            │
        │  → status: checked_out               │
        └───────────┬──────────────────────────┘
                    │
        ┌───────────▼──────────────────────────┐
        │  POST /orders                        │
        │  → Orden creada (status: created)    │
        └──────────────────────────────────────┘

  Si el TTL expira sin checkout:
        status: expired → GET /cart crea uno nuevo vacío
```

---

## Notas importantes para el frontend

1. **Guardar el `cart.id`**: no es obligatorio pero evita llamadas extra. Siempre se puede recuperar con `GET /cart`.

2. **El checkout no procesa el pago**: el frontend debe integrar el gateway de pagos (ej. Culqi, Stripe) y, una vez aprobado el pago, llamar a `POST /orders`.

3. **La dirección va en la orden, no en el carrito**: el carrito solo tiene los items. La dirección se pasa al crear la orden en `POST /orders`.

4. **`items_snapshot` es inmutable**: una vez creada la orden, los datos de precios e items quedan fijos, aunque el catálogo de servicios cambie después.

5. **Notificaciones push automáticas**: el backend envía push al usuario en `created`, `on_the_way`, `in_service`, `done` y `cancelled`. El frontend solo necesita mostrarlas.

6. **Disponibilidad**: el frontend debe verificar `available > 0` antes de mostrar un día como seleccionable en el calendario. Si `available == 0` o el día no aparece en `/availability`, debe mostrarse como bloqueado.
