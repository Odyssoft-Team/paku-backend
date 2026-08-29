# Paku — Workspace

Contexto de arranque. Léelo al inicio de cada sesión en cualquier repo Paku.
Reemplaza tener que explicar la estructura a mano.

## Los repos

Los 4 repos se clonan como hermanos en un mismo directorio de trabajo.

| Repo | Rol | Stack | GitHub |
|------|-----|-------|--------|
| **paku-backend** | API. Fuente de verdad del dominio. Nada existe sin esto. | Python 3.12, FastAPI, SQLAlchemy + Alembic, Postgres (Cloud SQL), Firebase Admin, Docker | — |
| **paku-web** | Web informativa + web app (login, compra, pedidos, tracking). | Next.js 16 (App Router), React 19, Tailwind + shadcn/radix, Firebase, Leaflet. Gestor: **pnpm**. | `git@github.com:fzalvarez/paku-web.git` |
| **paku-admin** | Panel de administración (asignación de allies, catálogo, órdenes). | Next.js (App Router), Tailwind + shadcn, Firebase, `middleware.ts`. Gestor: **pnpm**. | — |
| **paku-vet-dev** | App móvil (allies / veterinarios en campo). | React Native + Expo (EAS), Zustand store. Gestor: **pnpm**. | — |

> ⚠️ `paku-admin` y `paku-vet-dev` tienen `package-lock.json` obsoleto junto al `pnpm-lock.yaml`. Usar pnpm; limpiar el lock npm.

## Backend — arquitectura

Módulos en `app/modules/<módulo>/`, cada uno con capas: `api/` · `app/` (casos de uso) · `domain/` · `infra/`.

Módulos: `iam`, `catalog`, `commerce`, `cart`, `orders`, `booking`, `pets`, `pet_records`,
`clinical_history`, `paku_spa`, `geo`, `chat`, `streaming`, `tracking`, `notifications`, `push`, `wallet`, `store`.

`app/core/`: `auth.py`, `db.py`, `settings.py`, `rate_limiter.py`, `scheduler.py`, `errors.py`.

Routers públicos y `admin_router` separados por módulo (ver `app/main.py`).

## Flujo de negocio (resumen)

Compra de servicio: mascota → servicio + addons (fecha/hora) → dirección → disponibilidad (booking)
→ carrito (`POST /cart/items`, persiste 2 h) → validar → checkout → `POST /orders` (necesita `address_id`)
→ orden `created` → admin asigna ally y fecha → estados: `accepted → on_the_way → in_service → …`.
Detalle: `paku-backend/docs/flujo-compra-servicio.md`.

## Docs existentes a consolidar en specs/

- `paku-backend/docs/`: `chat-api.md`, `tracking-api.md`, `flujo-compra-servicio.md`
- `paku-backend/` raíz: `CART_*.md`, `FRONTEND_INTEGRATION_GUIDE.md`, `MIGRACION_CULQI.md` (en web)
- `paku-vet-dev/`: `ARCHITECTURE.md`, `COMMANDS.md`, `NEXT-STEPS.md`, `TROUBLESHOOTING.md`
- `paku-web/`: `ANALISIS_CRITICO.md`, `MIGRACION_CULQI.md`

## Convenciones

- Idioma de specs y docs: **español**.
- Fechas: absolutas (`2026-08-29`), no relativas.
- Pagos: migración a **Culqi** en curso (ver `paku-web/MIGRACION_CULQI.md`).
