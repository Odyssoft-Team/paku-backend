---
feature: 0002-busqueda-direcciones
spec: ./spec.md
---

# Plan — Búsqueda de direcciones

## Enfoque

El backend actúa de proxy hacia Google: la clave no viaja en la app y el gasto se controla con cache,
límites por usuario y `session_token`. El proveedor queda detrás de una interfaz (`AddressProvider`)
para poder cambiarlo por LocationIQ o Geoapify sin tocar los endpoints.

Descartado: llamar a Google desde la app (clave expuesta, sin control de gasto) y Nominatim público
(sus reglas prohíben autocompletar mientras se escribe).

Costo estimado (precios de Google a 2026-10): ~US$ 0,02 por dirección registrada fuera de lo gratis;
lo gratis cubre ~2 000 direcciones nuevas al mes.

## Cambios por repo

### paku-backend
- Módulo `geo` (sin tablas ni migraciones):
  - `domain/address_search.py`: contrato del proveedor, reglas (mínimo 3 letras, máx. 5),
    normalización de texto y cruce con el catálogo de distritos.
  - `infra/google_places.py`: Places API (New) autocomplete y detalle (field mask
    `addressComponents,location,formattedAddress` → tarifa Essentials) + Geocoding.
  - `infra/memory_store.py`: cache con vencimiento y contador por ventana, en memoria.
  - `infra/districts_data.py`: `lat`/`lng` del centro de cada distrito.
  - `use_cases/address_search.py`: orquesta cache, límites y sesgo por distrito.
  - `api/places_router.py`: 3 endpoints con sesión obligatoria; no importa la base de datos.
- `core/settings.py`: `GOOGLE_PLACES_API_KEY`, `GEO_AUTOCOMPLETE_PER_MINUTE` (60),
  `GEO_AUTOCOMPLETE_PER_DAY` (300), `GEO_LOOKUP_PER_DAY` (30), `GEO_CACHE_TTL_SECONDS` (86400).

### paku-monorepo (app de clientes)
- Formularios de dirección (perfil y flujo de compra): sugerencias desde 3 letras con espera de
  400 ms, un `session_token` por formulario; al elegir, completar calle/número, ajustar el distrito y
  guardar la coordenada real para el mapa. Si 429/503, seguir como hoy.

## Contrato

Todos requieren `Authorization: Bearer`.

- `GET /geo/places/autocomplete?q=&district_id=&session_token=` →
  `[{ place_id, main_text, secondary_text }]` (vacío con menos de 3 letras).
- `GET /geo/places/{place_id}?session_token=` →
  `{ place_id, lat, lng, formatted_address, address_line, building_number, district_id, district_name, district_active }`.
- `GET /geo/geocode?q=&district_id=` → `{ lat, lng }`.

Errores: 404 `GEO_NOT_FOUND`, 422 `DISTRICT_NOT_FOUND`, 429 `GEO_RATE_LIMITED`,
503 `GEO_UNAVAILABLE` (sin clave, proveedor caído o sin cuota).

## Migraciones de datos

Ninguna.

## Riesgos

- Con varias instancias, cache y límites serían por instancia (aceptable: sigue acotando el gasto).
- Si Google cambia el formato de `addressComponents`, el distrito puede venir `null`; la app deja el
  distrito elegido por el usuario.
