# 🐾 Flujo Completo: Paku Spa (Servicio de Baño/Grooming)

## 📋 **Flujo Paso a Paso**

### **1️⃣ Usuario selecciona MASCOTA**
```http
GET /pets
Authorization: Bearer {token}
```

**Response:**
```json
[
  {
    "id": "pet-uuid-123",
    "name": "Fido",
    "species": "dog",
    "breed": "Labrador",
    "weight_kg": 15.5,
    "owner_id": "user-uuid"
  }
]
```

**Frontend guarda:**
```javascript
const selectedPet = { id: "pet-uuid-123", name: "Fido", weight_kg: 15.5 }
```

---

### **2️⃣ Usuario selecciona SERVICIO/PLAN**
```http
GET /paku-spa/plans?pet_id=pet-uuid-123
Authorization: Bearer {token}
```

**Response:**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "code": "classic",
    "name": "Clásico",
    "description": "Cuidado esencial para el día a día",
    "price": 80.0,
    "currency": "PEN",
    "includes": [
      "Limpieza completa y segura",
      "Cuidado básico de uñas y oídos",
      "Brillo y frescura inmediata"
    ]
  },
  {
    "id": "550e8400-e29b-41d4-a716-446655440002",
    "code": "premium",
    "name": "Premium",
    "description": "Experiencia spa de alto nivel",
    "price": 89.0,
    "currency": "PEN",
    "includes": [...]
  },
  {
    "id": "550e8400-e29b-41d4-a716-446655440003",
    "code": "express",
    "name": "Express / Seco",
    "description": "Limpieza rápida sin agua",
    "price": 75.0,
    "currency": "PEN",
    "includes": [...]
  }
]
```

**Frontend guarda:**
```javascript
const selectedPlan = {
  id: "550e8400-e29b-41d4-a716-446655440001",
  code: "classic",
  name: "Clásico",
  price: 80.0
}
```

**Notas:**
- ✅ El endpoint valida que `pet_id` existe y pertenece al usuario
- 🔜 En el futuro: el precio se calculará según `weight_kg` de la mascota
- 📌 Por ahora: precio es fijo hardcoded

---

### **3️⃣ Usuario selecciona DIRECCIÓN**
```http
GET /iam/me/addresses
Authorization: Bearer {token}
```

**Response:**
```json
[
  {
    "id": "address-uuid-456",
    "address_line": "Av. Larco 1234",
    "district_id": "district-uuid",
    "reference": "Edificio azul, piso 3",
    "label": "Casa",
    "lat": -12.1234,
    "lng": -77.5678
  }
]
```

**Frontend guarda:**
```javascript
const selectedAddress = {
  id: "address-uuid-456",
  address_line: "Av. Larco 1234",
  district_id: "district-uuid"
}
```

---

### **4️⃣ Usuario selecciona FECHA disponible**
```http
GET /availability?service_id=550e8400-e29b-41d4-a716-446655440001&date_from=2026-02-20&days=7
Authorization: Bearer {token}
```

**Response (MOCK):**
```json
[
  {
    "date": "2026-02-20",
    "capacity": 10,
    "available": 8
  },
  {
    "date": "2026-02-21",
    "capacity": 10,
    "available": 3
  },
  {
    "date": "2026-02-22",
    "capacity": 10,
    "available": 10
  }
]
```

**Frontend:**
- Usuario selecciona: `date = "2026-02-22"`
- Usuario selecciona horario: `time = "10:00"` (de slots disponibles)

**Frontend guarda:**
```javascript
const selectedSchedule = {
  date: "2026-02-22",
  time: "10:00"
}
```

---

### **5️⃣ Agregar al CARRITO**

**Paso 5.1: Obtener/crear carrito activo**
```http
GET /cart
Authorization: Bearer {token}
```

**Response:**
```json
{
  "cart": {
    "id": "cart-uuid-789",
    "user_id": "user-uuid",
    "status": "active",
    "expires_at": "2026-02-20T12:00:00Z"
  },
  "items": []
}
```

**Paso 5.2: Agregar item al carrito**
```http
POST /cart/cart-uuid-789/items
Authorization: Bearer {token}
Content-Type: application/json

