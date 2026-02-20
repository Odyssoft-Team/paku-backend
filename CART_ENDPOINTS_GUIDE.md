# 📖 Guía de Endpoints de Carrito - ¿Cuándo usar cada uno?

## 🎯 **RESUMEN EJECUTIVO**

El módulo de carrito tiene **7 endpoints**, pero **solo necesitas usar 5** en producción:

| Endpoint | Estado | Cuándo usar |
|----------|--------|-------------|
| `GET /cart` | ✅ **Principal** | Al abrir la app (recuperar carrito) |
| `POST /cart/items` | ✅ **Principal** | Primera compra (crear carrito + items) |
| `PUT /cart/{id}/items` | ✅ **Principal** | Cambiar servicio base |
| `DELETE /cart/{id}/items/{item_id}` | ✅ Opcional | Eliminar addon específico |
| `POST /cart/{id}/validate` | ✅ Recomendado | Antes de mostrar pantalla de pago |
| `POST /cart/{id}/checkout` | ✅ **Principal** | Finalizar compra |
| `POST /cart/{id}/items` | ⚠️ **DEPRECADO** | NO USAR (mantener por compatibilidad) |

---

## 📋 **ENDPOINTS DETALLADOS**

### **1️⃣ GET /cart - Obtener/Crear Carrito Activo**

**Estado:** ✅ **Endpoint Principal**

#### **¿Cuándo usar?**
- ✅ Al abrir la app (primera pantalla)
- ✅ Al navegar a la sección de compras
- ✅ Después de login/registro
- ✅ Al volver del background

#### **¿Qué hace?**
- Busca el carrito activo del usuario
- Si no existe o expiró (>2 horas): crea uno nuevo vacío
- Retorna el carrito + items

#### **Request:**
```http
GET /cart
Authorization: Bearer {token}
```

#### **Response:**
```json
{
  "cart": {
    "id": "cart-uuid",
    "user_id": "user-uuid",
    "status": "active",
    "expires_at": "2026-02-20T14:00:00Z",
    "created_at": "2026-02-20T12:00:00Z",
    "updated_at": "2026-02-20T12:00:00Z"
  },
  "items": []  // Vacío si es nuevo
}
```

#### **Flujo típico:**
```javascript
// Al abrir la app
const cart = await getActiveCart();

if (cart.items.length > 0) {
  // Tiene items pendientes
  showCartBadge(cart.items.length);
  navigateToHome();
} else {
  // Carrito vacío
  navigateToHome();
}
```

---

### **2️⃣ POST /cart/items - Crear Carrito con Items (Batch)**

**Estado:** ✅ **Endpoint Principal**

#### **¿Cuándo usar?**
- ✅ Primera compra del usuario (carrito vacío)
- ✅ Después de seleccionar servicio + mascota + fecha
- ✅ Usuario agregó servicio base + addons

#### **¿Qué hace?**
- Crea un carrito NUEVO
- Agrega TODOS los items de una vez
- Valida: 1 servicio base + addons opcionales

#### **Request:**
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
        "scheduled_date": "2026-02-25",
        "scheduled_time": "10:00",
        "address_id": "address-uuid"
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
    }
  ]
}
```

#### **Response:**
```json
{
  "cart": {
    "id": "new-cart-uuid",
    "status": "active",
    ...
  },
  "items": [
    { "id": "item1-uuid", "kind": "service_base", ... },
    { "id": "item2-uuid", "kind": "service_addon", ... }
  ]
}
```

#### **Flujo típico:**
```javascript
// Usuario seleccionó todo
const selectedData = {
  pet: { id: "pet-123", name: "Fido" },
  plan: { id: "plan-uuid", name: "Clásico", price: 80 },
  addons: [
    { id: "addon1", name: "Corte de uñas", price: 15 }
  ],
  date: "2026-02-25",
  time: "10:00"
};

// Crear carrito con TODO
const cart = await createCartWithItems({
  items: [
    {
      kind: "service_base",
      ref_id: selectedData.plan.id,
      name: selectedData.plan.name,
      qty: 1,
      unit_price: selectedData.plan.price,
      meta: {
        pet_id: selectedData.pet.id,
        pet_name: selectedData.pet.name,
        scheduled_date: selectedData.date,
        scheduled_time: selectedData.time
      }
    },
    ...selectedData.addons.map(addon => ({
      kind: "service_addon",
      ref_id: addon.id,
      name: addon.name,
      qty: 1,
      unit_price: addon.price,
      meta: { requires_base: selectedData.plan.id }
    }))
  ]
});

