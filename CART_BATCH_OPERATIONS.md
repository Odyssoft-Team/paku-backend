# 🛒 Nuevo Sistema de Carrito - Batch Operations

## 📋 **CAMBIOS IMPLEMENTADOS**

### **✅ Nuevos Endpoints:**

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| **POST** | `/cart/items` | 🆕 Crea carrito + agrega múltiples items (batch) |
| **PUT** | `/cart/{id}/items` | 🆕 Reemplaza TODOS los items del carrito |
| **POST** | `/cart/{id}/validate` | 🆕 Valida carrito antes del checkout |
| **GET** | `/cart` | Obtiene carrito activo (auto-crea si no existe) |
| **DELETE** | `/cart/{id}/items/{item_id}` | Elimina item individual |
| **POST** | `/cart/{id}/checkout` | Finaliza carrito (con validación automática) |

### **🔒 Validaciones Automáticas:**

Todos los endpoints de creación/edición de carrito incluyen validaciones:

| Validación | Descripción | Bloqueante |
|------------|-------------|------------|
| **1 servicio base único** | Solo 1 servicio base por carrito | ✅ Sí |
| **Meta requeridos** | pet_id, scheduled_date, scheduled_time | ✅ Sí |
| **Formato fecha/hora** | YYYY-MM-DD y HH:MM | ✅ Sí |
| **Dependencias addons** | Addons referencian al servicio base correcto | ✅ Sí |
| **Precios válidos** | Todos los items tienen precio > 0 | ✅ Sí (en validate/checkout) |

📖 **Ver documentación completa:** [CART_VALIDATIONS.md](./CART_VALIDATIONS.md)

### **⚠️ Endpoints Deprecados (mantener por compatibilidad):**

| Método | Endpoint | Estado | Usar en su lugar |
|--------|----------|--------|------------------|
| ~~POST~~ | ~~/cart~~ | ⚠️ Deprecado | `POST /cart/items` |
| ~~POST~~ | ~~/cart/{id}/items~~ | ⚠️ Deprecado | `POST /cart/items` o `PUT /cart/{id}/items` |

---

## 🎯 **FLUJO COMPLETO (Nuevo)**

### **1️⃣ Usuario selecciona MASCOTA + SERVICIO BASE + ADDONS**

Frontend recolecta toda la info en memoria:

```javascript
const selectedData = {
  pet: { id: "pet-uuid", name: "Fido", weight_kg: 15.5 },
  basePlan: { id: "classic-uuid", name: "Clásico", price: 80.0 },
  addons: [
    { id: "addon1-uuid", name: "Corte de uñas", price: 15.0 },
    { id: "addon2-uuid", name: "Limpieza dental", price: 25.0 }
  ],
  scheduledDate: "2026-02-22",
  scheduledTime: "10:00",
  address: { id: "address-uuid", ... }
}
```

---

### **2️⃣ Crear carrito con TODOS los items de una vez**

```http
POST /cart/items
Authorization: Bearer {token}
Content-Type: application/json

{
  "items": [
    {
      "kind": "service_base",
      "ref_id": "550e8400-e29b-41d4-a716-446655440001",
      "name": "Clásico",
      "qty": 1,
      "unit_price": 80.0,
      "meta": {
        "pet_id": "pet-uuid",
        "pet_name": "Fido",
        "pet_weight": 15.5,
        "plan_code": "classic",
        "scheduled_date": "2026-02-22",
        "scheduled_time": "10:00"
      }
    },
    {
      "kind": "service_addon",
      "ref_id": "addon1-uuid",
      "name": "Corte de uñas",
      "qty": 1,
      "unit_price": 15.0,
      "meta": {
        "requires_base": "550e8400-e29b-41d4-a716-446655440001"
      }
    },
    {
      "kind": "service_addon",
      "ref_id": "addon2-uuid",
      "name": "Limpieza dental",
      "qty": 1,
      "unit_price": 25.0,
      "meta": {
        "requires_base": "550e8400-e29b-41d4-a716-446655440001"
      }
    }
  ]
}
```

