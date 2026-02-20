# 🗄️ Estado de Base de Datos - Cart Validations

## ✅ **NO SE REQUIEREN MIGRACIONES**

Las mejoras implementadas en el sistema de carrito son **únicamente a nivel de lógica de negocio** (use cases y validaciones), por lo que **NO se requieren cambios en el esquema de la base de datos**.

---

## 📊 **ESQUEMA ACTUAL (Sin Cambios)**

### **Tabla: cart_sessions**

```sql
CREATE TABLE cart_sessions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    status cartstatus NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX ix_cart_sessions_user_id ON cart_sessions(user_id);
CREATE INDEX ix_cart_sessions_user_status ON cart_sessions(user_id, status);
CREATE INDEX ix_cart_sessions_expires ON cart_sessions(expires_at);
```

### **Tabla: cart_items**

```sql
CREATE TABLE cart_items (
    id UUID PRIMARY KEY,
    cart_id UUID NOT NULL,
    kind cartitemkind NOT NULL,
    ref_id VARCHAR(200) NOT NULL,
    name VARCHAR(200),
    qty INTEGER NOT NULL,
    unit_price NUMERIC(10, 2),
    meta JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX ix_cart_items_cart_id ON cart_items(cart_id);
CREATE INDEX ix_cart_items_kind_ref ON cart_items(kind, ref_id);
```

### **Enums:**

```sql
CREATE TYPE cartstatus AS ENUM ('active', 'checked_out', 'expired', 'cancelled');
CREATE TYPE cartitemkind AS ENUM ('service_base', 'service_addon', 'product');
```

---

## 🔍 **¿QUÉ SE VALIDÓ EN BD?**

### **Estructura de meta (JSONB) - Ejemplos Válidos:**

#### **Servicio Base:**
```json
{
  "pet_id": "uuid-string",
  "pet_name": "Fido",
  "pet_weight": 15.5,
  "scheduled_date": "2026-02-25",
  "scheduled_time": "10:00",
  "address_id": "uuid-string",
  "plan_code": "classic"
}
```

#### **Addon:**
```json
{
  "requires_base": "uuid-string"
}
```

**Nota:** La estructura de `meta` es flexible (JSONB), pero las validaciones de negocio garantizan que los campos requeridos estén presentes.

---

## ✅ **CAMBIOS IMPLEMENTADOS (Solo Lógica)**

### **1. Validaciones en Use Cases:**
- `_validate_single_base_service()` - Lógica de negocio
- `_validate_required_meta_fields()` - Valida contenido de meta
- `_validate_addon_dependencies()` - Valida relaciones
- `_validate_date_format()` - Valida formato de fechas
- `_validate_time_format()` - Valida formato de horas

### **2. Nuevo Use Case:**
- `ValidateCart` - Validación completa pre-checkout

### **3. Nuevo Endpoint:**
- `POST /cart/{id}/validate` - Expone validación al frontend

---

## 🚀 **MIGRACIONES EXISTENTES (Sin Cambios)**

Las migraciones actuales ya cubren el esquema completo:

| Revisión | Descripción | Estado |
|----------|-------------|--------|
| `eae7270101c6` | Initial schema | ✅ Aplicada |
| `a1b2c3d4e5f6` | Add user addresses and geo districts | ✅ Aplicada |
| `7073a500860c` | Check | ✅ Aplicada |
| `2d6005ee35d7` | Add indexes and constraints | ✅ Aplicada |
| `cf01dde0409a` | Alter cart_sessions status to enum | ✅ Aplicada |
| `e03bb2e74308` | Fix cartstatus enum | ✅ Aplicada |
| `eba019248014` | Merge heads | ✅ Aplicada |

---

## 📝 **VERIFICACIÓN DE ESQUEMA**

Si deseas verificar que el esquema actual coincide con los modelos:

### **Opción 1: Generar migración de verificación (debe estar vacía)**

```bash
# Activar venv
.\.venv\Scripts\Activate.ps1

# Instalar alembic si no está
pip install alembic

# Generar migración automática
alembic revision --autogenerate -m "verify schema after cart validations"

# Si no hay cambios, el archivo estará vacío (solo upgrade/downgrade pass)
```

### **Opción 2: Inspeccionar BD directamente**

```sql
-- Ver estructura de cart_sessions
\d cart_sessions

-- Ver estructura de cart_items
\d cart_items

-- Ver enums
SELECT * FROM pg_type WHERE typname IN ('cartstatus', 'cartitemkind');
```

---

## 🎯 **CONCLUSIÓN**

✅ **NO se requieren migraciones de Alembic**

Las mejoras implementadas son:
- ✅ Validaciones de lógica de negocio
- ✅ Nuevos use cases
- ✅ Nuevos endpoints
- ✅ Mejor manejo de errores

Todo funciona con el esquema actual de BD, que es flexible gracias al uso de:
- `meta: JSONB` (permite cualquier estructura)
- Validaciones en capa de aplicación (no en BD)

---

## 📖 **DOCUMENTACIÓN RELACIONADA**

- [CART_VALIDATIONS.md](./CART_VALIDATIONS.md) - Validaciones implementadas
- [CART_IMPLEMENTATION_SUMMARY.md](./CART_IMPLEMENTATION_SUMMARY.md) - Resumen de implementación
- [FRONTEND_INTEGRATION_GUIDE.md](./FRONTEND_INTEGRATION_GUIDE.md) - Guía de integración

---

**Última actualización:** Febrero 2026  
**Estado:** ✅ Esquema estable, sin cambios requeridos
