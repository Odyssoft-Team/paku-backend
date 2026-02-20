# 🔒 Validaciones de Carrito - Paku Backend

## 📋 **OVERVIEW**

Sistema completo de validaciones para garantizar la integridad de datos en el flujo de carrito → checkout → orden.

**Última actualización:** Febrero 2026

---

## ✅ **VALIDACIONES IMPLEMENTADAS**

### **1. Validación de Servicio Base Único**

**Función:** `_validate_single_base_service(items)`

**Regla de negocio:**
- 1 carrito = 1 servicio base + opcionales addons
- No se permiten múltiples servicios base
- Debe existir al menos 1 servicio base

**Errores:**
```json
{
  "detail": "Cannot have multiple base services in cart. Only 1 base service + addons allowed."
}
```

```json
{
  "detail": "Cart must have at least one base service"
}
```

**Aplicado en:**
- `POST /cart/items` (crear carrito con items)
- `PUT /cart/{id}/items` (reemplazar todos los items)
- `POST /{id}/validate` (validación explícita)
- `POST /{id}/checkout` (validación pre-checkout)

---

### **2. Validación de Campos Requeridos en Meta**

**Función:** `_validate_required_meta_fields(items)`

**Regla de negocio:**
- Los servicios base DEBEN tener en `meta`:
  - `pet_id`: UUID de la mascota
  - `scheduled_date`: Fecha en formato YYYY-MM-DD
  - `scheduled_time`: Hora en formato HH:MM

**Validaciones de formato:**
- `scheduled_date`: Validado con `datetime.strptime(date, "%Y-%m-%d")`
- `scheduled_time`: Validado con `datetime.strptime(time, "%H:%M")`

**Errores:**
```json
{
  "detail": "Service 'Clásico' requires 'pet_id' in meta"
}
```

```json
{
  "detail": "Invalid scheduled_date format. Expected YYYY-MM-DD, got '22-02-2026'"
}
```

```json
{
  "detail": "Invalid scheduled_time format. Expected HH:MM, got '10:00:00'"
}
```

**Aplicado en:**
- `POST /cart/items`
- `PUT /cart/{id}/items`
- `POST /{id}/validate`
- `POST /{id}/checkout`

---

### **3. Validación de Dependencias de Addons**

**Función:** `_validate_addon_dependencies(items)`

**Regla de negocio:**
- Los addons pueden especificar `requires_base` en meta
- Si lo especifican, debe coincidir con el `ref_id` del servicio base del carrito
- Si no lo especifican, se asume que aplican al servicio base

**Errores:**
```json
{
  "detail": "Addon 'Corte de uñas' requires base service 'premium-uuid', but cart has 'classic-uuid'"
}
```

**Aplicado en:**
- `POST /cart/items`
- `PUT /cart/{id}/items`
- `POST /{id}/validate`
- `POST /{id}/checkout`

---

### **4. Validación Completa de Carrito (Endpoint Dedicado)**

**Endpoint:** `POST /cart/{id}/validate`

**Use Case:** `ValidateCart`

**Verificaciones completas:**

1. ✅ Carrito existe y está activo
2. ✅ Tiene al menos 1 item (servicio base)
3. ✅ Items tienen precios válidos (> 0)
4. ✅ Meta tiene campos requeridos
5. ✅ Addons referencian correctamente al servicio base
6. ⚠️ Advertencias (warnings) no bloqueantes

**Response:**
```json
{
  "valid": false,
  "errors": [
    "Service 'Clásico' missing required field: pet_id",
    "Item 'Corte de uñas' has invalid price"
  ],
  "warnings": [
    "Total is 0. Please verify prices."
  ],
  "total": 0.0,
  "currency": "PEN"
}
```

**Caso exitoso:**
```json
{
  "valid": true,
  "errors": [],
  "warnings": [],
  "total": 120.0,
  "currency": "PEN"
}
```

---

### **5. Validación Automática en Checkout**

**Endpoint:** `POST /cart/{id}/checkout`

**Comportamiento:**
- Ejecuta `ValidateCart` automáticamente antes de procesar
- Si hay errores, retorna `400 Bad Request` con detalles
- Si es válido, procede con checkout normal

**Error en checkout:**
```json
{
  "detail": {
    "message": "Cart validation failed",
    "errors": [
      "Service 'Clásico' missing required field: scheduled_date",
      "Cart must have at least one base service"
    ],
    "warnings": []
  }
}
```

---

## 🔄 **FLUJO DE VALIDACIÓN**

### **Crear Carrito (POST /cart/items)**

```
1. Request → items: [base, addon1, addon2]
2. _validate_single_base_service(items)
   └─ ✅ Solo 1 servicio base
3. _validate_required_meta_fields(items)
   └─ ✅ pet_id, scheduled_date, scheduled_time presentes y válidos
4. _validate_addon_dependencies(items)
   └─ ✅ Addons referencian al servicio base correcto
5. Crear carrito + items
6. Response → CartWithItemsOut
```

