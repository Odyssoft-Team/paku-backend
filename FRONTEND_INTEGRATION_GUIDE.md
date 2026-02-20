# 📱 Guía de Integración Frontend - Sistema de Carrito con Validaciones

## 🎯 **PARA DESARROLLADORES FRONTEND**

Esta guía te ayudará a integrar el nuevo sistema de carrito con validaciones automáticas.

---

## 🚀 **QUICK START**

### **1. Flujo Básico: Crear Carrito con Items**

```javascript
// 1. Usuario selecciona mascota, servicio y addons
const cartData = {
  items: [
    {
      kind: "service_base",
      ref_id: planId,
      name: planName,
      qty: 1,
      unit_price: planPrice,
      meta: {
        pet_id: selectedPet.id,
        pet_name: selectedPet.name,
        pet_weight: selectedPet.weight_kg,
        scheduled_date: selectedDate, // "2026-02-25"
        scheduled_time: selectedTime, // "10:00"
        address_id: selectedAddress?.id
      }
    },
    ...addons.map(addon => ({
      kind: "service_addon",
      ref_id: addon.id,
      name: addon.name,
      qty: 1,
      unit_price: addon.price,
      meta: {
        requires_base: planId
      }
    }))
  ]
};

// 2. Enviar a backend
try {
  const response = await fetch('/cart/items', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(cartData)
  });
  
  if (!response.ok) {
    const error = await response.json();
    showError(error.detail);
    return;
  }
  
  const result = await response.json();
  navigateToCart(result.cart.id);
  
} catch (error) {
  showError("Error al crear el carrito");
}
```

---

## ✅ **VALIDACIONES PRE-ENVÍO (RECOMENDADO)**

Valida los datos en frontend ANTES de enviar al backend para mejor UX:

```javascript
const validateCartData = (items) => {
  const errors = [];
  
  // 1. Verificar que hay items
  if (!items || items.length === 0) {
    errors.push("Debes agregar al menos un servicio");
    return { valid: false, errors };
  }
  
  // 2. Verificar servicio base
  const baseServices = items.filter(i => i.kind === 'service_base');
  
  if (baseServices.length === 0) {
    errors.push("Debes seleccionar un servicio base");
  } else if (baseServices.length > 1) {
    errors.push("Solo puedes agregar 1 servicio base por carrito");
  } else {
    // 3. Verificar meta del servicio base
    const base = baseServices[0];
    const meta = base.meta || {};
    
    if (!meta.pet_id) {
      errors.push("Debes seleccionar una mascota");
    }
    
    if (!meta.scheduled_date) {
      errors.push("Debes seleccionar una fecha");
    } else if (!isValidDateFormat(meta.scheduled_date)) {
      errors.push("Formato de fecha inválido. Usa YYYY-MM-DD");
    }
    
    if (!meta.scheduled_time) {
      errors.push("Debes seleccionar una hora");
    } else if (!isValidTimeFormat(meta.scheduled_time)) {
      errors.push("Formato de hora inválido. Usa HH:MM");
    }
  }
  
  // 4. Verificar precios
  const hasInvalidPrice = items.some(i => 
    !i.unit_price || i.unit_price <= 0
  );
  
  if (hasInvalidPrice) {
    errors.push("Algunos items no tienen precio válido");
  }
  
  return {
    valid: errors.length === 0,
    errors
  };
};

// Helpers
const isValidDateFormat = (date) => {
  return /^\d{4}-\d{2}-\d{2}$/.test(date);
};

const isValidTimeFormat = (time) => {
  return /^\d{2}:\d{2}$/.test(time);
};
```

---

## 🔍 **VALIDAR CARRITO ANTES DE CHECKOUT**

Usa el endpoint `/cart/{id}/validate` para verificar que todo está correcto:

```javascript
const validateCartBeforeCheckout = async (cartId) => {
  try {
    const response = await fetch(`/cart/${cartId}/validate`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (!response.ok) {
      throw new Error('Error al validar carrito');
    }
    
    const validation = await response.json();
    
    // Si hay errores bloqueantes
    if (!validation.valid) {
      showValidationErrors(validation.errors);
      return false;
    }
    
    // Si hay advertencias (no bloqueantes)
    if (validation.warnings.length > 0) {
      showWarnings(validation.warnings);
    }
    
    // Mostrar total calculado
    showTotal(validation.total, validation.currency);
    
    return true;
    
  } catch (error) {
    showError("Error al validar carrito");
    return false;
  }
};

// Usar antes de mostrar pantalla de pago
const handleCheckout = async () => {
  const isValid = await validateCartBeforeCheckout(cartId);
  
  if (isValid) {
    // Mostrar pantalla de pago
    navigateToPayment();
  } else {
    // Mostrar errores y permitir editar
    showMessage("Por favor corrige los errores antes de continuar");
  }
};
```

---

## 💳 **PROCESAR CHECKOUT**