**Response:**
```json
{
  "cart": {
    "id": "cart-uuid",
    "user_id": "user-uuid",
    "status": "active",
    "expires_at": "2026-02-20T12:00:00Z",
    "created_at": "2026-02-20T10:00:00Z",
    "updated_at": "2026-02-20T10:00:00Z"
  },
  "items": [
    {
      "id": "item1-uuid",
      "cart_id": "cart-uuid",
      "kind": "service_base",
      "ref_id": "550e8400-e29b-41d4-a716-446655440001",
      "name": "Clásico",
      "qty": 1,
      "unit_price": 80.0,
      "meta": { "pet_id": "pet-uuid", ... }
    },
    {
      "id": "item2-uuid",
      "cart_id": "cart-uuid",
      "kind": "service_addon",
      "ref_id": "addon1-uuid",
      "name": "Corte de uñas",
      "qty": 1,
      "unit_price": 15.0,
      "meta": { ... }
    },
    {
      "id": "item3-uuid",
      "cart_id": "cart-uuid",
      "kind": "service_addon",
      "ref_id": "addon2-uuid",
      "name": "Limpieza dental",
      "qty": 1,
      "unit_price": 25.0,
      "meta": { ... }
    }
  ]
}
```

**✅ Ventajas:**
- 1 solo request HTTP (más rápido)
- Carrito + items creados atómicamente
- Validación automática (solo 1 base service)

---

### **3️⃣ Usuario abandona temporalmente → Recuperar carrito**

```http
GET /cart
Authorization: Bearer {token}
```

**Response:**
```json
{
  "cart": {
    "id": "cart-uuid",
    "status": "active",
    ...
  },
  "items": [
    { "id": "item1-uuid", "name": "Clásico", ... },
    { "id": "item2-uuid", "name": "Corte de uñas", ... },
    { "id": "item3-uuid", "name": "Limpieza dental", ... }
  ]
}
```

---

### **4️⃣ Editar carrito - Opción A: Quitar addon individual**

```http
DELETE /cart/cart-uuid/items/item3-uuid
Authorization: Bearer {token}
```

**Resultado:**
- Item eliminado
- Carrito mantiene: Clásico + Corte de uñas

---

### **5️⃣ Editar carrito - Opción B: Cambiar servicio base (Clear + Rebuild)**

```http
PUT /cart/cart-uuid/items
Authorization: Bearer {token}
Content-Type: application/json

{
  "items": [
    {
      "kind": "service_base",
      "ref_id": "premium-uuid",
      "name": "Premium",
      "qty": 1,
      "unit_price": 89.0,
      "meta": {
        "pet_id": "pet-uuid",
        "pet_name": "Fido",
        "plan_code": "premium",
        "scheduled_date": "2026-02-22",
        "scheduled_time": "10:00"
      }
    },
    {
      "kind": "service_addon",
      "ref_id": "addon1-uuid",
      "name": "Corte de uñas",
      "qty": 1,
      "unit_price": 15.0,
      "meta": {}
    }
  ]
}
```

**Resultado:**
- TODOS los items anteriores eliminados
- Nuevos items agregados: Premium + Corte de uñas
- Same cart_id (no se crea carrito nuevo)

---

### **6️⃣ Checkout**

```http
POST /cart/cart-uuid/checkout
Authorization: Bearer {token}
```

**Response:**
```json
{
  "cart_id": "cart-uuid",
  "status": "checked_out",
  "total": 104.0,
  "currency": "PEN",
  "items": [...]
}
```

---

### **7️⃣ Crear orden**

```http
POST /orders
Authorization: Bearer {token}
Content-Type: application/json

{
  "cart_id": "cart-uuid",
  "address_id": "address-uuid"
}
```

---

## 🔒 **VALIDACIONES IMPLEMENTADAS**

### **1. Solo 1 servicio base por carrito**