### **Reemplazar Items (PUT /cart/{id}/items)**

```
1. Request → items: [base, addon1, addon2, addon3]
2. Verificar carrito existe y está activo
3. _validate_single_base_service(items)
4. _validate_required_meta_fields(items)
5. _validate_addon_dependencies(items)
6. DELETE todos los items anteriores
7. INSERT nuevos items
8. Response → CartWithItemsOut
```

### **Validar Carrito (POST /cart/{id}/validate)**

```
1. Request → cart_id
2. Obtener carrito + items de BD
3. Ejecutar TODAS las validaciones
4. Calcular total
5. Response → CartValidationOut (valid, errors, warnings, total)
```

### **Checkout (POST /cart/{id}/checkout)**

```
1. Request → cart_id
2. Ejecutar ValidateCart
3. SI valid = false:
   └─ ❌ Return 400 con errores
4. SI valid = true:
   └─ ✅ Marcar carrito como checked_out
   └─ ✅ Crear orden (en orders module)
   └─ ✅ Response → CheckoutOut
```

---

## 📝 **EJEMPLOS DE USO**

### **Ejemplo 1: Crear Carrito Válido**

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
        "pet_id": "pet-uuid-123",
        "pet_name": "Fido",
        "pet_weight": 15.5,
        "scheduled_date": "2026-02-25",
        "scheduled_time": "10:00",
        "address_id": "address-uuid-456"
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

**✅ Response 201 Created**

---

### **Ejemplo 2: Error - Múltiples Servicios Base**

```http
POST /cart/items
Authorization: Bearer {token}
Content-Type: application/json

{
  "items": [
    {
      "kind": "service_base",
      "ref_id": "classic-uuid",
      "name": "Clásico",
      "qty": 1,
      "unit_price": 80.0,
      "meta": { "pet_id": "pet-123", "scheduled_date": "2026-02-25", "scheduled_time": "10:00" }
    },
    {
      "kind": "service_base",
      "ref_id": "premium-uuid",
      "name": "Premium",
      "qty": 1,
      "unit_price": 120.0,
      "meta": { "pet_id": "pet-123", "scheduled_date": "2026-02-25", "scheduled_time": "10:00" }
    }
  ]
}
```

**❌ Response 400 Bad Request**
```json
{
  "detail": "Cannot have multiple base services in cart. Only 1 base service + addons allowed."
}
```

---

### **Ejemplo 3: Error - Meta Incompleto**

```http
POST /cart/items
Authorization: Bearer {token}
Content-Type: application/json

{
  "items": [
    {
      "kind": "service_base",
      "ref_id": "classic-uuid",
      "name": "Clásico",
      "qty": 1,
      "unit_price": 80.0,
      "meta": {
        "pet_id": "pet-123"
        // ❌ Falta scheduled_date y scheduled_time
      }
    }
  ]
}
```

**❌ Response 400 Bad Request**
```json
{
  "detail": "Service 'Clásico' requires 'scheduled_date' in meta (format: YYYY-MM-DD)"
}
```

---

### **Ejemplo 4: Validar Antes de Checkout**

```http
POST /cart/abc-123-def/validate
Authorization: Bearer {token}
```

**✅ Response 200 OK (válido)**
```json
{
  "valid": true,
  "errors": [],
  "warnings": [],
  "total": 95.0,
  "currency": "PEN"
}
```

**❌ Response 200 OK (inválido)**
```json
{
  "valid": false,
  "errors": [
    "Service 'Clásico' missing required field: pet_id",
    "Item 'Corte de uñas' has invalid price"
  ],
  "warnings": [
    "Total is 0. Please verify prices."
  ],
  "total": 0.0,
  "currency": "PEN"
}
```

---

### **Ejemplo 5: Checkout con Validación Automática**

```http
POST /cart/abc-123-def/checkout
Authorization: Bearer {token}
```

**Si el carrito tiene errores:**

**❌ Response 400 Bad Request**
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

**Si el carrito es válido:**