El checkout ahora valida automáticamente, maneja los errores correctamente:

```javascript
const processCheckout = async (cartId) => {
  try {
    const response = await fetch(`/cart/${cartId}/checkout`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    // Manejo de errores de validación
    if (response.status === 400) {
      const error = await response.json();
      
      // Checkout falló por validación
      if (error.detail.message === "Cart validation failed") {
        showValidationErrors(error.detail.errors);
        
        // Opcional: Ofrecer editar carrito
        showButton("Editar carrito", () => navigateToCart(cartId));
        return;
      }
    }
    
    if (!response.ok) {
      throw new Error('Error al procesar checkout');
    }
    
    const result = await response.json();
    
    // Checkout exitoso
    showSuccess("¡Pedido creado exitosamente!");
    navigateToOrderConfirmation(result.cart_id);
    
  } catch (error) {
    showError("Error al procesar el pedido");
  }
};
```

---

## 🔄 **EDITAR CARRITO (REPLACE ALL ITEMS)**

Si el usuario quiere cambiar el servicio base:

```javascript
const replaceCartItems = async (cartId, newItems) => {
  try {
    // Validar antes de enviar
    const validation = validateCartData(newItems);
    if (!validation.valid) {
      showErrors(validation.errors);
      return;
    }
    
    const response = await fetch(`/cart/${cartId}/items`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ items: newItems })
    });
    
    if (!response.ok) {
      const error = await response.json();
      showError(error.detail);
      return;
    }
    
    const result = await response.json();
    updateCartUI(result);
    showSuccess("Carrito actualizado");
    
  } catch (error) {
    showError("Error al actualizar carrito");
  }
};
```

---

## 📋 **COMPONENTE REACT EJEMPLO**

```jsx
import { useState, useEffect } from 'react';

const CartCheckout = ({ cartId }) => {
  const [validation, setValidation] = useState(null);
  const [loading, setLoading] = useState(false);
  
  // Validar al cargar el componente
  useEffect(() => {
    validateCart();
  }, [cartId]);
  
  const validateCart = async () => {
    setLoading(true);
    
    try {
      const response = await fetch(`/cart/${cartId}/validate`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      const result = await response.json();
      setValidation(result);
      
    } catch (error) {
      console.error('Error validating cart:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const handleCheckout = async () => {
    if (!validation?.valid) {
      return; // No permitir checkout si hay errores
    }
    
    setLoading(true);
    
    try {
      const response = await fetch(`/cart/${cartId}/checkout`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      if (response.status === 400) {
        const error = await response.json();
        setValidation({
          valid: false,
          errors: error.detail.errors || [error.detail],
          warnings: error.detail.warnings || []
        });
        return;
      }
      
      if (!response.ok) {
        throw new Error('Checkout failed');
      }
      
      const result = await response.json();
      // Navegar a confirmación
      window.location.href = `/orders/${result.cart_id}`;
      
    } catch (error) {
      alert('Error al procesar el pedido');
    } finally {
      setLoading(false);
    }
  };
  
  if (loading) {
    return <div>Cargando...</div>;
  }
  
  return (
    <div className="cart-checkout">
      {/* Mostrar errores */}
      {validation?.errors.length > 0 && (
        <div className="errors">
          <h3>Errores que debes corregir:</h3>
          <ul>
            {validation.errors.map((error, i) => (
              <li key={i} className="error">{error}</li>
            ))}
          </ul>
          <button onClick={() => window.location.href = `/cart/${cartId}/edit`}>
            Editar carrito
          </button>
        </div>
      )}
      
      {/* Mostrar advertencias */}
      {validation?.warnings.length > 0 && (
        <div className="warnings">
          <h3>Advertencias:</h3>
          <ul>
            {validation.warnings.map((warning, i) => (
              <li key={i} className="warning">{warning}</li>
            ))}
          </ul>
        </div>
      )}
      
      {/* Mostrar total */}
      {validation && (
        <div className="total">
          <h2>Total: {validation.currency} {validation.total.toFixed(2)}</h2>
        </div>
      )}
      
      {/* Botón de checkout */}
      <button
        onClick={handleCheckout}
        disabled={!validation?.valid || loading}
        className={validation?.valid ? 'btn-primary' : 'btn-disabled'}
      >
        {loading ? 'Procesando...' : 'Pagar'}
      </button>
    </div>
  );
};

export default CartCheckout;
```

---

## ⚠️ **MANEJO DE ERRORES COMUNES**

### **Error 400: Multiple base services**

```javascript
// Usuario intentó agregar 2 servicios base
{
  "detail": "Cannot have multiple base services in cart. Only 1 base service + addons allowed."
}

// Solución: Mostrar mensaje claro
showError("Solo puedes tener 1 servicio base por carrito. Si quieres cambiar de servicio, edita el carrito.");
```

### **Error 400: Missing required meta field**