navigateToCheckout(cart.cart.id);
```

---

### **3️⃣ PUT /cart/{id}/items - Reemplazar Todos los Items**

**Estado:** ✅ **Endpoint Principal**

#### **¿Cuándo usar?**
- ✅ Usuario quiere cambiar de servicio base
- ✅ Usuario quiere cambiar fecha/hora
- ✅ Usuario quiere cambiar mascota
- ✅ Usuario quiere modificar addons

#### **¿Qué hace?**
- ELIMINA todos los items existentes
- AGREGA los nuevos items
- Mantiene el mismo carrito (mismo ID)

#### **Request:**
```http
PUT /cart/{cart-uuid}/items
Authorization: Bearer {token}
Content-Type: application/json

{
  "items": [
    {
      "kind": "service_base",
      "ref_id": "premium-uuid",  // ← Cambió de Clásico a Premium
      "name": "Premium",
      "qty": 1,
      "unit_price": 120.0,
      "meta": {
        "pet_id": "pet-uuid",
        "scheduled_date": "2026-02-26",  // ← Cambió fecha
        "scheduled_time": "14:00"        // ← Cambió hora
      }
    },
    {
      "kind": "service_addon",
      "ref_id": "addon2-uuid",  // ← Addon diferente
      "name": "Limpieza dental",
      "qty": 1,
      "unit_price": 25.0,
      "meta": { "requires_base": "premium-uuid" }
    }
  ]
}
```

#### **Response:**
```json
{
  "cart": {
    "id": "same-cart-uuid",  // ← Mismo carrito
    "status": "active",
    ...
  },
  "items": [
    { "id": "new-item1-uuid", "kind": "service_base", "name": "Premium", ... },
    { "id": "new-item2-uuid", "kind": "service_addon", "name": "Limpieza dental", ... }
  ]
}
```

#### **Flujo típico:**
```javascript
// Usuario está en el carrito y quiere cambiar todo
const handleChangePlan = async (newPlan, newAddons) => {
  const updatedCart = await replaceAllItems(currentCart.id, {
    items: [
      {
        kind: "service_base",
        ref_id: newPlan.id,
        name: newPlan.name,
        qty: 1,
        unit_price: newPlan.price,
        meta: { /* datos actualizados */ }
      },
      ...newAddons.map(addon => ({ /* ... */ }))
    ]
  });
  
  showSuccess("Carrito actualizado");
  refreshCartUI(updatedCart);
};
```

---

### **4️⃣ DELETE /cart/{id}/items/{item_id} - Eliminar Item Individual**

**Estado:** ✅ Opcional (para UX avanzada)

#### **¿Cuándo usar?**
- ✅ Usuario quiere eliminar UN addon específico
- ✅ Usuario quiere quitar UN producto del carrito
- ❌ NO usar para cambiar servicio base (usar PUT /items)

#### **¿Qué hace?**
- Elimina UN item específico del carrito
- Mantiene los demás items

#### **Request:**
```http
DELETE /cart/{cart-uuid}/items/{item-uuid}
Authorization: Bearer {token}
```

#### **Response:**
```
204 No Content
```

#### **Flujo típico:**
```javascript
// Usuario hace click en "X" de un addon
const removeAddon = async (cartId, itemId) => {
  await deleteCartItem(cartId, itemId);
  showSuccess("Addon eliminado");
  refreshCart();
};
```

#### **⚠️ Limitación:**
Si eliminas el servicio base, el carrito queda inválido (solo addons). En ese caso, es mejor usar `PUT /cart/{id}/items` para reemplazar todo.

---

### **5️⃣ POST /cart/{id}/validate - Validar Carrito**

**Estado:** ✅ **Recomendado** (antes de checkout)

#### **¿Cuándo usar?**
- ✅ Antes de mostrar pantalla de pago
- ✅ Antes de llamar a checkout
- ✅ Para debug de problemas en carrito

#### **¿Qué hace?**
- Valida TODAS las reglas de negocio
- Calcula el total
- NO modifica el carrito (solo lectura)

#### **Request:**
```http
POST /cart/{cart-uuid}/validate
Authorization: Bearer {token}
```

#### **Response (válido):**
```json
{
  "valid": true,
  "errors": [],
  "warnings": [],
  "total": 95.0,
  "currency": "PEN"
}
```

#### **Response (inválido):**
```json
{
  "valid": false,
  "errors": [
    "Service 'Clásico' missing required field: pet_id",
    "Item 'Addon 1' has invalid price"
  ],
  "warnings": [
    "Total is 0. Please verify prices."
  ],
  "total": 0.0,
  "currency": "PEN"
}
```

#### **Flujo típico:**
```javascript
// Antes de mostrar pantalla de pago
const handleGoToPayment = async (cartId) => {
  const validation = await validateCart(cartId);
  
  if (!validation.valid) {
    // Mostrar errores
    showErrors(validation.errors);
    return;
  }
  
  // Mostrar total y continuar
  showPaymentScreen({
    total: validation.total,
    currency: validation.currency
  });
};
```

---

### **6️⃣ POST /cart/{id}/checkout - Finalizar Compra**

**Estado:** ✅ **Endpoint Principal**

#### **¿Cuándo usar?**
- ✅ Usuario confirmó el pago
- ✅ Usuario presionó "Confirmar pedido"

#### **¿Qué hace?**
- Valida automáticamente el carrito
- Si válido: marca como `checked_out`
- Si inválido: retorna 400 con errores
- Crea la orden (en módulo orders)
- Envía notificaciones

#### **Request:**
```http
POST /cart/{cart-uuid}/checkout
Authorization: Bearer {token}
```

#### **Response (éxito):**
```json
{
  "cart_id": "cart-uuid",
  "status": "checked_out",
  "total": 95.0,
  "currency": "PEN",
  "items": [
    { "id": "item1", "kind": "service_base", ... },
    { "id": "item2", "kind": "service_addon", ... }
  ]
}
```

#### **Response (error):**
```json
{
  "detail": {
    "message": "Cart validation failed",
    "errors": [
      "Service 'Clásico' missing required field: scheduled_date"
    ],
    "warnings": []
  }
}
```

#### **Flujo típico:**
```javascript
// Usuario presiona "Confirmar pedido"
const handleConfirmOrder = async (cartId) => {
  try {
    const result = await checkout(cartId);
    
    // Éxito
    showSuccess("¡Pedido confirmado!");
    navigateToOrderConfirmation(result.cart_id);
    
  } catch (error) {
    if (error.status === 400 && error.detail.message === "Cart validation failed") {
      // Mostrar errores de validación
      showErrors(error.detail.errors);
      offerEditCart();
    } else {
      // Otro error
      showError("Error al procesar el pedido");
    }
  }
};
```

---

### **7️⃣ POST /cart/{id}/items - Agregar Item Individual**

**Estado:** ⚠️ **DEPRECADO** (mantener por compatibilidad)

#### **¿Por qué está deprecado?**
- ❌ No valida la estructura completa del carrito
- ❌ Permite estados inconsistentes (ej: múltiples servicios base)
- ❌ Flujo antiguo (pre-batch operations)

#### **¿Cuándo NO usar?**
- ❌ NO usar para crear el primer carrito
- ❌ NO usar para agregar el servicio base
- ❌ NO usar en producción (preferir batch operations)

#### **¿Cuándo SÍ usar? (solo si es necesario)**
- ⚠️ Agregar UN addon DESPUÉS de crear el carrito (caso raro)
- ⚠️ Mantener compatibilidad con código legacy

#### **Alternativas:**
| Acción | En lugar de | Usar |
|--------|-------------|------|
| Crear carrito + items | POST /cart → POST /cart/{id}/items | `POST /cart/items` |
| Agregar addon | POST /cart/{id}/items | `PUT /cart/{id}/items` |
| Cambiar items | POST /cart/{id}/items | `PUT /cart/{id}/items` |

---

## 🎯 **FLUJOS COMPLETOS**

### **Flujo 1: Primera Compra (Usuario Nuevo)**

```
┌─────────────────────────────────────────────┐
│ 1. Abrir app                                │
│    GET /cart                                │
│    → Retorna carrito vacío                  │
└────────────────┬────────────────────────────┘
                 │
