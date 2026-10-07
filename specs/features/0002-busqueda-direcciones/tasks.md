---
feature: 0002-busqueda-direcciones
plan: ./plan.md
---

# Tasks — Búsqueda de direcciones

## Backend
- [x] Coordenadas del centro de los 43 distritos en el catálogo
- [x] Contrato del proveedor y reglas puras (`domain/address_search.py`)
- [x] Proveedor Google: autocomplete, detalle y geocode (`infra/google_places.py`)
- [x] Cache y límites en memoria (`infra/memory_store.py`)
- [x] Caso de uso con cache, límites y sesgo por distrito
- [x] Endpoints `/geo/places/autocomplete`, `/geo/places/{place_id}`, `/geo/geocode`
- [x] Variables de entorno en `core/settings.py`
- [x] Tests pytest (`tests/unit/test_geo_address_search.py`)
- [x] Entrada C-22 en `docs/cambios-api-para-front.md`

## Despliegue
- [ ] Activar Places API (New) y Geocoding API en Google Cloud
- [ ] Clave de servidor restringida (IP del servidor + esas dos APIs) y presupuesto con alerta
- [ ] `GOOGLE_PLACES_API_KEY` en el `.env` del servidor y redespliegue

## Frontend (app de clientes)
- [ ] Servicio API `geo` y hook de sugerencias (3 letras, 400 ms, `session_token`)
- [ ] Sugerencias en los dos formularios de dirección
- [ ] Ubicación real del pin (detalle → geocode → centro del distrito)

## Cierre
- [ ] Spec a estado `done`
