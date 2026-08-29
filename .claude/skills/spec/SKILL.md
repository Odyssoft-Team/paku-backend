---
name: spec
description: Arranca o avanza el flujo Spec-Driven Development de Paku (specify → plan → tasks). Úsalo cuando el usuario pida "/spec", crear un spec, planificar una feature, o generar tasks. También para consolidar un doc de dominio antes de tocar un área.
---

# Spec-Driven Development — Paku

Lee primero `specs/README.md`, `specs/constitution.md` y `specs/workspace.md` de `paku-backend`.

## Al invocar

1. Determina el repo objetivo (dónde está el grueso del trabajo; si es dominio/API → `paku-backend`).
2. Determina la fase pedida:
   - **specify** (default si es nuevo): crea `specs/features/NNNN-slug/` copiando `paku-backend/specs/features/_template/`.
     `NNNN` = siguiente correlativo en ese repo. Rellena `spec.md` con lo que sepas, marca huecos con `[ ]`.
     No escribas `plan.md` ni `tasks.md` todavía. Pide aprobación del spec.
   - **plan**: con el spec aprobado, rellena `plan.md`. Enumera impacto por repo y si rompe clientes. Pide aprobación.
   - **tasks**: con el plan aprobado, rellena `tasks.md`. Checklist ejecutable, cada ítem = un commit.
   - **implement**: sigue `tasks.md`, marca ítems, actualiza el doc de dominio afectado.
3. Actualiza el índice en `specs/features/README.md` (backend) o `specs/README.md` (frontends).

## Reglas

- Una fase a la vez. No adelantes la siguiente sin OK.
- `spec.md` sin tecnología ni nombres de archivo. Eso va en `plan.md`.
- Si tocas una entidad de dominio, primero crea/actualiza `paku-backend/specs/domain/<entidad>.md` desde `_template.md`.
- Español. Directo. Sin relleno.