┌────────────────▼────────────────────────────┐
│ 2. Seleccionar mascota, servicio, addons   │
│    (Todo en memoria, no API calls)          │
└────────────────┬────────────────────────────┘
                 │
┌────────────────▼────────────────────────────┐
│ 3. Usuario presiona "Agregar al carrito"   │
│    POST /cart/items                         │
│    → Crea carrito + items                   │
└────────────────┬────────────────────────────┘
                 │
┌────────────────▼────────────────────────────┐
│ 4. Mostrar resumen del carrito             │
│    (Usar response del paso 3)               │
└────────────────┬────────────────────────────┘
                 │
┌────────────────▼────────────────────────────┐
│ 5. Usuario presiona "Pagar"                │
│    POST /cart/{id}/validate (opcional)      │
│    → Verificar que todo está OK             │
└────────────────┬────────────────────────────┘
                 │
┌────────────────▼────────────────────────────┐
│ 6. Usuario confirma pago                   │
│    POST /cart/{id}/checkout                 │
│    → Crea orden                             │
└────────────────┬────────────────────────────┘
                 │
┌────────────────▼────────────────────────────┐
│ 7. Mostrar confirmación                    │
│    Navegar a orden                          │
└─────────────────────────────────────────────┘
```

### **Flujo 2: Usuario con Carrito Existente**

```
┌─────────────────────────────────────────────┐
│ 1. Abrir app                                │
│    GET /cart                                │
│    → Retorna carrito con items              │
└────────────────┬────────────────────────────┘
                 │
