# 🧪 IDs de prueba para desarrollo Frontend

Este archivo documenta los UUIDs hardcoded para testing durante el desarrollo.

---

## 📦 **SERVICE IDs (Commerce)**

Estos IDs están hardcoded en `app/modules/commerce/infra/postgres_commerce_repository.py` y se crean automáticamente al iniciar el backend.

| **Servicio** | **UUID** | **Tipo** | **Especie** |
|--------------|----------|----------|-------------|
| **Baño base (perro)** | `11111111-1111-1111-1111-111111111111` | base | dog |
| **Aseo base (gato)** | `33333333-3333-3333-3333-333333333333` | base | cat |
| **Corte de uñas** | `22222222-2222-2222-2222-222222222222` | addon | dog |
| **Limpieza dental** | `44444444-4444-4444-4444-444444444444` | addon | dog |
| **Corte de pelo** | `55555555-5555-5555-5555-555555555555` | addon | dog |

---

## 🗓️ **Endpoints de Booking**

### **GET /availability**

Devuelve disponibilidad mock para testing.

**Ejemplo de llamada:**
```bash
GET /availability?service_id=11111111-1111-1111-1111-111111111111&date_from=2026-02-20&days=7
Authorization: Bearer {token}
```

**Respuesta:**
```json
[
  {
    "date": "2026-02-20",
    "capacity": 20,
    "available": 14
  },
  {
    "date": "2026-02-21",
    "capacity": 20,
    "available": 17
  }
  // ... más días
]
```

---

### **POST /holds**

Crea una reserva temporal (expira en 10 minutos).

**Ejemplo de llamada:**
```bash
POST /holds
Authorization: Bearer {token}
Content-Type: application/json

{
  "pet_id": "{tu_pet_id}",
  "service_id": "11111111-1111-1111-1111-111111111111"
}
```

**Respuesta:**
```json
{
  "id": "generated-hold-id",
  "user_id": "your-user-id",
  "pet_id": "your-pet-id",
  "service_id": "11111111-1111-1111-1111-111111111111",
  "status": "held",
  "expires_at": "2026-02-18T15:30:00Z",
  "created_at": "2026-02-18T15:20:00Z"
}
```

---

### **POST /holds/{id}/confirm**

Confirma una reserva temporal.

**Ejemplo de llamada:**
```bash
POST /holds/{hold_id}/confirm
```

**Respuesta:**
```json
{
  "id": "hold-id",
  "status": "confirmed",
  // ... resto de campos
}
```

---

## 📍 **District IDs (Geo)**

Los distritos están hardcoded en `app/modules/geo/infra/districts_data.py`.

Usar `GET /geo/districts` para obtener la lista completa.

**Ejemplos:**
- `san_isidro`
- `miraflores`
- `surco`
- `la_molina`

---

## 🐾 **Breeds (Catalog)**

Usar `GET /catalog/breeds?species=dog` para obtener la lista de razas.

**Ejemplos de `breed.id`:**
- `labrador`
- `husky`
- `poodle`
- `bulldog`
- `golden_retriever`
- `mixed` (mestizo)

---

## 💅 **Paku Spa Plans**

Usar `GET /paku-spa/plans` para obtener planes.

**Códigos de plan:**
- `classic` (80 PEN)
- `premium` (89 PEN)
- `express` (75 PEN)

---

## ⚠️ **NOTAS IMPORTANTES**

1. **Availability es MOCK:** Los valores de disponibilidad son calculados, no reflejan reservas reales.
2. **No hay validaciones de FK:** Puedes crear holds con IDs inexistentes (se validará en el futuro).
3. **Expiración de holds:** Los holds expiran automáticamente a los 10 minutos.
4. **Autenticación:** Todos los endpoints de booking requieren token JWT.

---

## 🔄 **Flujo completo de testing**

```bash
# 1. Registrar usuario
POST /auth/register

# 2. Login
POST /auth/login

# 3. Crear mascota
POST /pets
{
  "name": "Firulais",
  "species": "dog",
  "breed": "labrador"
}

# 4. Ver disponibilidad
GET /availability?service_id=11111111-1111-1111-1111-111111111111

# 5. Crear hold
POST /holds
{
  "pet_id": "{pet_id_del_paso_3}",
  "service_id": "11111111-1111-1111-1111-111111111111"
}

# 6. Confirmar hold
POST /holds/{hold_id}/confirm
```