```javascript
// ❌ ESTO FALLA:
POST /cart/items
{
  "items": [
    { "kind": "service_base", "ref_id": "classic-uuid", ... },
    { "kind": "service_base", "ref_id": "premium-uuid", ... }  // ❌ Error!
  ]
}

// Response: 400 Bad Request
{
  "detail": "Cannot have multiple base services in cart. Only 1 base service + addons allowed."
}
```

### **2. Al menos 1 servicio base requerido**

```javascript
// ❌ ESTO FALLA:
POST /cart/items
{
  "items": [
    { "kind": "service_addon", "ref_id": "addon-uuid", ... }  // ❌ Sin base!
  ]
}

// Response: 400 Bad Request
{
  "detail": "Cart must have at least one base service"
}
```

### **3. Carrito debe estar activo**

- Si carrito expiró → Error 410 Gone
- Si carrito en checkout → Error 410 Gone

---

## 📊 **COMPARACIÓN: Antes vs Ahora**

### **ANTES (3 requests):**
```javascript
// 1. Crear carrito vacío
const { cart } = await POST('/cart')

// 2. Agregar base service
await POST(`/cart/${cart.id}/items`, { ...basePlan })

// 3. Agregar addon
await POST(`/cart/${cart.id}/items`, { ...addon })
```

**Problemas:**
- ❌ 3 requests HTTP
- ❌ Si falla request 2 o 3 → carrito inconsistente
- ❌ Frontend maneja cart_id manualmente

---

### **AHORA (1 request):**
```javascript
// Todo de una vez
const { cart, items } = await POST('/cart/items', {
  items: [basePlan, addon1, addon2]
})
```

**Ventajas:**
- ✅ 1 solo request
- ✅ Atómico (todo o nada)
- ✅ Validación automática
- ✅ Más simple

---

## 🚀 **MIGRACIÓN FRONTEND**

### **Cambio mínimo:**

**ANTES:**
```javascript
// Paso 1: Crear carrito
const { cart } = await fetch('/cart', { method: 'POST' })

// Paso 2-N: Agregar items
for (const item of items) {
  await fetch(`/cart/${cart.id}/items`, {
    method: 'POST',
    body: JSON.stringify(item)
  })
}
```

**AHORA:**
```javascript
// Un solo paso
const { cart, items } = await fetch('/cart/items', {
  method: 'POST',
  body: JSON.stringify({ items })
})
```

---

## ✅ **COMPATIBILIDAD**

Los endpoints antiguos **se mantienen** para no romper código existente:

- ✅ `POST /cart` - Sigue funcionando (crea carrito vacío)
- ✅ `POST /cart/{id}/items` - Sigue funcionando (agrega item individual)

**Pero se recomienda migrar a:**
- 🆕 `POST /cart/items` - Crea cart + items batch
- 🆕 `PUT /cart/{id}/items` - Reemplaza todos los items

---

## 🎯 **REGLAS DE NEGOCIO**

1. ✅ **1 carrito = 1 servicio base + N addons**
2. ✅ **Cambiar servicio base = reemplazar items** (PUT)
3. ✅ **Addons se pueden agregar/quitar individualmente** (POST/DELETE)
4. ✅ **Carrito expira en 2 horas** (auto-cleanup)
5. ✅ **Solo 1 carrito activo por usuario** (GET /cart auto-maneja)

---

## 📝 **NOTAS TÉCNICAS**

### **¿Por qué batch en vez de individual?**
- Más rápido (1 request vs N)
- Atómico (validación completa)
- Mejor UX (usuario espera menos)

### **¿Cuándo usar PUT vs DELETE+POST?**
- **PUT** → Cambiar servicio base completo
- **DELETE+POST** → Ajustar addons específicos

### **¿Qué pasa con los carritos abandonados?**
- Expiran automáticamente en 2 horas
- Se limpian con scheduler (`expire_carts`)
- Usuario puede recuperarlos con `GET /cart` (si no expiraron)

---

## ✅ **TODO LISTO**

- ✅ Endpoints batch implementados
- ✅ Validaciones de negocio
- ✅ Compatibilidad con código existente
- ✅ Sin cambios en BD (no migración)
- ✅ Documentación completa
