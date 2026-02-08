# Geo Module

## Responsibility

The Geo module provides a read-only catalog of geographic administrative divisions (ubigeo) for Peru: departments, provinces, and districts. It serves as the authoritative source for district validation throughout the application.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/geo/districts` | List all districts (default: only active) |
| GET | `/geo/districts/{district_id}` | Get specific district by ID |

### Query Parameters

- `active` (bool, default: true): Filter districts by active status

## Response Schema (DistrictOut)

```json
{
  "id": "150101",
  "name": "Lima",
  "province_name": "Lima",
  "department_name": "Lima",
  "active": true
}
```

## Data Source

The catalog is stored in the `geo_districts` table (PostgreSQL). IDs follow the standard Peruvian ubigeo format (6-digit strings, e.g., "150101").

### Future Data Loading

Seed/migration scripts for loading the initial district catalog will be implemented separately. This module focuses on the API layer only.

## Integration

Other modules (e.g., IAM addresses) validate `district_id` references via `GeoService.validate_district_exists_and_active()`.
