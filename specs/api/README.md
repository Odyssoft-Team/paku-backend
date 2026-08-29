# Contrato de API

## Fuente de verdad

- **Forma** (endpoints, request/response, tipos): OpenAPI generado por FastAPI → `GET /openapi.json`, UI en `/docs`.
- **Comportamiento** (reglas, estados, errores de negocio): los specs de `domain/` y `features/`.
- Si el código y el spec de comportamiento divergen → bug. Reconciliar, no ignorar.

Base URL: `https://api.paku.app` · local `http://localhost:8000`.

## Convenciones

- Auth: `Authorization: Bearer <access_token>` (JWT). `refresh_token` para renovar.
- Routers `admin_router` separados por módulo para operación interna.
- Errores: formato de `app/core/errors.py`. Documentar códigos de negocio en el spec de la entidad.
- Paginación / filtros: (TODO documentar patrón real).

## Cambios de contrato

Un cambio que rompe a un cliente (web / admin / vet-dev) requiere:
1. Nota en el `plan.md` de la feature listando los 3 clientes y el impacto.
2. Coordinación o versionado antes de mergear.

## Docs de API existentes

- `paku-backend/docs/chat-api.md`
- `paku-backend/docs/tracking-api.md`
- `paku-backend/docs/flujo-compra-servicio.md`
- `paku-backend/FRONTEND_INTEGRATION_GUIDE.md`, `CART_*.md`

Migrar su contenido de referencia a `domain/<entidad>.md` cuando se toque cada área.