┌────────────────▼────────────────────────────┐
│ 2. Mostrar badge con cantidad de items     │
│    Navegar a home                           │
└────────────────┬────────────────────────────┘
                 │
┌────────────────▼────────────────────────────┐
│ 3. Usuario quiere cambiar servicio         │
│    PUT /cart/{id}/items                     │
│    → Reemplaza todos los items              │
└────────────────┬────────────────────────────┘
                 │
┌────────────────▼────────────────────────────┐
│ 4. Continuar con checkout...                │
└─────────────────────────────────────────────┘
```

### **Flujo 3: Eliminar Addon Específico**

```
┌─────────────────────────────────────────────┐
│ 1. Usuario está en carrito                 │
│    (Ya tiene carrito cargado)               │
└────────────────┬────────────────────────────┘
                 │
┌────────────────▼────────────────────────────┐
│ 2. Usuario hace click en "X" de un addon   │
│    DELETE /cart/{id}/items/{item_id}        │
│    → Elimina ese addon                      │
└────────────────┬────────────────────────────┘
                 │
┌────────────────▼────────────────────────────┐
│ 3. Actualizar UI                            │
│    GET /cart/{id} (opcional, para refresh)  │
└─────────────────────────────────────────────┘
```

---

## 📊 **TABLA COMPARATIVA**

| Endpoint | Crea Carrito | Valida | Modifica Items | Uso Principal |
|----------|--------------|--------|----------------|---------------|
| `GET /cart` | ✅ Si no existe | ❌ | ❌ | Recuperar carrito |
| `POST /cart/items` | ✅ Siempre | ✅ | ✅ Todo | Primera compra |
| `PUT /cart/{id}/items` | ❌ | ✅ | ✅ Todo | Cambiar servicio |
| `DELETE /cart/{id}/items/{item_id}` | ❌ | ❌ | ✅ Uno | Quitar addon |
| `POST /cart/{id}/validate` | ❌ | ✅ | ❌ | Pre-checkout |
| `POST /cart/{id}/checkout` | ❌ | ✅ | ❌ | Finalizar |
| `POST /cart/{id}/items` ⚠️ | ❌ | ❌ | ✅ Uno | DEPRECADO |

---

## ✅ **CONCLUSIÓN**

### **Endpoints que DEBES usar:**
1. ✅ `GET /cart` - Al abrir la app
2. ✅ `POST /cart/items` - Primera compra
3. ✅ `PUT /cart/{id}/items` - Cambiar servicio/fecha
4. ✅ `POST /cart/{id}/validate` - Antes de pagar
5. ✅ `POST /cart/{id}/checkout` - Confirmar pedido

### **Endpoints opcionales:**
- ✅ `DELETE /cart/{id}/items/{item_id}` - Eliminar addon (UX avanzada)

### **Endpoints deprecados:**
- ⚠️ `POST /cart/{id}/items` - NO USAR (mantener por compatibilidad)

---

## 🚀 **NO HAY ENDPOINTS HUÉRFANOS**

Todos los endpoints tienen un propósito claro:
- ✅ `GET /cart` - Recuperar carrito activo
- ✅ `POST /cart/items` - Batch creation (principal)
- ✅ `PUT /cart/{id}/items` - Batch replacement (principal)
- ✅ `DELETE /cart/{id}/items/{item_id}` - Eliminar uno (opcional)
- ✅ `POST /cart/{id}/validate` - Validar (recomendado)
- ✅ `POST /cart/{id}/checkout` - Finalizar (principal)
- ⚠️ `POST /cart/{id}/items` - Deprecado pero funcional

**Todos están documentados y tienen uso específico.** 🎉
