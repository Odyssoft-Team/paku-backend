# Paku Backend — Agentes

## Antes de nada

Lee `specs/workspace.md` (contexto de los 4 repos) y `specs/constitution.md` (reglas invariantes).

## Spec-Driven Development

Este repo es el **canon del dominio y la API** de Paku. Antes de implementar una feature nueva o
un cambio de comportamiento: spec → plan → tasks aprobados en `specs/features/NNNN-slug/`.
Flujo completo en `specs/README.md`. Bugfixes triviales y refactors sin cambio de comportamiento no lo requieren.

Al tocar un área del dominio, actualiza primero su `specs/domain/<entidad>.md`.

## Arquitectura

- Un módulo por bounded context en `app/modules/<módulo>/`, capas `api / app / domain / infra`.
- Lógica en `domain` y `app`. `api` solo orquesta.
- Migraciones solo con Alembic.
- Cambios de comportamiento llevan tests `pytest`.

## Correr local

`uvicorn app.main:app --reload` (venv, `pip install -r requirements.txt`). Ver `README.md`.