{
  "kind": "service_base",
  "ref_id": "550e8400-e29b-41d4-a716-446655440001",
  "name": "Clásico",
  "qty": 1,
  "unit_price": 80.0,
  "meta": {
    "pet_id": "pet-uuid-123",
    "pet_name": "Fido",
    "pet_weight": 15.5,
    "plan_code": "classic",
    "scheduled_date": "2026-02-22",
    "scheduled_time": "10:00",
    "address_id": "address-uuid-456"
  }
}
```

**Response:**
```json
{
  "id": "item-uuid-999",
  "cart_id": "cart-uuid-789",
  "kind": "service_base",
  "ref_id": "550e8400-e29b-41d4-a716-446655440001",
  "name": "Clásico",
  "qty": 1,
  "unit_price": 80.0,
  "meta": {
    "pet_id": "pet-uuid-123",
    "pet_name": "Fido",
    "pet_weight": 15.5,
    "plan_code": "classic",
    "scheduled_date": "2026-02-22",
    "scheduled_time": "10:00",
    "address_id": "address-uuid-456"
  }
}
```

---

### **6️⃣ CHECKOUT del carrito**
```http
POST /cart/cart-uuid-789/checkout
Authorization: Bearer {token}
```

**Response:**
```json
{
  "cart_id": "cart-uuid-789",
  "status": "checked_out",
  "total": 80.0,
  "currency": "PEN",
  "items": [
    {
      "id": "item-uuid-999",
      "name": "Clásico",
      "qty": 1,
      "unit_price": 80.0,
      "meta": {
        "pet_id": "pet-uuid-123",
        "pet_name": "Fido",
        "scheduled_date": "2026-02-22",
        "scheduled_time": "10:00"
      }
    }
  ]
}
```

**Estado del carrito:** `checked_out` (no se puede modificar)

---

### **7️⃣ Crear ORDEN (Pedido confirmado)**
```http
POST /orders
Authorization: Bearer {token}
Content-Type: application/json

{
  "cart_id": "cart-uuid-789",
  "address_id": "address-uuid-456"
}
```

**Response:**
```json
{
  "id": "order-uuid-111",
  "user_id": "user-uuid",
  "status": "pending",
  "items_snapshot": [
    {
      "id": "item-uuid-999",
      "cart_id": "cart-uuid-789",
      "kind": "service_base",
      "ref_id": "550e8400-e29b-41d4-a716-446655440001",
      "name": "Clásico",
      "qty": 1,
      "unit_price": 80.0,
      "meta": {
        "pet_id": "pet-uuid-123",
        "pet_name": "Fido",
        "pet_weight": 15.5,
        "plan_code": "classic",
        "scheduled_date": "2026-02-22",
        "scheduled_time": "10:00",
        "address_id": "address-uuid-456"
      }
    }
  ],
  "total_snapshot": 80.0,
  "currency": "PEN",
  "delivery_address_snapshot": {
    "district_id": "district-uuid",
    "address_line": "Av. Larco 1234",
    "reference": "Edificio azul, piso 3",
    "lat": -12.1234,
    "lng": -77.5678
  },
  "created_at": "2026-02-20T10:30:00Z"
}
```

**Backend automáticamente:**
- ✅ Crea la orden con snapshot de items + dirección
- ✅ Envía notificación al usuario: "Pedido creado"

---

### **8️⃣ Usuario recibe NOTIFICACIÓN**
```http
GET /notifications
Authorization: Bearer {token}
```

**Response:**
```json
[
  {
    "id": "notif-uuid-222",
    "user_id": "user-uuid",
    "type": "order_status",
    "title": "Pedido creado",
    "body": "Tu pedido fue creado y está en preparación.",
    "data": {
      "order_id": "order-uuid-111",
      "status": "pending"
    },
    "is_read": false,
    "created_at": "2026-02-20T10:30:05Z"
  }
]
```

---

### **9️⃣ Proceso de PAGO (futuro)**
🚧 **Pendiente de implementar:**
- Integración con pasarela de pago (Culqi, Mercado Pago, etc.)
- Actualizar orden a `paid` cuando se confirme pago
- Enviar notificación de pago confirmado

---

### **🔟 Admin actualiza ESTADO de la orden**
```http
PUT /orders/order-uuid-111/status
Authorization: Bearer {admin_token}
Content-Type: application/json

