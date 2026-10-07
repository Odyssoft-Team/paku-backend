---
feature: 0002-busqueda-direcciones
estado: in-progress   # draft | approved | in-progress | done | abandoned
repos: [paku-backend, paku-monorepo]
creado: 2026-10-07
---

# Búsqueda de direcciones con sugerencias y ubicación real

## Problema

Al registrar una dirección en la app de clientes, el usuario escribe la calle a mano y el pin del
mapa cae en el **centro del distrito**, no en su casa. El groomer llega con una ubicación imprecisa.
El equipo de pruebas pidió (2026-10-06): sugerencias al escribir la calle, que el distrito se ajuste
solo y que el mapa ubique la dirección real.

## Objetivo

Que el cliente elija su dirección de una lista de sugerencias y que se guarde con su coordenada real,
**controlando el gasto** del proveedor de mapas.

## Fuera de alcance

- Cambiar el mapa que se muestra (sigue siendo Google Maps en la app).
- Validar cobertura del distrito al guardar la dirección (la app ya lista solo distritos activos).
- Guardar el `place_id` en la dirección.
- Cache o límites compartidos entre varias instancias (hoy hay una sola).

## Comportamiento esperado

1. **Dado** un usuario con sesión que eligió el distrito, **cuando** escribe 3 o más letras de la
   calle, **entonces** recibe hasta 5 sugerencias de Perú, priorizando las cercanas a su distrito.
2. **Dado** menos de 3 letras, **cuando** pide sugerencias, **entonces** recibe una lista vacía y no
   se consulta al proveedor.
3. **Dado** que elige una sugerencia, **cuando** pide su detalle, **entonces** recibe calle, número
   (si lo hay), coordenadas y el distrito de nuestro catálogo que coincide (o `null`), indicando si
   está activo.
4. **Dado** que no eligió ninguna sugerencia, **cuando** confirma la dirección, **entonces** la app
   puede pedir las coordenadas del texto escrito (respaldo).
5. **Dado** que el usuario superó su límite, **entonces** recibe 429 `GEO_RATE_LIMITED`.
6. **Dado** que el proveedor no responde, no tiene cuota o no hay clave configurada, **entonces** se
   responde 503 `GEO_UNAVAILABLE` y la app sigue funcionando como antes (sin sugerencias, pin en el
   centro del distrito).
7. **Dado** que dos usuarios buscan lo mismo en el mismo distrito dentro de 24 h, **entonces** el
   segundo se responde desde el cache, sin costo.

## Criterios de aceptación

- [x] Sugerencias solo desde 3 letras; máximo 5.
- [x] Detalle con distrito del catálogo (sin distinguir tildes ni mayúsculas).
- [x] Respaldo de geocodificación.
- [x] Cache de 24 h y límites por usuario configurables por variables de entorno.
- [x] Sin clave o con el proveedor caído: 503, sin afectar otros endpoints.
- [x] `GET /geo/districts` no cambia.
- [ ] App de clientes usando los endpoints (paku-monorepo).

## Impacto en el dominio

Ninguna entidad persistida cambia. El catálogo de distritos (fijo en código) suma `lat`/`lng` del
centro de cada distrito, usados solo para centrar la búsqueda; no se exponen en la API.

## Preguntas abiertas

- [ ] Activación en Google Cloud (Places API (New) + Geocoding, clave de servidor, presupuesto) y
      variable `GOOGLE_PLACES_API_KEY` en el servidor: la hace el encargado del despliegue.