**✅ Response 200 OK**
```json
{
  "cart_id": "abc-123-def",
  "status": "checked_out",
  "total": 95.0,
  "currency": "PEN",
  "items": [
    {
      "id": "item-1",
      "cart_id": "abc-123-def",
      "kind": "service_base",
      "ref_id": "550e8400-e29b-41d4-a716-446655440001",
      "name": "Clásico",
      "qty": 1,
      "unit_price": 80.0,
      "meta": {
        "pet_id": "pet-123",
        "scheduled_date": "2026-02-25",
        "scheduled_time": "10:00"
      }
    },
    {
      "id": "item-2",
      "cart_id": "abc-123-def",
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

---

## 🎯 **RECOMENDACIONES PARA FRONTEND**

### **1. Validar en Frontend Antes de Enviar**

```javascript
// Validación básica antes de POST /cart/items
const validateBeforeSubmit = (items) => {
  const baseServices = items.filter(i => i.kind === 'service_base');
  
  if (baseServices.length === 0) {
    showError("Debes seleccionar un servicio base");
    return false;
  }
  
  if (baseServices.length > 1) {
    showError("Solo puedes agregar 1 servicio base por carrito");
    return false;
  }
  
  const baseService = baseServices[0];
  const meta = baseService.meta || {};
  
  if (!meta.pet_id) {
    showError("Debes seleccionar una mascota");
    return false;
  }
  
  if (!meta.scheduled_date) {
    showError("Debes seleccionar una fecha");
    return false;
  }
  
  if (!meta.scheduled_time) {
    showError("Debes seleccionar una hora");
    return false;
  }
  
  return true;
};
```

### **2. Usar Endpoint de Validación Antes de Checkout**

```javascript
// Validar carrito antes de mostrar pantalla de pago
const validateCart = async (cartId) => {
  const response = await fetch(`/cart/${cartId}/validate`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` }
  });
  
  const validation = await response.json();
  
  if (!validation.valid) {
    showErrors(validation.errors);
    return false;
  }
  
  if (validation.warnings.length > 0) {
    showWarnings(validation.warnings);
  }
  
  // Mostrar total calculado
  showTotal(validation.total, validation.currency);
  
  return true;
};

// Antes de checkout
if (await validateCart(cartId)) {
  proceedToCheckout();
} else {
  showMessage("Por favor corrige los errores antes de continuar");
}
```

### **3. Manejar Errores de Validación en Checkout**

```javascript
const checkout = async (cartId) => {
  try {
    const response = await fetch(`/cart/${cartId}/checkout`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` }
    });
    
    if (response.status === 400) {
      const error = await response.json();
      
      if (error.detail.message === "Cart validation failed") {
        // Mostrar errores de validación
        showValidationErrors(error.detail.errors);
        return;
      }
    }
    
    if (!response.ok) {
      throw new Error('Checkout failed');
    }
    
    const result = await response.json();
    navigateToOrderConfirmation(result);
    
  } catch (error) {
    showError("Error al procesar el pedido");
  }
};
```

---

## 📊 **TABLA RESUMEN DE VALIDACIONES**

| Validación | Función | Momento | Endpoint | Bloqueante |
|------------|---------|---------|----------|------------|
| 1 servicio base único | `_validate_single_base_service` | Pre-insert | `POST /cart/items`, `PUT /cart/{id}/items` | ✅ Sí |
| Meta requeridos | `_validate_required_meta_fields` | Pre-insert | `POST /cart/items`, `PUT /cart/{id}/items` | ✅ Sí |
| Formato fecha/hora | `_validate_date_format`, `_validate_time_format` | Pre-insert | `POST /cart/items`, `PUT /cart/{id}/items` | ✅ Sí |
| Dependencias addons | `_validate_addon_dependencies` | Pre-insert | `POST /cart/items`, `PUT /cart/{id}/items` | ✅ Sí |
| Precios válidos | `ValidateCart` | Pre-checkout | `POST /{id}/validate`, `POST /{id}/checkout` | ✅ Sí |
| Total > 0 | `ValidateCart` | Pre-checkout | `POST /{id}/validate`, `POST /{id}/checkout` | ⚠️ Warning |
| Carrito activo | Todas | Siempre | Todos los endpoints | ✅ Sí |
| Items no vacíos | `ValidateCart` | Pre-checkout | `POST /{id}/validate`, `POST /{id}/checkout` | ✅ Sí |

---

## 🔧 **MANTENIMIENTO**

### **Agregar Nueva Validación**

1. Crear función `_validate_xyz(items)` en `use_cases.py`
2. Agregar llamada en `CreateCartWithItems`, `ReplaceAllItems`, `ValidateCart`
3. Documentar en este archivo
4. Actualizar tests

### **Modificar Campos Requeridos**

Editar función `_validate_required_meta_fields`:
```python
# Agregar nuevo campo requerido
if not meta.get("address_id"):
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Service '{item.get('name')}' requires 'address_id' in meta"
    )
```

---

## ✅ **CONCLUSIÓN**

El sistema de validaciones está diseñado para:
- ✅ Garantizar integridad de datos
- ✅ Prevenir estados inconsistentes
- ✅ Mejorar experiencia de usuario (errores claros)
- ✅ Facilitar debugging
- ✅ Mantener reglas de negocio centralizadas

**Regla de oro:** Validar temprano, fallar rápido, mostrar errores claros.