{
  "status": "in_process"
}
```

**Backend automáticamente:**
- ✅ Actualiza el estado de la orden
- ✅ Envía notificación al usuario: "Pedido en proceso"

**Estados posibles:**
- `pending` → Orden creada, esperando confirmación
- `in_process` → En preparación / asignado a groomer
- `on_the_way` → Groomer en camino a la dirección
- `delivered` → Servicio completado

---

## 📊 **Resumen de Datos por Paso**

| Paso | Endpoint | Datos Guardados |
|------|----------|-----------------|
| 1 | `GET /pets` | `pet_id`, `name`, `weight_kg` |
| 2 | `GET /paku-spa/plans?pet_id=` | `plan_id`, `code`, `price` |
| 3 | `GET /iam/me/addresses` | `address_id` |
| 4 | `GET /availability` | `scheduled_date`, `scheduled_time` |
| 5 | `POST /cart/{id}/items` | Todo en `meta` del item |
| 6 | `POST /cart/{id}/checkout` | Cart status → `checked_out` |
| 7 | `POST /orders` | Snapshot completo en orden |
| 8 | `GET /notifications` | Notificación automática |

---

## 🎯 **Campos Clave en `meta` del Cart Item**

```javascript
{
  // Información de la mascota
  "pet_id": "uuid",           // ✅ OBLIGATORIO
  "pet_name": "string",        // ✅ Para display
  "pet_weight": 15.5,          // 🔜 Para cálculo futuro de precio
  
  // Información del servicio
  "plan_code": "classic",      // ✅ Para tracking
  
  // Fecha y hora programada
  "scheduled_date": "2026-02-22",  // ✅ OBLIGATORIO
  "scheduled_time": "10:00",       // ✅ OBLIGATORIO
  
  // Dirección (opcional aquí, se envía en POST /orders)
  "address_id": "uuid"         // 📌 Redundante pero útil
}
```

---

## ✅ **Estado Actual del Sistema**

| Componente | Estado | Notas |
|------------|--------|-------|
| **Plans Hardcode** | ✅ Listo | Precio fijo, recibe `pet_id` |
| **Cart** | ✅ Listo | Guarda todo en `meta` |
| **Orders** | ✅ Listo | Snapshot + notificaciones |
| **Notifications** | ✅ Listo | Async consistente |
| **Availability** | ⚠️ Mock | Devuelve datos hardcoded |
| **Pricing dinámico** | 🔜 Futuro | Calcular según peso |
| **Payment** | 🚧 Pendiente | Integración con pasarela |

---

## 🚀 **Próximos Pasos**

1. ✅ **Frontend usa `GET /paku-spa/plans?pet_id=uuid`**
2. ✅ **Frontend guarda toda la info en `meta` del cart item**
3. 🔜 **Implementar cálculo de precio por peso** (cuando estén listos)
4. 🔜 **Migrar de `/paku-spa/plans` → `/commerce/services`** (cuando estén listos)
5. 🔜 **Integrar pasarela de pago**

---

## 📝 **Notas Técnicas**

### **¿Por qué `meta` es un objeto libre?**
- Flexibilidad para agregar campos sin migraciones
- Snapshot completo en la orden (no se pierde info)
- Frontend puede agregar contexto adicional

### **¿Por qué validar `pet_id` en `/paku-spa/plans`?**
- Estructura el flujo correcto
- Garantiza que la mascota existe y pertenece al usuario
- Prepara el sistema para pricing dinámico futuro

### **¿Cuándo se valida la fecha?**
- **Actualmente:** No se valida (availability es mock)
- **Futuro:** Validar que `scheduled_date` + `scheduled_time` estén disponibles

### **¿Dónde se guarda la fecha seleccionada?**
- En el campo `meta` del cart item
- Hace snapshot en la orden (no se pierde aunque el usuario cambie la fecha después)
