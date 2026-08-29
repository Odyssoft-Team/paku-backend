# Paku — Constitution

Reglas invariantes. Aplican a todos los repos. Cambiarlas requiere decisión explícita del owner.
Los specs de feature no pueden contradecir esto.

## Producto

- Paku conecta dueños de mascotas con **allies** (veterinarios / cuidadores) que prestan servicios a domicilio.
- Clientes finales usan **paku-web** y (allies) **paku-vet-dev**. Operación interna vía **paku-admin**.

## Arquitectura

1. **El backend es la única fuente de verdad del dominio y de la API.** Los frontends no replican lógica de negocio.
2. Backend: un módulo por bounded context, capas `api / app / domain / infra`. La lógica vive en `domain` y `app`, no en `api`.
3. Contrato de API: OpenAPI generado por FastAPI es la fuente de la **forma**. Ver `api/README.md`.
4. Frontends consumen la API vía una capa `api/` o `lib/` dedicada; nunca `fetch` suelto en componentes.

## Stack (no cambiar sin decisión)

- Backend: Python 3.12, FastAPI, SQLAlchemy, Alembic, Postgres.
- Web/Admin: Next.js App Router, React, TypeScript, Tailwind + shadcn/ui. Gestor **pnpm**.
- Móvil: React Native + Expo (EAS), Zustand.
- Auth e infra push: Firebase.

## Next.js

- Esta versión tiene breaking changes respecto al conocimiento previo. **Leer `node_modules/next/dist/docs/`**
  del guide relevante antes de escribir código. Respetar avisos de deprecación.

## Calidad

- Todo cambio de comportamiento en backend lleva tests (`pytest`).
- Migraciones de esquema siempre vía Alembic, nunca DDL manual.
- No romper contratos de API sin versionar o coordinar con los 3 clientes.

## Estilo

- Specs, docs y comentarios en **español**.
- Fechas absolutas.
- Directo, sin relleno.

## TODO (confirmar con owner)

- [ ] Lint/format backend: ¿ruff? ¿black? ¿configurado en CI?
- [ ] Convención de commits (¿Conventional Commits? los recientes son mixtos).
- [ ] Estrategia de branching y despliegue.
- [ ] Versionado de API (¿prefijo `/v1`?).
