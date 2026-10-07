# Geo Module - Geographic Districts Catalog

## 📍 Overview

This module provides a **read-only catalog of geographic districts** (distritos) supported by the Paku platform.

It is used by other modules (primarily **IAM** for address validation) to:
- List available districts for UI dropdowns
- Validate that a district exists and is active before creating/updating addresses
- Display district information in orders and delivery contexts

---

## 🏗️ Architecture

### Current Implementation: **Hardcoded Data (No Database)**

For the MVP phase, districts are **hardcoded** in `infra/districts_data.py` instead of stored in the database.

**Why?**
- ✅ **Simpler**: No need to seed/populate `geo_districts` table
- ✅ **Faster**: No database queries for district lookups
- ✅ **Sufficient**: District list is static and small (starting with 3 districts)
- ✅ **Easy to expand**: Just add more districts to the Python list

**Future**: When scaling to all of Peru, this can be moved to:
- Database (`geo_districts` table already exists via migration)
- External API (RENIEC, INEI)
- Redis cache

---

## 📂 Structure

```
geo/
├── api/
│   └── router.py          # Public HTTP endpoints
├── domain/
│   ├── __init__.py        # DistrictRepository protocol
│   └── schemas.py         # DistrictOut DTO
├── infra/
│   ├── districts_data.py  # 🆕 HARDCODED district list
│   ├── model.py           # SQLAlchemy model (for future DB use)
│   └── repository.py      # Repository (now uses hardcoded data)
└── use_cases/
    └── geo_service.py     # Business logic
```

---

## 🔌 API Endpoints

### `GET /geo/districts`
List all districts.

**Query Parameters:**
- `active` (bool, default=true): Filter by active status

**Response:**
```json
{
  "id": "150101",
  "name": "Lima",
  "province_name": "Lima",
  "department_name": "Lima",
  "active": true
}
```

### `GET /geo/districts/{district_id}`
Get a specific district by UBIGEO code.

**Response:**
```json
{
  "id": "150104",
  "name": "Barranco",
  "province_name": "Lima",
  "department_name": "Lima",
  "active": true
}
```

**Errors:**
- `404 Not Found`: District does not exist

---

## 🔄 How It Works

### 1. **District Validation in Address Creation**

When a user creates an address (`POST /addresses`):

```python
# In IAM router
geo_service = GeoService(district_repo=PostgresDistrictRepository(session))

# Validate district exists and is active
if not await geo_service.validate_district_exists_and_active(payload.district_id):
    raise HTTPException(422, "District not found or not active")
```

This ensures users can only create addresses in supported districts.

### 2. **District Listing in UI**

The frontend calls `GET /geo/districts?active=true` to populate a dropdown:

```typescript
// Example frontend code
const { data: districts } = await api.get('/geo/districts?active=true');

// Show in UI select
<Select>
  {districts.map(d => (
    <Option key={d.id} value={d.id}>{d.name}</Option>
  ))}
</Select>
```

---

## ➕ How to Add More Districts

Edit `app/modules/geo/infra/districts_data.py`:

```python
DISTRICTS_DATA: list[dict[str, Any]] = [
    # Existing districts...
    {
        "id": "150104",
        "name": "Barranco",
        "province_name": "Lima",
        "department_name": "Lima",
        "active": True,
        "created_at": utcnow(),
        "updated_at": utcnow(),
    },
    
    # Add new district:
    {
        "id": "150114",  # UBIGEO code from INEI
        "name": "La Molina",
        "province_name": "Lima",
        "department_name": "Lima",
        "active": True,  # Set to False to disable
        "created_at": utcnow(),
        "updated_at": utcnow(),
    },
]
```

No database migration needed! Changes take effect immediately on server restart.

---

## 🧪 Testing

Run the test script to verify districts work without database:

```bash
python test_hardcoded_districts.py
```

---

## 🔮 Future Migration to Database

When ready to move to database:

1. Populate `geo_districts` table via Alembic migration or seed script
2. Modify `repository.py` to query database instead of `districts_data.py`
3. Keep the same interface - no changes needed in other modules!

The table already exists (`geo_districts` from migration `a1b2c3d4e5f6`).

---

## 📊 Current Coverage

**Active Districts:** 3
- Barranco (150104)
- Jesús María (150113)
- Lince (150116)

All in Lima Metropolitana, Lima, Perú.

---

## ⚠️ Important Notes

- District IDs use **UBIGEO codes** from INEI (official Peru geographic codes)
- The `active` flag controls service availability (can disable districts without deleting)
- `user_addresses` table has FK to `geo_districts.id` but currently validation is done via hardcoded list
- When a district is inactive, users cannot create new addresses there (existing addresses remain valid)

## Búsqueda de direcciones (feature 0002)

`GET /geo/places/autocomplete`, `GET /geo/places/{place_id}` y `GET /geo/geocode` (con sesión).
Proxy hacia Google Places API (New) + Geocoding con cache de 24 h y límites por usuario en memoria.
Sin `GOOGLE_PLACES_API_KEY` responden 503 `GEO_UNAVAILABLE`. Ver `specs/features/0002-busqueda-direcciones/`.