```javascript
// Usuario no seleccionó mascota o fecha
{
  "detail": "Service 'Clásico' requires 'pet_id' in meta"
}

// Solución: Navegar al paso correspondiente
if (error.includes("pet_id")) {
  showError("Debes seleccionar una mascota");
  navigateToPetSelection();
} else if (error.includes("scheduled_date")) {
  showError("Debes seleccionar una fecha");
  navigateToDateSelection();
}
```

### **Error 400: Invalid date/time format**

```javascript
// Formato incorrecto
{
  "detail": "Invalid scheduled_date format. Expected YYYY-MM-DD, got '22-02-2026'"
}

// Solución: Formatear fecha correctamente
const formatDate = (date) => {
  // date puede ser Date object o string "dd/mm/yyyy"
  const d = new Date(date);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`; // "2026-02-25"
};

const formatTime = (time) => {
  // time puede ser "10:00 AM" o Date object
  const d = new Date(time);
  const hours = String(d.getHours()).padStart(2, '0');
  const minutes = String(d.getMinutes()).padStart(2, '0');
  return `${hours}:${minutes}`; // "10:00"
};
```

### **Error 400: Cart validation failed (en checkout)**

```javascript
// Validación falló en checkout
{
  "detail": {
    "message": "Cart validation failed",
    "errors": [
      "Service 'Clásico' missing required field: pet_id",
      "Item 'Corte de uñas' has invalid price"
    ],
    "warnings": []
  }
}

// Solución: Mostrar lista de errores y permitir editar
const errors = error.detail.errors;
showErrorList(errors);
showButton("Editar carrito", () => navigateToCart(cartId));
```

---

## 🎨 **COMPONENTES UI RECOMENDADOS**

### **ValidationErrorsList Component**

```jsx
const ValidationErrorsList = ({ errors, warnings }) => {
  if (!errors?.length && !warnings?.length) return null;
  
  return (
    <div className="validation-messages">
      {errors?.length > 0 && (
        <div className="errors">
          <h3>⚠️ Debes corregir lo siguiente:</h3>
          <ul>
            {errors.map((error, i) => (
              <li key={i} className="error-item">
                {error}
              </li>
            ))}
          </ul>
        </div>
      )}
      
      {warnings?.length > 0 && (
        <div className="warnings">
          <h3>💡 Advertencias:</h3>
          <ul>
            {warnings.map((warning, i) => (
              <li key={i} className="warning-item">
                {warning}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
```

### **CartSummary Component**

```jsx
const CartSummary = ({ cartId, onValidChange }) => {
  const [validation, setValidation] = useState(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    validateCart();
  }, [cartId]);
  
  const validateCart = async () => {
    // ... (código de validación)
    onValidChange?.(result.valid);
  };
  
  return (
    <div className="cart-summary">
      <ValidationErrorsList 
        errors={validation?.errors} 
        warnings={validation?.warnings} 
      />
      
      {validation && (
        <div className="total">
          <div className="total-label">Total:</div>
          <div className="total-amount">
            {validation.currency} {validation.total.toFixed(2)}
          </div>
        </div>
      )}
    </div>
  );
};
```

---

## 📊 **TABLA DE REFERENCIA RÁPIDA**

| Acción | Endpoint | Método | Valida? |
|--------|----------|--------|---------|
| Crear carrito + items | `/cart/items` | POST | ✅ Sí |
| Editar todos los items | `/cart/{id}/items` | PUT | ✅ Sí |
| Validar carrito | `/cart/{id}/validate` | POST | ✅ Sí (solo lectura) |
| Hacer checkout | `/cart/{id}/checkout` | POST | ✅ Sí (automático) |
| Obtener carrito activo | `/cart` | GET | ❌ No |
| Eliminar item | `/cart/{id}/items/{item_id}` | DELETE | ❌ No |

---

## ✅ **CHECKLIST DE INTEGRACIÓN**

- [ ] Validar datos en frontend antes de enviar
- [ ] Formatear fecha como YYYY-MM-DD
- [ ] Formatear hora como HH:MM
- [ ] Incluir todos los campos requeridos en meta
- [ ] Usar endpoint de validación antes de checkout
- [ ] Manejar errores de validación con mensajes claros
- [ ] Permitir editar carrito si hay errores
- [ ] Mostrar total calculado antes de pagar
- [ ] Manejar error 400 en checkout
- [ ] Navegar a confirmación tras checkout exitoso

---

## 📖 **DOCUMENTACIÓN ADICIONAL**

- [CART_VALIDATIONS.md](./CART_VALIDATIONS.md) - Documentación técnica de validaciones
- [CART_BATCH_OPERATIONS.md](./CART_BATCH_OPERATIONS.md) - Documentación de endpoints
- [FLUJO_PAKU_SPA.md](./FLUJO_PAKU_SPA.md) - Flujo completo de la app

---

**¿Dudas?** Contacta al equipo de backend o revisa la documentación técnica.
