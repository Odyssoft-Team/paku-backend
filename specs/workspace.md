# Paku — Workspace

Contexto de arranque. Léelo al inicio de cada sesión en cualquier repo Paku.
Reemplaza tener que explicar la estructura a mano.

## Los repos

Los repos se clonan como hermanos en un mismo directorio de trabajo.

| Repo | Rol | Stack | GitHub |
|------|-----|-------|--------|
| **paku-backend** | API. Fuente de verdad del dominio. Nada existe sin esto. | Python 3.12, FastAPI, SQLAlchemy + Alembic, Postgres (Cloud SQL), Firebase Admin, Docker | — |
| **paku-web** | Web informativa + web app (login, compra, pedidos, tracking). | Next.js 16 (App Router), React 19, Tailwind + shadcn/radix, Firebase, Leaflet. Gestor: **pnpm**. | `git@github.com:fzalvarez/paku-web.git` |
| **paku-admin** | Web admin (asignación de groomers, catálogo, órdenes). | Next.js (App Router), Tailwind + shadcn, Firebase, `middleware.ts`. Gestor: **pnpm**. | — |
| **paku-vet-dev** | App Paku Groomer (groomers de Paku en la van). | React Native + Expo (EAS), Zustand store. Gestor: **pnpm**. | — |
| **culqi-python** | Microservicio de pagos. Encapsula Culqi API v2 (cobros, tarjetas). | Python 3.12, FastAPI, SQLModel, Postgres, deploy Cloud Run | — |

> ⚠️ `paku-admin` y `paku-vet-dev` tienen `package-lock.json` obsoleto junto al `pnpm-lock.yaml`. Usar pnpm; limpiar el lock npm.

## Backend — arquitectura

Módulos en `app/modules/<módulo>/`, cada uno con capas: `api/` · `app/` (casos de uso) · `domain/` · `infra/`.

Módulos: `iam`, `catalog` (razas), `store` (servicios, addons, reglas de precio, cotización), `cart`,
`orders`, `booking`, `pets`, `pet_records`, `geo`, `chat`, `streaming`, `tracking`, `notifications`, `push`, `wallet`.
(`commerce` y `clinical_history` ya no tienen código; `paku_spa` está vacío.)

Plan de trabajo vigente: `paku-backend/docs/plan-de-trabajo.md`.

`app/core/`: `auth.py`, `db.py`, `settings.py`, `rate_limiter.py`, `scheduler.py`, `errors.py`.

Routers públicos y `admin_router` separados por módulo (ver `app/main.py`).

## Flujo de negocio (resumen)

Compra de servicio: mascota → servicio + addons (fecha/hora) → dirección → disponibilidad (booking)
→ carrito (`POST /cart/items`, persiste 2 h) → validar → checkout → `POST /orders` (necesita `address_id`)
→ orden `created` → admin asigna ally y fecha → estados: `accepted → on_the_way → in_service → …`.
Detalle: `paku-backend/docs/flujo-compra-servicio.md`.

## Docs existentes a consolidar en specs/

- `paku-backend/docs/`: `chat-api.md`, `tracking-api.md`, `flujo-compra-servicio.md`
- `paku-web/referencias/`: `flujo-compra-servicio.md`, `frontend-api.md` (API de pagos), `streaming-integration-docs.md`
- `paku-web/` raíz: `ANALISIS_CRITICO.md`, `MIGRACION_CULQI.md`
- `paku-vet-dev/`: `ARCHITECTURE.md`, `COMMANDS.md`, `NEXT-STEPS.md`, `TROUBLESHOOTING.md`

> El `README.md` de `paku-backend` enlaza `CART_*.md` y `FRONTEND_INTEGRATION_GUIDE.md` que ya no existen. Enlaces obsoletos.

## Convenciones

- Idioma de specs y docs: **español**.
- Fechas: absolutas (`2026-08-29`), no relativas.
- Pagos: **Culqi es la única pasarela**. Migración desde Mercado Pago completada (`paku-web/MIGRACION_CULQI.md`).
  Arquitectura de 3 piezas:
  1. **Culqi** directo desde el cliente (`secure.culqi.com/v2/tokens` o SDK `checkout.culqi.com/js/v4`): tokeniza, la tarjeta nunca toca servidores propios.
  2. **culqi-python**: microservicio propio. `/api/culqi/{customers,cards,charges}`, auth `X-API-Key`, idempotencia. Hace el cobro real.
  3. **paku-backend**: `/wallet/cards` (referencia de tarjetas) y `/orders/{id}/confirm-payment` (guarda `culqi_charge_id`). No cobra.
  Flujo: orden `pending` → `POST culqi-python /api/culqi/charges` → `POST paku-backend /orders/{id}/confirm-payment`.
  Detalle en `domain/payments.md` (pendiente).

## Preguntas abiertas

- [ ] URL canónica de culqi-python: web usa `stream.dev-qa.site/payment`, vet-dev usa `culqi-backend-*.run.app`. ¿Cuál?
- [ ] `paku-web/.env` no define `NEXT_PUBLIC_PAYMENT_API_URL/KEY` ni `NEXT_PUBLIC_CULQI_PUBLIC_KEY` → pago roto con ese `.env`; además apunta a prod mientras los defaults del código van a `dev-qa.site`.
- [ ] Enfoque de captura de tarjeta: web usa form propio, vet-dev usa SDK oficial de Culqi en WebView. Unificar.
